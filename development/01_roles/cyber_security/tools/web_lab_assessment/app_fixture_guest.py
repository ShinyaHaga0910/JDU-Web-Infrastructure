"""Teacher-only, new fictional DB/app fixture. Secrets arrive only over pinned SSH stdin.

Never included in student artifacts. Refuses existing classroom databases,
roles, application directories or users. Outputs only bounded public status.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import subprocess
import sys
import tarfile
import types
import urllib.request

WORK = Path('/var/lib/jdu-web/d11-app-acceptance-r1')


def command(args, *, data=None, timeout=480, env=None, cwd=None):
    return subprocess.run(args, input=data, capture_output=True, text=True, check=True, timeout=timeout,
        env=env or dict(os.environ, DEBIAN_FRONTEND='noninteractive', LC_ALL='C'), cwd=cwd, umask=0o022).stdout


def private_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream)


def public_write(path, raw, mode=0o644):
    path = Path(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(raw)


def psql(text, database='postgres'):
    return command(['sudo', '-n', '-u', 'postgres', '/usr/lib/postgresql/16/bin/psql', '-X', '-qAt',
        '-v', 'ON_ERROR_STOP=1', '-d', database], data=text, timeout=60)


def literal(value):
    if type(value) is not str or len(value) < 16 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in value):
        raise ValueError('Only the newly generated fixture secret format')
    return "'" + value + "'"


def install_db(request, b, helper):
    installed = helper['packages']()
    if 'postgresql-16' in installed or Path('/var/lib/postgresql/16/main').exists():
        raise ValueError('Existing database cluster retained')
    WORK.mkdir(mode=0o700, exist_ok=False)
    helper['install_internal'](b, ['postgresql-16', 'postgresql-client-16'], WORK)
    existing = psql("SELECT to_json(EXISTS(SELECT 1 FROM pg_database WHERE datname IN ('jdu_catalog','jdu_catalog_practice')) OR "
        "EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN ('catalog_setup','catalog_app','catalog_practice_setup','catalog_practice_app')));\n")
    if json.loads(existing.strip()) is not False:
        raise ValueError('Existing database/role names retained')
    config = Path('/etc/postgresql/16/main/postgresql.conf')
    public_write(WORK / 'postgresql.conf.before', config.read_bytes(), 0o600)
    config.write_text(config.read_text() + "\n# JDU fictional D11 acceptance\nlisten_addresses='10.20.2.20'\nport=5432\npassword_encryption='scram-sha-256'\n")
    hba = Path('/etc/postgresql/16/main/pg_hba.conf')
    public_write(WORK / 'pg_hba.conf.before', hba.read_bytes(), 0o600)
    lines = ['local all postgres peer', 'local all all reject']
    for item in request['profiles'].values():
        for role in (item['setup_role'], item['runtime_role']):
            lines.append('host ' + item['db_name'] + ' ' + role + ' 10.20.1.20/32 scram-sha-256')
    lines += ['host all all 0.0.0.0/0 reject', 'host all all ::/0 reject']
    hba.write_text('\n'.join(lines) + '\n')
    command(['systemctl', 'restart', 'postgresql@16-main'], timeout=60)
    if psql("SELECT to_json(current_setting('password_encryption'));\n").strip() != '"scram-sha-256"':
        raise ValueError('SCRAM encryption must be active before setting new role passwords')
    for profile, item in request['profiles'].items():
        secrets = request['credentials'][profile]
        psql(request['sql'][profile]['01_create_roles.sql'])
        psql('ALTER ROLE ' + item['setup_role'] + ' PASSWORD ' + literal(secrets['setup']) + ';\n'
            'ALTER ROLE ' + item['runtime_role'] + ' PASSWORD ' + literal(secrets['runtime']) + ';\n')
        psql(request['sql'][profile]['02_prepare_schema.sql'], item['db_name'])
    return dict(databases_created=2, scram=True, web_source_only=True)


def extract_app(request):
    raw = base64.b64decode(request['application_b64'], validate=True)
    registry = request['registry']
    if hashlib.sha256(raw).hexdigest() != registry['application_archive_sha256']:
        raise ValueError('Pinned application archive differs')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for item in archive:
            name = item.name.removeprefix('jdu-catalog/')
            if (not item.name.startswith('jdu-catalog/') or not item.isfile() or name in files
                    or any(p in ('', '.', '..') for p in name.split('/')) or '\\' in name or ':' in name
                    or not 0 <= item.size <= 262144 or len(files) >= 100):
                raise ValueError('Unsafe application member')
            files[name] = archive.extractfile(item).read()
    manifest = json.loads(files['APP-MANIFEST.json'])
    if manifest != registry['application_manifest'] or set(files) != {e['path'] for e in manifest['files']} | {'APP-MANIFEST.json'}:
        raise ValueError('Pinned application manifest differs')
    for item in manifest['files']:
        if (len(files[item['path']]), hashlib.sha256(files[item['path']]).hexdigest()) != (item['size_bytes'], item['sha256']):
            raise ValueError('Application bytes differ')
    return files


SETUP_CHILD = '''import json,os,pwd,sys
p=json.load(sys.stdin);config=p['config'];user=pwd.getpwnam('catalog')
os.environ.clear();os.environ.update(config,PATH='/usr/bin:/bin',LANG='C.UTF-8',HOME='/nonexistent',DJANGO_SETTINGS_MODULE='jdu_catalog.settings',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True;os.setgroups([]);os.setgid(user.pw_gid);os.setuid(user.pw_uid)
import django;django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from catalog.models import Item
call_command('migrate',interactive=False,verbosity=0)
call_command('seed_catalog',verbosity=0)
u=get_user_model()(username=p['admin'],is_staff=True,is_superuser=False,is_active=True)
validate_password(p['password'],user=u);u.set_password(p['password']);u.save()
permissions=Permission.objects.filter(content_type__app_label='catalog',content_type__model='item',codename__in=['view_item','add_item','change_item'])
assert permissions.count()==3;u.user_permissions.set(permissions)
Item.objects.bulk_create([Item(**row) for row in p['records']])
print('FICTIONAL_PROFILE_DATA_READY')
'''


def prepare_web(request, b, helper):
    root = Path('/opt/jdu-catalog')
    if root.exists() or root.is_symlink() or Path('/etc/jdu-catalog').exists():
        raise ValueError('Existing student app/configuration retained')
    try:
        pwd.getpwnam('catalog')
    except KeyError:
        pass
    else:
        raise ValueError('Existing service user retained')
    WORK.mkdir(mode=0o700, exist_ok=False)
    helper['install_internal'](b, ['python3-venv', 'python3-pip', 'postgresql-client-16'], WORK)
    files = extract_app(request)
    root.mkdir(mode=0o755); root.chmod(0o755)
    app = root / 'app'; app.mkdir(mode=0o755); app.chmod(0o755)
    for name, raw in files.items():
        target = app / name
        directory = app
        for part in PurePosixPath(name).parts[:-1]:
            directory = directory / part
            directory.mkdir(mode=0o755, exist_ok=True)
            directory.chmod(0o755)
        public_write(target, raw)
    library = Path('/usr/local/lib/jdu-web') / b['release_id']
    sys.path.insert(0, str(library))
    from payload_runtime import signed_manifest
    _, sums = signed_manifest('/var/lib/jdu-web/initial/client-metadata', '/var/lib/jdu-web/initial/archive-key.asc',
        b['fingerprint'], b['release_id'], allow_package_candidate=True)
    prefix = 'http://10.20.2.30/releases/' + b['release_id'] + '/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def fetch(name, limit):
        with opener.open(prefix + name, timeout=45) as response:
            raw = response.read(limit + 1)
        if len(raw) > limit or hashlib.sha256(raw).hexdigest() != sums[name]:
            raise ValueError('Signed offline wheel resource differs')
        return raw
    wheels = json.loads(fetch('manifests/python-packages.json', 65536))
    wheelhouse = WORK / 'wheels'; wheelhouse.mkdir(mode=0o755); wheelhouse.chmod(0o755)
    for wheel in wheels:
        name = wheel['filename']
        if Path(name).name != name:
            raise ValueError('Unsafe wheel filename')
        public_write(wheelhouse / name, fetch('artifacts/python/wheelhouse/' + name, wheel['size_bytes']))
    lock = WORK / 'requirements.lock'; public_write(lock, fetch('artifacts/python/requirements.lock', 65536))
    venv = root / 'venv'
    command(['python3', '-m', 'venv', str(venv)], timeout=120)
    command([str(venv / 'bin/python'), '-m', 'pip', '--isolated', '--no-cache-dir', 'install', '--no-index',
        '--find-links=' + str(wheelhouse), '--only-binary=:all:', '--require-hashes', '-r', str(lock)], timeout=300)
    command([str(venv / 'bin/python'), '-m', 'pip', '--isolated', 'check'], timeout=30)
    command(['useradd', '--system', '--user-group', '--home-dir', '/nonexistent', '--no-create-home', '--shell', '/usr/sbin/nologin', 'catalog'], timeout=30)
    user = pwd.getpwnam('catalog')
    config_root = Path('/etc/jdu-catalog'); config_root.mkdir(mode=0o700)
    profiles = config_root / 'profiles'; profiles.mkdir(mode=0o700)
    static = Path('/var/lib/jdu-catalog/static')
    static.parent.mkdir(mode=0o755); static.parent.chmod(0o755)
    static.mkdir(mode=0o755); static.chmod(0o755)
    os.chown(static, user.pw_uid, user.pw_gid)
    sys.path.insert(0, str(app))
    import configuration
    for profile, item in request['profiles'].items():
        secrets = request['credentials'][profile]
        config = dict(DJANGO_SECRET_KEY=secrets['django'], DJANGO_ALLOWED_HOSTS='web.lab.test,admin.lab.test,10.20.1.20'
            + (',' + request['public_ipv4'] if request.get('public_ipv4') else ''), DB_HOST='db.lab.test', DB_PORT='5432',
            DB_NAME=item['db_name'], DB_USER=item['runtime_role'], DB_PASSWORD=secrets['runtime'],
            DJANGO_STATIC_ROOT=str(static), CATALOG_SITE_NAME='JDU fictional acceptance catalog')
        configuration.private_create(profiles / (profile + '.app.env'), config, 'runtime')
        helper['save_new'](Path(item['db_runtime_env']), ''.join(k + '=' + json.dumps(config[k]) + '\n'
            for k in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')).encode())
        setup = dict(config, DB_USER=item['setup_role'], DB_PASSWORD=secrets['setup'])
        child = dict(config=setup, admin=item['app_admin'], password=secrets['admin'], records=item['records'])
        command([str(venv / 'bin/python'), '-B', '-c', SETUP_CHILD], data=json.dumps(child), cwd=app, timeout=180)
    return dict(offline_runtime_installed=True, pinned_application=True, fictional_profiles_created=2)


def finalize_db(request):
    for profile, item in request['profiles'].items():
        psql(request['sql'][profile]['03_runtime_grants.sql'], item['db_name'])
        psql(request['sql'][profile]['04_disable_setup.sql'], item['db_name'])
    return dict(runtime_grants_applied=True, setup_roles_retired=True)


def start_web(request):
    app = Path('/opt/jdu-catalog/app')
    sys.path.insert(0, str(app)); import configuration
    profile = request.get('profile', 'practice')
    root = Path('/etc/jdu-catalog')
    config = configuration.private_read(root / 'profiles' / (profile + '.app.env'), 'runtime')
    configuration.private_create(root / 'app.env', config, 'runtime')
    venv = Path('/opt/jdu-catalog/venv/bin/python')
    command([str(venv), '-B', str(app / 'manage_secure.py'), '--phase', 'runtime', 'collectstatic'], timeout=120)
    default = Path('/etc/nginx/sites-available/default')
    public_write(WORK / 'nginx.before-app.conf', default.read_bytes(), 0o600)
    default.write_bytes((app / 'config/jdu-catalog.nginx.conf').read_bytes())
    public_write('/etc/systemd/system/jdu-catalog.service', (app / 'config/jdu-catalog.service').read_bytes())
    command(['nginx', '-t'], timeout=20)
    command(['systemctl', 'daemon-reload'], timeout=30)
    command(['systemctl', 'enable', '--now', 'jdu-catalog'], timeout=60)
    command(['systemctl', 'reload', 'nginx'], timeout=30)
    return dict(active_profile=profile, private_admin_only=True, loopback_app_only=True)


def switch_web(request):
    app = Path('/opt/jdu-catalog/app')
    sys.path.insert(0, str(app)); import configuration
    command(['systemctl', 'stop', 'jdu-catalog'], timeout=30)
    configuration.activate_profile('/etc/jdu-catalog', request['profile'])
    command(['systemctl', 'start', 'jdu-catalog'], timeout=60)
    return dict(active_profile=request['profile'], existing_profiles_retained=True)


def run(request):
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if os.geteuid() != 0 or any(b[k] != request[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
        raise ValueError('Wrong registered fixture host')
    helper = {'__name__': '_trusted_foundation_helper'}
    exec(compile(request['foundation_source'], '<teacher-foundation-helper>', 'exec'), helper)
    op = request['operation']
    allowed = {'install-db': 'db', 'prepare-web': 'web', 'finalize-db': 'db', 'start-web': 'web', 'switch-web': 'web'}
    if op not in allowed or b['role'] != allowed[op]:
        raise ValueError('Wrong role/operation')
    if op == 'install-db':
        result = install_db(request, b, helper)
    elif op == 'prepare-web':
        result = prepare_web(request, b, helper)
    elif op == 'finalize-db':
        result = finalize_db(request)
    elif op == 'start-web':
        result = start_web(request)
    else:
        result = switch_web(request)
    return dict(operation=op, instance_id=b['instance_id'], **result)


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin)), separators=(',', ':')))
    except Exception as exc:
        print('D11_APP_FIXTURE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
