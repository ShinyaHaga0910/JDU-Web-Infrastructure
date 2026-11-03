"""Retire only the five explicitly approved old verification instances.

Default is read-only. --apply first protects every original root, verifies all
five protections, then sends one termination request. Original private state,
credentials, grades and networking are untouched. An intent prevents blind
re-execution after an unknown outcome; inspect the instances/receipt instead.
"""
import argparse
import json
import os
from pathlib import Path
import time

ACCOUNT='965244652544'
LAB='class193548-test1'
DEPLOYMENT='3ab82943-031d-4806-b4c0-c0b0e4554006'
ROOTS={
 'i-0488d26e69614e096':'vol-0dd3097fd722b6bb5',
 'i-0c43b73c9a75c41eb':'vol-08dce34a5376e7d58',
 'i-0f4cfc066e59488a6':'vol-031fe29759bd1d27d',
 'i-0ccc3e9206d30867b':'vol-05586863b8491a998',
 'i-08f8a40fdaa5bb240':'vol-07c3cc6ffdd36afb9',
}


def inventory(sts,ec2):
    if sts.get_caller_identity()['Account']!=ACCOUNT:
        raise ValueError('Wrong student account')
    nodes=[i for r in ec2.describe_instances(InstanceIds=list(ROOTS))['Reservations'] for i in r['Instances']]
    if len(nodes)!=5 or {i['InstanceId'] for i in nodes}!=set(ROOTS):
        raise ValueError('Wrong five instances')
    rows=[]
    for i in nodes:
        tags={v['Key']:v['Value'] for v in i['Tags']}
        roots=[r for r in i['BlockDeviceMappings'] if r['DeviceName']==i['RootDeviceName']]
        if (tags.get('LabId')!=LAB or tags.get('DeploymentId')!=DEPLOYMENT or len(roots)!=1
                or roots[0]['Ebs']['VolumeId']!=ROOTS[i['InstanceId']]
                or i['State']['Name'] not in ('running','stopped')):
            raise ValueError('Instance identity, deployment or original root differs')
        rows.append({'instance_id':i['InstanceId'],'root_device':i['RootDeviceName'],
                     'volume_id':ROOTS[i['InstanceId']],
                     'delete_on_termination':roots[0]['Ebs']['DeleteOnTermination']})
    vols=ec2.describe_volumes(VolumeIds=list(ROOTS.values()))['Volumes']
    if (len(vols)!=5 or {v['VolumeId'] for v in vols}!=set(ROOTS.values())
            or sum(v['Size'] for v in vols)!=96 or not all(v['Encrypted'] for v in vols)):
        raise ValueError('Original encrypted 96GiB roots differ')
    return sorted(rows,key=lambda r:r['instance_id'])


def save(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(value,f,indent=2)


def apply(sts,ec2,directory):
    rows=inventory(sts,ec2)
    intent=directory/'retirement-intent.private.json'
    save(intent,{'account':ACCOUNT,'lab_id':LAB,'deployment_id':DEPLOYMENT,'original_roots':rows})
    for r in rows:
        ec2.modify_instance_attribute(InstanceId=r['instance_id'],BlockDeviceMappings=[{
            'DeviceName':r['root_device'],'Ebs':{'DeleteOnTermination':False}}])
    for _ in range(12):
        protected=inventory(sts,ec2)
        if all(r['delete_on_termination'] is False for r in protected):
            break
        time.sleep(2)
    if any(r['delete_on_termination'] is not False for r in protected):
        raise ValueError('Not all roots protected; no instance terminated')
    finish_protected(sts,ec2,directory)


def finish_protected(sts,ec2,directory):
    """Explicit recovery after inspecting a protection propagation delay."""
    intent=json.loads((directory/'retirement-intent.private.json').read_text(encoding='utf-8'))
    protected=inventory(sts,ec2)
    if (intent.get('account')!=ACCOUNT or intent.get('lab_id')!=LAB or intent.get('deployment_id')!=DEPLOYMENT
            or {r['instance_id']:r['volume_id'] for r in intent['original_roots']}!=ROOTS
            or any(r['delete_on_termination'] is not False for r in protected)):
        raise ValueError('Original intent and all protected roots must match; no instance terminated')
    save(directory/'roots-protected.private.json',{'original_roots':protected,'all_five_protected':True})
    ec2.terminate_instances(InstanceIds=list(ROOTS))
    print('APPROVED_OLD_FIVE_TERMINATION_REQUESTED',flush=True)
    ec2.get_waiter('instance_terminated').wait(InstanceIds=list(ROOTS),WaiterConfig={'Delay':5,'MaxAttempts':96})
    ec2.get_waiter('volume_available').wait(VolumeIds=list(ROOTS.values()),WaiterConfig={'Delay':5,'MaxAttempts':24})
    vols=ec2.describe_volumes(VolumeIds=list(ROOTS.values()))['Volumes']
    receipt={'account':ACCOUNT,'lab_id':LAB,'deployment_id':DEPLOYMENT,'terminated_instance_ids':sorted(ROOTS),
        'retained_volumes':[{'id':v['VolumeId'],'state':v['State'],'size_gib':v['Size'],'encrypted':v['Encrypted']} for v in vols],
        'retained_gib':sum(v['Size'] for v in vols),'private_state_or_credentials_changed':False,'new_resources':0}
    if receipt['retained_gib']!=96 or len(vols)!=5 or not all(v['State']=='available' and v['Encrypted'] for v in vols):
        raise ValueError('Inspect retained roots; post-retirement receipt not confirmed')
    save(directory/'retirement.accepted.public.json',receipt)
    print('APPROVED_OLD_FIVE_RETIRED_ROOTS_RETAINED='+json.dumps(receipt,separators=(',',':')),flush=True)


if __name__=='__main__':
    import boto3
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--finish-protected',action='store_true')
    p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    a.directory.mkdir(mode=0o700,exist_ok=True,parents=True)
    sts,ec2=[boto3.client(n,region_name='us-east-1') for n in ('sts','ec2')]
    if a.apply:apply(sts,ec2,a.directory)
    elif a.finish_protected:finish_protected(sts,ec2,a.directory)
    else:print(json.dumps({'scope':'read_only_retirement_review','original_roots':inventory(sts,ec2),'executed':False}))
