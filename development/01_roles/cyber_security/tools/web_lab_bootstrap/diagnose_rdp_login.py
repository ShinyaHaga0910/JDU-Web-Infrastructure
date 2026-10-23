"""Read a fresh bastion snapshot with retained recovery3; never change credentials.

The original bastion root stays attached and running. A new encrypted clone is
attached only AFTER the helper boots its own root, then mounted ro,noload.
Only fixed diagnostic facts and categorized log events leave the cloned disk.
"""
import argparse
import base64
from datetime import datetime,timezone
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import re

BASTION='i-0561e59b67914f372'
BASTION_ROOT='vol-0538033bb821f5a3f'
HELPER='i-022e4605fe093960e'
HELPER_ROOT='vol-0bcf355d74caef268'


def inspect_root(root):
    import configparser
    import hmac
    import json
    import re
    import stat
    import subprocess
    from datetime import datetime,timezone
    from pathlib import Path
    root=Path(root)
    passwd=[x.split(':') for x in (root/'etc/passwd').read_text().splitlines() if x.startswith('labuser:')]
    shadow=[x.split(':') for x in (root/'etc/shadow').read_text().splitlines() if x.startswith('labuser:')]
    cfg=json.loads((root/'var/lib/jdu-web/initial/private.json').read_text())
    report={'scope':'teacher_read_only_rdp_snapshot_diagnosis','mount_options':'ro,noload',
        'credentials_changed':False,'hashes_exported':False,'account_exists':len(passwd)==1 and len(shadow)==1}
    if report['account_exists']:
        p=passwd[0];s=shadow[0];days=int(datetime.now(timezone.utc).timestamp()//86400)
        session=root/p[5].lstrip('/')/'.xsession'
        report.update(shell=p[6],home_is_expected=p[5]=='/home/labuser',
            shadow_is_sha512=bool(re.fullmatch(r'\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}',s[1])),
            shadow_locked=s[1].startswith(('!','*')),shadow_matches_bootstrap=hmac.compare_digest(s[1],cfg['rdp_hash']),
            password_change_required=s[2]=='0',
            password_expired=bool(s[2] and s[4] and int(s[4])>=0 and int(s[2])+int(s[4])<days),
            account_expired=bool(s[7] and int(s[7])>=0 and int(s[7])<days),
            session_file_exists=session.is_file())
        if session.is_file():
            info=session.stat();report.update(session_owned_by_user=info.st_uid==int(p[2]),
                session_mode=oct(stat.S_IMODE(info.st_mode)),session_has_xfce='startxfce4' in session.read_text(),
                session_has_dbus='dbus-run-session' in session.read_text())
    group=[x.split(':') for x in (root/'etc/group').read_text().splitlines()]
    parser=configparser.ConfigParser(interpolation=None,strict=False)
    parser.read(root/'etc/xrdp/sesman.ini')
    report['sesman_security']={k:parser.get('Security',k,fallback='absent') for k in
        ('AllowRootLogin','MaxLoginRetry','TerminalServerUsers','TerminalServerAdmins','AlwaysGroupCheck')}
    name=parser.get('Security','TerminalServerUsers',fallback='tsusers')
    report['terminal_users_group_exists']=any(x[0]==name for x in group)
    report['labuser_in_terminal_users_group']=any(x[0]==name and 'labuser' in x[3].split(',') for x in group)
    pam=(root/'etc/pam.d/xrdp-sesman').read_text()
    report['pam_includes_common_auth']='@include common-auth' in pam
    report['pam_includes_common_account']='@include common-account' in pam
    report['pam_includes_common_session']='@include common-session' in pam
    categories=[
        ('pam_authentication_failed',r'pam_authenticate failed|authentication failure|AUTHFAIL|auth failed'),
        ('pam_account_denied',r'pam_acct_mgmt|account.*(?:expired|locked|denied)'),
        ('login_failed',r'login failed|login failure'),
        ('login_success',r'login successful|login succeeded|access permitted'),
        ('session_created',r'created session|starting Xorg session|starting session'),
        ('window_manager_exited',r'window manager.*(?:exited|exit code)'),
        ('xserver_failed',r'X server.*(?:could not|startup|failed)|Xorg.*error|X server.*not active'),
        ('connection_problem',r'scp_process_msg failed|transport.*failed|connect.*failed'),
        ('session_auth_started',r'Performing.*login|auth_start_session'),
        ('pam_session_opened',r'pam_unix\(xrdp-sesman:session\): session opened')]
    sources={}
    for path in ['var/log/xrdp.log','var/log/xrdp-sesman.log','var/log/auth.log','home/labuser/.xsession-errors']:
        file=root/path
        if file.is_file():sources[path]=file.read_text(errors='replace').splitlines()[-250:]
    journals=list((root/'var/log/journal').glob('*/*.journal'))
    report['persistent_journal_files']=len(journals)
    if journals:
        result=subprocess.run(['journalctl','--directory='+str(root/'var/log/journal'),'-u','xrdp-sesman','-u','xrdp',
            '--no-pager','--output=json','-n','200'],capture_output=True,text=True)
        sources['persistent_journal']=[]
        if result.returncode==0:
            for line in result.stdout.splitlines():
                try:message=json.loads(line).get('MESSAGE','')
                except ValueError:continue
                if isinstance(message,str):sources['persistent_journal'].append(message)
        report['journal_read_success']=result.returncode==0
    report['logs']={}
    for source,lines in sources.items():
        counts={};events=[]
        for line in lines:
            labels=[label for label,pattern in categories if re.search(pattern,line,re.I)]
            for label in labels:counts[label]=counts.get(label,0)+1
            if labels:
                event={'categories':labels,'mentions_labuser':bool(re.search(r'\blabuser\b',line))}
                timestamp=re.search(r'\[(\d{8}-\d\d:\d\d:\d\d)\]',line)
                if timestamp:event['time']=timestamp[1]
                code=re.search(r'pam_authenticate failed:\s*(\d+)',line)
                if code:event['pam_error_code']=int(code[1])
                events.append(event)
        report['logs'][source]={'lines_examined':len(lines),'counts':counts,'last_events':events[-20:]}
    return report


def userdata(clone):
    source="from pathlib import Path\nimport base64,json,subprocess,time\n"+inspect.getsource(inspect_root)+"\n"
    source+="""mount=Path('/mnt/jdu-rdp-diagnostic');mount.mkdir(exist_ok=True)
device=None
for _ in range(150):
 info=json.loads(subprocess.check_output(['lsblk','-J','--tree','-o','PATH,SERIAL,TYPE,MOUNTPOINTS'],text=True))
 disk=next((d for d in info['blockdevices'] if (d.get('serial') or '').replace('-','')==CLONE.replace('-','')),None)
 if disk:
  part=next((p for p in disk.get('children',[]) if p['path']==disk['path']+'p1'),None)
  if part and any(part.get('mountpoints') or []):raise ValueError('Target clone already mounted')
  if part:
   device=part['path'];break
 time.sleep(2)
if not device:raise ValueError('Explicit cloned volume not found')
if subprocess.check_output(['blkid','-p','-s','TYPE','-o','value',device],text=True).strip()!='ext4':raise ValueError('Expected ext4 clone')
subprocess.run(['mount','-o','ro,noload',device,str(mount)],check=True)
try:
 report=inspect_root(mount)
 print('JDU_RDP_DIAG_BEGIN'+base64.b64encode(json.dumps(report,separators=(',',':')).encode()).decode()+'JDU_RDP_DIAG_END',flush=True)
finally:subprocess.run(['umount',str(mount)],check=True)
"""
    source='CLONE='+repr(clone)+'\n'+source
    packed=base64.b64encode(gzip.compress(source.encode(),mtime=0)).decode()
    return ("#cloud-boothook\n#!/bin/bash\nset -eu\nexec > /dev/ttyS0 2>&1\necho JDU_RDP_DIAG_STARTED\n"
        "python3 - <<'PY'\nimport base64,gzip\nexec(compile(gzip.decompress(base64.b64decode('"+packed+"')),'jdu-rdp-diagnostic','exec'))\nPY\n"
        "echo JDU_RDP_DIAG_FINISHED\nshutdown -h +1\n").encode()


def save(path,state,exclusive=False):
    with path.open('x' if exclusive else 'w') as stream:json.dump(state,stream,indent=2);stream.write('\n')


def main():
    import boto3
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('snapshot','clone','boot','attach','read','stop','restore','status'))
    p.add_argument('--probe-state',required=True);p.add_argument('--state',required=True)
    a=p.parse_args();os.umask(0o077)
    probe=json.loads(Path(a.probe_state).read_text());path=Path(a.state)
    account=boto3.client('sts').get_caller_identity()['Account']
    if account!=probe['account'] or probe['stack_name']!='jdu-web-five-node-probe-20261015':raise ValueError('Wrong probe account')
    ec2=boto3.client('ec2',region_name='us-east-1');cfn=boto3.client('cloudformation',region_name='us-east-1')
    refs={r['LogicalResourceId']:r.get('PhysicalResourceId') for r in cfn.list_stack_resources(StackName=probe['stack_id'])['StackResourceSummaries']}
    if refs['BastionInstance']!=BASTION:raise ValueError('Wrong bastion reference')
    nodes={n['InstanceId']:n for r in ec2.describe_instances(InstanceIds=[BASTION,HELPER])['Reservations'] for n in r['Instances']}
    bastion=nodes[BASTION];helper=nodes[HELPER]
    def root(node):return next(v['Ebs']['VolumeId'] for v in node['BlockDeviceMappings'] if v['DeviceName']==node['RootDeviceName'])
    if root(bastion)!=BASTION_ROOT or root(helper)!=HELPER_ROOT or bastion['PrivateIpAddress']!='10.20.1.10':raise ValueError('Original root identity differs')
    if helper['Placement']['AvailabilityZone']!=bastion['Placement']['AvailabilityZone']:raise ValueError('Helper AZ differs')
    prior=path.with_name('recovery3-userdata.before-node-diagnosis.private.b64')
    previous=base64.b64decode(prior.read_text())
    if a.action=='snapshot':
        if path.exists() or helper['State']['Name']!='stopped' or len(helper['BlockDeviceMappings'])!=1:raise ValueError('Existing or unsafe diagnosis state')
        current=base64.b64decode(ec2.describe_instance_attribute(InstanceId=HELPER,Attribute='userData').get('UserData',{}).get('Value',''))
        if current!=previous:raise ValueError('Helper original user data differs')
        state={'account':account,'stack_id':probe['stack_id'],'deployment_id':probe['deployment_id'],
            'source_instance':BASTION,'source_volume':BASTION_ROOT,'helper_instance':HELPER,'helper_root':HELPER_ROOT,
            'az':bastion['Placement']['AvailabilityZone'],'phase':'snapshot_requested'}
        save(path,state,True)
        snap=ec2.create_snapshot(VolumeId=BASTION_ROOT,Description='Read-only xrdp diagnosis; original bastion remains attached',
            TagSpecifications=[{'ResourceType':'snapshot','Tags':[{'Key':'Name','Value':'jdu-web-rdp-diagnosis-20261016'}]}])
        state.update(snapshot_id=snap['SnapshotId'],phase='snapshot_pending');save(path,state)
    else:
        state=json.loads(path.read_text())
        if any(state[k]!=v for k,v in {'account':account,'stack_id':probe['stack_id'],'deployment_id':probe['deployment_id'],
                'source_instance':BASTION,'source_volume':BASTION_ROOT,'helper_instance':HELPER,'helper_root':HELPER_ROOT}.items()):raise ValueError('Saved identity differs')
        if 'clone_volume' in state:
            volume=ec2.describe_volumes(VolumeIds=[state['clone_volume']])['Volumes'][0]
            if volume['SnapshotId']!=state['snapshot_id'] or not volume['Encrypted']:raise ValueError('Wrong encrypted snapshot clone')
        if a.action=='clone':
            if state['phase']!='snapshot_pending':raise ValueError('Clone already requested')
            snap=ec2.describe_snapshots(SnapshotIds=[state['snapshot_id']])['Snapshots'][0]
            if snap['State']!='completed' or snap['VolumeId']!=BASTION_ROOT:raise ValueError('Wait for exact snapshot')
            state['phase']='clone_requested';save(path,state)
            volume=ec2.create_volume(AvailabilityZone=state['az'],SnapshotId=state['snapshot_id'],Encrypted=True,VolumeType='gp3',
                TagSpecifications=[{'ResourceType':'volume','Tags':[{'Key':'Name','Value':'jdu-web-rdp-readonly-clone-20261016'}]}])
            state.update(clone_volume=volume['VolumeId'],phase='clone_pending');save(path,state)
        elif a.action=='boot':
            if state['phase']!='clone_pending' or helper['State']['Name']!='stopped' or len(helper['BlockDeviceMappings'])!=1 or volume['State']!='available' or volume['Attachments']:raise ValueError('Expected stopped root-only helper and detached clone')
            current=base64.b64decode(ec2.describe_instance_attribute(InstanceId=HELPER,Attribute='userData').get('UserData',{}).get('Value',''))
            if current!=previous:raise ValueError('Helper original user data changed')
            state['phase']='boot_requested';save(path,state)
            ec2.modify_instance_attribute(InstanceId=HELPER,UserData={'Value':userdata(state['clone_volume'])})
            ec2.start_instances(InstanceIds=[HELPER]);state.update(phase='booting',started_at=datetime.now(timezone.utc).isoformat());save(path,state)
        elif a.action=='attach':
            if state['phase']!='booting' or helper['State']['Name']!='running' or len(helper['BlockDeviceMappings'])!=1 or volume['State']!='available' or volume['Attachments']:raise ValueError('Wait for own-root helper boot')
            if (datetime.now(timezone.utc)-datetime.fromisoformat(state['started_at'])).total_seconds()<45:raise ValueError('Wait 45 seconds before attaching clone')
            ec2.attach_volume(Device='/dev/sdf',InstanceId=HELPER,VolumeId=state['clone_volume']);state['phase']='attached';save(path,state)
        elif a.action=='read':
            output=ec2.get_console_output(InstanceId=HELPER,Latest=True).get('Output','')
            if 'JDU_RDP_DIAG' not in output:
                try:output=base64.b64decode(output,validate=True).decode()
                except Exception:pass
            output=re.sub(r'\[\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z?\]','',output)
            found=re.search(r'JDU_RDP_DIAG_BEGIN([A-Za-z0-9+/=\r\n]+)JDU_RDP_DIAG_END',output)
            if found:
                report=json.loads(base64.b64decode(found[1]));target=path.with_name('rdp-login-diagnosis.public.json')
                save(target,report);state['report_file']=str(target);save(path,state)
                print('RDP_DIAG_REPORT='+json.dumps(report,separators=(',',':')))
            else:print('RDP_DIAG_PENDING='+json.dumps([x for x in output.splitlines() if 'JDU_RDP_DIAG_' in x and len(x)<100][-4:]))
        elif a.action=='stop':
            if helper['State']['Name']=='running':ec2.stop_instances(InstanceIds=[HELPER])
            state['phase']='stopping';save(path,state)
        elif a.action=='restore':
            if helper['State']['Name']!='stopped' or 'report_file' not in state or len(volume['Attachments'])!=1 or volume['Attachments'][0]['InstanceId']!=HELPER:raise ValueError('Wait for stopped helper and successful report')
            ec2.modify_instance_attribute(InstanceId=HELPER,UserData={'Value':previous})
            ec2.detach_volume(VolumeId=state['clone_volume'],InstanceId=HELPER,Device='/dev/sdf');state['phase']='restored';save(path,state)
        elif a.action=='status':
            if 'snapshot_id' in state:print('RDP_SNAPSHOT_STATE='+ec2.describe_snapshots(SnapshotIds=[state['snapshot_id']])['Snapshots'][0]['State'])
            if 'clone_volume' in state:print('RDP_CLONE_STATE='+volume['State'])
    print('RDP_DIAG_STATE='+json.dumps({'phase':state['phase'],'bastion_state':bastion['State']['Name'],'helper_state':helper['State']['Name'],'original_root_untouched':True}))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('RDP_DIAG_FAILED='+type(exc).__name__)
        if hasattr(exc,'response'):print('AWS_ERROR_CODE='+exc.response['Error']['Code'])
        elif isinstance(exc,ValueError):print('PUBLIC_REASON='+str(exc))
        raise SystemExit(2)
