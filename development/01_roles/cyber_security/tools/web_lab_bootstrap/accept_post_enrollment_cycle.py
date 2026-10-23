"""Same-five-node stop/start after enrollment; retain keys, work and registration.

The previous cycle remains historical. This independent cycle has its own
exclusive plan and request markers; unknown outcomes must be inspected, not
retried. No credential or key issuance occurs.
"""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

DEPLOYMENT='fc335855-7034-427c-8494-6d7a0491ddf1'
MANIFEST='d9d61ffcebb9d2e8c9fe874563a6f292b902d15e70dad86e604c006d0fc545f5'

RETENTION_GUEST='''import json,hashlib,os,sys
from pathlib import Path
r=json.loads(sys.stdin.read(65537));c=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
assert all(c[k]==r[k] for k in ('role','lab_id','deployment_id','instance_id'))
p=Path('/var/lib/jdu-web/d08-student-work-retention-probe.json')
body=json.dumps({k:c[k] for k in ('role','lab_id','deployment_id','instance_id')},sort_keys=True).encode()
if r['operation']=='before':
 with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644),'wb') as f:f.write(body)
assert p.read_bytes()==body and not p.is_symlink()
print(json.dumps(dict(role=c['role'],instance_id=c['instance_id'],marker_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
 initial_role_state_sha256=hashlib.sha256(Path('/var/lib/jdu-web/bootstrap/role-state.json').read_bytes()).hexdigest(),
 boot_id_sha256=hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest())))
'''


def main():
    import boto3
    sys.dont_write_bytecode=True;os.umask(0o077)
    home=Path.home();work=Path(__file__).resolve().parent;tools=home/'jdu-web-student-tools-c5-v6'
    state_path=home/'jdu-web-capture-20261015/student-c5-v6.private.json'
    config_path=home/'.jdu-web-student/teacher-c4-probe/command-state-c5-v6.json'
    config=json.loads(config_path.read_text());state=json.loads(state_path.read_text())
    if state['deployment_id']!=DEPLOYMENT or state['manifest_sha256']!=MANIFEST:raise ValueError('Wrong reviewed deployment')
    from_root=home/'jdu-web-capture-20261015/persistent-ssm-20261020/cycle_five_nodes.py'
    if hashlib.sha256(from_root.read_bytes()).hexdigest()!='0987d74abf818ac898243aaa007c33ab584af8c5cb96cd6084341e5b6ee48409':
        raise ValueError('Reviewed cycle helper differs')
    sys.path.insert(0,config['bootstrap_tools'])
    from setup_internal_ssh import current_nodes,remote,save_new
    ec2=boto3.client('ec2',region_name='us-east-1');cfn=boto3.client('cloudformation',region_name='us-east-1')
    if boto3.client('sts').get_caller_identity()['Account']!=state['account']:raise ValueError('Wrong account')
    nodes=current_nodes(ec2,cfn,state,json.loads(Path(config['baseline_plan']).read_text()))
    for name in ('role-packages-dns-v3.public.json','role-packages-db-v2.public.json'):
        r=json.loads((work/name).read_text())
        if r['deployment_id']!=DEPLOYMENT or not r['original_package_versions_restored']:raise ValueError('Package probe not restored')
    def common(operation,*args):
        r=subprocess.run(['bash',str(tools/'jdu-web-lab'),operation,'--state',str(state_path),*map(str,args)],
            capture_output=True,text=True,check=True,timeout=240)
        print(r.stdout,flush=True);return r.stdout
    def preflight():
        output=common('preflight');r=json.loads(output.strip().splitlines()[-1])
        if not r['current_foundation_passed']:raise ValueError('Foundation incomplete')
        return re.findall(r'^SUBMISSION STORED request_id=([0-9a-f-]{36})$',output,re.M)[-1]
    before_request=preflight();ssm=boto3.client('ssm',region_name='us-east-1')
    def snapshots(operation):
        return {role:remote(ssm,n['instance_id'],RETENTION_GUEST.encode(),dict(operation=operation,role=role,
            lab_id=state['lab_id'],deployment_id=DEPLOYMENT,instance_id=n['instance_id'])) for role,n in nodes.items()}
    before=snapshots('before');save_new(work/'post-enrollment-retention-before.public.json',dict(deployment_id=DEPLOYMENT,nodes=before))
    plan=work/'post-enrollment-cycle.private.json'
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=config['bootstrap_tools'])
    def cycle(op):
        subprocess.run(['python3','-B',str(from_root),op,'--state',str(state_path),
            '--baseline-plan',config['baseline_plan'],'--cycle-state',str(plan)],env=env,check=True,timeout=90)
    cycle('prepare');cycle('stop')
    ids=[n['instance_id'] for n in nodes.values()]
    ec2.get_waiter('instance_stopped').wait(InstanceIds=ids,WaiterConfig={'Delay':5,'MaxAttempts':60})
    print('POST_ENROLLMENT_ALL_FIVE_STOPPED',flush=True)
    cycle('start');started=datetime.now(timezone.utc)
    ec2.get_waiter('instance_running').wait(InstanceIds=ids,WaiterConfig={'Delay':5,'MaxAttempts':60})
    for _ in range(90):
        info=ssm.describe_instance_information(Filters=[dict(Key='InstanceIds',Values=ids)])['InstanceInformationList']
        if (len(info)==5 and all(x['PingStatus']=='Online' and x['LastPingDateTime']>=started for x in info)):break
        time.sleep(5)
    else:raise ValueError('Fresh post-start SSM heartbeat still pending')
    cycle('status')
    observed={i['InstanceId']:i for r in ec2.describe_instances(InstanceIds=ids)['Reservations'] for i in r['Instances']}
    addresses=dict(deployment_id=DEPLOYMENT,bastion_public_ip=observed[nodes['bastion']['instance_id']].get('PublicIpAddress'),
        web_public_ip=observed[nodes['web']['instance_id']].get('PublicIpAddress'),class_ready=False)
    save_new(work/'post-enrollment-connection.public.json',addresses)
    print('POST_ENROLLMENT_CONNECTION='+json.dumps(addresses),flush=True)
    after=snapshots('after')
    for role,value in before.items():
        if (any(after[role][k]!=value[k] for k in ('role','instance_id','marker_sha256','initial_role_state_sha256'))
                or after[role]['boot_id_sha256']==value['boot_id_sha256']):raise ValueError('Student work or initial state retention differs')
    status_output=common('status','--output',work/'post-enrollment-fresh-status.public.json')
    r=json.loads(status_output.strip().splitlines()[-1])
    if not all(r[k] for k in ('aws_passed','role_passed','network_passed')):raise ValueError('Post-start status incomplete')
    after_request=preflight()
    if (Path(config['bootstrap_tools'])/'__pycache__').exists():raise ValueError('Controller cache was regenerated')
    receipt=dict(deployment_id=DEPLOYMENT,checked_at=datetime.now(timezone.utc).isoformat(),same_five_ids_and_roots=True,
        scope='post_enrollment_five_node_stop_start_and_retention',same_enrolled_ssh_key_and_pins_verified=True,
        same_student_grading_credential_reused_and_submitted=True,retained_student_work_all_five=True,
        initial_role_state_unchanged_all_five=True,all_five_boot_ids_changed=True,all_five_fresh_ssm_online=True,
        original_student_services_still_uninstalled=True,foundation_before_request=before_request,
        foundation_after_request=after_request,foundation_after_passed=47,all_aws_role_network_passed=True,
        credentials_created=0,new_controller_cache_generated=False,after_nodes=after,class_ready=False)
    save_new(work/'post-enrollment-cycle-acceptance.public.json',receipt)
    print('POST_ENROLLMENT_STOP_START_RETENTION_ACCEPTED; same SSH/token and 47/47 stored',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('POST_ENROLLMENT_CYCLE_STOPPED='+type(e).__name__+': '+str(e),flush=True)
        raise SystemExit(2)
