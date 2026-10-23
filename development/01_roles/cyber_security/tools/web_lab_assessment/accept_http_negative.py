"""Teacher-only actual HTTP 8 -> 4 -> 8 acceptance, restoring its own exact fixture file."""
import argparse
import base64
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', required=True)
    p.add_argument('--command-state', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    import boto3
    if boto3.client('sts').get_caller_identity()['Account'] != '965244652544':
        raise ValueError('Verification student account only')
    c = json.loads(Path(a.command_state).read_text())
    state, baseline = [json.loads(Path(c[k]).read_text()) for k in ('state', 'baseline_plan')]
    if state['deployment_id'] != baseline['deployment_id'] or state['deployment_id'] != '3ab82943-031d-4806-b4c0-c0b0e4554006':
        raise ValueError('Selected verification deployment only')
    out = Path(a.output)
    if out.exists():
        raise ValueError('Existing acceptance retained')
    sys.path[:0] = [str(Path(a.candidate)), c['bootstrap_tools']]
    from setup_internal_ssh import current_nodes
    from registry import TASKS
    nodes = current_nodes(boto3.client('ec2', region_name='us-east-1'), boto3.client('cloudformation', region_name='us-east-1'), state, baseline)
    ssm = boto3.client('ssm', region_name='us-east-1')
    expected = TASKS['M1']['expected']
    wrong = b'D11 acceptance: deliberately wrong HTTP body.\n'

    def change(operation):
        code = ('import json,os\nfrom pathlib import Path\nb=json.loads(Path("/etc/jdu-web/bootstrap.json").read_text())\n'
            + 'assert b["role"]=="web" and b["deployment_id"]==' + repr(state['deployment_id'])
            + ' and b["instance_id"]==' + repr(nodes['web']['instance_id']) + '\n'
            + 'p=Path(' + repr(expected['file']) + ');assert not p.is_symlink() and p.stat().st_uid==0\n'
            + 'original=' + repr(expected['body'].encode()) + ';wrong=' + repr(wrong) + '\n'
            + 'backup=Path("/var/lib/jdu-web/d11-foundation-acceptance-r1/http/mission.correct.before-negative")\n')
        if operation == 'wrong':
            code += ('assert p.read_bytes()==original and not backup.exists()\n'
                'with backup.open("xb") as f:f.write(original)\nbackup.chmod(0o600)\np.write_bytes(wrong)\n')
        else:
            code += 'assert p.read_bytes()==wrong and backup.read_bytes()==original\np.write_bytes(original)\n'
        code += 'p.chmod(0o644)\nprint("D11_HTTP_FIXTURE_' + operation.upper() + '")\n'
        command = 'python3 -c ' + shlex.quote('import base64;exec(base64.b64decode(' + repr(base64.b64encode(code.encode()).decode()) + '))')
        cid = ssm.send_command(InstanceIds=[nodes['web']['instance_id']], DocumentName='AWS-RunShellScript',
            Parameters={'commands': [command], 'executionTimeout': ['60']})['Command']['CommandId']
        for _ in range(90):
            time.sleep(1)
            try:
                result = ssm.get_command_invocation(CommandId=cid, InstanceId=nodes['web']['instance_id'])
            except ssm.exceptions.InvocationDoesNotExist:
                continue
            if result['Status'] == 'Success':
                return cid
            if result['Status'] in ('Failed', 'TimedOut', 'Cancelled'):
                raise ValueError('Own HTTP fixture change failed; inspect retained SSM job ' + cid)
        raise ValueError('Own HTTP fixture still pending; inspect ' + cid)

    def check(expected_points):
        pending = Path(c['pending_directory'])
        before = set(pending.glob('*.report.json'))
        r = subprocess.run([sys.executable, '-B', str(Path(a.candidate) / 'assessment_check.py'), 'M1',
            '--command-state', a.command_state], capture_output=True, text=True, timeout=300)
        print(r.stdout, flush=True)
        result = json.loads(r.stdout.splitlines()[-1])
        reports = [json.loads(f.read_text()) for f in set(pending.glob('*.report.json')) - before]
        reports = [v for v in reports if v.get('schema_version') == 2]
        if (len(reports) != 1 or result['submission'] != 'STORED' or result['raw_earned'] != expected_points
                or result['raw_maximum'] != 8 or result['evaluable'] is not True or r.returncode != (0 if expected_points == 8 else 1)):
            raise ValueError('Actual wrong/restored HTTP result differs')
        return dict(points=expected_points, request_id=reports[0]['request_id'], result=result)

    wrong_job = change('wrong')
    try:
        failed = check(4)
    finally:
        restored_job = change('restore')
    restored = check(8)
    with out.open('x') as stream:
        json.dump(dict(actual_http_negative_verified=True, wrong=failed, restored=restored,
            wrong_job=wrong_job, restored_job=restored_job, original_body_restored=True, credentials_changed=False), stream, indent=2)
    print('D11_ACTUAL_HTTP_8_TO_4_TO_8_PASSED', flush=True)


if __name__ == '__main__':
    main()
