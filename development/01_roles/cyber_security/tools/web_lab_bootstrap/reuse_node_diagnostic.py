"""Reuse the stopped recovery3 host; retain/restore its original user data."""
import argparse
import base64
from datetime import datetime,timezone
import gzip
import json
import os
from pathlib import Path
import re

from diagnose_teacher_node import GUEST

HELPER='i-022e4605fe093960e'
ROOT='vol-0bcf355d74caef268'


def userdata(clone):
    source="from pathlib import Path\nimport json\np=Path('/var/lib/jdu-node-diagnostic');p.mkdir(mode=0o700,exist_ok=True)\n(p/'config.json').write_text(json.dumps({'volume_id':"+repr(clone)+"}))\n"+GUEST
    payload=base64.b64encode(gzip.compress(source.encode(),mtime=0)).decode()
    return ("#cloud-boothook\n#!/bin/bash\nset -eu\nexec > /dev/ttyS0 2>&1\necho JDU_REUSED_DIAG_STARTED\n"
        "python3 - <<'PY'\nimport base64,gzip\nexec(compile(gzip.decompress(base64.b64decode('"+payload+"')),'jdu-reused-diagnostic','exec'))\nPY\n"
        "echo JDU_REUSED_DIAG_FINISHED\nshutdown -h +1\n").encode()


def save(path,state,exclusive=False):
    with path.open('x' if exclusive else 'w') as stream:json.dump(state,stream,indent=2);stream.write('\n')


def validate_resume(state,node,volume,previous,current):
    if state['phase'] not in ('pause_restored_detach_requested','restored'):raise ValueError('Only a restored paused diagnosis can resume')
    if node['State']['Name']!='stopped' or len(node['BlockDeviceMappings'])!=1:raise ValueError('Wait for stopped recovery root only')
    if volume['State']!='available' or volume['Attachments']:raise ValueError('Expected detached clean clone')
    if previous!=current:raise ValueError('Original recovery user data changed')


def main():
    import boto3
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','resume','stop','detach','refresh','start','attach','read','restore'))
    p.add_argument('--diagnostic-state',required=True);p.add_argument('--state',required=True)
    args=p.parse_args();os.umask(0o077);path=Path(args.state)
    original=json.loads(Path(args.diagnostic_state).read_text())
    account=boto3.client('sts').get_caller_identity()['Account']
    if account!=original['account']:raise ValueError('Wrong AWS account')
    ec2=boto3.client('ec2',region_name='us-east-1');cfn=boto3.client('cloudformation',region_name='us-east-1')
    node=ec2.describe_instances(InstanceIds=[HELPER])['Reservations'][0]['Instances'][0]
    root=next(x['Ebs']['VolumeId'] for x in node['BlockDeviceMappings'] if x['DeviceName']==node['RootDeviceName'])
    if root!=ROOT or node['Placement']['AvailabilityZone']!=original['availability_zone']:raise ValueError('Wrong retained recovery host')
    resources=cfn.list_stack_resources(StackName=original['stack_id'])['StackResourceSummaries']
    clone=next(x['PhysicalResourceId'] for x in resources if x['LogicalResourceId']=='CloneVolume')
    if path.exists():clone=json.loads(path.read_text())['clone_volume']
    if clone==original['source_volume'] or clone==ROOT:raise ValueError('Never use original disks as diagnosis target')
    volume=ec2.describe_volumes(VolumeIds=[clone])['Volumes'][0]
    if volume['SnapshotId']!=original['snapshot_id'] or not volume['Encrypted']:raise ValueError('Wrong cloned volume')
    if args.action=='prepare':
        if path.exists() or node['State']['Name']!='stopped' or len(node['BlockDeviceMappings'])!=1 or volume['State']!='available':raise ValueError('Expected stopped empty recovery host and unattached clone')
        previous=ec2.describe_instance_attribute(InstanceId=HELPER,Attribute='userData').get('UserData',{}).get('Value','')
        backup=path.with_name('recovery3-userdata.before-node-diagnosis.private.b64')
        with backup.open('x') as stream:stream.write(previous)
        state={'account':account,'helper_instance':HELPER,'helper_root_volume':ROOT,'clone_volume':clone,'phase':'preparing','previous_userdata_file':str(backup)}
        save(path,state,True)
        ec2.modify_instance_attribute(InstanceId=HELPER,UserData={'Value':userdata(clone)})
        state['phase']='prepared';save(path,state)
    else:
        state=json.loads(path.read_text())
        if state['account']!=account or state['helper_instance']!=HELPER or state['clone_volume']!=clone:raise ValueError('Recovery identity changed')
        if args.action=='resume':
            previous=base64.b64decode(Path(state['previous_userdata_file']).read_text())
            current=base64.b64decode(ec2.describe_instance_attribute(InstanceId=HELPER,Attribute='userData').get('UserData',{}).get('Value',''))
            validate_resume(state,node,volume,previous,current)
            ec2.modify_instance_attribute(InstanceId=HELPER,UserData={'Value':userdata(clone)})
            state['phase']='prepared';save(path,state)
        elif args.action=='stop':
            if node['State']['Name']=='running':ec2.stop_instances(InstanceIds=[HELPER])
            state['phase']='stopping';save(path,state)
        elif args.action=='detach':
            if node['State']['Name']!='stopped':raise ValueError('Wait for recovery host to stop')
            if len(volume['Attachments'])!=1 or volume['Attachments'][0]['InstanceId']!=HELPER:raise ValueError('Wrong clone attachment')
            ec2.detach_volume(InstanceId=HELPER,VolumeId=clone,Device='/dev/sdf')
            state['phase']='detaching';save(path,state)
        elif args.action=='refresh':
            if state['phase']!='detaching' or node['State']['Name']!='stopped' or len(node['BlockDeviceMappings'])!=1 or volume['State']!='available':raise ValueError('Wait for empty stopped host')
            fresh=ec2.create_volume(AvailabilityZone=original['availability_zone'],SnapshotId=original['snapshot_id'],VolumeType='gp3',Encrypted=True,
                TagSpecifications=[{'ResourceType':'volume','Tags':[{'Key':'Name','Value':'jdu-web-clean-node-diagnostic-20261015'}]}])
            state['booted_clone_volume']=clone;clone=fresh['VolumeId'];state['clone_volume']=clone;state['phase']='refreshing';save(path,state)
            ec2.modify_instance_attribute(InstanceId=HELPER,UserData={'Value':userdata(clone)})
            state['phase']='prepared';save(path,state)
        elif args.action=='start':
            if state['phase']!='prepared' or node['State']['Name']!='stopped':raise ValueError('Start already requested')
            if volume['State']!='available' or len(node['BlockDeviceMappings'])!=1:raise ValueError('Boot with the recovery root only')
            state['phase']='start_requested';save(path,state)
            ec2.start_instances(InstanceIds=[HELPER]);state.update(phase='booting',started_at=datetime.now(timezone.utc).isoformat());save(path,state)
        elif args.action=='attach':
            if state['phase']!='booting' or node['State']['Name']!='running':raise ValueError('Wait for root-only boot')
            if (datetime.now(timezone.utc)-datetime.fromisoformat(state['started_at'])).total_seconds()<45:raise ValueError('Wait 45 seconds for root-only boot')
            if volume['State']!='available' or len(node['BlockDeviceMappings'])!=1:raise ValueError('Unexpected attachment before safe boot')
            ec2.attach_volume(Device='/dev/sdf',InstanceId=HELPER,VolumeId=clone);state['phase']='started';save(path,state)
        elif args.action=='read':
            output=ec2.get_console_output(InstanceId=HELPER,Latest=True).get('Output','')
            if 'JDU_REUSED' not in output:
                try:output=base64.b64decode(output,validate=True).decode()
                except Exception:pass
            # Standalone EC2 serial timestamps may interrupt a long report line.
            output=re.sub(r'\[2026-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z?\]','',output)
            found=re.search(r'JDU_DISK_DIAG_BEGIN([A-Za-z0-9+/=\r\n]+)JDU_DISK_DIAG_END',output)
            if found:
                report=json.loads(base64.b64decode(found[1]));target=path.with_name('failed-repo-disk-diagnosis.public.json')
                save(target,report);state['report_file']=str(target);save(path,state)
                print('JDU_REUSED_DIAG_REPORT_READY')
                for name,lines in report['logs'].items():print('JDU_REUSED_DIAG_LOG='+json.dumps({'file':name,'tail':lines[-12:]},separators=(',',':')))
            else:
                selected=[x for x in output.splitlines() if re.search(r'JDU_REUSED|ValueError|jdu-reused-diagnostic',x) and len(x)<250]
                print('JDU_REUSED_DIAG_PENDING='+json.dumps(selected[-5:]))
        elif args.action=='restore':
            if node['State']['Name']!='stopped' or 'report_file' not in state:raise ValueError('Wait for report and automatic stop')
            if volume['State']!='in-use' or len(volume['Attachments'])!=1 or volume['Attachments'][0]['InstanceId']!=HELPER:raise ValueError('Unexpected clone attachment')
            previous=Path(state['previous_userdata_file']).read_text()
            ec2.modify_instance_attribute(InstanceId=HELPER,UserData={'Value':base64.b64decode(previous)})
            ec2.detach_volume(VolumeId=clone,InstanceId=HELPER,Device='/dev/sdf')
            state['phase']='restored';save(path,state)
    print('JDU_REUSED_DIAG_STATE='+json.dumps({'phase':state['phase'],'helper_instance':HELPER,'helper_state':node['State']['Name'],'clone_volume':clone,'original_root_untouched':True},separators=(',',':')))


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('JDU_REUSED_DIAG_ERROR='+type(e).__name__)
        if hasattr(e,'response'):print('JDU_REUSED_DIAG_API='+e.response['Error']['Code'])
        elif isinstance(e,ValueError):print('JDU_REUSED_DIAG_REASON='+str(e))
        raise SystemExit(2)
