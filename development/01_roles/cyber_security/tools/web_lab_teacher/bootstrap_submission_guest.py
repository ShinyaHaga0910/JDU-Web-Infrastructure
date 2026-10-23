"""Submit an immutable observed report using the bastion's stored token."""
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import uuid


def checked(path, mode):
    s = path.lstat()
    if s.st_uid != 0 or stat.S_IMODE(s.st_mode) != mode or not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise ValueError('Unsafe report or credential path')


def retained(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if path.exists() or path.is_symlink():
        checked(path, 0o600)
        if path.read_bytes() != data:
            raise ValueError('Existing pending report or receipt retained')
    else:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as f:
            f.write(data)


def validate(report, bootstrap):
    fields = {'schema_version', 'kind', 'lab_id', 'release_id', 'deployment_id', 'request_id', 'checks'}
    if report.get('kind') == 'assessment':
        fields.add('mission_id')
        if report.get('mission_id') not in {'P1', 'M1'}:
            raise ValueError('Unsupported WEB-02 assessment')
    if (set(report) != fields or report['schema_version'] != 1 or type(report['schema_version']) is not int
            or report['kind'] not in {'bootstrap', 'assessment'} or bootstrap['role'] != 'bastion'
            or any(report[k] != bootstrap[k] for k in ('lab_id', 'release_id', 'deployment_id'))):
        raise ValueError('Wrong bootstrap report identity or kind')
    request_id = uuid.UUID(report['request_id'])
    if request_id.version != 4 or str(request_id) != report['request_id']:
        raise ValueError('Invalid request ID')
    if set(bootstrap['instances']) != {'bastion', 'web', 'dns', 'db', 'repo'}:
        raise ValueError('Five roles required')
    if type(report['checks']) is not list or not 1 <= len(report['checks']) <= 100:
        raise ValueError('Invalid checks')
    seen = set()
    for c in report['checks']:
        if (set(c) != {'id', 'role', 'instance_id', 'status'}
                or not re.fullmatch(r'[A-Z][A-Z0-9_-]{1,47}', c['id'])
                or c['role'] not in bootstrap['instances']
                or c['instance_id'] != bootstrap['instances'][c['role']]
                or c['status'] not in {'PASS', 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE'}
                or (c['role'], c['id']) in seen):
            raise ValueError('Invalid check identity, status or duplicate')
        seen.add((c['role'], c['id']))


def run(request):
    if os.geteuid() != 0:
        raise ValueError('Root helper required')
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    report = request['report']
    validate(report, b)
    config_path = Path('/etc/jdu-web/progress.credentials.json')
    checked(config_path, 0o600)
    config = json.loads(config_path.read_text())
    if (set(config) != {'schema_version', 'api_base_url', 'fixed_ingress_ipv4', 'release_id', 'lab_id', 'lab_token'}
            or config['api_base_url'] != b['grading_api_url'] or config['fixed_ingress_ipv4'] != b['grading_ipv4']):
        raise ValueError('Wrong stored grading credential')
    client_path = Path('/usr/local/lib/jdu-web') / b['release_id'] / 'web_progress.py'
    checked(client_path, 0o644)
    spec = importlib.util.spec_from_file_location('web_progress', client_path)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    root = Path('/var/lib/jdu-web/bootstrap')
    pending = root / ('progress-' + report['request_id'] + '.pending.json')
    receipt_path = root / ('progress-' + report['request_id'] + '.receipt.json')
    retained(pending, report)  # Persist BEFORE network; retries always use the original body.
    first = client.submit(config, report)
    retained(receipt_path, first)
    second = client.submit(config, report)
    if second != first:
        raise ValueError('Idempotent retry receipt differs')
    return dict(receipt=first, exact_retry_same_receipt=True, check_count=len(report['checks']),
                passed=sum(c['status'] == 'PASS' for c in report['checks']),
                credential_exported=False, class_ready=False)


if __name__ == '__main__':
    try:
        import sys
        os.umask(0o077)
        print(json.dumps(run(json.loads(sys.stdin.read(65537))), separators=(',', ':')))
    except Exception as exc:
        print('BOOTSTRAP_SUBMISSION_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
