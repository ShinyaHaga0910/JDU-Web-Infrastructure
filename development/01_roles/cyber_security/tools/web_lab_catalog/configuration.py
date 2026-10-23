"""Strict data-only EnvironmentFile format shared by setup helpers and systemd.

Every value is one JSON-quoted UTF-8 line. Control characters are forbidden;
only quote/backslash escaping is needed, matching systemd EnvironmentFile.
This file is never sourced by a shell. No secret is a command-line argument.
"""
import ipaddress
import json
import os
from pathlib import Path
import stat

KEYS = {'DJANGO_SECRET_KEY', 'DJANGO_ALLOWED_HOSTS', 'DB_HOST', 'DB_PORT', 'DB_NAME',
        'DB_USER', 'DB_PASSWORD', 'DJANGO_STATIC_ROOT', 'CATALOG_SITE_NAME'}
PROFILES = {
    'mission': ('jdu_catalog', 'catalog_setup', 'catalog_app', 'lab_admin'),
    'practice': ('jdu_catalog_practice', 'catalog_practice_setup', 'catalog_practice_app', 'practice_admin'),
}


def profile_of(config):
    matches = [name for name, values in PROFILES.items() if values[0] == config.get('DB_NAME')]
    if len(matches) != 1:
        raise ValueError('Unknown classroom database profile')
    return matches[0]


def validate(config, phase):
    if phase not in ('setup', 'runtime') or set(config) != KEYS:
        raise ValueError('Invalid environment fields or phase')
    if any(type(v) is not str or not 1 <= len(v) <= 512 or any(ord(c) < 32 or ord(c) == 127 for c in v)
           for v in config.values()):
        raise ValueError('Use nonempty single-line values without control characters')
    profile = PROFILES[profile_of(config)]
    if (len(config['DJANGO_SECRET_KEY']) < 50 or len(config['DB_PASSWORD']) < 16
            or any(v.startswith('<') or v.startswith('CHANGE_ME') for v in config.values())
            or config['DB_HOST'] != 'db.lab.test' or config['DB_PORT'] != '5432'
            or config['DB_USER'] != profile[1 if phase == 'setup' else 2]
            or config['DJANGO_STATIC_ROOT'] != '/var/lib/jdu-catalog/static'):
        raise ValueError('Environment differs from the classroom service contract')
    hosts = config['DJANGO_ALLOWED_HOSTS'].split(',')
    expected = ['web.lab.test', 'admin.lab.test', '10.20.1.20']
    if hosts[:3] != expected or len(hosts) not in (3, 4):
        raise ValueError('Use only the explicit classroom hosts and optional current public IPv4')
    if len(hosts) == 4 and not ipaddress.IPv4Address(hosts[3]).is_global:
        raise ValueError('The optional Web address must be public IPv4')
    return config


def encode(config, phase):
    validate(config, phase)
    return ''.join(k + '=' + json.dumps(config[k], ensure_ascii=False) + '\n' for k in sorted(KEYS)).encode()


def decode(data, phase):
    if len(data) > 16384:
        raise ValueError('Environment file too large')
    config = {}
    for line in data.decode('utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key not in KEYS or key in config or not value.startswith('"'):
            raise ValueError('Use the generated quoted environment format without duplicate keys')
        config[key] = json.loads(value)
    return validate(config, phase)


def private_read(path, phase):
    path = Path(path)
    # Validate the directory separately, then open with O_NOFOLLOW and inspect that fd.
    parent = path.parent.lstat()
    if parent.st_uid != 0 or not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o022:
        raise ValueError('Environment directory must be root-owned and not writable by others')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as f:
        s = os.fstat(f.fileno())
        if s.st_uid != 0 or not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode) != 0o600 or s.st_nlink != 1:
            raise ValueError('Environment file must be root-owned regular mode 0600 without links')
        return decode(f.read(16385), phase)


def private_create(path, config, phase):
    data = encode(config, phase)
    parent = Path(path).parent.lstat()
    if parent.st_uid != 0 or not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o022:
        raise ValueError('Unsafe environment directory')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as f:
        f.write(data)


def main():
    import argparse
    from getpass import getpass
    import secrets
    import sys
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('create-runtime', 'create-setup', 'check', 'activate'))
    p.add_argument('--profile', choices=tuple(PROFILES), default='mission')
    p.add_argument('--phase', choices=('setup', 'runtime'))
    p.add_argument('--public-web-ipv4')
    a = p.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Run on the Web server as root')
    os.umask(0o077)
    root = Path('/etc/jdu-catalog')
    profile_root = root / 'profiles'
    if a.command == 'activate':
        activate_profile(root, a.profile)
        print('CATALOG_PROFILE_ACTIVATED=' + a.profile + '; existing profile retained')
        return
    if a.command == 'check':
        if not a.phase:
            raise ValueError('Select setup or runtime')
        private_read(root / ('setup.env' if a.phase == 'setup' else 'app.env'), a.phase)
        print('CATALOG_ENV_VALID; values are not printed')
        return
    if not sys.stdin.isatty():
        raise ValueError('Use an interactive terminal; secrets are never arguments')
    if not root.exists() and not root.is_symlink():
        root.mkdir(mode=0o700)
    if not profile_root.exists() and not profile_root.is_symlink():
        profile_root.mkdir(mode=0o700)
    path = profile_root / (a.profile + ('.app.env' if a.command == 'create-runtime' else '.setup.env'))
    if path.exists() or path.is_symlink():
        raise ValueError('Existing environment retained; no automatic replacement')
    if a.command == 'create-runtime':
        config = dict(DJANGO_SECRET_KEY=secrets.token_urlsafe(48),
            DJANGO_ALLOWED_HOSTS='web.lab.test,admin.lab.test,10.20.1.20' + (',' + a.public_web_ipv4 if a.public_web_ipv4 else ''),
            DB_HOST='db.lab.test', DB_PORT='5432', DB_NAME=PROFILES[a.profile][0], DB_USER=PROFILES[a.profile][2],
            DB_PASSWORD='pending-interactive-value', DJANGO_STATIC_ROOT='/var/lib/jdu-catalog/static',
            CATALOG_SITE_NAME='JDU 備品カタログ')
        phase = 'runtime'
    else:
        if profile_of(private_read(root / 'app.env', 'runtime')) != a.profile:
            raise ValueError('Explicitly activate the selected runtime profile before creating setup credentials')
        config = private_read(profile_root / (a.profile + '.app.env'), 'runtime').copy()
        config['DB_USER'] = PROFILES[a.profile][1]
        phase = 'setup'
    first = getpass('Existing ' + config['DB_USER'] + ' database password (hidden): ')
    second = getpass('Confirm existing database password: ')
    if first != second or (phase == 'setup' and first == config['DB_PASSWORD']):
        raise ValueError('Password confirmation differs or setup/runtime passwords are identical')
    config['DB_PASSWORD'] = first
    private_create(path, config, phase)
    # Preserve the original one-profile classroom commands on a fresh host.
    canonical = root / ('app.env' if phase == 'runtime' else 'setup.env')
    if not canonical.exists() and not canonical.is_symlink():
        private_create(canonical, config, phase)
    print('CATALOG_ENV_CREATED=' + a.profile + '; root-owned mode 0600; no values printed')


def activate_profile(root, profile):
    """Explicit stopped-service switch. Preserve both profiles and never overwrite setup secrets."""
    import subprocess
    if profile not in PROFILES:
        raise ValueError('Unknown profile')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'jdu-catalog'], capture_output=True).returncode == 0:
        raise ValueError('Stop the application explicitly before switching profiles')
    root = Path(root)
    if (root / 'setup.env').exists() or (root / 'setup.env').is_symlink():
        raise ValueError('Finish and retire setup before switching profiles')
    source = root / 'profiles' / (profile + '.app.env')
    config = private_read(source, 'runtime')
    if profile_of(config) != profile:
        raise ValueError('Profile file mismatch')
    target = root / 'app.env'
    if target.exists() or target.is_symlink():
        previous = private_read(target, 'runtime')
        backup = root / 'profiles' / (profile_of(previous) + '.app.env')
        if backup.exists() or backup.is_symlink():
            if private_read(backup, 'runtime') != previous:
                raise ValueError('Existing profile backup differs; retained')
        else:
            private_create(backup, previous, 'runtime')
    staged = root / 'app.env.activate-new'
    private_create(staged, config, 'runtime')
    os.replace(staged, target)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('CATALOG_CONFIGURATION_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
