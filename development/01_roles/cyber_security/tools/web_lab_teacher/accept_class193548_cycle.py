"""One stop/start of the accepted separate student's five original nodes.

Preserves student work, initial records, existing SSH keys and grading token.
Only the reviewed student's five IDs are stopped; the teacher is excluded.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'
MANIFEST = 'a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2'
RETENTION_GUEST = '''import json,hashlib,os,sys
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
    sys.dont_write_bytecode = True; os.umask(0o077)
    home = Path.home(); base = home / 'jdu-web-class193548'; work = Path(__file__).resolve().parent
    kit = base / 'cross-account-delivery-v1'; sys.path.insert(0, str(kit))
    for name, pin in {
        'class_student_delivery.py': '1bbaf46daa1eed027e17e422e64ff0af5e8f24791d36df2f2379a57ff652a184',
        'web_progress.py': 'a966bbe49eefdb4fc6f9ca1dc39d930532992490923fde155caf3ed5a5aed6a4',
        'release_validation.py': 'e9aebc2f1ed3d54df70e862e5a9aabe8e08970004106c8a89a6260da9e34096c',
        'enroll_class193548_student.py': 'a3d1443aad2ec349da638df742f539957484ada82c99437b05a0911635fb3fba',
    }.items():
        if hashlib.sha256((kit / name).read_bytes()).hexdigest() != pin:
            raise ValueError('Accepted helper changed')
    import class_student_delivery as delivery
    session = boto3.Session(region_name='us-east-1'); delivery.identity(session, delivery.STUDENT)
    tools = base / 'student-software-v7/student-tools'
    verified = delivery.verified_tools(tools)
    if verified['manifest_sha256'] != MANIFEST:
        raise ValueError('Accepted signed v7 required')
    state_path = base / 'student-v7.private.json'; state = json.loads(state_path.read_text())
    config = json.loads((home / '.jdu-web-student/class193548-test1/command-state.json').read_text())
    from setup_internal_ssh import current_nodes, remote, save_new
    from enroll_class193548_student import require_nodes
    ec2 = session.client('ec2'); cfn = session.client('cloudformation'); ssm = session.client('ssm')
    nodes = current_nodes(ec2, cfn, state, json.loads(Path(config['baseline_plan']).read_text()))
    require_nodes(state, nodes)
    fixture = json.loads((base / 'web02-acceptance-20261022/web02-integration.public.json').read_text())
    if (fixture['deployment_id'] != DEPLOYMENT or fixture['fixture_package_inventory_restored'] is not True
            or fixture['repository_service_restored'] is not True or fixture['assessment_count'] != 13):
        raise ValueError('Completed and restored WEB-02 fixtures required')
    cycle_helper = work / 'cycle_five_nodes.py'
    if hashlib.sha256(cycle_helper.read_bytes()).hexdigest() != '0987d74abf818ac898243aaa007c33ab584af8c5cb96cd6084341e5b6ee48409':
        raise ValueError('Reviewed cycle helper differs')
    if (work / 'cycle-plan.private.json').exists():
        raise ValueError('Existing cycle retained; inspect partial state instead')
    def common(operation, *extra):
        result = subprocess.run(['bash', str(tools / 'jdu-web-lab'), operation, '--state', str(state_path),
            *map(str, extra)], capture_output=True, text=True, timeout=300)
        (work / (operation + '-' + str(time.time_ns()) + '.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError('Signed operation stopped; inspect retained log')
        print(result.stdout, end='', flush=True)
        return result.stdout
    def preflight():
        output = common('preflight'); result = json.loads(output.strip().splitlines()[-1])
        ids = re.findall(r'^SUBMISSION STORED request_id=([0-9a-f-]{36})$', output, re.M)
        if result['current_foundation_passed'] is not True or not ids:
            raise ValueError('Actual 47/47 submission required')
        return ids[-1]
    def snapshots(operation):
        return {role: remote(ssm, node['instance_id'], RETENTION_GUEST.encode(), dict(operation=operation,
            role=role, lab_id=state['lab_id'], deployment_id=DEPLOYMENT, instance_id=node['instance_id']))
            for role, node in nodes.items()}
    before_request = preflight(); before = snapshots('before')
    save_new(work / 'retention-before.public.json', dict(deployment_id=DEPLOYMENT, nodes=before))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=config['bootstrap_tools'])
    def cycle(operation):
        subprocess.run(['python3', '-B', str(cycle_helper), operation, '--state', str(state_path),
            '--baseline-plan', config['baseline_plan'], '--cycle-state', str(work / 'cycle-plan.private.json')],
            env=env, check=True, timeout=90)
    cycle('prepare'); cycle('stop')
    ids = [node['instance_id'] for node in nodes.values()]
    ec2.get_waiter('instance_stopped').wait(InstanceIds=ids, WaiterConfig={'Delay': 5, 'MaxAttempts': 60})
    print('CLASS193548_ALL_FIVE_STOPPED; roots retained', flush=True)
    cycle('start'); started = datetime.now(timezone.utc)
    ec2.get_waiter('instance_running').wait(InstanceIds=ids, WaiterConfig={'Delay': 5, 'MaxAttempts': 60})
    for _ in range(90):
        info = ssm.describe_instance_information(Filters=[dict(Key='InstanceIds', Values=ids)])['InstanceInformationList']
        if len(info) == 5 and all(x['PingStatus'] == 'Online' and x['LastPingDateTime'] >= started for x in info):
            break
        time.sleep(5)
    else:
        raise ValueError('Fresh post-start SSM heartbeat still pending; retain cycle')
    cycle('status')
    actual = {i['InstanceId']: i for r in ec2.describe_instances(InstanceIds=ids)['Reservations'] for i in r['Instances']}
    connection = dict(deployment_id=DEPLOYMENT, bastion_public_ip=actual[nodes['bastion']['instance_id']].get('PublicIpAddress'),
        web_public_ip=actual[nodes['web']['instance_id']].get('PublicIpAddress'), class_ready=False)
    save_new(work / 'connection.public.json', connection)
    print('CLASS193548_POST_RESTART_CONNECTION=' + json.dumps(connection), flush=True)
    after = snapshots('after')
    for role, value in before.items():
        if (any(after[role][k] != value[k] for k in ('role', 'instance_id', 'marker_sha256', 'initial_role_state_sha256'))
                or after[role]['boot_id_sha256'] == value['boot_id_sha256']):
            raise ValueError('Student work, initial records or reboot evidence differ')
    output = common('status', '--output', work / 'post-restart-status.public.json')
    result = json.loads(output.strip().splitlines()[-1])
    if not all(result[k] for k in ('aws_passed', 'role_passed', 'network_passed')):
        raise ValueError('Post-start foundation still incomplete')
    credential = base / 'student-delivery-renewal-20261022/received/own-student.credentials.json'
    common('register-verify', '--student-config', credential)
    after_request = preflight()
    if (Path(config['bootstrap_tools']) / '__pycache__').exists():
        raise ValueError('Unexpected controller cache generated')
    save_new(work / 'cycle-acceptance.public.json', dict(scope='actual_separate_student_stop_start_retention',
        deployment_id=DEPLOYMENT, checked_at=datetime.now(timezone.utc).isoformat(), same_five_ids_and_roots=True,
        student_work_and_initial_role_records_retained_all_five=True, all_five_boot_ids_changed=True,
        all_five_fresh_ssm_online=True, same_internal_ssh_and_grading_credential_verified=True,
        foundation_before_request=before_request, foundation_after_request=after_request,
        foundation_after_passed=47, all_aws_role_network_passed=True, after_nodes=after,
        new_credentials_created=False, teacher_storage_verification_pending=True, class_ready=False))
    print('CLASS193548_STOP_START_RETENTION_ACCEPTED; same SSH/token and fresh 47/47 submitted', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('CLASS193548_CYCLE_STOPPED=' + type(exc).__name__ + '; preserve original resources and partial cycle', flush=True)
        raise SystemExit(2)
