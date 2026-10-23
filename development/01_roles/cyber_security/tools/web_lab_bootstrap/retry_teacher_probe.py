"""Repair the existing failed teacher probe without re-entering RDP credentials.

Create/review a bounded change set first. Reimage only the existing failed repo,
retaining its original disk and the diagnostic snapshot. Never delete nodes or disks.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

NODES={'Repo','Bastion','Web','Dns','Db'}
WAIT={'RepoHandle','RepoReady','AllNodesHandle','AllNodesReady'}
AMI='ami-0fa5967347d08d2df'


def revision_template(old,new,revision):
    if not re.fullmatch(r'C[3-9][0-9]*',revision):raise ValueError('Expected immutable candidate revision C3 or later')
    if set(old)!=set(new) or set(old['Resources'])!=set(new['Resources']):raise ValueError('Template shape differs')
    for key in old:
        if key!='Resources' and old[key]!=new[key]:raise ValueError('Template contract changed')
    for key in old['Resources']:
        a=json.loads(json.dumps(old['Resources'][key]));b=json.loads(json.dumps(new['Resources'][key]))
        if key in {n+'Instance' for n in NODES}:
            a['Properties'].pop('UserData');b['Properties'].pop('UserData')
        if a!=b:raise ValueError('Repair may only change node UserData')
    def rename(value):
        if isinstance(value,list):return [rename(x) for x in value]
        if isinstance(value,dict):return {(k+revision if k in WAIT else k):rename(v) for k,v in value.items()}
        if isinstance(value,str):
            if value in WAIT:return value+revision
            for name in WAIT:value=value.replace('${'+name+'}','${'+name+revision+'}')
        return value
    return rename(new)


def validate_repo_for_update(node,state):
    roots=[m['Ebs']['VolumeId'] for m in node.get('BlockDeviceMappings',[])
           if m['DeviceName']==node.get('RootDeviceName') and 'Ebs' in m]
    if (node.get('InstanceId')!=state['source_instance'] or node.get('RootDeviceType')!='ebs'
            or node.get('ImageId')!=AMI or node.get('PrivateIpAddress')!='10.20.2.30'
            or roots!=[state['source_volume']] or node['State']['Name'] not in ('stopped','running')):
        raise ValueError('Existing EBS repo identity changed')


def check_changes(changes,revision,repo_ebs_verified=False):
    """No network widening, EC2 replacement, or removal of an existing node."""
    result=[]
    for item in changes:
        r=item['ResourceChange'];name=r['LogicalResourceId'];action=r['Action'];kind=r['ResourceType']
        if name in WAIT:
            allowed=action=='Remove' and kind.startswith('AWS::CloudFormation::WaitCondition')
        elif name in {x+revision for x in WAIT}:
            allowed=action=='Add' and kind.startswith('AWS::CloudFormation::WaitCondition')
        elif name=='RepoInstance':
            allowed=action=='Modify' and kind=='AWS::EC2::Instance' and r.get('Replacement')=='False'
            if r.get('Replacement')=='Conditional':
                # CFN labels UserData conditionally replacing because instance-store
                # roots replace; the exact existing EBS root must be verified live.
                details=r.get('Details',[])
                allowed=(repo_ebs_verified and action=='Modify' and kind=='AWS::EC2::Instance'
                    and r.get('Scope')==['Properties'] and bool(details)
                    and all(d.get('Target',{}).get('Attribute')=='Properties'
                        and d['Target'].get('Name')=='UserData'
                        and d['Target'].get('RequiresRecreation') in ('Never','Conditionally') for d in details))
        elif name in {x+'Instance' for x in NODES-{'Repo'}}:
            allowed=action=='Add' and kind=='AWS::EC2::Instance'
        elif name=='S3Endpoint':
            allowed=action=='Modify' and kind=='AWS::EC2::VPCEndpoint' and r.get('Replacement')=='False'
        else:allowed=False
        if not allowed:raise ValueError('Unreviewed repair resource change')
        result.append({'logical_id':name,'action':action,'type':kind,'replacement':r.get('Replacement')})
    if not any(v['logical_id']=='RepoInstance' for v in result):raise ValueError('Missing existing repo UserData update')
    return result


def write(path,data,exclusive=False):
    with path.open('x' if exclusive else 'w') as stream:json.dump(data,stream,indent=2);stream.write('\n')


def main():
    import boto3
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','review','execute','reimage','status'))
    for name in ('probe-state','diagnostic-state','previous-template','template','candidate','state'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--revision',default='C3')
    args=parser.parse_args();os.umask(0o077)
    old_path=Path(args.previous_template);new_path=Path(args.template);state_path=Path(args.state)
    probe_path=Path(args.probe_state);probe=json.loads(probe_path.read_text());diagnostic=json.loads(Path(args.diagnostic_state).read_text())
    old_bytes=old_path.read_bytes();old=json.loads(old_bytes);new=json.loads(new_path.read_bytes())
    candidate=json.loads(Path(args.candidate).read_text())
    template=revision_template(old,new,args.revision);template_bytes=(json.dumps(template,separators=(',',':'))+'\n').encode()
    digest=hashlib.sha256(template_bytes).hexdigest()
    account=boto3.client('sts').get_caller_identity()['Account']
    if account!=probe['account'] or account!=diagnostic['account'] or probe['stack_name']!='jdu-web-five-node-probe-20261015':raise ValueError('Wrong AWS identity')
    if diagnostic['probe_stack_id']!=probe['stack_id'] or diagnostic['source_instance']!='i-06b2bb81ce309a610':raise ValueError('Wrong diagnosed instance')
    ec2=boto3.client('ec2',region_name='us-east-1');cfn=boto3.client('cloudformation',region_name='us-east-1')
    stack=cfn.describe_stacks(StackName=probe['stack_id'])['Stacks'][0]
    if stack['StackId']!=probe['stack_id']:raise ValueError('Wrong failed stack')
    params={p['ParameterKey']:p['ParameterValue'] for p in stack['Parameters']}
    if params['DeploymentId']!=probe['deployment_id'] or params['LabId']!=probe['lab_id']:raise ValueError('Wrong deployment')
    if args.action=='prepare':
        if state_path.exists() or stack['StackStatus']!='CREATE_FAILED':raise ValueError('Existing repair or nonfailed source retained')
        if hashlib.sha256(old_bytes).hexdigest()!=probe['template_sha256']:raise ValueError('Previous template hash differs')
        live=cfn.get_template(StackName=probe['stack_id'],TemplateStage='Original')['TemplateBody']
        if isinstance(live,str):live=json.loads(live)
        if live!=old:raise ValueError('Live source template differs')
        # The public candidate report has no password or scoped URL.
        bundle_key='teacher-candidates/web-2026-10-r1/'+args.revision.lower()+'/repo-bundle.tar.gz'
        bucket='jdu-web-capture-20261015-bf04d16eb603'
        if (candidate.get('bucket')!=bucket or candidate.get('key')!=bundle_key
                or candidate.get('scope')!='signed_candidate_reassembled_not_os_acceptance'
                or candidate.get('release_id')!='web-2026-10-r1'
                or candidate.get('fingerprint')!='65EC6784750CCFA703BA7179519284E45155EC2A'
                or candidate.get('student_release_ready') is not False):raise ValueError('Wrong immutable candidate object')
        bundle_sha=candidate.get('bundle_sha256')
        if not isinstance(bundle_sha,str) or not re.fullmatch('[0-9a-f]{64}',bundle_sha):raise ValueError('Missing bundle hash')
        snap=ec2.describe_snapshots(SnapshotIds=[diagnostic['snapshot_id']])['Snapshots'][0]
        if snap['VolumeId']!=diagnostic['source_volume'] or snap['State']!='completed':raise ValueError('Diagnostic snapshot not complete')
        s3=boto3.client('s3',region_name='us-east-1')
        obj=s3.head_object(Bucket=bucket,Key=bundle_key)
        if obj['ContentLength']!=candidate.get('bundle_size_bytes') or obj.get('Metadata',{}).get('sha256')!=bundle_sha:raise ValueError('Candidate S3 object differs')
        url=s3.generate_presigned_url('get_object',Params={'Bucket':bucket,'Key':bundle_key},ExpiresIn=14400)
        overrides={'BundleUrl':url,'BundleSha256':bundle_sha,'BootstrapPrefix':bundle_key.rsplit('/',1)[0]+'/'}
        parameters=[{'ParameterKey':key,'ParameterValue':overrides[key]} if key in overrides else {'ParameterKey':key,'UsePreviousValue':True} for key in params]
        state={'account':account,'stack_id':probe['stack_id'],'revision':args.revision,'template_sha256':digest,
            'source_volume':diagnostic['source_volume'],'source_instance':diagnostic['source_instance'],
            'bundle_sha256':bundle_sha,'phase':'preparing','root_replace_token':str(uuid.uuid4())}
        write(state_path,state,True)
        result=cfn.create_change_set(StackName=probe['stack_id'],ChangeSetName='repair-'+args.revision.lower()+'-'+uuid.uuid4().hex[:8],
            ChangeSetType='UPDATE',TemplateBody=template_bytes.decode(),Parameters=parameters)
        state.update(change_set_id=result['Id'],phase='prepared');write(state_path,state)
        private_template=state_path.with_name('web-lab-repair-'+args.revision.lower()+'.template.json')
        with private_template.open('xb') as stream:stream.write(template_bytes)
    else:
        state=json.loads(state_path.read_text())
        if state['account']!=account or state['stack_id']!=probe['stack_id'] or state['template_sha256']!=digest or state['revision']!=args.revision:raise ValueError('Repair identity changed')
        if args.action in ('review','execute'):
            change=cfn.describe_change_set(ChangeSetName=state['change_set_id'],StackName=state['stack_id'])
            if change['Status']!='CREATE_COMPLETE' or change.get('NextToken'):raise ValueError('Wait for complete bounded change set')
            node=ec2.describe_instances(InstanceIds=[state['source_instance']])['Reservations'][0]['Instances'][0]
            validate_repo_for_update(node,state)
            changes=check_changes(change['Changes'],args.revision,repo_ebs_verified=True)
            print('JDU_REPAIR_CHANGES='+json.dumps(changes,separators=(',',':')))
            if args.action=='execute':
                if state['phase']!='prepared' or stack['StackStatus']!='CREATE_FAILED':raise ValueError('Repair execution already requested')
                backup=probe_path.with_name('five-node-state.before-'+args.revision.lower()+'.private.json')
                write(backup,probe,True)
                state['phase']='execute_requested';write(state_path,state)
                cfn.execute_change_set(ChangeSetName=state['change_set_id'],StackName=state['stack_id'],DisableRollback=True)
                probe['template_sha256']=digest;write(probe_path,probe)
                state['phase']='executed';write(state_path,state)
        elif args.action=='reimage':
            if state['phase']!='executed':raise ValueError('Root restoration already requested or repair not executed')
            resources=cfn.list_stack_resources(StackName=state['stack_id'])['StackResourceSummaries']
            repo=next(x for x in resources if x['LogicalResourceId']=='RepoInstance')
            if repo['PhysicalResourceId']!=state['source_instance'] or repo['ResourceStatus']!='UPDATE_COMPLETE':raise ValueError('Wait for repo UserData update')
            node=ec2.describe_instances(InstanceIds=[state['source_instance']])['Reservations'][0]['Instances'][0]
            root=next(x['Ebs']['VolumeId'] for x in node['BlockDeviceMappings'] if x['DeviceName']==node['RootDeviceName'])
            if node['ImageId']!=AMI or node['PrivateIpAddress']!='10.20.2.30' or root!=state['source_volume']:raise ValueError('Source instance changed')
            if node['State']['Name']!='running':raise ValueError('Wait for existing repo to run')
            userdata=ec2.describe_instance_attribute(InstanceId=state['source_instance'],Attribute='userData')['UserData']['Value']
            config=json.loads(base64.b64decode(userdata).decode().split('\n',1)[1])
            private=next(json.loads(x['content']) for x in config['write_files'] if x['path']=='/var/lib/jdu-web/initial/private.json')
            expected=json.loads(new['Resources']['RepoInstance']['Properties']['UserData']['Fn::Base64']['Fn::Sub'].split('\n',1)[1])
            pins=next(json.loads(x['content']) for x in expected['write_files'] if x['path']=='/var/lib/jdu-web/initial/private.json')['script_pins']
            if private['script_pins']!=pins or private['bundle_sha256']!=state['bundle_sha256'] or private['deployment_id']!=probe['deployment_id']:raise ValueError('Updated bootstrap identity differs')
            state['phase']='reimage_requested';write(state_path,state)
            result=ec2.create_replace_root_volume_task(InstanceId=state['source_instance'],DeleteReplacedRootVolume=False,ClientToken=state['root_replace_token'])
            state.update(root_replace_task_id=result['ReplaceRootVolumeTask']['ReplaceRootVolumeTaskId'],phase='reimage_started');write(state_path,state)
        elif args.action=='status':
            if 'root_replace_task_id' in state:
                task=ec2.describe_replace_root_volume_tasks(ReplaceRootVolumeTaskIds=[state['root_replace_task_id']])['ReplaceRootVolumeTasks'][0]
                state['root_replace_status']=task['TaskState'];write(state_path,state)
    safe={k:v for k,v in state.items() if k not in ('account','stack_id','change_set_id','root_replace_token')}
    safe['stack_status']=stack['StackStatus'];print('JDU_REPAIR_STATE='+json.dumps(safe,separators=(',',':')))


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('JDU_REPAIR_ERROR='+type(e).__name__)
        if hasattr(e,'response'):print('JDU_REPAIR_API='+e.response['Error']['Code'])
        elif isinstance(e,ValueError):print('JDU_REPAIR_REASON='+str(e))
        raise SystemExit(2)
