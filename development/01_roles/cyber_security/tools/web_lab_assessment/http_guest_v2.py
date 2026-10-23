"""D11 HTTP observer: retain D08 checks and accept the catalog's fixed access log."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys

LEGACY_SHA256 = 'd0f7e10575f2db17047df3b8fc22fbfb545e7bb4aa3d240d49f915135e326ac0'
CONTRACT_SHA256 = '5f50d4b586630c93b0c4c3274dc8ac0bc05a4d6bba9d35f1145ecf2c24cb2462'
LOGS = ('/var/log/nginx/access.log', '/var/log/nginx/jdu-catalog-public.access.log')


def current_log_matches(request, spec, paths=LOGS):
    if not re.fullmatch('[a-f0-9]{32}', request['nonce']):
        raise ValueError('Current HTTP nonce required')
    pattern = r'^' + re.escape(request['bastion_ip']) + r' .*"GET ' + re.escape(
        spec['path'] + '?jdu_check=' + request['nonce']) + r' HTTP/1\.[01]" 200 '
    for name in paths:
        path = Path(name)
        try:
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 2 * 1024 * 1024))
                text = stream.read(2 * 1024 * 1024).decode('utf-8', 'replace')
            if re.search(pattern, text, re.M):
                return True
        except FileNotFoundError:
            continue
    return False


def run(request):
    original = base64.b64decode(LEGACY_SOURCE_B64, validate=True)
    if hashlib.sha256(original).hexdigest() != LEGACY_SHA256:
        raise ValueError('Retain the original D08 HTTP observations')
    if request['role'] == 'web' and request['operation'] == 'log':
        b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
        if os.geteuid() != 0 or any(b[k] != request[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
            raise ValueError('Wrong registered Web')
        contract = base64.b64decode(request['contract_source_b64'], validate=True)
        if hashlib.sha256(contract).hexdigest() != CONTRACT_SHA256:
            raise ValueError('HTTP task contract changed')
        namespace = {'__name__': '_trusted_http_contract'}
        exec(compile(contract, '<trusted-http-contract>', 'exec'), namespace)
        spec = namespace['contract'](request['mission_id'])
        return dict(current_bastion_request_logged=current_log_matches(request, spec))
    namespace = {'__name__': '_trusted_d08_http_guest'}
    exec(compile(original, '<trusted-d08-http-guest>', 'exec'), namespace)
    return namespace['run'](request)


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin)), separators=(',', ':')))
    except Exception as exc:
        print('D11_HTTP_OBSERVER_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
