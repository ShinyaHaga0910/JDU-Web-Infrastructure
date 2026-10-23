"""Web-only hidden input for an existing runtime DB password. Never alters a role."""
from getpass import getpass
import json
import os
from pathlib import Path
import stat
import sys

from registry import REGISTRY


def save(profile, password):
    p = REGISTRY['profiles'][profile]
    if len(password) < 16 or any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise ValueError('Use at least 16 single-line characters')
    path = Path(p['db_runtime_env'])
    parent = path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_mode & 0o022:
        raise ValueError('Use the root-owned Web configuration directory')
    config = dict(DB_HOST='db.lab.test', DB_PORT='5432', DB_NAME=p['db_name'], DB_USER=p['runtime_role'], DB_PASSWORD=password)
    raw = ''.join(k + '=' + json.dumps(v) + '\n' for k, v in sorted(config.items())).encode()
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--profile', choices=('practice', 'mission'), required=True)
    a = p.parse_args()
    try:
        if os.geteuid() != 0 or not sys.stdin.isatty():
            raise ValueError('Use an interactive SSM terminal on Web as root')
        path = Path(REGISTRY['profiles'][a.profile]['db_runtime_env'])
        if path.exists() or path.is_symlink():
            raise ValueError('Existing private runtime configuration retained')
        first = getpass('Existing runtime database password (hidden): ')
        if first != getpass('Confirm existing runtime database password: '):
            raise ValueError('Confirmation differs')
        save(a.profile, first); del first
        print('D11_EXISTING_DB_PASSWORD_STORED_LOCALLY; no role changed; no values printed')
    except Exception as exc:
        print('D11_DB_SECRET_STOPPED=' + type(exc).__name__); raise SystemExit(2)
