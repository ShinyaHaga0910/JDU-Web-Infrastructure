"""Install Web-prefixed command launchers for the accepted Test2 probe only.

No credential is generated, copied, displayed or replaced. The public launchers
reference the original private files within this individual's CloudShell.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import sys


def main():
    import boto3
    home = Path.home(); os.umask(0o077)
    root = home / 'jdu-web-capture-20261015'
    tools = Path(__file__).resolve().parent
    state_path = root / 'five-node-ssm-state.private.json'
    baseline_path = root / 'ssm-access.private.json'
    state = json.loads(state_path.read_text()); baseline = json.loads(baseline_path.read_text())
    if state['account'] != boto3.client('sts').get_caller_identity()['Account'] or state['lab_id'] != 'teacher-five-probe':
        raise ValueError('Only the accepted teacher probe account is allowed')
    bootstrap_tools = root / 'c3-transfer/ssh-v1'
    sys.path.insert(0, str(bootstrap_tools))
    from setup_internal_ssh import current_nodes, save_new
    nodes = current_nodes(boto3.client('ec2', region_name='us-east-1'),
        boto3.client('cloudformation', region_name='us-east-1'), state, baseline)
    credential = home / '.jdu-web-teacher/private/teacher-five-probe.credentials.json'
    if not credential.is_file() or credential.is_symlink() or credential.stat().st_mode & 0o077:
        raise ValueError('Existing individual credential must remain private')
    command_root = home / '.jdu-web-student'
    bin_path = home / '.local/bin'
    for directory in (command_root, bin_path):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        s = directory.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o022:
            raise ValueError('Unsafe command directory')
    quote = shlex.quote
    command = 'exec python3 ' + quote(str(tools / 'web_commands.py'))
    config_arg = ' --config ' + quote(str(credential))
    deployment_path = command_root / 'probe-deployment.public.json'
    launchers = {
        'jdu-web-dashboard': command + ' dashboard "$@"\n',
        'jdu-web-my-progress': command + ' my-progress' + config_arg + ' "$@"\n',
        'jdu-web-register': command + ' register' + config_arg + ' --state ' + quote(str(deployment_path)) + ' "$@"\n',
        'jdu-web-progress': 'operation="${1:-}"\n[ -n "$operation" ] || { printf "%s\\n" "Usage: jdu-web-progress id|link-email|submit"; exit 2; }\nshift\n'
            + command + ' "$operation"' + config_arg + ' "$@"\n',
        'jdu-web-check': 'exec python3 ' + quote(str(tools / 'check_bootstrap.py')) + ' "$@"\n',
    }
    config_path = command_root / 'command-state.json'
    if any(p.exists() or p.is_symlink() for p in [deployment_path, config_path, *[bin_path / n for n in launchers]]):
        raise ValueError('Existing commands/config retained; no automatic replacement')
    config = dict(scope='teacher_probe_commands_pending_student_signed_release',
        state=str(state_path), baseline_plan=str(baseline_path), bootstrap_tools=str(bootstrap_tools),
        ssh_enrollment=str(root / 'internal-ssh-v1.private.json.enrolled.public.json'),
        pending_directory=str(command_root / 'pending'),
        network_source_sha256='0720fff6f8b1b9271bdb363f937bfea8addd977040324f6adcad252100f26d27')
    for key, filename in [('guest_source', 'post_restart_guest.py'), ('submission_source', 'bootstrap_submission_guest.py')]:
        config[key] = str(tools / filename)
        config[key + '_sha256'] = hashlib.sha256((tools / filename).read_bytes()).hexdigest()
    save_new(config_path, config)
    save_new(deployment_path, dict(lab_id=state['lab_id'], deployment_id=state['deployment_id'], release_id='web-2026-10-r1',
                                  instances={r: n['instance_id'] for r, n in nodes.items()}))
    for name, body in launchers.items():
        path = bin_path / name
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700), 'w') as f:
            f.write('#!/usr/bin/env bash\nset -euo pipefail\n' + body)
    public = dict(commands=list(launchers), private_credential_copied=False,
                  scope='accepted_test2_probe_commands_not_student_release', class_ready=False)
    save_new(root / 'web-command-install.public.json', public)
    print('WEB_COMMANDS_INSTALLED=' + json.dumps(public, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('WEB_COMMAND_INSTALL_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
