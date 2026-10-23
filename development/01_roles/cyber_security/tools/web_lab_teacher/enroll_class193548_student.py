"""Human-run internal SSH and existing-credential registration for Class193548.

Review creates no authentication key or registration. Apply never issues or
rotates a Lab token, and only touches this student's five original nodes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ACCOUNT = '965244652544'
LAB = 'class193548-test1'
DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'
MANIFEST = 'a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2'
NODES = {
    'bastion': ('i-0488d26e69614e096', 'vol-0dd3097fd722b6bb5'),
    'web': ('i-0c43b73c9a75c41eb', 'vol-08dce34a5376e7d58'),
    'dns': ('i-0f4cfc066e59488a6', 'vol-031fe29759bd1d27d'),
    'db': ('i-0ccc3e9206d30867b', 'vol-05586863b8491a998'),
    'repo': ('i-08f8a40fdaa5bb240', 'vol-07c3cc6ffdd36afb9'),
}


def require_nodes(state, nodes):
    if (state['account'] != ACCOUNT or state['lab_id'] != LAB or state['deployment_id'] != DEPLOYMENT
            or state['manifest_sha256'] != MANIFEST or set(nodes) != set(NODES)
            or any((n['instance_id'], n['root_volumes']) != (NODES[r][0], [NODES[r][1]]) for r, n in nodes.items())):
        raise ValueError('Only the reviewed student five and original roots are allowed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('review', 'apply'))
    args = parser.parse_args()
    if args.operation == 'apply' and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError('Human CloudShell TTY execution required')
    sys.dont_write_bytecode = True; os.umask(0o077)
    home = Path.home(); base = home / 'jdu-web-class193548'
    kit = base / 'cross-account-delivery-v1'; sys.path.insert(0, str(kit))
    pins = {
        'class_student_delivery.py': '1bbaf46daa1eed027e17e422e64ff0af5e8f24791d36df2f2379a57ff652a184',
        'web_progress.py': 'a966bbe49eefdb4fc6f9ca1dc39d930532992490923fde155caf3ed5a5aed6a4',
        'release_validation.py': 'e9aebc2f1ed3d54df70e862e5a9aabe8e08970004106c8a89a6260da9e34096c',
    }
    if any(hashlib.sha256((kit / name).read_bytes()).hexdigest() != pin for name, pin in pins.items()):
        raise ValueError('Accepted delivery helper changed')
    import class_student_delivery as delivery
    import boto3
    session = boto3.Session(region_name='us-east-1'); delivery.identity(session, ACCOUNT)
    tools = base / 'student-software-v7/student-tools'
    verified = delivery.verified_tools(tools)
    if verified['manifest_sha256'] != MANIFEST:
        raise ValueError('Accepted signed v7 required')
    import student_controller as controller
    from setup_internal_ssh import current_nodes
    state_path = base / 'student-v7.private.json'; state = controller.private(state_path)
    nodes = current_nodes(session.client('ec2'), session.client('cloudformation'), state,
        controller.private(str(state_path) + '.baseline.json'))
    require_nodes(state, nodes)
    credential = base / 'student-delivery-renewal-20261022/received/own-student.credentials.json'
    controller.student_credential(verified, state, credential)
    ssh_plan = controller.private(str(state_path) + '.ssh.json')
    registration = controller.private(str(state_path) + '.registration.json')
    if (ssh_plan['deployment_id'] != DEPLOYMENT or set(ssh_plan['peers']) != set(NODES) - {'bastion'}
            or ssh_plan['bastion'] != nodes['bastion'] or registration['deployment_id'] != DEPLOYMENT
            or registration['nodes'] != nodes):
        raise ValueError('Prepared SSH or grading plan differs')
    output = base / 'student-v7-enrollment-20261022.public.json'
    if output.exists():
        raise ValueError('Completed enrollment retained; use signed verify commands')
    print('CLASS193548_ENROLLMENT_REVIEW_PASSED; own bastion key and own existing Lab token only', flush=True)
    if args.operation == 'review':
        return
    def run(operation, *extra):
        result = subprocess.run(['bash', str(tools / 'jdu-web-lab'), operation, '--state', str(state_path),
            *map(str, extra)], capture_output=True, text=True, timeout=300)
        print(result.stdout, end='', flush=True)
        if result.returncode:
            raise ValueError('Signed operation stopped; inspect retained partial state')
        return result.stdout
    enrolled = Path(str(state_path) + '.ssh.json.enrolled.public.json')
    checked = Path(str(state_path) + '.ssh.json.verified.public.json')
    if not enrolled.exists():
        run('ssh-apply')
    enrollment = controller.private(enrolled)
    if enrollment['deployment_id'] != DEPLOYMENT or enrollment['private_key_exported'] is not False:
        raise ValueError('Existing SSH enrollment differs')
    if not checked.exists():
        remaining = max(0, 63 - (time.time() - enrollment['last_ephemeral_key_at']))
        if remaining:
            print('WAITING_FOR_SHORT_PUBLIC_KEY_EXPIRY; persistent key stays on bastion', flush=True)
            while remaining > 0:
                time.sleep(min(30, remaining))
                remaining = max(0, 63 - (time.time() - enrollment['last_ephemeral_key_at']))
        run('ssh-verify')
    accepted = Path(str(state_path) + '.registration.json.accepted.json')
    if not accepted.exists():
        run('register-apply', '--student-config', credential)
    run('register-verify', '--student-config', credential)
    state = controller.private(state_path)
    config = home / '.jdu-web-student' / LAB / 'command-state.json'
    bin_path = home / '.local/share/jdu-web/class193548-v7-bin'
    if not state.get('command_config'):
        run('install-commands', '--student-config', credential, '--bin-directory', bin_path)
    elif state['command_config'] != str(config):
        raise ValueError('Existing command configuration differs')
    observed = run('preflight')
    result = json.loads(observed.strip().splitlines()[-1])
    requests = re.findall(r'^SUBMISSION STORED request_id=([0-9a-f-]{36})$', observed, re.M)
    if result.get('current_foundation_passed') is not True or not requests:
        raise ValueError('Fresh foundation and actual stored receipt required')
    controller.save_new(output, dict(lab_id=LAB, deployment_id=DEPLOYMENT, manifest_sha256=MANIFEST,
        checked_at=datetime.now(timezone.utc).isoformat(), all_four_persistent_ssh_verified=True,
        existing_lab_credential_registered=True, foundation_passed=47, foundation_request=requests[-1],
        private_key_exported=False, new_lab_token_issued=False, teacher_admin_copied=False, class_ready=False))
    print('CLASS193548_STUDENT_ENROLLMENT_COMPLETE; 47/47 submitted to separate teacher', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('CLASS193548_ENROLLMENT_STOPPED=' + type(exc).__name__ + '; preserve all keys, credentials and partial state')
        raise SystemExit(2)
