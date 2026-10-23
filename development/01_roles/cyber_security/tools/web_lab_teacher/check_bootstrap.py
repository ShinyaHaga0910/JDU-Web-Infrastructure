"""CloudShell bootstrap check: fresh five-node observation, automatic submit, retained retry.

Matches the OS/Linux command behavior. Foundation checks do not award task points.
The command-state file contains reviewed paths and source hashes, no passwords.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

from submit_five_node_bootstrap import build_report


def validate_network_controls(observed, connects):
    controls = {}
    for node in observed['nodes'].values():
        addresses = node.get('probe_ipv4s', [])
        if len(addresses) != 2:
            node['network']['s3_denied'] = node['network']['direct_api_egress_denied'] = None
        else:
            for address, key in zip(addresses, ('s3_denied', 'direct_api_egress_denied')):
                if address not in controls: controls[address] = connects(address)
                if not controls[address]: node['network'][key] = None
        node['all_checks_passed'] = all(v is True for group in ('checks', 'network') for v in node[group].values())
    observed['denial_control_targets_live_from_cloudshell'] = controls
    observed['all_five_guest_checks_passed'] = all(n['all_checks_passed'] for n in observed['nodes'].values())


def print_result(report, submitted):
    if not report['checks']:
        raise ValueError('An empty result cannot pass')
    for c in report['checks']:
        print(c['status'] + ' ' + c['role'] + ' ' + c['id'])
    passed = sum(c['status'] == 'PASS' for c in report['checks'])
    print('RESULT ' + str(passed) + ' / ' + str(len(report['checks'])) + ' foundation checks cleared')
    print('SUBMISSION ' + submitted)
    print('Foundation checks do not award mission points or declare CLASS_READY.')
    return 0 if passed == len(report['checks']) else 1


def main(argv=None):
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind', choices=('bootstrap',))
    p.add_argument('--command-state', default=str(Path.home() / '.jdu-web-student/command-state.json'))
    p.add_argument('--no-submit', action='store_true')
    p.add_argument('--submit', action='store_true', help='Compatibility option; submission is automatic')
    p.add_argument('--retry', help='Retry the exact retained report UUID; never recollect or change its body')
    a = p.parse_args(argv); os.umask(0o077)
    config = json.loads(Path(a.command_state).read_text())
    sys.path.insert(0, config['bootstrap_tools'])
    from setup_internal_ssh import current_nodes, remote, save_new
    state = json.loads(Path(config['state']).read_text())
    baseline = json.loads(Path(config['baseline_plan']).read_text())
    if (boto3.client('sts').get_caller_identity()['Account'] != state['account']
            or any(state[k] != baseline[k] for k in ('account', 'stack_id', 'deployment_id'))):
        raise ValueError('Wrong account or deployment')
    nodes = current_nodes(boto3.client('ec2', region_name='us-east-1'),
        boto3.client('cloudformation', region_name='us-east-1'), state, baseline)
    ssm = boto3.client('ssm', region_name='us-east-1')
    def source(key):
        data = Path(config[key]).read_bytes()
        if hashlib.sha256(data).hexdigest() != config[key + '_sha256']:
            raise ValueError('Reviewed command source changed')
        return data
    guest = source('guest_source')
    submission = source('submission_source')
    pending = Path(config['pending_directory'])
    pending.mkdir(mode=0o700, parents=True, exist_ok=True)
    if a.retry:
        parsed = uuid.UUID(a.retry)
        if str(parsed) != a.retry or parsed.version != 4 or a.no_submit:
            raise ValueError('Retry needs an exact saved request UUID')
        report = json.loads((pending / (a.retry + '.report.json')).read_text())
        if any(report[k] != state[k] for k in ('lab_id', 'deployment_id')):
            raise ValueError('Saved report belongs to another deployment')
    else:
        enrollment = json.loads(Path(config['ssh_enrollment']).read_text())
        request = dict(lab_id=state['lab_id'], deployment_id=state['deployment_id'], role='bastion',
            instance_id=nodes['bastion']['instance_id'], peers={r: n['instance_id'] for r, n in nodes.items() if r != 'bastion'},
            expected_public_key=enrollment['public_key'], network_source_sha256=config['network_source_sha256'],
            guest_source_b64=base64.b64encode(guest).decode(), allow_partial=True)
        observed = remote(ssm, nodes['bastion']['instance_id'], guest, request)
        # A dead comparison host cannot prove a network denial. Recheck each
        # control from CloudShell and retain UNKNOWN if the control is unavailable.
        import socket
        def connects(address):
            try:
                with socket.create_connection((address, 443), timeout=5): pass
                return True
            except OSError:
                return False
        validate_network_controls(observed, connects)
        request_id = str(uuid.uuid4())
        report = build_report(observed, state, nodes, request_id)
        save_new(pending / (request_id + '.observation.json'), observed)
        save_new(pending / (request_id + '.report.json'), report)
    submitted = 'SKIPPED (--no-submit)'
    if not a.no_submit:
        try:
            ack = remote(ssm, nodes['bastion']['instance_id'], submission, {'report': report})
            receipt_path = pending / (report['request_id'] + '.receipt.json')
            if receipt_path.exists():
                if json.loads(receipt_path.read_text()) != ack: raise ValueError('Saved receipt differs')
            else:
                save_new(receipt_path, ack)
            submitted = 'STORED request_id=' + report['request_id']
        except Exception:
            submitted = 'PENDING; retry with jdu-web-check bootstrap --retry ' + report['request_id']
    # Like OS/Linux, transport failure never changes the local check result.
    return print_result(report, submitted)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('WEB_BOOTSTRAP_CHECK_STOPPED=' + type(exc).__name__ + '; no readiness granted')
        raise SystemExit(2)
