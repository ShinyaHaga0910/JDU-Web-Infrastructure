"""Teacher-only scheduler for the selected existing D11 verification deployment."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import zlib

ROOT = Path(__file__).resolve().parent
EXPECTED = '3ab82943-031d-4806-b4c0-c0b0e4554006'


def save(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect', 'http', 'dns', 'resolver', 'storage', 'poll'))
    parser.add_argument('--role', choices=('bastion', 'web', 'dns'), required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--command-state', required=True)
    a = parser.parse_args()
    import boto3
    os.umask(0o077)
    if boto3.client('sts').get_caller_identity()['Account'] != '965244652544':
        raise ValueError('Only the selected separate student verification account')
    c = json.loads(Path(a.command_state).read_text())
    state, baseline = [json.loads(Path(c[k]).read_text()) for k in ('state', 'baseline_plan')]
    if state['deployment_id'] != baseline['deployment_id'] or state['deployment_id'] != EXPECTED:
        raise ValueError('Retain the selected verification deployment')
    sys.path.insert(0, c['bootstrap_tools'])
    from setup_internal_ssh import current_nodes
    nodes = current_nodes(boto3.client('ec2', region_name='us-east-1'), boto3.client('cloudformation', region_name='us-east-1'), state, baseline)
    ssm = boto3.client('ssm', region_name='us-east-1')
    job = Path(a.job)
    if a.operation == 'poll':
        info = json.loads(job.read_text())
        if info['deployment_id'] != EXPECTED or info['instance_id'] != nodes[a.role]['instance_id']:
            raise ValueError('Wrong retained fixture job')
        result = ssm.get_command_invocation(CommandId=info['command_id'], InstanceId=info['instance_id'])
        print('D11_FIXTURE_STATUS=' + result['Status'])
        if result['Status'] in ('Success', 'Failed', 'TimedOut', 'Cancelled'):
            text = result['StandardOutputContent'].strip()
            if result['Status'] == 'Success':
                public = json.loads(text)
                out = Path(str(job) + '.public.json')
                if not out.exists():
                    save(out, public)
                print(json.dumps(public, separators=(',', ':')))
            else:
                print(text[-500:])
                raise SystemExit(2)
        return
    if job.exists() or job.is_symlink():
        raise ValueError('Existing job retained; poll it')
    # Use only fixed public expectations from the independently verified D11 candidate.
    sys.path.insert(0, str(ROOT.parent / 'candidate'))
    from registry import TASKS
    request = {k: state[k] for k in ('lab_id', 'deployment_id')}
    request.update(role=a.role, instance_id=nodes[a.role]['instance_id'], operation=a.operation)
    if a.operation == 'http':
        request['http_files'] = {TASKS[t]['expected']['file'].rsplit('/', 1)[1]: TASKS[t]['expected']['body'] for t in ('P1', 'M1')}
    if a.operation == 'dns':
        request['records'] = TASKS['M2']['expected']['records'] | TASKS['P2']['expected']['records']
    if a.operation == 'storage':
        request['markers'] = {t: TASKS[t]['expected'] for t in ('P3', 'M3')}
    source = (ROOT / 'foundation_fixture_guest.py').read_bytes()
    wrapped = ('import io,json,sys\nsys.stdin=io.StringIO(' + repr(json.dumps(request)) + ')\n'
        + 'exec(compile(' + repr(source.decode()) + ',"<teacher-d11-foundation>","exec"))\n')
    packed = base64.b64encode(zlib.compress(wrapped.encode(), 9)).decode()
    command = 'python3 -c ' + shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode(' + repr(packed) + ')))')
    response = ssm.send_command(InstanceIds=[nodes[a.role]['instance_id']], DocumentName='AWS-RunShellScript',
        Parameters={'commands': [command], 'executionTimeout': ['900']}, TimeoutSeconds=30)
    save(job, dict(deployment_id=EXPECTED, role=a.role, instance_id=nodes[a.role]['instance_id'], operation=a.operation,
        source_sha256=hashlib.sha256(source).hexdigest(), command_id=response['Command']['CommandId']))
    print('D11_FOUNDATION_FIXTURE_REQUESTED=' + a.operation + ':' + a.role)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('D11_FIXTURE_CONTROLLER_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
