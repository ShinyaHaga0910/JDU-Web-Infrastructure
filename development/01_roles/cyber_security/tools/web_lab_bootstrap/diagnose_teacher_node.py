"""Teacher-only snapshot diagnosis; never mount or detach the original root disk."""
import argparse
import base64
import gzip
import json
import os
from pathlib import Path

STACK='jdu-web-node-diagnostic-20261015'
GUEST=r'''import base64,json,re,subprocess,time
from pathlib import Path
cfg=json.loads(Path('/var/lib/jdu-node-diagnostic/config.json').read_text())
mount=Path('/mnt/jdu-node-diagnostic');mount.mkdir(exist_ok=True)
device=None
for _ in range(120):
 info=json.loads(subprocess.check_output(['lsblk','-J','--tree','-o','PATH,SERIAL,TYPE,MOUNTPOINTS'],text=True))
 disk=next((d for d in info['blockdevices'] if (d.get('serial') or '').replace('-','')==cfg['volume_id'].replace('-','')),None)
 if disk:
  selected=next((p for p in disk.get('children',[]) if p['path']==disk['path']+'p1'),None)
  if selected and any(selected.get('mountpoints') or []):raise ValueError('Diagnostic clone is already mounted; never inspect a booted clone')
  part=selected['path'] if selected else None
  if part:
   kind=subprocess.check_output(['blkid','-p','-s','TYPE','-o','value',part],text=True).strip()
   if kind!='ext4':raise ValueError('Expected ext4 root partition')
   device=part;break
 time.sleep(2)
if not device:raise ValueError('Explicit cloned volume not found')
subprocess.run(['mount','-o','ro,noload',device,str(mount)],check=True)
try:
 if 'VERSION_ID="24.04"' not in (mount/'etc/os-release').read_text():raise ValueError('Unexpected OS')
 logs={}
 for name in ('jdu-web-bootstrap.log','cloud-init-output.log'):
  path=mount/'var/log'/name
  if not path.is_file():continue
  lines=[]
  for line in path.read_text(errors='replace').splitlines()[-100:]:
   line=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',line)
   line=re.sub(r'https?://\S+','[URL]',line)
   line=re.sub(r'arn:[^\s]+','[ARN]',line)
   line=re.sub(r'\$6\$[^\s"\x27]+','[REDACTED_HASH]',line)
   if len(line)>500 or re.search(r'password|credential|token|signature|[A-Za-z0-9+/=]{120}',line,re.I):continue
   lines.append(line)
  logs[name]=lines[-55:]
 report={'scope':'teacher_read_only_cloned_root_diagnosis','original_disk_detached':False,'mount_options':'ro,noload','logs':logs}
 print('JDU_DISK_DIAG_BEGIN'+base64.b64encode(json.dumps(report,separators=(',',':')).encode()).decode()+'JDU_DISK_DIAG_END',flush=True)
finally:subprocess.run(['umount',str(mount)],check=True)
'''


def save(path,value,exclusive=False):
    with path.open('x' if exclusive else 'w') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def main():
    import boto3
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','snapshot','launch','status'))
    parser.add_argument('--probe-state',required=True);parser.add_argument('--state',required=True)
    args=parser.parse_args();os.umask(0o077)
    probe=json.loads(Path(args.probe_state).read_text());path=Path(args.state)
    account=boto3.client('sts').get_caller_identity()['Account']
    if account!=probe['account'] or probe['stack_name']!='jdu-web-five-node-probe-20261015':raise ValueError('Wrong source identity')
    ec2=boto3.client('ec2',region_name='us-east-1');cfn=boto3.client('cloudformation',region_name='us-east-1')
    resources=cfn.list_stack_resources(StackName=probe['stack_id'])['StackResourceSummaries']
    refs={r['LogicalResourceId']:r.get('PhysicalResourceId') for r in resources}
    instance=ec2.describe_instances(InstanceIds=[refs['RepoInstance']])['Reservations'][0]['Instances'][0]
    root=next(v for v in instance['BlockDeviceMappings'] if v['DeviceName']==instance['RootDeviceName'])['Ebs']['VolumeId']
    if instance['InstanceId']!='i-06b2bb81ce309a610' or instance['PrivateIpAddress']!='10.20.2.30':raise ValueError('Wrong failed repo')
    if args.action=='prepare':
        if path.exists():raise ValueError('Existing diagnosis state retained')
        state={'account':account,'probe_stack_id':probe['stack_id'],'source_instance':instance['InstanceId'],'source_volume':root,
            'availability_zone':instance['Placement']['AvailabilityZone'],'subnet_id':instance['SubnetId'],'group_id':refs['BootstrapSg'],
            'phase':'stopping_original','stack_name':STACK}
        save(path,state,True)
        if instance['State']['Name']!='stopped':ec2.stop_instances(InstanceIds=[instance['InstanceId']])
    else:
        state=json.loads(path.read_text())
        if state['account']!=account or state['source_volume']!=root or state['probe_stack_id']!=probe['stack_id']:raise ValueError('Diagnostic identity differs')
        if args.action=='snapshot':
            if state['phase']!='stopping_original' or instance['State']['Name']!='stopped':raise ValueError('Wait for original repo to stop')
            snap=ec2.create_snapshot(VolumeId=root,Description='Read-only diagnosis of failed JDU Web repo',
                TagSpecifications=[{'ResourceType':'snapshot','Tags':[{'Key':'Name','Value':STACK}]}])
            state.update(snapshot_id=snap['SnapshotId'],phase='snapshot_pending');save(path,state)
        elif args.action=='launch':
            if state['phase']!='snapshot_pending':raise ValueError('Diagnostic launch already requested')
            snap=ec2.describe_snapshots(SnapshotIds=[state['snapshot_id']])['Snapshots'][0]
            if snap['VolumeId']!=root or snap['State']!='completed':raise ValueError('Wait for exact snapshot completion')
            try:cfn.describe_stacks(StackName=STACK)
            except cfn.exceptions.ClientError as e:
                if e.response['Error']['Code']!='ValidationError' or e.response['Error']['Message']!=f'Stack with id {STACK} does not exist':raise
            else:raise ValueError('Existing diagnostic stack retained')
            user={'package_update':False,'package_upgrade':False,'write_files':[
                {'path':'/var/lib/jdu-node-diagnostic/run.py','permissions':'0600','encoding':'gz+b64','content':base64.b64encode(gzip.compress(GUEST.encode(),mtime=0)).decode()},
                {'path':'/var/lib/jdu-node-diagnostic/config.json','permissions':'0600','content':'{"volume_id":"${CloneVolume}"}'}],
                'runcmd':[['bash','-c','set -o pipefail; python3 /var/lib/jdu-node-diagnostic/run.py 2>&1 > /dev/ttyS0']],
                'power_state':{'mode':'poweroff','delay':'now','timeout':60,'condition':True}}
            template={'AWSTemplateFormatVersion':'2010-09-09','Resources':{
                'CloneVolume':{'Type':'AWS::EC2::Volume','Properties':{'AvailabilityZone':state['availability_zone'],'SnapshotId':state['snapshot_id'],'VolumeType':'gp3','Encrypted':True}},
                'DiagnosticInstance':{'Type':'AWS::EC2::Instance','Properties':{'ImageId':'ami-0fa5967347d08d2df','InstanceType':'t3a.micro',
                    'CreditSpecification':{'CPUCredits':'standard'},'MetadataOptions':{'HttpTokens':'required'},
                    'BlockDeviceMappings':[{'DeviceName':'/dev/sda1','Ebs':{'VolumeSize':8,'VolumeType':'gp3','Encrypted':True,'DeleteOnTermination':True}}],
                    'NetworkInterfaces':[{'DeviceIndex':'0','SubnetId':state['subnet_id'],'AssociatePublicIpAddress':False,'GroupSet':[state['group_id']]}],
                    'UserData':{'Fn::Base64':{'Fn::Sub':'#cloud-config\n'+json.dumps(user)+'\n'}},'Tags':[{'Key':'Name','Value':STACK}]}},
                'CloneAttachment':{'Type':'AWS::EC2::VolumeAttachment','Properties':{'Device':'/dev/sdf','InstanceId':{'Ref':'DiagnosticInstance'},'VolumeId':{'Ref':'CloneVolume'}}}}}
            cfn.validate_template(TemplateBody=json.dumps(template))
            state['phase']='create_requested';save(path,state)
            result=cfn.create_stack(StackName=STACK,TemplateBody=json.dumps(template),DisableRollback=True)
            state.update(stack_id=result['StackId'],phase='created');save(path,state)
        elif args.action=='status':
            if 'snapshot_id' in state:state['snapshot_status']=ec2.describe_snapshots(SnapshotIds=[state['snapshot_id']])['Snapshots'][0]['State']
            if 'stack_id' in state:
                stack=cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
                state['stack_status']=stack['StackStatus']
                for r in cfn.list_stack_resources(StackName=state['stack_id'])['StackResourceSummaries']:
                    if r['LogicalResourceId']=='DiagnosticInstance' and r.get('PhysicalResourceId'):state['diagnostic_instance']=r['PhysicalResourceId']
            save(path,state)
    public={k:v for k,v in state.items() if k not in ('account','stack_id','probe_stack_id')}
    public['original_state']=instance['State']['Name'];print('JDU_DIAGNOSTIC_STATE='+json.dumps(public,separators=(',',':')))


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('JDU_DIAGNOSTIC_ERROR='+type(e).__name__)
        if hasattr(e,'response'):print('JDU_DIAGNOSTIC_API='+e.response['Error']['Code'])
        elif isinstance(e,ValueError):print('JDU_DIAGNOSTIC_REASON='+str(e))
        raise SystemExit(2)
