"""Prepare/execute a two-resource S3 closure for the accepted teacher probe only."""
import argparse
import json
import os
from datetime import datetime,timezone
from pathlib import Path

from inspect_teacher_probe import collect


def require_baseline(report):
    if (report['stack_status'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE') or report['phase']!='bootstrap'
            or report['all_five_role_checks_passed'] is not True or report['all_aws_checks_passed'] is not True
            or report['all_five_network_checks_passed'] is not True or len(report['nodes'])!=5):
        raise ValueError('Five live prepared nodes and exact bootstrap AWS state are required')
    for node in report['nodes'].values():
        result=node['network_result']
        if result['phase']!='BOOTSTRAP_OBSERVED' or result['s3_tcp_reachable'] is not True or result['s3_bootstrap_reachable_seen'] is not True:
            raise ValueError('Every node must first prove a live S3 bootstrap baseline')


def validate_change_set(change):
    if change['Status']!='CREATE_COMPLETE' or change['ExecutionStatus']!='AVAILABLE':
        raise ValueError('Closure change set is not available')
    expected={'BootstrapSg':'AWS::EC2::SecurityGroup','S3Endpoint':'AWS::EC2::VPCEndpoint'}
    observed={}
    for item in change.get('Changes',[]):
        resource=item.get('ResourceChange',{})
        name=resource.get('LogicalResourceId')
        if (name in observed or name not in expected or resource.get('Action')!='Modify'
                or resource.get('Replacement')!='False' or resource.get('ResourceType')!=expected[name]):
            raise ValueError('Closure must not replace, create, delete or modify other resources')
        observed[name]=resource['ResourceType']
    if observed!=expected:raise ValueError('Expected exactly BootstrapSg and S3Endpoint changes')
    return [{'logical_id':name,'action':'Modify','replacement':False} for name in sorted(observed)]


def save(path,value):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def main():
    import boto3
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('prepare','review','execute'))
    for field in ('state','template','change-state'):p.add_argument('--'+field,required=True)
    a=p.parse_args();os.umask(0o077)
    state=json.loads(Path(a.state).read_text())
    if state['account']!=boto3.client('sts').get_caller_identity()['Account']:raise ValueError('Wrong AWS account')
    cfn=boto3.client('cloudformation',region_name='us-east-1')
    actual=cfn.get_template(StackName=state['stack_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(actual,str):actual=json.loads(actual)
    if actual!=json.loads(Path(a.template).read_text()):raise ValueError('Live template differs from the reviewed template')
    if a.command=='prepare':
        if Path(a.change_state).exists():raise ValueError('Existing closure plan retained')
        report=collect(a.state,a.template);require_baseline(report)
        stack=cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
        values=[{'ParameterKey':v['ParameterKey'],'ParameterValue':'teaching'} if v['ParameterKey']=='DeploymentPhase' else {'ParameterKey':v['ParameterKey'],'UsePreviousValue':True} for v in stack['Parameters']]
        name='teaching-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        response=cfn.create_change_set(StackName=state['stack_id'],ChangeSetName=name,ChangeSetType='UPDATE',UsePreviousTemplate=True,Parameters=values)
        save(a.change_state,{'account':state['account'],'stack_id':state['stack_id'],'deployment_id':state['deployment_id'],'change_set_id':response['Id'],'name':name})
        print('CLOSURE_CHANGE_SET_PREPARING='+name,flush=True)
        return
    plan=json.loads(Path(a.change_state).read_text())
    if any(plan[k]!=state[k] for k in ('account','stack_id','deployment_id')):raise ValueError('Closure plan belongs to another deployment')
    change=cfn.describe_change_set(StackName=state['stack_id'],ChangeSetName=plan['change_set_id']);review=validate_change_set(change)
    print('CLOSURE_CHANGE_SET_REVIEW='+json.dumps(review),flush=True)
    if a.command=='execute':
        require_baseline(collect(a.state,a.template))
        cfn.execute_change_set(StackName=state['stack_id'],ChangeSetName=plan['change_set_id'])
        print('CLOSURE_EXECUTION_REQUESTED; live verification still required',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:print('CLOSURE_STOPPED='+type(exc).__name__,flush=True);raise SystemExit(2)
