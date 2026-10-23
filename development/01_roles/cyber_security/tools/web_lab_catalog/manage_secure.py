"""Run a fixed management operation as catalog, reading root-only data without shell source."""
import argparse
import os
from pathlib import Path
import pwd
import stat
import sys

from configuration import private_read, profile_of, PROFILES

OPERATIONS = {
    'setup': {'check', 'migrate', 'seed_catalog', 'create_lab_admin'},
    'runtime': {'check', 'collectstatic', 'set_lab_password'},
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=tuple(OPERATIONS), required=True)
    p.add_argument('operation')
    a = p.parse_args()
    if a.operation not in OPERATIONS[a.phase] or os.geteuid() != 0:
        raise ValueError('Use an allowed operation as root')
    if sys.executable != '/opt/jdu-catalog/venv/bin/python':
        raise ValueError('Use the offline application venv Python')
    root = Path('/opt/jdu-catalog/app')
    for path in (root.parent, root, Path(sys.executable).parent.parent):
        s = path.lstat()
        if s.st_uid != 0 or not stat.S_ISDIR(s.st_mode) or s.st_mode & 0o022:
            raise ValueError('App and venv directories must remain root-controlled')
    config = private_read('/etc/jdu-catalog/' + ('setup.env' if a.phase == 'setup' else 'app.env'), a.phase)
    user = pwd.getpwnam('catalog')
    if user.pw_uid == 0 or user.pw_shell not in ('/usr/sbin/nologin', '/bin/false'):
        raise ValueError('Use the non-login catalog service user')
    os.chdir(root)
    os.environ.clear()
    os.environ.update(config, PATH='/usr/bin:/bin', LANG='C.UTF-8', HOME='/nonexistent',
                      DJANGO_SETTINGS_MODULE='jdu_catalog.settings', PYTHONDONTWRITEBYTECODE='1')
    sys.dont_write_bytecode = True
    os.setgroups([])
    os.setgid(user.pw_gid)
    os.setuid(user.pw_uid)
    import django
    django.setup()
    from django.core.management import call_command
    options = {'interactive': False} if a.operation in ('migrate', 'collectstatic') else {}
    if a.operation in ('create_lab_admin', 'set_lab_password'):
        options['username'] = PROFILES[profile_of(config)][3]
    call_command(a.operation, **options)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not print exception values, config or database connection strings.
        print('CATALOG_MANAGEMENT_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
