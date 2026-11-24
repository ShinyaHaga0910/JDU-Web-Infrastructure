"""Per-host read-only state collectors. Output is booleans and bounded public evidence."""
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat

from db_observer import database_observations, read_runtime, web_database, admin_sql, literal, authenticated_sql
from network_checks import active, command, dns_client, dns_server, normal_resolve, resolver_policy
from registry import COURSE_INTRO_MARKERS, REGISTRY, TASKS


def merge_all(values):
    return False if any(v is False for v in values) else None if any(v is None for v in values) else True


def root_volume(blocks):
    """Resolve the mounted / device to its EBS disk serial, including partition children."""
    matches = []

    def walk(rows, parents=()):
        for row in rows:
            lineage = (*parents, row)
            if '/' in (row.get('mountpoints') or []):
                serials = [r.get('serial', '').strip().replace('-', '') for r in lineage if r.get('serial')]
                matches.extend('vol-' + s[3:] for s in serials if re.fullmatch(r'vol[0-9a-f]{8,17}', s))
            walk(row.get('children', []), lineage)
    walk(blocks)
    return matches[0] if len(set(matches)) == 1 else None


def storage(task, lab_id):
    expected = task['expected']; path = Path(expected['file'])
    out, aux = {}, {}
    try:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Marker links are forbidden')
        s = path.stat(); parent = path.parent.stat()
        raw = path.read_bytes() if s.st_size <= 65536 else b''
        out['WEB04_MARKER_CONTENT'] = stat.S_ISREG(s.st_mode) and raw == expected['body_template'].format(lab_id=lab_id).encode()
        out['WEB04_MARKER_PERMISSIONS'] = (s.st_uid == s.st_gid == 0 and stat.S_IMODE(s.st_mode) == 0o644
                                            and parent.st_uid == parent.st_gid == 0 and stat.S_IMODE(parent.st_mode) == 0o755)
        aux['marker_sha256'] = hashlib.sha256(raw).hexdigest()
        aux['on_root_filesystem'] = s.st_dev == Path('/').stat().st_dev
    except (OSError, ValueError):
        out.update(WEB04_MARKER_CONTENT=False, WEB04_MARKER_PERMISSIONS=False)
        aux['on_root_filesystem'] = False
    p = command(['lsblk', '--json', '--output', 'NAME,PATH,TYPE,SERIAL,MOUNTPOINTS'])
    try:
        aux['root_volume'] = root_volume(json.loads(p.stdout)['blockdevices']) if p and p.returncode == 0 else None
    except (ValueError, KeyError):
        aux['root_volume'] = None
    free = os.statvfs('/var/lib')
    out['WEB04_CAPACITY_READINESS'] = (free.f_bavail * free.f_frsize >= 2 * 1024 ** 3
                                      and free.f_blocks > 0 and free.f_bavail / free.f_blocks >= .20)
    aux['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return out, aux


def valid_secret_metadata(path):
    try:
        s = path.lstat()
        return stat.S_ISREG(s.st_mode) and s.st_uid == s.st_gid == 0 and stat.S_IMODE(s.st_mode) == 0o600 and s.st_nlink == 1
    except OSError:
        return False


def sudo_policy_denied(result):
    """Require an explicit whole-policy denial, including sudo versions returning 0."""
    if result is None:
        return None
    text = result.stdout.strip()
    if result.returncode in (0, 1) and re.fullmatch(
            r'User catalog is not allowed to run sudo on [A-Za-z0-9_.-]+\.', text):
        return True
    if result.returncode == 0 and 'may run the following commands' in text:
        return False
    # Empty output, a policy error or an unexpected translation is not evidence
    # that the service account has no privileges.
    return None


def code_protected(root):
    try:
        user = pwd.getpwnam('catalog')
        if user.pw_uid == 0 or user.pw_shell not in ('/usr/sbin/nologin', '/bin/false'):
            return False
        group = command(['id', '-nG', 'catalog'])
        if group is None or {'sudo', 'wheel'} & set(group.stdout.split()):
            return False
        sudo = command(['sudo', '-n', '-l', '-U', 'catalog'])
        denied = sudo_policy_denied(sudo)
        if denied is not True:
            return denied
        paths = [root, *root.parents]
        for directory in (root, root.parent / 'venv'):
            if not directory.is_dir():
                return False
            found = list(directory.rglob('*'))
            if len(found) > 12000:
                return None
            paths += found
        # A single subprocess avoids spawning thousands of test processes.
        check = "import os,sys;raise SystemExit(any(os.access(p,os.W_OK) for p in sys.argv[1:]))"
        p = command(['sudo', '-n', '-u', 'catalog', 'python3', '-c', check, *map(str, paths)], timeout=20)
        return None if p is None else p.returncode == 0
    except (OSError, KeyError):
        return False


def application(profile):
    out, aux = {}, {}
    root = Path('/opt/jdu-catalog/app')
    try:
        manifest = json.loads((root / 'APP-MANIFEST.json').read_text())
        entries = manifest['files']
        valid = (manifest == REGISTRY.get('application_manifest') and manifest['artifact'] == 'jdu-catalog'
                 and len(entries) == len({e['path'] for e in entries}))
        for e in entries:
            relative = Path(e['path'])
            if (relative.is_absolute() or '..' in relative.parts
                    or any(p.is_symlink() for p in [root / relative, *(root / relative).parents] if p == root or root in p.parents)):
                valid = False; break
            p = root / relative
            valid &= p.is_file() and len(p.read_bytes()) == e['size_bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == e['sha256']
        out['WEB06_ARTIFACTS'] = bool(valid)
    except (OSError, ValueError, KeyError):
        out['WEB06_ARTIFACTS'] = False
    properties = command(['systemctl', 'show', 'jdu-catalog', '--property=User,MainPID,ActiveState'])
    info = dict(line.split('=', 1) for line in properties.stdout.splitlines() if '=' in line) if properties else {}
    enabled = command(['systemctl', 'is-enabled', '--quiet', 'jdu-catalog'])
    out['WEB06_SERVICE'] = info.get('ActiveState') == 'active' and info.get('User') == 'catalog' and enabled is not None and enabled.returncode == 0
    listeners = command(['ss', '-H', '-ltn'])
    endpoints = {line.split()[3] for line in listeners.stdout.splitlines() if len(line.split()) >= 4 and line.split()[3].endswith(':8000')} if listeners else None
    out['WEB06_LOOPBACK'] = None if endpoints is None else endpoints == {'127.0.0.1:8000'}
    config = read_runtime(profile)
    try:
        active_env = Path('/etc/jdu-catalog/app.env').read_text()
        active_pairs = dict(line.split('=', 1) for line in active_env.splitlines() if line and not line.startswith('#'))
        aux['active_profile'] = next((key for key, p in REGISTRY['profiles'].items() if json.loads(active_pairs.get('DB_NAME', '""')) == p['db_name']), None)
    except (OSError, ValueError):
        aux['active_profile'] = None
    db = authenticated_sql(profile, 'db.lab.test') if config else None
    process_matches = False
    try:
        pid = int(info.get('MainPID', '0'))
        if pid > 0 and config:
            proc = dict(entry.split(b'=', 1) for entry in Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0') if b'=' in entry)
            process_matches = all(proc.get(k.encode()) == config[k].encode() for k in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'))
    except (OSError, ValueError):
        pass
    out['WEB06_PROFILE_DATABASE'] = bool(config and db and db['ok'] and process_matches and aux['active_profile'] == profile)
    secrets = [Path('/etc/jdu-catalog/app.env')]
    runtime = Path(REGISTRY['profiles'][profile]['db_runtime_env'])
    if runtime.exists() or runtime.is_symlink():
        secrets.append(runtime)
    out['WEB07_SECRET_PERMISSIONS'] = all(valid_secret_metadata(p) for p in secrets)
    out['WEB07_CODE_PROTECTED'] = code_protected(root)
    setup_files = [Path('/etc/jdu-catalog/setup.env'), Path('/etc/jdu-catalog/profiles') / (profile + '.setup.env')]
    out['WEB07_SETUP_FILE_RETIRED'] = all(not p.exists() and not p.is_symlink() for p in setup_files)
    # A name-based filesystem check is combined with real HTTP refusals by the bastion.
    public = Path('/var/lib/jdu-catalog/static')
    out['WEB07_SECRET_FILES_OUTSIDE_PUBLIC'] = public.is_dir() and not any(
        (folder / p.name).exists() or (folder / p.name).is_symlink()
        for folder in (public, Path('/var/www/html')) for p in secrets + [Path('setup.env'), Path('.env')])
    return out, aux


def connection_marker(role, filename):
    """Read a small, student-owned file without following links or changing it."""
    try:
        user = pwd.getpwnam('ssm-user')
        home = Path(user.pw_dir)
        if not home.is_absolute() or home.resolve() != home:
            return False
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(home / filename, flags)
        try:
            info = os.fstat(fd)
            expected = (role + '\n').encode()
            return (stat.S_ISREG(info.st_mode) and info.st_uid == user.pw_uid
                    and os.read(fd, len(expected) + 1) == expected)
        finally:
            os.close(fd)
    except (FileNotFoundError, KeyError):
        return False
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EISDIR):
            return False
        return None


def observe(request):
    if os.geteuid() != 0:
        raise ValueError('Root observer required')
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if any(b[k] != request[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
        raise ValueError('Observer belongs to another deployment')
    task = TASKS[request['task_id']]
    role, number = b['role'], int(request['task_id'][1:])
    out, aux = {}, {}
    for check_id, marker_role, filename in COURSE_INTRO_MARKERS.get(task['id'], ()):
        if role == marker_role:
            out[check_id] = connection_marker(role, filename)
    profile = task.get('profile', 'mission')
    if number in (2, 4, 5, 6) and role in ('bastion', 'web'):
        dns_task = TASKS[('P' if request['task_id'].startswith('P') and number == 2 else 'M') + '2']
        records = dns_task['expected']['records']
        aux['dns_client'] = dns_client(records)
        aux['normal_resolver'] = resolver_policy(records, firefox=role == 'bastion')
        aux['db_name'] = normal_resolve(dns_task['expected']['db_name'], '10.20.2.20')
    if number == 2 and role == 'dns':
        out.update(dns_server(task['expected']['records'], request['run_id'].replace('-', '')))
    if number == 3 and role == 'web':
        out, aux = storage(task, request['lab_id'])
    if number in (4, 5, 6) and role == 'db':
        out.update(database_observations(profile, app=number >= 5))
        if number >= 5:
            db = REGISTRY['profiles'][profile]['db_name']
            codes = admin_sql("SELECT COALESCE(json_agg(code),'[]'::json) FROM (SELECT code FROM catalog_item WHERE NOT is_public LIMIT 1001) x", db)
            aux['private_codes'] = codes if codes is not None and len(codes) <= 1000 else None
    if number in (4, 5, 6) and role == 'web':
        out.update(web_database(profile, task.get('connection_host', 'db.lab.test')))
    if number >= 5 and role == 'web':
        app, evidence = application(profile)
        out.update(app); aux.update(evidence)
    return dict(identity_ok=True, role=role, instance_id=b['instance_id'], checks=out, evidence=aux)
