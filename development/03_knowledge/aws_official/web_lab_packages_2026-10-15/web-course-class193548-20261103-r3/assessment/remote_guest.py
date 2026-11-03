"""Bastion aggregation through pinned SSH. Only this host submits using its existing token."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from app_probe import probe, public_match
from db_observer import admin_sql, literal
from network_checks import http, inventory, normal_resolve
from registry import TASKS, REGISTRY, canonical_checks, build_report, validate_report
from system_observer import observe, merge_all


def identity(request):
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if os.geteuid() != 0 or any(b[k] != request[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
        raise ValueError('Wrong observer identity')
    return b


def peer(request, role, *, operation='observe', code=None):
    payload = {k: request[k] for k in ('lab_id', 'deployment_id', 'task_id', 'run_id')}
    payload.update(role=role, instance_id=request['instances'][role], operation=operation)
    if code is not None:
        payload['code'] = code
    packed = dict(request=payload, sources=PUBLIC_SOURCES)
    command = 'sudo -n python3 -c ' + shlex.quote(LOADER_SOURCE)
    proc = subprocess.run(['sudo', '-n', '-u', 'labuser', 'ssh', '-F', '/home/labuser/.ssh/jdu-web-internal/config',
                           '-o', 'ConnectTimeout=5', role, command], input=json.dumps(packed), capture_output=True, text=True, timeout=100)
    if proc.returncode != 0:
        raise ValueError('Peer observation unavailable')
    return json.loads(proc.stdout)


def record(request):
    code = request['code']
    nonce = request['run_id'].replace('-', '')[:12]
    if not re.fullmatch(r'CK-[PMD]-' + re.escape(nonce), code):
        raise ValueError('Only this run\'s probe record can be observed')
    profile = TASKS[request['task_id']]['profile']
    data = admin_sql("SELECT json_build_object('row',(SELECT json_build_object('id',id,'code',code,'name',name,"
        "'quantity',quantity,'location',location,'is_public',is_public) FROM catalog_item WHERE code=" + literal(code) + '))', REGISTRY['profiles'][profile]['db_name'])
    if data is None:
        raise ValueError('Probe database observation unavailable')
    return data


def collect(request, *, password=None):
    b = identity(request)
    if b['role'] != 'bastion' or b['instances'] != request['instances']:
        raise ValueError('The registered bastion aggregates this deployment')
    key = subprocess.run(['sudo', '-n', '-u', 'labuser', 'ssh-keygen', '-y', '-f',
                          '/home/labuser/.ssh/jdu-web-internal/id_ed25519'], capture_output=True, text=True, timeout=5)
    if key.returncode != 0 or ' '.join(key.stdout.split()[:2]) != request['expected_public_key']:
        raise ValueError('The original bastion SSH key must be retained')
    task = TASKS[request['task_id']]; number = int(task['id'][1:])
    import concurrent.futures
    results = {'bastion': observe(request)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {role: pool.submit(peer, request, role) for role in ('web', 'dns', 'db', 'repo')}
        for role, future in futures.items():
            try:
                results[role] = future.result()
            except (ValueError, OSError, subprocess.SubprocessError):
                results[role] = None
    checks = {cid: None for cid in canonical_checks(task['id'])}
    for value in results.values():
        if value:
            checks.update(value['checks'])
    all_ok = all(r and r.get('identity_ok') is True for r in results.values())
    checks.update(WEB_READY_IDENTITY=all_ok, WEB_READY_MANAGEMENT=all_ok,
                  WEB_READY_NETWORK_BASELINE=request.get('network_baseline'),
                  WEB01_SELF_IDENTITY=True, WEB01_ROLE_ENDPOINTS=all_ok, WEB01_MANAGEMENT=all_ok)
    source = http('10.20.2.30', '/releases/' + b['release_id'] + '/manifests/release.json')
    if source and source[0] == 200:
        try:
            repo = json.loads(source[2])
            checks['WEB_READY_PACKAGE_SOURCE'] = repo.get('release_id') == b['release_id']
        except ValueError:
            checks['WEB_READY_PACKAGE_SOURCE'] = False
    else:
        checks['WEB_READY_PACKAGE_SOURCE'] = None if source is None else False
    evidence = {r: (v or {}).get('evidence', {}) for r, v in results.items()}
    dependency = []
    if number == 2:
        predecessor = TASKS['P1' if task['id'].startswith('P') else 'M1']['expected']
        needed = http('10.20.1.20', predecessor['path'])
        dependency.append(None if needed is None else needed[0] == 200 and needed[2] == predecessor['body'])
    if number in (4, 5, 6):
        dependency += [evidence[r].get('normal_resolver') for r in ('bastion', 'web')]
        dependency.append(evidence['web'].get('db_name'))
    if number >= 5:
        dependency += [checks.get(c) for c in ('WEB05_WEB_SQL', 'WEB05_DATABASE_OWNER', 'WEB05_ROLE_ATTRIBUTES')]
    if number == 2:
        clients = [evidence[r].get('dns_client', {}) for r in ('bastion', 'web')]
        checks['WEB03_UDP_RESPONSE'] = merge_all([x.get('udp') for x in clients])
        checks['WEB03_TCP_RESPONSE'] = merge_all([x.get('tcp') for x in clients])
        checks['WEB03_AXFR_DENIED'] = merge_all([x.get('axfr') for x in clients])
        checks['WEB03_NORMAL_RESOLVER'] = merge_all([evidence[r].get('normal_resolver') for r in ('bastion', 'web')])
        checks['WEB03_DB_NAME'] = evidence['web'].get('db_name')
        expected = task['expected']
        response = http(expected['http_name'], expected['http_path']) if normal_resolve(expected['http_name'], '10.20.1.20') else None
        body = TASKS['P1' if task['id'].startswith('P') else 'M1']['expected']['body']
        checks['WEB03_NAMED_HTTP'] = None if response is None else response[0] == 200 and response[2] == body
    if number == 3:
        after = evidence['web']; before, stopped = request.get('before'), request.get('stopped')
        volume = request['root_volumes']['web']
        checks['WEB04_VOLUME_READINESS'] = None if not after else after.get('root_volume') in volume and after.get('on_root_filesystem') is True
        checks['WEB04_STOP_START_RETENTION'] = None
        if before and stopped and after:
            keys = ('lab_id', 'deployment_id', 'task_id', 'instance_id')
            valid = all(before.get(k) == stopped.get(k) == request.get(k if k != 'instance_id' else 'web_instance_id') for k in keys)
            checks['WEB04_STOP_START_RETENTION'] = (valid and stopped.get('state') == 'stopped'
                and before.get('evidence_id') == stopped.get('evidence_id')
                and before.get('root_volume') == stopped.get('root_volume') == after.get('root_volume')
                and before.get('marker_sha256') == after.get('marker_sha256')
                and bool(before.get('boot_id')) and before['boot_id'] != after.get('boot_id'))
    if number >= 5:
        profile = task['profile']; expected = REGISTRY['profiles'][profile]
        public = http('web.lab.test') if normal_resolve('web.lab.test', '10.20.1.20') else None
        rows = None
        try:
            rows = inventory(public[2]) if public and public[0] == 200 else None
        except ValueError:
            pass
        visible = [r for r in expected['records'] if r['is_public']]
        checks['WEB06_PUBLIC_DATA'] = None if public is None else rows is not None and all(
            rows.get(r['code'], [])[:3] == [r['name'], str(r['quantity']), r['location']] for r in visible) and checks.get('WEB06_REQUIRED_RECORDS') is True
        private_codes = evidence['db'].get('private_codes')
        checks['WEB07_PRIVATE_DATA_HIDDEN'] = None if rows is None or private_codes is None else (
            checks['WEB06_PUBLIC_DATA'] is True and all(code not in rows for code in private_codes))
        admin = http('admin.lab.test', '/admin/login/', port=8080, host='admin.lab.test:8080') if normal_resolve('admin.lab.test', '10.20.1.20') else None
        checks['WEB06_ADMIN_ENTRY'] = None if admin is None else admin[0] == 200 and all(s in admin[2] for s in ('csrfmiddlewaretoken', 'username', 'password'))
        styles = [http('web.lab.test', '/static/catalog/inventory.css', host='web.lab.test'),
                  http('admin.lab.test', '/static/admin/css/base.css', port=8080, host='admin.lab.test:8080')]
        checks['WEB06_STATIC'] = None if any(s is None for s in styles) else all(s[0] == 200 and 'text/css' in s[1].get('content-type', '') and len(s[2]) > 20 for s in styles)
        denied = [http('10.20.1.20', path, host='admin.lab.test:8080', headers={'X-JDU-Entry': 'admin'})
                  for path in ('/admin', '/admin/', '/admin/catalog/item/add/', '//admin/', '/%61dmin/')]
        checks['WEB07_PUBLIC_ADMIN_DENIED'] = None if any(d is None for d in denied) else public is not None and public[0] == 200 and all(d[0] in (403, 404) for d in denied)
        secret_paths = [http('10.20.1.20', path) for path in ('/.env', '/app.env', '/setup.env', '/etc/jdu-catalog/app.env', '/static/app.env')]
        checks['WEB07_SECRET_HTTP_DENIED'] = None if any(d is None for d in secret_paths) else (
            checks.get('WEB07_SECRET_FILES_OUTSIDE_PUBLIC') is True and public is not None and public[0] == 200 and all(d[0] in (403, 404) for d in secret_paths))
        checks['WEB07_SETUP_RETIRED'] = merge_all([checks.get('WEB07_SETUP_ROLE_RETIRED'), checks.get('WEB07_SETUP_FILE_RETIRED')])
        if evidence['web'].get('active_profile') not in (None, profile):
            # Keep the practice history without grading the inactive runtime as broken.
            for cid in task['progress_scored_checks']:
                checks[cid] = None
        elif password is not None and checks.get('WEB06_ADMIN_ENTRY') is True and checks.get('WEB06_PROFILE_DATABASE') is True:
            checks.update(probe(profile, request['run_id'].replace('-', ''), password,
                                lambda code: peer(request, 'db', operation='record', code=code)['row']))
        if number == 6:
            dependency += [checks.get(c) for c in ('WEB06_SERVICE', 'WEB06_PROFILE_DATABASE', 'WEB06_PUBLIC_DATA',
                                                  'WEB06_PASSWORD_LOGIN', 'WEB06_CREATE_REFLECT')]
    checks['WEB_READY_DEPENDENCIES'] = merge_all(dependency)
    identity_data = {k: b[k] for k in ('lab_id', 'release_id', 'deployment_id', 'instances')}
    report = build_report(task['id'], identity_data, {cid: checks.get(cid) for cid in canonical_checks(task['id'])},
                          request['run_id'], mode='functional' if password is not None else 'read_only',
                          checked_at=datetime.now(timezone.utc).isoformat())
    return dict(report=report, storage_evidence=evidence['web'] if number == 3 else {})


def submit(report):
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    validate_report(report, b['instances'])
    if b['role'] != 'bastion' or any(report[k] != b[k] for k in ('lab_id', 'release_id', 'deployment_id')):
        raise ValueError('Wrong registered submitter')
    from system_observer import valid_secret_metadata
    path = Path('/etc/jdu-web/progress.credentials.json')
    if not valid_secret_metadata(path):
        raise ValueError('Stored credential protection changed')
    config = json.loads(path.read_text())
    if config['api_base_url'] != b['grading_api_url'] or config['fixed_ingress_ipv4'] != b['grading_ipv4']:
        raise ValueError('Wrong grading destination')
    source = Path('/usr/local/lib/jdu-web') / b['release_id'] / 'web_progress.py'
    spec = importlib.util.spec_from_file_location('web_progress', source)
    client = importlib.util.module_from_spec(spec); spec.loader.exec_module(client)
    root = Path('/var/lib/jdu-web/assessment-results')
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise ValueError('Unsafe retained report directory')

    def retain(name, value):
        p = root / name
        data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
        if p.exists() or p.is_symlink():
            if not valid_secret_metadata(p) or p.read_bytes() != data:
                raise ValueError('Original pending body/receipt retained')
        else:
            with os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as f:
                f.write(data)
    retain(report['request_id'] + '.report.json', report)
    receipt = client.submit(config, report)
    retain(report['request_id'] + '.receipt.json', receipt)
    if client.submit(config, report) != receipt:
        raise ValueError('Idempotent receipt differs')
    return dict(receipt=receipt, exact_retry_same_receipt=True, credentials_exported=False)


def run(request):
    identity(request)
    if request['operation'] == 'interactive-result' and request['role'] == 'bastion':
        import uuid
        run_id = str(uuid.UUID(request['run_id']))
        if run_id != request['run_id']:
            raise ValueError('Wrong interactive run ID')
        path = Path('/var/lib/jdu-web/assessment-interactive-' + run_id + '.result.json')
        from system_observer import valid_secret_metadata
        if not valid_secret_metadata(path):
            raise ValueError('Interactive result protection changed')
        result = json.loads(path.read_text())
        b = identity(request)
        validate_report(result['report'], b['instances'])
        if result['report']['run_id'] != run_id or result['report']['mission_id'] != request['task_id']:
            raise ValueError('Wrong interactive result')
        return result
    if request['operation'] == 'observe':
        return observe(request)
    if request['operation'] == 'record' and request['role'] == 'db':
        return record(request)
    if request['operation'] == 'collect':
        return collect(request)
    if request['operation'] == 'submit' and request['role'] == 'bastion':
        return submit(request['report'])
    raise ValueError('Unsupported read-only operation')
