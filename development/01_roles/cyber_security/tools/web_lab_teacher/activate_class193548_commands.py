"""Activate the accepted signed commands in individual CloudShell only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

MANIFEST = 'a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2'


def save(path, data, mode):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=('teacher', 'student')); args = parser.parse_args()
    import boto3
    os.umask(0o077); sys.dont_write_bytecode = True
    expected = '170126527713' if args.role == 'teacher' else '965244652544'
    if boto3.client('sts').get_caller_identity()['Account'] != expected:
        raise ValueError('Correct individual CloudShell account required')
    home = Path.home(); base = home / 'jdu-web-class193548'; kit = base / 'cross-account-delivery-v1'
    for name, pin in {
        'class_student_delivery.py': '1bbaf46daa1eed027e17e422e64ff0af5e8f24791d36df2f2379a57ff652a184',
        'web_progress.py': 'a966bbe49eefdb4fc6f9ca1dc39d930532992490923fde155caf3ed5a5aed6a4',
        'release_validation.py': 'e9aebc2f1ed3d54df70e862e5a9aabe8e08970004106c8a89a6260da9e34096c',
    }.items():
        if hashlib.sha256((kit / name).read_bytes()).hexdigest() != pin:
            raise ValueError('Accepted delivery helper changed')
    sys.path.insert(0, str(kit)); import class_student_delivery as delivery
    tools = base / ('signed-tools-v7-transfer/student-tools' if args.role == 'teacher' else 'student-software-v7/student-tools')
    verified = delivery.verified_tools(tools)
    if verified['manifest_sha256'] != MANIFEST:
        raise ValueError('Accepted signed v7 required')
    import web_commands
    q = shlex.quote
    directory = home / '.local/share/jdu-web' / ('class193548-teacher-bin' if args.role == 'teacher' else 'class193548-v7-bin')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.geteuid() or directory.stat().st_mode & 0o022:
        raise ValueError('Unsafe individual command directory')
    credential = (home / '.jdu-web-teacher/teacher.credentials.json' if args.role == 'teacher' else
        base / 'student-delivery-renewal-20261022/received/own-student.credentials.json')
    if args.role == 'teacher':
        name = 'jdu-web-dashboard'
        body = ('#!/usr/bin/env bash\nset -euo pipefail\nexec python3 -B ' + q(str(Path(web_commands.__file__).resolve()))
            + ' dashboard --config ' + q(str(credential)) + ' "$@"\n').encode()
        command_names = [name]
    else:
        name = 'jdu-web-lab'
        body = ('#!/usr/bin/env bash\nset -euo pipefail\nexec bash ' + q(str(tools / 'jdu-web-lab')) + ' "$@"\n').encode()
        command_names = [name, 'jdu-web-check', 'jdu-web-progress', 'jdu-web-register', 'jdu-web-my-progress']
    target = directory / name
    if target.exists() or target.is_symlink():
        raise ValueError('Existing command retained for inspection')
    save(target, body, 0o700)
    rc = home / '.bashrc'; backup = home / ('.bashrc.before-jdu-web-class193548-' + args.role + '-20261022')
    original = rc.read_bytes()
    if rc.is_symlink() or rc.stat().st_uid != os.geteuid():
        raise ValueError('Unsafe individual shell configuration')
    relative = directory.relative_to(home).as_posix()
    marker = '# JDU Web Class193548 ' + args.role + ' commands'
    if marker.encode() in original:
        raise ValueError('Existing activation retained')
    save(backup, original, 0o600)
    block = ('\n' + marker + '\ncase ":$PATH:" in\n  *":$HOME/' + relative + ':"*) ;;\n'
        + '  *) export PATH="$HOME/' + relative + ':$PATH" ;;\nesac\n').encode()
    with rc.open('ab') as stream:
        stream.write(block)
    env = dict(os.environ, PATH=str(directory) + os.pathsep + os.environ['PATH'])
    for command in command_names:
        if shutil.which(command, path=env['PATH']) != str(directory / command):
            raise ValueError('Short command resolution differs')
    if args.role == 'student':
        result = subprocess.run(['jdu-web-progress', 'id'], env=env, capture_output=True, text=True, check=True)
        if result.stdout.strip() != 'class193548-test1':
            raise ValueError('Short identity command resolved another Lab')
    session = base / 'progress-pages-20261022' / (args.role + '-short-command.session.private.json')
    command = 'jdu-web-dashboard' if args.role == 'teacher' else 'jdu-web-my-progress'
    result = subprocess.run([command, '--save-session', str(session)], env=env, capture_output=True, text=True, check=True)
    if result.stdout.strip() != 'DASHBOARD_SESSION_SAVED; temporary private URL not displayed':
        raise ValueError('Short progress command did not preserve its private viewing URL')
    output = base / ('short-commands-' + args.role + '-20261022.public.json')
    save(output, (json.dumps(dict(scope='accepted_signed_commands_in_individual_cloudshell', role=args.role,
        account=expected, manifest_sha256=MANIFEST, checked_at=datetime.now(timezone.utc).isoformat(),
        commands=command_names, all_short_commands_resolve=True, actual_private_view_session_command_passed=True,
        original_bashrc_preserved=True, credentials_copied=False, bearer_urls_exported=False,
        lab_token_issued=False, class_ready=False), indent=2) + '\n').encode(), 0o600)
    print('CLASS193548_SHORT_COMMANDS_ACTIVATED=' + args.role, flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('CLASS193548_COMMAND_ACTIVATION_STOPPED=' + type(exc).__name__ + '; preserve partial files and shell backup')
        raise SystemExit(2)
