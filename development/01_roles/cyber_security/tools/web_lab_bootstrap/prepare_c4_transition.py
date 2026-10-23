"""Review/retire the exact old Test2 five, preserving 96 GiB original roots.

Plan is read-only. Retire requires explicit approval and never targets teacher,
recovery or Linux resources. Verify is a separate read-only completion step.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from setup_internal_ssh import current_nodes,save_new


def validate_targets(instances,plan):
    if {i['InstanceId'] for i in instances}!={n['instance_id'] for n in plan['nodes'].values()}:
        raise ValueError('Retirement instance set differs')
    by_id={n['instance_id']:n for n in plan['nodes'].values()}
    for i in instances:
        tags={t['Key']:t['Value'] for t in i['Tags']}
        n=by_id[i['InstanceId']]
        if (i['State']['Name'] not in ('running','stopped','stopping','shutting-down','terminated')
                or tags.get('LabId')!=plan['lab_id'] or tags.get('DeploymentId')!=plan['deployment_id']
                or [x['Ebs']['VolumeId'] for x in i['BlockDeviceMappings']]!=n['root_volumes']):
            raise ValueError('Retirement root, tags or instance state changed')


def main():
    import boto3
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=('plan','retire','verify-retired'))
    for n in ('state','baseline','plan'):p.add_argument('--'+n,required=True)
    p.add_argument('--confirmed-retire-and-replace',action='store_true')
    a=p.parse_args();state=json.loads(Path(a.state).read_text());baseline=json.loads(Path(a.baseline).read_text())
    if (boto3.client('sts').get_caller_identity()['Account']!=state['account'] or state['lab_id']!='teacher-five-probe'
            or state['deployment_id']!='05342512-1a55-4e11-b2d3-cd450487a138'):
        raise ValueError('Only the accepted old Test2 pilot may be retired')
    e=boto3.client('ec2',region_name='us-east-1');cfn=boto3.client('cloudformation',region_name='us-east-1')
    if a.operation=='plan':
        nodes=current_nodes(e,cfn,state,baseline)
        resources=[v for page in cfn.get_paginator('list_stack_resources').paginate(StackName=state['stack_id']) for v in page['StackResourceSummaries']]
        refs={v['LogicalResourceId']:v['PhysicalResourceId'] for v in resources}
        endpoint_ids=[refs['SsmEndpoint'],refs['SsmMessagesEndpoint']]
        endpoints=e.describe_vpc_endpoints(VpcEndpointIds=endpoint_ids)['VpcEndpoints']
        if ({x['ServiceName'] for x in endpoints}!={'com.amazonaws.us-east-1.ssm','com.amazonaws.us-east-1.ssmmessages'}
                or any(x['VpcId']!=refs['Vpc'] or x['VpcEndpointType']!='Interface' for x in endpoints)):
            raise ValueError('Old SSM endpoints differ')
        roots=[n['root_volumes'][0] for n in nodes.values()]
        volumes=e.describe_volumes(VolumeIds=roots)['Volumes']
        if len(volumes)!=5 or sum(v['Size'] for v in volumes)!=96 or not all(v['Encrypted'] for v in volumes):
            raise ValueError('Expected five encrypted original roots totaling 96 GiB')
        value={k:state[k] for k in ('account','stack_id','lab_id','deployment_id')}
        value.update(nodes=nodes,old_ssm_endpoints=endpoint_ids,old_vpc=refs['Vpc'],
            helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            planned_at=datetime.now(timezone.utc).isoformat(),new_lab_id='teacher-c4-probe',
            original_roots_retained=True,original_root_total_gib=96,
            original_instance_ids_irrecoverable=True,new_instances_get_new_ids=True,
            other_old_network_resources_retained=True,teacher_and_recovery_untouched=True,
            new_resources=dict(ec2=5,root_gib=96,ssm_interface_endpoints=2,rdp_reviewed_cidrs=50,public_web_port=80))
        save_new(a.plan,value)
        print('C4_TRANSITION_REVIEW_READY='+json.dumps({k:v for k,v in value.items() if k not in ('account','stack_id','helper_sha256')},separators=(',',':')))
        return
    plan=json.loads(Path(a.plan).read_text())
    if any(plan[k]!=state[k] for k in ('account','stack_id','lab_id','deployment_id')) or plan['helper_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('Reviewed retirement plan or helper differs')
    ids=[n['instance_id'] for n in plan['nodes'].values()];roots=[n['root_volumes'][0] for n in plan['nodes'].values()]
    if a.operation=='verify-retired':
        instances=[i for r in e.describe_instances(InstanceIds=ids)['Reservations'] for i in r['Instances']]
        volumes=e.describe_volumes(VolumeIds=roots)['Volumes']
        if {i['InstanceId'] for i in instances}!=set(ids) or not all(i['State']['Name']=='terminated' for i in instances) or len(volumes)!=5 or not all(v['State']=='available' and not v['Attachments'] and v['Encrypted'] for v in volumes):
            raise ValueError('Retirement or preserved root release still pending')
        endpoints=e.describe_vpc_endpoints(Filters=[dict(Name='vpc-id',Values=[plan['old_vpc']])])['VpcEndpoints']
        if any(x['VpcEndpointId'] in plan['old_ssm_endpoints'] and x['State']!='deleted' for x in endpoints):raise ValueError('Old SSM endpoint deletion pending')
        save_new(str(a.plan)+'.retired.public.json',dict(old_five_terminated=True,encrypted_original_roots_retained=True,root_total_gib=96,
            old_ssm_endpoints_removed=True,teacher_and_recovery_untouched=True,class_ready=False))
        print('OLD_FIVE_RETIRED_WITH_96_GIB_ROOTS_RETAINED; new deployment may now be planned')
        return
    if not a.confirmed_retire_and_replace:raise ValueError('Explicit action-time approval required')
    if Path(str(a.plan)+'.retirement-requested.json').exists():raise ValueError('Retirement already requested; inspect and verify, never resubmit blindly')
    if current_nodes(e,cfn,state,baseline)!=plan['nodes']:raise ValueError('Reviewed five nodes changed')
    refs={x['LogicalResourceId']:x['PhysicalResourceId'] for page in cfn.get_paginator('list_stack_resources').paginate(StackName=state['stack_id']) for x in page['StackResourceSummaries']}
    if plan['old_ssm_endpoints']!=[refs['SsmEndpoint'],refs['SsmMessagesEndpoint']] or plan['old_vpc']!=refs['Vpc']:
        raise ValueError('Reviewed old endpoint set changed')
    instances=[i for r in e.describe_instances(InstanceIds=ids)['Reservations'] for i in r['Instances']];validate_targets(instances,plan)
    for i in instances:
        for device in i['BlockDeviceMappings']:
            if device['Ebs']['DeleteOnTermination']:
                e.modify_instance_attribute(InstanceId=i['InstanceId'],BlockDeviceMappings=[dict(DeviceName=device['DeviceName'],Ebs=dict(DeleteOnTermination=False))])
    instances=[i for r in e.describe_instances(InstanceIds=ids)['Reservations'] for i in r['Instances']];validate_targets(instances,plan)
    if any(x['Ebs']['DeleteOnTermination'] for i in instances for x in i['BlockDeviceMappings']):raise ValueError('Original root retention not yet confirmed')
    save_new(str(a.plan)+'.retirement-requested.json',dict(retirement_requested_at=datetime.now(timezone.utc).isoformat(),instances=ids,roots=roots))
    e.terminate_instances(InstanceIds=ids)
    result=e.delete_vpc_endpoints(VpcEndpointIds=plan['old_ssm_endpoints'])
    if result.get('Unsuccessful'):raise ValueError('Old SSM endpoint deletion not accepted; inspect same IDs')
    print('OLD_FIVE_TERMINATION_AND_OLD_SSM_ENDPOINT_REMOVAL_REQUESTED; verify preserved roots before create')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('C4_TRANSITION_STOPPED='+type(exc).__name__+'; preserve state and inspect existing resources');raise SystemExit(2)
