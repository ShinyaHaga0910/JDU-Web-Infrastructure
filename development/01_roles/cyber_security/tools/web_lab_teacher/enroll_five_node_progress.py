"""Prepare encrypted SSM registration; human executes apply for new Lab token.

Only ciphertext/public code is sent through Run Command. The teacher admin key
stays in individual CloudShell; the Lab token stays there and on own bastion.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import web_progress


def encrypt(certificate, data):
    with tempfile.TemporaryDirectory(prefix='jdu-public-recipient-') as t:
        cert = Path(t) / 'recipient.crt'
        cert.write_bytes(certificate)
        return subprocess.run(['openssl', 'cms', '-encrypt', '-binary', '-aes-256-gcm',
            '-outform', 'DER', '-recip', str(cert), '-keyopt', 'rsa_padding_mode:oaep',
            '-keyopt', 'rsa_oaep_md:sha256', '-keyopt', 'rsa_mgf1_md:sha256'],
            input=data, capture_output=True, check=True).stdout


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'apply', 'verify'))
    for name in ('state', 'baseline-plan', 'plan', 'teacher-config', 'bootstrap-tools'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    os.umask(0o077)
    sys.path.insert(0, str(Path(a.bootstrap_tools)))
    from setup_internal_ssh import current_nodes, remote, save_new
    state = json.loads(Path(a.state).read_text())
    baseline = json.loads(Path(a.baseline_plan).read_text())
    teacher = web_progress.private_json(a.teacher_config)
    if (boto3.client('sts').get_caller_identity()['Account'] != state['account']
            or any(state[k] != baseline[k] for k in ('account', 'stack_id', 'deployment_id'))
            or teacher['release_id'] != 'web-2026-10-r1'):
        raise ValueError('Wrong account, deployment or release')
    ec2 = boto3.client('ec2', region_name='us-east-1')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    ssm = boto3.client('ssm', region_name='us-east-1')
    nodes = current_nodes(ec2, cfn, state, baseline)
    bastion = nodes['bastion']['instance_id']
    source = Path(__file__).with_name('progress_enrollment_guest.py').read_bytes()
    client = Path(web_progress.__file__).read_bytes()
    common = {k: state[k] for k in ('lab_id', 'deployment_id')}
    common.update(release_id=teacher['release_id'], instance_id=bastion)
    client_fields = {'client_source_b64': base64.b64encode(client).decode(),
                     'client_sha256': hashlib.sha256(client).hexdigest()}
    if a.command == 'prepare':
        if Path(a.plan).exists():
            raise ValueError('Existing enrollment plan retained')
        response = remote(ssm, bastion, source, dict(common, command='recipient'))
        certificate = response['certificate_pem'].encode()
        if (hashlib.sha256(certificate).hexdigest() != response['certificate_sha256']
                or not certificate.startswith(b'-----BEGIN CERTIFICATE-----')):
            raise ValueError('Recipient certificate differs')
        probe = hashlib.sha256(os.urandom(32)).hexdigest()  # Public transport fixture, not a credential.
        value = dict(common, schema_version=1, purpose='transport_probe', probe=probe)
        ciphertext = encrypt(certificate, json.dumps(value).encode())
        ack = remote(ssm, bastion, source, dict(common, command='probe',
            ciphertext_b64=base64.b64encode(ciphertext).decode()))
        if ack != {'transport_probe': probe, 'plaintext_credential_written': False}:
            raise ValueError('Encrypted transport probe failed')
        plan = dict(common, account=state['account'], stack_id=state['stack_id'], nodes=nodes,
            recipient=response, guest_sha256=hashlib.sha256(source).hexdigest(),
            client_sha256=client_fields['client_sha256'],
            prepared_at=datetime.now(timezone.utc).isoformat(),
            encrypted_transport_live_probe_passed=True, new_lab_token_issued=False)
        save_new(a.plan, plan)
        print('GRADING_ENROLLMENT_PREPARED; encrypted SSM transport probe PASS; no Lab token created')
        return
    plan = json.loads(Path(a.plan).read_text())
    if (any(plan[k] != common[k] for k in common) or plan['nodes'] != nodes
            or plan['account'] != state['account'] or plan['stack_id'] != state['stack_id']
            or plan['guest_sha256'] != hashlib.sha256(source).hexdigest()
            or plan['client_sha256'] != client_fields['client_sha256']):
        raise ValueError('Reviewed enrollment plan differs')
    receipt_path = Path(str(a.plan) + '.registered.public.json')
    if a.command == 'verify':
        ack = remote(ssm, bastion, source, dict(common, command='verify', **client_fields))
    else:
        if receipt_path.exists():
            raise ValueError('Registration already completed; use verify')
        status = remote(ssm, bastion, source, dict(common, command='status'))
        if status['credential_present'] and status['registration_present']:
            operation='complete' if status['transport_private_key_present'] else 'verify'
            ack = remote(ssm, bastion, source, dict(common, command=operation, **client_fields))
        else:
            output = Path(a.teacher_config).parent / 'private' / (state['lab_id'] + '.credentials.json')
            # New token creation/registration: this apply command is executed by the human.
            web_progress.issue(teacher, state['lab_id'], output)
            student = web_progress.private_json(output)
            value = dict(common, schema_version=1, purpose='progress_registration', credentials=student)
            ciphertext = encrypt(plan['recipient']['certificate_pem'].encode(), json.dumps(value).encode())
            ack = remote(ssm, bastion, source, dict(common, command='register', **client_fields,
                ciphertext_b64=base64.b64encode(ciphertext).decode()))
    if (any(ack.get(k) != common[k] for k in ('lab_id', 'release_id', 'deployment_id'))
            or ack.get('registered') is not True or ack.get('instance_count') != 5
            or ack.get('private_credential_exported') is not False
            or ack.get('transport_private_key_retired') is not True):
        raise ValueError('Registration acknowledgment differs')
    public = dict(ack, checked_at=datetime.now(timezone.utc).isoformat(),
                  scope='actual_five_node_registration_not_class_acceptance', class_ready=False)
    if a.command == 'apply':
        save_new(receipt_path, public)
    else:
        save_new(str(a.plan) + '.verified.public.json', public)
    print('FIVE_NODE_GRADING_REGISTRATION=' + json.dumps(public, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('GRADING_ENROLLMENT_STOPPED=' + type(exc).__name__, flush=True)
        raise SystemExit(2)
