"""Observe WEB-02 through existing SSM -> bastion -> pinned internal SSH.

Only public source and probe identifiers enter command history. No configuration,
credentials, key enrollment, package installation or service changes occur here.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys


def execute(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=15, **kwargs)


def run(request):
    if os.geteuid() != 0:
        raise ValueError('Root observer required')
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if any(b[k] != request[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
        raise ValueError('Wrong observer identity')
    source = base64.b64decode(request['contract_source_b64'], validate=True)
    # The controller pins this source inside the signed checker bundle.
    import types
    task = types.ModuleType('http_task')
    exec(compile(source, '<signed-http-task>', 'exec'), task.__dict__)
    spec = task.contract(request['mission_id'])
    nonce = request['nonce']
    if not re.fullmatch('[a-f0-9]{32}', nonce):
        raise ValueError('Wrong probe identifier')
    if b['role'] == 'web':
        if request['operation'] == 'log':
            log = Path('/var/log/nginx/access.log')
            try:
                with log.open('rb') as f:
                    f.seek(max(0, log.stat().st_size - 2 * 1024 * 1024))
                    data = f.read(2 * 1024 * 1024).decode('utf-8', 'replace')
                pattern = r'^' + re.escape(request['bastion_ip']) + r' .*"GET ' + re.escape(spec['path'] + '?jdu_check=' + nonce) + r' HTTP/1\.[01]" 200 '
                return {'current_bastion_request_logged': bool(re.search(pattern, data, re.M))}
            except FileNotFoundError:
                return {'current_bastion_request_logged': False}
        if request['operation'] != 'observe':
            raise ValueError('Unknown operation')
        c = dict(WEB02_IDENTITY=True,
            WEB02_NGINX_ACTIVE=execute(['systemctl', 'is-active', '--quiet', 'nginx']).returncode == 0)
        try:
            c['WEB02_CONFIG_VALID'] = execute(['/usr/sbin/nginx', '-t']).returncode == 0
        except FileNotFoundError:
            c['WEB02_CONFIG_VALID'] = False
        ports = execute(['ss', '-H', '-lnt']).stdout
        c['WEB02_LISTEN_80'] = any(line.split()[3] in ('0.0.0.0:80', '*:80', '[::]:80', ':::80', b['private_ip'] + ':80')
            for line in ports.splitlines() if len(line.split()) >= 4)
        try:
            file = Path(spec['file']); s = file.lstat()
            c['WEB02_FILE'] = (stat.S_ISREG(s.st_mode) and s.st_uid == 0
                and stat.S_IMODE(s.st_mode) == 0o644 and s.st_size <= 65536
                and not any(p.is_symlink() for p in file.parents)
                and file.read_bytes() == spec['body'].encode())
        except FileNotFoundError:
            c['WEB02_FILE'] = False
        c['WEB02_LOCAL_HTTP'] = task.http_probe('127.0.0.1', spec['path'], spec['body'], nonce)
        import urllib.request
        try:
            url = 'http://' + request['repo_ip'] + '/releases/' + b['release_id'] + '/manifests/release.json'
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=5) as response:
                release = json.loads(response.read(262145))
            c['WEB02_REPO_PREREQUISITE'] = release['release_id'] == b['release_id']
        except Exception:
            c['WEB02_REPO_PREREQUISITE'] = None
        return c
    if b['role'] != 'bastion' or request['operation'] != 'collect':
        raise ValueError('Bastion collector required')
    if b['instances']['web'] != request['web_id']:
        raise ValueError('Wrong Web destination')
    root = Path('/home/labuser/.ssh/jdu-web-internal')
    key = execute(['ssh-keygen', '-y', '-f', str(root / 'id_ed25519')])
    if key.returncode or ' '.join(key.stdout.split()[:2]) != request['expected_public_key']:
        raise ValueError('Original internal SSH identity changed')
    guest = base64.b64decode(request['guest_source_b64'], validate=True)
    code = "import base64;exec(base64.b64decode('" + base64.b64encode(guest).decode() + "'))"
    def peer(operation):
        r = dict(request, role='web', instance_id=request['web_id'], operation=operation,
                 bastion_ip=request['bastion_ip'])
        result = execute(['sudo', '-n', '-u', 'labuser', 'ssh', '-F', str(root / 'config'), 'web',
                          'sudo -n python3 -c ' + shlex.quote(code)], input=json.dumps(r))
        if result.returncode:
            raise ValueError('Pinned Web observation unavailable')
        return json.loads(result.stdout)
    checks = dict.fromkeys(task.CHECKS)
    try:
        checks.update(peer('observe'))
    except (ValueError, subprocess.TimeoutExpired):
        pass
    checks['WEB02_BASTION_HTTP'] = task.http_probe(request['web_ip'], spec['path'], spec['body'], nonce)
    try:
        checks['WEB02_ACCESS_LOG'] = peer('log')['current_bastion_request_logged']
    except (ValueError, subprocess.TimeoutExpired):
        pass
    return dict(scope='web02_current_state_no_points', checked_at=datetime.now(timezone.utc).isoformat(),
        mission_id=request['mission_id'], lab_id=b['lab_id'], deployment_id=b['deployment_id'],
        instance_id=request['web_id'], nonce=nonce, checks=checks, class_ready=False,
        same_private_key_and_strict_host_pins_used=True, credentials_exported=False)


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.loads(sys.stdin.read(262145))), separators=(',', ':')))
    except Exception as exc:
        print('HTTP_TASK_OBSERVER_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
