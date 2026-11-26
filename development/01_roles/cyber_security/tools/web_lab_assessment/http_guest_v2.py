"""D11 HTTP observer: retain D08 checks and accept the catalog's fixed access log."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import sys

LEGACY_SHA256 = 'd0f7e10575f2db17047df3b8fc22fbfb545e7bb4aa3d240d49f915135e326ac0'
CONTRACT_SHA256 = '4f7106a170154ba21577956a60246c05a51757876854e9a685caefed155b8be4'
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


def custom_root_config(text, specs):
    """Read exact location/root directives from nginx -T, ignoring comments."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars='{};')
    lexer.whitespace_split = True
    tokens = [piece for token in lexer for piece in
              (list(token) if token and all(c in '{};' for c in token) else [token])]
    tree, stack, statement = [], [], []
    current = tree
    try:
        for token in tokens:
            if token == '{':
                child = []
                current.append((statement, child))
                stack.append(current)
                current, statement = child, []
            elif token == '}':
                if statement:
                    return False
                current = stack.pop()
            elif token == ';':
                current.append((statement, None))
                statement = []
            else:
                statement.append(token)
    except (IndexError, ValueError):
        return False
    if stack or statement:
        return False
    found = set()
    def visit(nodes):
        for header, children in nodes:
            if children is not None:
                for spec in specs:
                    if header == ['location', '=', spec['path']] and any(
                            h == ['root', str(PurePosixPath(spec['file']).parent)] and c is None for h, c in children):
                        found.add(spec['path'])
                visit(children)
    visit(tree)
    return found == {s['path'] for s in specs}


def current_file(spec):
    import grp
    path = Path(spec['file'])
    try:
        info = path.lstat()
        return (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and info.st_gid == grp.getgrnam('www-data').gr_gid
                and stat.S_IMODE(info.st_mode) == 0o640 and info.st_size <= 65536
                and not any(parent.is_symlink() for parent in path.parents)
                and path.read_bytes() == spec['body'].encode())
    except (FileNotFoundError, KeyError):
        return False


def run(request):
    original = base64.b64decode(LEGACY_SOURCE_B64, validate=True)
    if hashlib.sha256(original).hexdigest() != LEGACY_SHA256:
        raise ValueError('Retain the original D08 HTTP observations')
    contract = base64.b64decode(request['contract_source_b64'], validate=True)
    if hashlib.sha256(contract).hexdigest() != CONTRACT_SHA256:
        raise ValueError('HTTP task contract changed')
    task = {'__name__': '_trusted_http_contract'}
    exec(compile(contract, '<trusted-http-contract>', 'exec'), task)
    spec = task['contract'](request['mission_id'])
    if request['role'] == 'web' and request['operation'] == 'log':
        b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
        if os.geteuid() != 0 or any(b[k] != request[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
            raise ValueError('Wrong registered Web')
        return dict(current_bastion_request_logged=current_log_matches(request, spec))
    namespace = {'__name__': '_trusted_d08_http_guest'}
    exec(compile(original, '<trusted-d08-http-guest>', 'exec'), namespace)
    result = namespace['run'](request)
    if request['role'] == 'web' and request['operation'] == 'observe':
        result['WEB02_FILE'] = current_file(spec)
        specs = [task['contract']('P1'), spec] if request['mission_id'] == 'M1' else [spec]
        try:
            config = namespace['execute'](['/usr/sbin/nginx', '-T'])
            result['WEB02_CONFIG_VALID'] = (result['WEB02_CONFIG_VALID'] and config.returncode == 0
                                           and custom_root_config(config.stdout, specs))
        except FileNotFoundError:
            result['WEB02_CONFIG_VALID'] = False
        if request['mission_id'] == 'M1':
            practice = specs[0]
            result['WEB02_LOCAL_HTTP'] = result['WEB02_LOCAL_HTTP'] and task['http_probe'](
                '127.0.0.1', practice['path'], practice['body'], request['nonce'])
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin)), separators=(',', ':')))
    except Exception as exc:
        print('D11_HTTP_OBSERVER_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
