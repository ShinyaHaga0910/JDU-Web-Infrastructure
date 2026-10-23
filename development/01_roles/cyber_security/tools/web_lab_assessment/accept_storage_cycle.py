"""Teacher-only reversible Web stop/start acceptance; checker never stops instances."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', required=True)
    p.add_argument('--command-state', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    import boto3
    os.umask(0o077)
    if boto3.client('sts').get_caller_identity()['Account'] != '965244652544':
        raise ValueError('Only the selected verification student')
    c = json.loads(Path(a.command_state).read_text())
    state, baseline = [json.loads(Path(c[k]).read_text()) for k in ('state', 'baseline_plan')]
    if state['deployment_id'] != baseline['deployment_id'] or state['deployment_id'] != DEPLOYMENT:
        raise ValueError('Wrong retained deployment')
    out = Path(a.output)
    journal = Path(str(out) + '.private-journal.json')
    if out.exists() or journal.exists():
        raise ValueError('Existing cycle retained; inspect its journal before any further action')
    sys.path[:0] = [a.candidate, c['bootstrap_tools']]
    from setup_internal_ssh import current_nodes
    from registry import CONTRACT_ID, CONTRACT_SHA256
    ec2, cfn, ssm = [boto3.client(n, region_name='us-east-1') for n in ('ec2', 'cloudformation', 'ssm')]
    nodes = current_nodes(ec2, cfn, state, baseline)
    web = nodes['web']['instance_id']
    root = Path(c['pending_directory']) / CONTRACT_ID
    for task in ('M3', 'P3'):
        pointer = json.loads((root / (task + '.active.json')).read_text())
        before = json.loads((root / (task + '.' + pointer['evidence_id'] + '.before.json')).read_text())
        if (before['instance_id'] != web or before['deployment_id'] != DEPLOYMENT
                or before['contract_sha256'] != CONTRACT_SHA256 or before['root_volume'] not in nodes['web']['root_volumes']):
            raise ValueError('Retain both existing marker baselines before stopping the Web')
    record = dict(deployment_id=DEPLOYMENT, instance_id=web, root_volumes=nodes['web']['root_volumes'], phase='prepared')
    def checkpoint(phase):
        record['phase'] = phase
        temporary = Path(str(journal) + '.new')
        with temporary.open('x') as f:
            json.dump(record, f)
        os.replace(temporary, journal)
        print('D11_STORAGE_CYCLE=' + phase, flush=True)
    checkpoint('prepared')
    results = []
    def check(task, flag=None):
        args = [sys.executable, '-B', str(Path(a.candidate) / 'assessment_check.py'), task,
            '--command-state', a.command_state] + ([flag] if flag else [])
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
        print(result.stdout, flush=True)
        if result.returncode:
            raise ValueError('Actual storage acceptance failed at ' + task + str(flag))
        if not flag:
            value = json.loads(result.stdout.splitlines()[-1])
            if value['raw_earned'] != value['raw_maximum'] or value['submission'] != 'STORED' or not value['complete']:
                raise ValueError('After-restart checker is not complete')
            results.append(dict(task=task, result=value))
    started = None
    stop_requested = False
    try:
        ec2.stop_instances(InstanceIds=[web])
        stop_requested = True
        checkpoint('stop_requested')
        ec2.get_waiter('instance_stopped').wait(InstanceIds=[web], WaiterConfig=dict(Delay=5, MaxAttempts=60))
        checkpoint('stopped')
        for task in ('M3', 'P3'):
            check(task, '--observe-stopped')
        checkpoint('stopped_evidence_retained')
    finally:
        if stop_requested:
            # Restore the same instance even if evidence verification fails.
            ec2.get_waiter('instance_stopped').wait(InstanceIds=[web], WaiterConfig=dict(Delay=5, MaxAttempts=60))
            ec2.start_instances(InstanceIds=[web])
            started = datetime.now(timezone.utc)
            checkpoint('start_requested')
    ec2.get_waiter('instance_running').wait(InstanceIds=[web], WaiterConfig=dict(Delay=5, MaxAttempts=60))
    for _ in range(240):
        info = ssm.describe_instance_information(Filters=[dict(Key='InstanceIds', Values=[web])])['InstanceInformationList']
        if info and info[0]['PingStatus'] == 'Online' and info[0]['LastPingDateTime'] >= started:
            break
        time.sleep(2)
    else:
        raise ValueError('Same Web is running; fresh SSM heartbeat still pending')
    after = current_nodes(ec2, cfn, state, baseline)
    if after['web']['instance_id'] != web or after['web']['root_volumes'] != nodes['web']['root_volumes']:
        raise ValueError('Original Web or root disk changed')
    checkpoint('same_web_and_fresh_ssm_verified')
    for task in ('M3', 'P3', 'M1', 'M2'):
        check(task)
    public = dict(web_instance_id=web, root_volumes_retained=True, same_web_after_stop_start=True,
        stopped_observation_retained=True, fresh_ssm=True, results=results,
        other_four_instances_not_stopped=True, credentials_changed=False, class_ready=False)
    with out.open('x') as f:
        json.dump(public, f, indent=2)
    checkpoint('complete')
    print('D11_ACTUAL_STORAGE_CYCLE_PASSED', flush=True)


if __name__ == '__main__':
    main()
