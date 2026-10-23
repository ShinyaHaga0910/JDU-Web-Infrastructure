"""CloudShell jdu-web-check P1|M1: observe, retain, and submit without secrets."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

from http_task import TASKS, build_report, contract, http_probe


def result(report, submitted):
    for c in report['checks']:
        print(c['status'] + ' ' + c['id'])
    passed = sum(c['status'] == 'PASS' for c in report['checks'])
    print(report['mission_id'] + ' RESULT ' + str(passed) + ' / ' + str(len(report['checks'])))
    print('SUBMISSION ' + submitted)
    print('WEB-02 task progress; no points or course completion awarded.')
    return 0 if passed == len(report['checks']) else 1


def main(argv=None):
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mission_id', choices=tuple(TASKS))
    p.add_argument('--command-state', default=str(Path.home() / '.jdu-web-student/command-state.json'))
    p.add_argument('--no-submit', action='store_true')
    p.add_argument('--submit', action='store_true')
    p.add_argument('--retry')
    a = p.parse_args(argv); os.umask(0o077)
    config = json.loads(Path(a.command_state).read_text())
    sys.path.insert(0, config['bootstrap_tools'])
    from setup_internal_ssh import current_nodes, remote, save_new
    state = json.loads(Path(config['state']).read_text())
    baseline = json.loads(Path(config['baseline_plan']).read_text())
    if (boto3.client('sts').get_caller_identity()['Account'] != state['account']
            or any(state[k] != baseline[k] for k in ('account', 'stack_id', 'deployment_id'))):
        raise ValueError('Wrong account or deployment')
    ec2 = boto3.client('ec2', region_name='us-east-1')
    nodes = current_nodes(ec2, boto3.client('cloudformation', region_name='us-east-1'), state, baseline)
    state.setdefault('release_id', 'web-2026-10-r1')
    here = Path(__file__).resolve().parent
    # All three files are verified by the signed bundle installer before launch.
    guest = (here / 'http_task_guest.py').read_bytes()
    source = (here / 'http_task.py').read_bytes()
    submission = (here / 'bootstrap_submission_guest.py').read_bytes()
    ssm = boto3.client('ssm', region_name='us-east-1')
    pending = Path(config['pending_directory']); pending.mkdir(mode=0o700, parents=True, exist_ok=True)
    if a.retry:
        parsed = uuid.UUID(a.retry)
        if str(parsed) != a.retry or parsed.version != 4 or a.no_submit:
            raise ValueError('Retry requires an original retained UUID')
        report = json.loads((pending / (a.retry + '.report.json')).read_text())
        if (report['mission_id'] != a.mission_id or report['kind'] != 'assessment'
                or any(report[k] != state[k] for k in ('lab_id', 'release_id', 'deployment_id'))):
            raise ValueError('Retained report belongs to another task or deployment')
    else:
        enrollment = json.loads(Path(config['ssh_enrollment']).read_text())
        nonce = uuid.uuid4().hex
        request = dict(lab_id=state['lab_id'], deployment_id=state['deployment_id'], role='bastion',
            instance_id=nodes['bastion']['instance_id'], web_id=nodes['web']['instance_id'],
            web_ip=nodes['web']['private_ip'], repo_ip=nodes['repo']['private_ip'],
            bastion_ip=nodes['bastion']['private_ip'], expected_public_key=enrollment['public_key'],
            mission_id=a.mission_id, nonce=nonce, operation='collect',
            contract_source_b64=base64.b64encode(source).decode(), guest_source_b64=base64.b64encode(guest).decode())
        observed = remote(ssm, nodes['bastion']['instance_id'], guest, request)
        web = ec2.describe_instances(InstanceIds=[nodes['web']['instance_id']])['Reservations'][0]['Instances'][0]
        address = web.get('PublicIpAddress')
        spec = contract(a.mission_id)
        observed['checks']['WEB02_PUBLIC_HTTP'] = http_probe(address, spec['path'], spec['body'], nonce) if address else None
        report = build_report(observed, state, nodes, str(uuid.uuid4()))
        save_new(pending / (report['request_id'] + '.observation.json'), observed)
        save_new(pending / (report['request_id'] + '.report.json'), report)
    submitted = 'SKIPPED (--no-submit)'
    if not a.no_submit:
        try:
            ack = remote(ssm, nodes['bastion']['instance_id'], submission, {'report': report})
            path = pending / (report['request_id'] + '.receipt.json')
            if path.exists():
                if json.loads(path.read_text()) != ack: raise ValueError('Receipt changed')
            else:
                save_new(path, ack)
            submitted = 'STORED request_id=' + report['request_id']
        except Exception:
            submitted = 'PENDING; retry with jdu-web-check ' + a.mission_id + ' --retry ' + report['request_id']
    return result(report, submitted)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('WEB_HTTP_CHECK_STOPPED=' + type(exc).__name__ + '; no readiness granted')
        raise SystemExit(2)
