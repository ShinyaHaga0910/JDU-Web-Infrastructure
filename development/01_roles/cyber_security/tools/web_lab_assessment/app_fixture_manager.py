"""Teacher-only bastion manager. Apply creates credentials only after the human runs it.

Private values stay on root-owned hosts or pinned SSH/normal private app HTTP.
Public SSM parameters and results never carry a password, cookie, hash or token.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import stat
import subprocess
import sys
import types

ROOT = Path('/var/lib/jdu-web/d11-app-manager-r1')
SECRET = ROOT / 'credentials.private.json'
DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'


def create_private(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream)


def read_private(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if info.st_uid != 0 or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise ValueError('Root-only private regular file required')
        return json.load(stream)


def checkpoint(phase, results):
    staged = ROOT / 'state.new'
    create_private(staged, dict(phase=phase, results=results, at=datetime.now(timezone.utc).isoformat()))
    os.replace(staged, ROOT / 'state.public.json')
    print('D11_APP_STEP=' + phase, file=sys.stderr, flush=True)


def peer(bundle, b, operation, role, credentials=None, profile=None):
    request = {k: b[k] for k in ('lab_id', 'deployment_id')}
    request.update(role=role, instance_id=b['instances'][role], operation=operation,
        profiles=bundle['registry']['profiles'], foundation_source=bundle['foundation_source'])
    if role == 'db':
        request['sql'] = bundle['sql']
        if credentials is not None:
            request['credentials'] = {p: {k: v[k] for k in ('setup', 'runtime')} for p, v in credentials.items()}
    if operation == 'prepare-web':
        request.update(registry=bundle['registry'], application_b64=bundle['application_b64'],
            credentials=credentials, public_ipv4=bundle['public_ipv4'])
    if profile:
        request['profile'] = profile
    source = base64.b64encode(bundle['guest_source'].encode()).decode()
    code = 'import base64;exec(base64.b64decode(' + repr(source) + '))'
    result = subprocess.run(['sudo', '-n', '-u', 'labuser', 'ssh', '-F', '/home/labuser/.ssh/jdu-web-internal/config',
        '-o', 'ConnectTimeout=8', role, 'sudo -n python3 -c ' + shlex.quote(code)],
        input=json.dumps(request), capture_output=True, text=True, timeout=1500)
    if result.returncode:
        # Captured output can include tool diagnostics; never print private request/SQL/values.
        raise ValueError('Guest step failed: ' + operation + ':' + role)
    return json.loads(result.stdout)


def probe(bundle, b, payload, credentials):
    request = payload['request']
    if (request['role'] != 'bastion' or request['instance_id'] != b['instance_id']
            or request['deployment_id'] != b['deployment_id'] or request['instances'] != b['instances']):
        raise ValueError('Wrong current observation identity')
    sources = bundle['observer_sources']
    for name in ('registry', 'network_checks', 'db_observer', 'system_observer', 'app_probe', 'remote_guest'):
        module = types.ModuleType(name); module.__file__ = '/trusted-d11/' + name + '.py'; sys.modules[name] = module
        if name == 'registry':
            module.__dict__['_REGISTRY_BYTES'] = sources['assessment-registry.json'].encode()
        exec(compile(sources[name + '.py'], module.__file__, 'exec'), module.__dict__)
    registry = sys.modules['registry']
    if request['task_id'] not in ('P5', 'P6', 'M5', 'M6'):
        raise ValueError('Only the fixture functional task')
    profile = registry.TASKS[request['task_id']]['profile']
    guest = sys.modules['remote_guest']; guest.PUBLIC_SOURCES = sources; guest.LOADER_SOURCE = sources['loader']
    return guest.collect(request, password=credentials[profile]['admin'])


def run(operation, payload):
    os.umask(0o077)
    if os.geteuid() != 0:
        raise ValueError('Root bastion fixture required')
    bundle = read_private(ROOT / 'bundle.public.json')
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if (b['role'] != 'bastion' or b['deployment_id'] != DEPLOYMENT
            or any(b[k] != bundle['identity'][k] for k in ('lab_id', 'deployment_id', 'instance_id', 'instances'))):
        raise ValueError('Wrong retained bastion')
    digest = hashlib.sha256(bundle['observer_sources']['assessment-registry.json'].encode()).hexdigest()
    if digest != bundle['contract_sha256'] or json.loads(bundle['observer_sources']['assessment-registry.json']) != bundle['registry']:
        raise ValueError('Public registry binding differs')
    result = subprocess.run(['sudo', '-n', '-u', 'labuser', 'ssh-keygen', '-y', '-f',
        '/home/labuser/.ssh/jdu-web-internal/id_ed25519'], capture_output=True, text=True, timeout=10)
    if result.returncode or ' '.join(result.stdout.split()[:2]) != bundle['expected_public_key']:
        raise ValueError('Keep the original pinned internal SSH key')
    if operation == 'apply':
        if SECRET.exists() or SECRET.is_symlink() or (ROOT / 'state.public.json').exists():
            raise ValueError('Existing fixture credentials/state retained; never apply twice')
        credentials = {profile: dict(setup=secrets.token_urlsafe(32), runtime=secrets.token_urlsafe(32),
            admin=secrets.token_urlsafe(32), django=secrets.token_urlsafe(48)) for profile in ('practice', 'mission')}
        create_private(SECRET, credentials)
        results = []
        checkpoint('credentials_created_by_human_started_apply', results)
        for op, role in (('install-db', 'db'), ('prepare-web', 'web'), ('finalize-db', 'db'), ('start-web', 'web')):
            results.append(peer(bundle, b, op, role, credentials=credentials, profile='practice'))
            checkpoint(op + '_complete', results)
        return dict(fixture_ready=True, active_profile='practice', new_databases=2, new_app_staff=2,
            credential_values_exported=False, old_ssh_rdp_grading_credentials_unchanged=True,
            instance_ids_unchanged=True, results=results, class_ready=False)
    if operation == 'status':
        return read_private(ROOT / 'state.public.json')
    credentials = read_private(SECRET)
    if operation == 'probe':
        return probe(bundle, b, payload, credentials)
    if operation == 'switch':
        if payload.get('profile') not in ('practice', 'mission'):
            raise ValueError('Known retained profile required')
        return peer(bundle, b, 'switch-web', 'web', profile=payload['profile'])
    raise ValueError('Unknown fixture operation')
