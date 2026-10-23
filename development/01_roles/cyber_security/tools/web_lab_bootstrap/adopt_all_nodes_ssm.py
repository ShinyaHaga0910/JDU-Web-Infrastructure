"""Teacher-pilot migration from approved temporary SSM to signed all-node SSM.

No new access recipients or credentials: the same five nodes already have SSM.
Review proves equivalent private endpoint access and keeps IDs/roots/parameters.
Never execute the older recovery plan's restoration after this migration.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

from all_nodes_ssm import template as permanent_template
from temporary_ssm_recovery import DEPLOYMENT, NODES, check_context, make_template as temporary_template, save, wait_stack

FP = '65EC6784750CCFA703BA7179519284E45155EC2A'


def verify_folder(folder):
    # Each release validates against its own pinned wrapper/schema, not the
    # other release's already-imported Python module.
    import importlib.util
    folder=Path(folder)
    spec=importlib.util.spec_from_file_location('jdu_migration_validation_'+hashlib.sha256(str(folder).encode()).hexdigest(),
        folder/'release_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.verify_release(folder/'deployment-manifest.json',str(folder/'deployment-manifest.json')+'.asc',
        folder/'package-signing-public.asc',FP,folder,include_bundle=False)


def validate_changes(value):
    if value['Status'] != 'CREATE_COMPLETE' or value['ExecutionStatus'] != 'AVAILABLE':
        raise ValueError('Migration change set not available')
    wanted = {'SsmSg', 'BastionSsmOut'} | {'Recovery' + n + 'SsmOut' for n in ('Web','Dns','Db','Repo')}
    seen = set()
    for item in value.get('Changes', []):
        c = item['ResourceChange']; n = c['LogicalResourceId']
        if n in seen or n not in wanted: raise ValueError('Unexpected or duplicate migration change')
        if n.startswith('Recovery'):
            if c['Action'] != 'Remove' or c['ResourceType'] != 'AWS::EC2::SecurityGroupEgress':
                raise ValueError('Only temporary egress rules may be removed')
        else:
            prop = 'SecurityGroupIngress' if n == 'SsmSg' else 'GroupId'
            kind = 'AWS::EC2::SecurityGroup' if n == 'SsmSg' else 'AWS::EC2::SecurityGroupEgress'
            if (c['Action'] != 'Modify' or c['ResourceType'] != kind
                    or c['Replacement'] not in (('False',) if n == 'SsmSg' else ('True','False'))
                    or not c.get('Details') or any(d.get('Target', {}).get('Name') != prop for d in c['Details'])):
                raise ValueError('Only endpoint ingress and the existing egress group may change')
        seen.add(n)
    if seen != wanted: raise ValueError('Exactly six equivalent network changes required')
    return sorted(seen)


def wait_change(cfn, state, cid):
    for _ in range(90):
        result = cfn.describe_change_set(StackName=state['stack_id'], ChangeSetName=cid, IncludePropertyValues=True)
        if result['Status'] not in ('CREATE_PENDING','CREATE_IN_PROGRESS'): return result
        time.sleep(2)
    raise ValueError('Change set still pending')


def context(ec2, cfn, state):
    stack = check_context(ec2, cfn, state)
    refs = {x['LogicalResourceId']: x.get('PhysicalResourceId')
        for page in cfn.get_paginator('list_stack_resources').paginate(StackName=state['stack_id'])
        for x in page['StackResourceSummaries']}
    selected = list(NODES.values()); ids = {i for i,v in selected}
    def members(groups):
        return {i['InstanceId'] for page in ec2.get_paginator('describe_instances').paginate(
            Filters=[dict(Name='instance.group-id',Values=groups), dict(Name='instance-state-name',Values=['pending','running','stopping','stopped'])])
            for r in page['Reservations'] for i in r['Instances']}
    if members([refs['BootstrapSg']]) != ids:
        raise ValueError('Shared SSM source group must contain exactly the five reviewed nodes')
    for label,(iid,root) in NODES.items():
        i=ec2.describe_instances(InstanceIds=[iid])['Reservations'][0]['Instances'][0]
        if ({g['GroupId'] for g in i['SecurityGroups']} != {refs[label+'Sg'],refs['BootstrapSg']}
                or members([refs[label+'Sg']]) != {iid}
                or not i.get('IamInstanceProfile',{}).get('Arn','').endswith('/LabInstanceProfile')):
            raise ValueError('Existing access recipient or instance groups differ')
    return stack


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=('prepare','review','apply','adopt'))
    for n in ('old-tools','new-tools','state','new-state','plan'):p.add_argument('--'+n,required=True)
    a=p.parse_args(); os.umask(0o077); sys.dont_write_bytecode=True
    new=Path(a.new_tools); sys.path.insert(0,str(new))
    old_verified=verify_folder(a.old_tools); new_verified=verify_folder(new)
    state=json.loads(Path(a.state).read_text()); path=Path(a.plan)
    if (state['manifest_sha256'] != old_verified['manifest_sha256']
            or hashlib.sha256(old_verified['files']['template'].read_bytes()).hexdigest() != state['template_sha256']):
        raise ValueError('Original state is not bound to the old signed release')
    original=json.loads(old_verified['files']['template'].read_text())
    target=json.loads(new_verified['files']['template'].read_text())
    if target != permanent_template(original):raise ValueError('New signature permits unrelated template changes')
    for field in ('release_id','region','ami','network','grading','bootstrap'):
        if old_verified['manifest'][field] != new_verified['manifest'][field]:raise ValueError('Signed destinations changed')
    if old_verified['manifest']['artifacts']['repo_bundle'] != new_verified['manifest']['artifacts']['repo_bundle']:
        raise ValueError('Student payload must stay unchanged')
    import boto3
    if boto3.client('sts').get_caller_identity()['Account'] != state['account']:raise ValueError('Wrong account')
    cfn=boto3.client('cloudformation',region_name='us-east-1');ec2=boto3.client('ec2',region_name='us-east-1')
    stack=context(ec2,cfn,state)
    live=cfn.get_template(StackName=state['stack_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(live,str):live=json.loads(live)
    if live not in (temporary_template(original),target):raise ValueError('Unexpected current template')
    if a.operation=='prepare':
        if path.exists() or Path(a.new_state).exists() or live==target:raise ValueError('Existing migration retained')
        if stack['StackStatus']!='UPDATE_COMPLETE':raise ValueError('Stable temporary deployment required')
        cid=cfn.create_change_set(StackName=state['stack_id'],ChangeSetName='persistent-ssm-'+uuid.uuid4().hex,
            ChangeSetType='UPDATE',TemplateBody=(json.dumps(target,separators=(',',':'))+'\n'),
            Parameters=[dict(ParameterKey=x['ParameterKey'],UsePreviousValue=True) for x in stack['Parameters']])['Id']
        save(path,dict(account=state['account'],stack_id=state['stack_id'],deployment_id=DEPLOYMENT,
            old_manifest_sha256=old_verified['manifest_sha256'],new_manifest_sha256=new_verified['manifest_sha256'],change_set_id=cid))
        print('PERSISTENT_SSM_MIGRATION_PREPARED; not executed');return
    plan=json.loads(path.read_text())
    if (any(plan[k]!=state[k] for k in ('account','stack_id','deployment_id'))
            or plan['old_manifest_sha256']!=old_verified['manifest_sha256']
            or plan['new_manifest_sha256']!=new_verified['manifest_sha256']):raise ValueError('Migration identity changed')
    if a.operation in ('review','apply'):
        changes=validate_changes(wait_change(cfn,state,plan['change_set_id']))
        print('PERSISTENT_SSM_REVIEW='+json.dumps(dict(changes=changes,access_recipients_unchanged=5,
            all_parameters_previous=True,ec2_replacements=0,new_instances=0,new_disks=0,new_credentials=0)),flush=True)
        if a.operation=='review':return
        save(str(path)+'.executed.json',dict(execution_requested=True))
        cfn.execute_change_set(StackName=state['stack_id'],ChangeSetName=plan['change_set_id'])
        wait_stack(cfn,state['stack_id'],target)
    live=cfn.get_template(StackName=state['stack_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(live,str):live=json.loads(live)
    if live!=target:raise ValueError('Signed target template is not live')
    context(ec2,cfn,state)
    updated=dict(state,manifest_sha256=new_verified['manifest_sha256'],template_sha256=hashlib.sha256(new_verified['files']['template'].read_bytes()).hexdigest(),
        phase='WAITING',configuration_migration=dict(old_manifest_sha256=old_verified['manifest_sha256'],kind='same-five-node-persistent-ssm'))
    save(a.new_state,updated)
    print('SIGNED_PERSISTENT_SSM_STATE_ADOPTED; run fresh signed status, not a readiness assertion',flush=True)


if __name__=='__main__':main()
