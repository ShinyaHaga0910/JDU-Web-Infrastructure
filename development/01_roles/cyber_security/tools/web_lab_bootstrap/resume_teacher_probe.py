"""Resume only the four failed roles, preserving the accepted repo and credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import uuid

from inspect_teacher_probe import collect

ROLES={'BastionInstance','WebInstance','DnsInstance','DbInstance'}
RETAINED={
    'i-0040d8f349c83f2dd','i-06b2bb81ce309a610','i-07ffde0cd85b7376d',
    'i-0523cd927d585d519','i-022e4605fe093960e'}
RETIRED={
    'i-0300371ced4a4ed0f':'vol-0e9fe0388064da14f',
    'i-04371f658f49c1c84':'vol-0a6be064f21969faa',
    'i-0ba43fa2147f49f09':'vol-0f4c6d62f96b6d570',
    'i-08759e082254d248a':'vol-0d2f730362ecbc77c'}


def validate_changes(change):
    if (change['Status']!='CREATE_COMPLETE' or change['ExecutionStatus']!='AVAILABLE'
            or change.get('NextToken')):raise ValueError('Wait for available bounded retry change set')
    found=set();safe=[]
    for item in change.get('Changes',[]):
        r=item['ResourceChange'];name=r['LogicalResourceId']
        expected='AWS::EC2::Instance' if name in ROLES else 'AWS::CloudFormation::WaitCondition' if name=='AllNodesReadyC3' else None
        initial_add=r['Action']=='Add' and r.get('Replacement') in (None,'False')
        failed_retry=(name in ROLES-{'BastionInstance'} and r['Action']=='Modify'
            and r.get('Replacement')=='True' and r.get('Scope')==[] and r.get('Details')==[])
        if (expected is None or name in found or not (initial_add or failed_retry) or r['ResourceType']!=expected):
            raise ValueError('Retry must only add the four failed roles and their wait condition')
        found.add(name);safe.append({'logical_id':name,'action':r['Action'],'type':expected,'replacement':r.get('Replacement')})
    if not ROLES<=found:raise ValueError('Retry must include exactly four missing EC2 roles')
    return safe


def validate_report(report):
    repo=report['nodes'].get('repo',{})
    role=repo.get('role_result') or {};network=repo.get('network_result') or {}
    if (report['stack_status']!='UPDATE_FAILED' or report['phase']!='bootstrap'
            or repo.get('instance_id')!='i-06b2bb81ce309a610' or repo.get('state')!='running'
            or repo.get('root_volumes')!=['vol-0431aba5aa1bc7677']
            or role.get('stage')!='ROLE_PREPARED' or not role.get('checks') or not all(role['checks'].values())
            or network.get('phase')!='BOOTSTRAP_OBSERVED' or network.get('s3_tcp_reachable') is not True
            or not network.get('checks') or not all(network['checks'].values())):
        raise ValueError('Accepted live repo and bootstrap baseline must be preserved')
    required={'repo_identity_and_access','repo_encrypted_root_size','s3_endpoint_policy',
        's3_endpoint_routes','public_exact_routes','private_exact_routes','no_nat_gateway'}
    required.update(x+'_exact_rules' for x in ('BastionSg','WebSg','DnsSg','DbSg','RepoSg','BootstrapSg'))
    if not all(report['aws_checks'].get(x) is True for x in required):raise ValueError('Existing network or repo differs')


def save(path,data,new=False):
    encoded=json.dumps(data,indent=2)+'\n'
    if new:
        with path.open('x') as f:f.write(encoded)
    else:
        temporary=path.with_suffix('.tmp');temporary.write_text(encoded);os.replace(temporary,path)


def live_guard(ec2,cfn,probe,template,state_path,template_path):
    raw=Path(template_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=probe['template_sha256']:raise ValueError('Reviewed repair template differs')
    actual=cfn.get_template(StackName=probe['stack_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(actual,str):actual=json.loads(actual)
    if actual!=template:raise ValueError('Live template differs')
    nodes=[i for r in ec2.describe_instances(Filters=[{'Name':'instance-state-name',
        'Values':['pending','running','stopping','stopped']}])['Reservations'] for i in r['Instances']]
    if {i['InstanceId'] for i in nodes}!=RETAINED:raise ValueError('Expected five retained nodes before adding four')
    if {i['InstanceId'] for i in nodes if i['State']['Name']!='stopped'}!={'i-0040d8f349c83f2dd','i-06b2bb81ce309a610'}:
        raise ValueError('Recovery nodes must remain stopped')
    retired=[i for r in ec2.describe_instances(InstanceIds=list(RETIRED))['Reservations'] for i in r['Instances']]
    if len(retired)!=4 or any(i['State']['Name']!='terminated' for i in retired):raise ValueError('Approved retirement incomplete')
    volumes=ec2.describe_volumes(VolumeIds=list(RETIRED.values())+['vol-0e031253b244e195d'])['Volumes']
    if len(volumes)!=5 or any(v['State']!='available' or v['Attachments'] or not v['Encrypted'] for v in volumes):
        raise ValueError('All retired roots and original repo root must be retained')
    report=collect(state_path,template_path);validate_report(report)
    resources=cfn.list_stack_resources(StackName=probe['stack_id'])['StackResourceSummaries']
    resources={r['LogicalResourceId']:r for r in resources}
    if resources['RepoInstance']['ResourceStatus']!='UPDATE_COMPLETE' or resources['RepoReadyC3']['ResourceStatus']!='CREATE_COMPLETE':
        raise ValueError('Accepted repo resources changed')
    for name in ROLES:
        resource=resources.get(name)
        if resource is None:continue  # Dependencies can prevent any initial create attempt.
        if resource['ResourceStatus']!='CREATE_FAILED':raise ValueError('Role is not a failed initial creation')
        iid=resource.get('PhysicalResourceId')
        if iid:
            node=ec2.describe_instances(InstanceIds=[iid])['Reservations'][0]['Instances'][0]
            if node['State']['Name']!='terminated':raise ValueError('Failed role still has a live instance')


def main():
    import boto3
    from botocore.exceptions import ClientError
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','review','execute'))
    for key in ('probe-state','template','state'):p.add_argument('--'+key,required=True)
    a=p.parse_args();os.umask(0o077)
    probe=json.loads(Path(a.probe_state).read_text());template=json.loads(Path(a.template).read_text());path=Path(a.state)
    if (probe['account']!=boto3.client('sts').get_caller_identity()['Account']
            or probe['stack_name']!='jdu-web-five-node-probe-20261015'):raise ValueError('Wrong teacher probe identity')
    ec2=boto3.client('ec2',region_name='us-east-1');cfn=boto3.client('cloudformation',region_name='us-east-1')
    if a.action=='prepare':
        if path.exists():raise ValueError('Existing retry retained')
        live_guard(ec2,cfn,probe,template,a.probe_state,a.template)
        stack=cfn.describe_stacks(StackName=probe['stack_id'])['Stacks'][0]
        parameters=[{'ParameterKey':v['ParameterKey'],'UsePreviousValue':True} for v in stack['Parameters']]
        state={k:probe[k] for k in ('account','stack_id','deployment_id','template_sha256')}
        state['phase']='preparing';save(path,state,True)
        response=cfn.create_change_set(StackName=probe['stack_id'],ChangeSetName='resume-c3-'+uuid.uuid4().hex[:8],
            ChangeSetType='UPDATE',UsePreviousTemplate=True,Parameters=parameters)
        state.update(phase='prepared',change_set_id=response['Id']);save(path,state)
    else:
        state=json.loads(path.read_text())
        if any(state[k]!=probe[k] for k in ('account','stack_id','deployment_id','template_sha256')):
            raise ValueError('Retry identity changed')
        # Resolved property values omit the repo/endpoint no-op records returned
        # by the unresolved view after a preserved partial update.
        change=cfn.describe_change_set(StackName=probe['stack_id'],ChangeSetName=state['change_set_id'],IncludePropertyValues=True)
        safe=validate_changes(change);print('JDU_RESUME_CHANGES='+json.dumps(safe,separators=(',',':')))
        if a.action=='execute':
            if state['phase']!='prepared':raise ValueError('Retry already requested')
            live_guard(ec2,cfn,probe,template,a.probe_state,a.template)
            state['phase']='execute_requested';save(path,state)
            cfn.execute_change_set(StackName=probe['stack_id'],ChangeSetName=state['change_set_id'],DisableRollback=True)
            state['phase']='executed';save(path,state)
    print('JDU_RESUME_STATE='+json.dumps({'phase':state['phase'],'successful_repo_preserved':True,
        'template_and_all_parameters_unchanged':True,'student_release_ready':False}))


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('JDU_RESUME_ERROR='+type(e).__name__)
        if hasattr(e,'response'):print('JDU_RESUME_API='+e.response['Error']['Code'])
        elif isinstance(e,ValueError):print('JDU_RESUME_REASON='+str(e))
        raise SystemExit(2)
