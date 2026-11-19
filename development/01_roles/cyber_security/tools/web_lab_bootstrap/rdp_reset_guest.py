"""Apply a one-use encrypted RDP password reset to the current bastion."""

import base64
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys

from progress_enrollment_guest import decrypt, recipient, safe


def run(request):
    bootstrap = Path('/etc/jdu-web/bootstrap.json')
    info = bootstrap.lstat()
    if os.geteuid() != 0 or not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Invalid bastion configuration')
    config = json.loads(bootstrap.read_text())
    keys = ('lab_id', 'deployment_id', 'instance_id')
    if config['role'] != 'bastion' or any(config[key] != request[key] for key in keys):
        raise ValueError('Wrong bastion identity')
    if pwd.getpwnam('labuser').pw_uid == 0:
        raise ValueError('Invalid desktop user')
    nonce = request['nonce']
    if not re.fullmatch(r'[0-9a-f]{32}', nonce):
        raise ValueError('Invalid reset nonce')
    directory = Path('/run') / ('jdu-rdp-reset-' + nonce)
    phase = request['phase']

    if phase == 'prepare':
        directory.mkdir(mode=0o700)
        try:
            return dict(recipient(directory, config['deployment_id']), nonce=nonce)
        except Exception:
            shutil.rmtree(directory)
            raise
    if phase == 'cancel':
        if directory.exists():
            safe(directory, 0o700, directory=True)
            shutil.rmtree(directory)
        return {'nonce': nonce}
    if phase != 'apply':
        raise ValueError('Unknown reset phase')

    safe(directory, 0o700, directory=True)
    try:
        secret = decrypt(directory, base64.b64decode(request['ciphertext'], validate=True))
        expected = {key: request[key] for key in (*keys, 'nonce')}
        if (set(secret) != set(expected) | {'purpose', 'password_hash'}
                or any(secret[key] != value for key, value in expected.items())):
            raise ValueError('Wrong reset envelope identity')
        password_hash = secret['password_hash']
        if secret['purpose'] != 'rdp-password-reset' or not re.fullmatch(r'\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}', password_hash):
            raise ValueError('Invalid reset envelope')
        subprocess.run(['chpasswd', '--encrypted'], input=f'labuser:{password_hash}\n'.encode(),
                       capture_output=True, check=True)
        with Path('/etc/shadow').open() as shadow:
            line = next((line for line in shadow if line.startswith('labuser:')), '')
        if not line or line.split(':', 2)[1] != password_hash:
            raise ValueError('New password hash could not be verified')
        return dict(expected, applied=True)
    finally:
        shutil.rmtree(directory)


if __name__ == '__main__':
    print(json.dumps(run(json.load(sys.stdin))))
