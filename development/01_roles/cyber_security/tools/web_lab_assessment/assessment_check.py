"""CloudShell D11 entry point. Does not create servers, keys, users or credentials."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
LEGACY = ROOT / 'legacy' if (ROOT / 'legacy').is_dir() else ROOT.parent / 'web_lab_teacher'
BOOTSTRAP = ROOT / 'legacy' if (ROOT / 'legacy').is_dir() else ROOT.parent / 'web_lab_bootstrap'
sys.path[:0] = [str(LEGACY), str(BOOTSTRAP)]

from registry import TASKS, canonical_checks, build_report, validate_report, score, CONTRACT_ID, CONTRACT_SHA256
from transport import ssm_command, payload, LOADER


def save_once(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if path.exists() or path.is_symlink():
        if path.is_symlink() or path.stat().st_mode & 0o077 or path.read_bytes() != data:
            raise ValueError('Existing private evidence differs; retained')
    else:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            stream.write(data)


def invoke(ssm, instance, request):
    command_id = ssm.send_command(InstanceIds=[instance], DocumentName='AWS-RunShellScript',
        Parameters={'commands': [ssm_command(request)], 'executionTimeout': ['600']}, TimeoutSeconds=30)['Command']['CommandId']
    for _ in range(240):
        try:
            result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance)
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(1); continue
        if result['Status'] == 'Success':
            return json.loads(result['StandardOutputContent'])
        if result['Status'] in ('Failed', 'TimedOut', 'Cancelled'):
            raise ValueError('Assessment observer unavailable; no grade finalized')
        time.sleep(1)
    raise ValueError('Assessment still pending; inspect the existing command before retrying')


def http_report(task_id, identity, pending, nodes, ssm, enrollment):
    from setup_internal_ssh import remote
    from http_task import contract, http_probe
    from http_guest_v2 import LEGACY_SHA256, CONTRACT_SHA256 as HTTP_SHA256
    original = (LEGACY / 'http_task_guest.py').read_bytes()
    source = (LEGACY / 'http_task.py').read_bytes()
    if hashlib.sha256(original).hexdigest() != LEGACY_SHA256 or hashlib.sha256(source).hexdigest() != HTTP_SHA256:
        raise ValueError('Original HTTP checks and expectations must be retained')
    guest = ('LEGACY_SOURCE_B64=' + repr(base64.b64encode(original).decode()) + '\n').encode() + (ROOT / 'http_guest_v2.py').read_bytes()
    nonce = uuid.uuid4()
    request = dict(lab_id=identity['lab_id'], deployment_id=identity['deployment_id'], role='bastion',
        instance_id=nodes['bastion']['instance_id'], web_id=nodes['web']['instance_id'],
        web_ip=nodes['web']['private_ip'], repo_ip=nodes['repo']['private_ip'], bastion_ip=nodes['bastion']['private_ip'],
        expected_public_key=enrollment['public_key'], mission_id=task_id, nonce=nonce.hex, operation='collect',
        contract_source_b64=base64.b64encode(source).decode(), guest_source_b64=base64.b64encode(guest).decode())
    observed = remote(ssm, nodes['bastion']['instance_id'], guest, request)
    spec = contract(task_id)
    import boto3
    web = boto3.client('ec2', region_name='us-east-1').describe_instances(InstanceIds=[nodes['web']['instance_id']])['Reservations'][0]['Instances'][0]
    address = web.get('PublicIpAddress')
    observed['checks']['WEB02_PUBLIC_HTTP'] = http_probe(address, spec['path'], spec['body'], nonce.hex) if address else None
    report = build_report(task_id, identity, observed['checks'], str(nonce), checked_at=observed['checked_at'])
    save_once(pending / (report['request_id'] + '.observation.json'), observed)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('task', choices=tuple(TASKS) + ('bootstrap',))
    p.add_argument('--command-state', default=str(Path.home() / '.jdu-web-student/command-state.json'))
    p.add_argument('--no-submit', action='store_true')
    p.add_argument('--submit', action='store_true')
    p.add_argument('--retry')
    p.add_argument('--prepare-stop', action='store_true')
    p.add_argument('--observe-stopped', action='store_true')
    p.add_argument('--functional', action='store_true')
    a = p.parse_args(argv); os.umask(0o077)
    import boto3
    if a.task == 'bootstrap':
        import check_bootstrap
        return check_bootstrap.main(['bootstrap', '--command-state', a.command_state] + (['--no-submit'] if a.no_submit else []))
    if (a.prepare_stop or a.observe_stopped) and a.task not in ('P3', 'M3'):
        raise ValueError('Stop evidence is specific to the storage task')
    if a.prepare_stop and a.observe_stopped or a.functional and a.task not in ('P5', 'M5', 'P6', 'M6'):
        raise ValueError('Conflicting or unsupported mode')
    config_path = Path(a.command_state)
    if config_path.is_symlink() or config_path.stat().st_mode & 0o077:
        raise ValueError('Use your existing private personal CloudShell configuration')
    c = json.loads(config_path.read_text())
    state = json.loads(Path(c['state']).read_text()); baseline = json.loads(Path(c['baseline_plan']).read_text())
    state.setdefault('release_id', 'web-2026-10-r1')
    if (boto3.client('sts').get_caller_identity()['Account'] != state['account']
            or any(state[k] != baseline[k] for k in ('account', 'deployment_id', 'stack_id'))):
        raise ValueError('Wrong CloudShell account or retained state')
    ec2, cfn, ssm = [boto3.client(n, region_name='us-east-1') for n in ('ec2', 'cloudformation', 'ssm')]
    pending = Path(c['pending_directory']); pending.mkdir(mode=0o700, parents=True, exist_ok=True)
    evidence_root = pending / CONTRACT_ID; evidence_root.mkdir(mode=0o700, exist_ok=True)
    pointer = evidence_root / (a.task + '.active.json')
    evidence_id = str(uuid.uuid4())
    if pointer.exists():
        current = json.loads(pointer.read_text())
        evidence_id = str(uuid.UUID(current['evidence_id']))
    before_path = evidence_root / (a.task + '.' + evidence_id + '.before.json')
    stopped_path = evidence_root / (a.task + '.' + evidence_id + '.stopped.json')
    if a.observe_stopped:
        before = json.loads(before_path.read_text())
        node = ec2.describe_instances(InstanceIds=[before['instance_id']])['Reservations'][0]['Instances'][0]
        tags = {t['Key']: t['Value'] for t in node.get('Tags', [])}
        volumes = [v['Ebs']['VolumeId'] for v in node['BlockDeviceMappings']]
        if (node['State']['Name'] != 'stopped' or before['root_volume'] not in volumes
                or tags.get('DeploymentId') != state['deployment_id'] or tags.get('LabId') != state['lab_id']
                or any(before[k] != state[k] for k in ('lab_id', 'deployment_id'))
                or before['instance_id'] != baseline['nodes']['web']['instance_id']
                or before['contract_sha256'] != CONTRACT_SHA256):
            raise ValueError('Observe the same stopped Web and original root volume')
        save_once(stopped_path, {k: before[k] for k in ('lab_id', 'deployment_id', 'instance_id', 'task_id', 'root_volume', 'evidence_id')} | dict(state='stopped'))
        print('STORAGE_STOPPED_OBSERVED; start the same Web explicitly, then rerun this task')
        return 0
    from setup_internal_ssh import current_nodes
    nodes = current_nodes(ec2, cfn, state, baseline)
    identity = {k: state[k] for k in ('lab_id', 'release_id', 'deployment_id')}
    identity['instances'] = {r: n['instance_id'] for r, n in nodes.items()}
    enrollment = json.loads(Path(c['ssh_enrollment']).read_text())
    if a.retry:
        if a.no_submit:
            raise ValueError('A retry submits the exact retained report')
        report = json.loads((pending / (str(uuid.UUID(a.retry)) + '.report.json')).read_text())
        validate_report(report, identity['instances'])
        if report['mission_id'] != a.task or any(report[k] != identity[k] for k in ('lab_id', 'deployment_id', 'release_id')):
            raise ValueError('Retained report belongs to another task or deployment')
    elif a.task in ('P1', 'M1'):
        report = http_report(a.task, identity, pending, nodes, ssm, enrollment)
    else:
        template = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
        if isinstance(template, str):
            template = json.loads(template)
        from aws_readiness import verify
        network = verify(ec2, cfn, ssm, state, template, nodes)
        request = dict(identity, role='bastion', instance_id=nodes['bastion']['instance_id'],
            operation='collect', task_id=a.task, run_id=str(uuid.uuid4()), network_baseline=network,
            root_volumes={r: n['root_volumes'] for r, n in nodes.items()},
            expected_public_key=enrollment['public_key'], web_instance_id=nodes['web']['instance_id'])
        for key, path in (('before', before_path), ('stopped', stopped_path)):
            if path.exists():
                request[key] = json.loads(path.read_text())
        observed = (interactive(ssm, nodes['bastion']['instance_id'], request, pending, no_submit=a.no_submit)
                    if a.functional else invoke(ssm, nodes['bastion']['instance_id'], request))
        report = observed['report']
        if a.prepare_stop:
            before = observed['storage_evidence']
            required = ('marker_sha256', 'root_volume', 'boot_id')
            if any(not before.get(k) for k in required) or score(report)['raw_earned'] < 2:
                raise ValueError('Prepare the marker and permissions before retaining stop evidence')
            value = {k: identity[k] for k in ('lab_id', 'deployment_id')}
            evidence_id = str(uuid.uuid4())
            value.update({k: before[k] for k in required}, task_id=a.task, instance_id=nodes['web']['instance_id'], contract_sha256=CONTRACT_SHA256, evidence_id=evidence_id)
            save_once(evidence_root / (a.task + '.' + evidence_id + '.before.json'), value)
            staged = evidence_root / (a.task + '.' + evidence_id + '.pointer-new')
            save_once(staged, dict(evidence_id=evidence_id))
            if pointer.is_symlink():
                raise ValueError('Linked storage evidence pointer refused')
            os.replace(staged, pointer)
            print('STORAGE_BEFORE_RETAINED; stop the Web explicitly, then use --observe-stopped')
            return 0
    validate_report(report, identity['instances'])
    if a.task in ('P6', 'M6') and not a.retry:
        from network_checks import http
        node = ec2.describe_instances(InstanceIds=[nodes['web']['instance_id']])['Reservations'][0]['Instances'][0]
        address = node.get('PublicIpAddress')
        control = http(address, '/', host='web.lab.test') if address else None
        controls_ok = control is not None and control[0] == 200
        groups = {
            'WEB07_PUBLIC_ADMIN_DENIED': ('/admin', '/admin/', '/admin/catalog/item/add/', '//admin/', '/%61dmin/'),
            'WEB07_SECRET_HTTP_DENIED': ('/.env', '/app.env', '/setup.env', '/etc/jdu-catalog/app.env', '/static/app.env')}
        for cid, paths in groups.items():
            values = [http(address, path, host='admin.lab.test:8080' if cid == 'WEB07_PUBLIC_ADMIN_DENIED' else 'web.lab.test',
                           headers={'X-JDU-Entry': 'admin'}) for path in paths] if controls_ok else []
            result = None if not values or any(v is None for v in values) else all(v[0] in (403, 404) for v in values)
            item = next(c for c in report['checks'] if c['id'] == cid)
            if result is False or item['status'] == 'FAIL':
                item['status'] = 'FAIL'
            elif result is None or item['status'] == 'UNKNOWN':
                item['status'] = 'UNKNOWN'
    save_once(pending / (report['request_id'] + '.report.json'), report)
    submitted = 'SKIPPED'
    if not a.no_submit:
        try:
            request = dict(identity, role='bastion', instance_id=nodes['bastion']['instance_id'],
                           operation='submit', task_id=a.task, run_id=report['run_id'], report=report)
            receipt = invoke(ssm, nodes['bastion']['instance_id'], request)
            save_once(pending / (report['request_id'] + '.receipt.json'), receipt)
            submitted = 'STORED'
        except Exception:
            submitted = 'PENDING --retry ' + report['request_id']
    result = score(report)
    print(json.dumps(dict(task=a.task, submission=submitted, **result), separators=(',', ':')))
    return 0 if result['complete'] and not submitted.startswith('PENDING') else 1


def interactive(ssm, instance, request, pending, no_submit=False):
    """Stage only public code/request, then use a real SSM TTY for existing-password entry."""
    if not sys.stdin.isatty():
        raise ValueError('Functional verification requires your interactive CloudShell terminal')
    job = '/var/lib/jdu-web/assessment-interactive-' + request['run_id']
    import zlib
    content = zlib.compress(json.dumps(payload(request), separators=(',', ':')).encode(), 9)
    code = ('import base64,os,zlib\nfrom pathlib import Path\np=Path(' + repr(job + '.json') + ')\n'
            'data=zlib.decompress(base64.b64decode(' + repr(base64.b64encode(content).decode()) + '))\n'
            'fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n'
            'with os.fdopen(fd,"wb") as f:f.write(data)\nprint("PUBLIC_INTERACTIVE_JOB_STAGED")\n')
    # A public source file is staged once; no password is in command history.
    command_id = ssm.send_command(InstanceIds=[instance], DocumentName='AWS-RunShellScript',
        Parameters={'commands': ['python3 -c ' + shlex.quote(code)]})['Command']['CommandId']
    for _ in range(30):
        time.sleep(1)
        try:
            result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if result['Status'] == 'Success':
            break
        if result['Status'] in ('Failed', 'TimedOut', 'Cancelled'):
            raise ValueError('Interactive public source staging failed')
    else:
        raise ValueError('Interactive staging is still pending')
    # Same loader initializes modules, but the TTY stays connected for getpass.
    loader = LOADER[:LOADER.index('try:\n print(json.dumps(m.run')]
    entry = ('import io\nfrom pathlib import Path\n_p=Path(' + repr(job + '.json') + ')\n'
             'sys.stdin=io.StringIO(_p.read_text())\n' + loader
             + '\nfrom getpass import getpass\n'
             'print("Functional check creates/updates only its own fictional record; existing items stay intact.")\n'
             'password=getpass("Existing application password (hidden): ")\n'
             'result=m.collect(p["request"],password=password)\ndel password\n'
             'out=Path(' + repr(job + '.result.json') + ')\n'
             'fd=__import__("os").open(out,__import__("os").O_WRONLY|__import__("os").O_CREAT|__import__("os").O_EXCL,0o600)\n'
             'with __import__("os").fdopen(fd,"w") as f:json.dump(result,f)\n'
             + 'print("D11_FUNCTIONAL_CHECK_RETAINED")\n')
    entry = 'import sys\n' + entry
    subprocess.run(['aws', 'ssm', 'start-session', '--region', 'us-east-1', '--target', instance,
                    '--document-name', 'AWS-StartInteractiveCommand', '--parameters',
                    json.dumps({'command': ['sudo python3 -c ' + shlex.quote(entry)]})], check=True)
    result_request = dict(request, operation='interactive-result')
    return invoke(ssm, instance, result_request)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('D11_CHECK_STOPPED=' + type(exc).__name__ + '; retained state and credentials unchanged')
        raise SystemExit(2)
