"""Read-only fresh service/network/SSH evidence after the five-node stop/start."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import stat
import subprocess


def active(unit):
    return subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode == 0


def per_node(request):
    c = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if any(c[k] != request[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
        raise ValueError('Wrong node identity')
    network_path = Path('/usr/local/lib/jdu-web/web-2026-10-r1/network_probe.py')
    if hashlib.sha256(network_path.read_bytes()).hexdigest() != request['network_source_sha256']:
        raise ValueError('Network probe differs from accepted source')
    spec = importlib.util.spec_from_file_location('probe', network_path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    network = {'repo_http': probe.repo_health(c), 's3_denied': not probe.connects(c['s3_probe_ipv4']),
               'direct_api_egress_denied': not probe.connects(c['direct_api_probe_ipv4'])}
    network['fixed_teacher_https' if c['role'] == 'bastion' else 'teacher_ingress_denied'] = (
        probe.teacher_health(c) if c['role'] == 'bastion' else not probe.connects(c['grading_ipv4']))
    retained = json.loads(Path('/var/lib/jdu-web/bootstrap/role-state.json').read_text())
    checks = {'ssh_service_or_socket_ready': active('ssh') or active('ssh.socket'),
        'chrony_active': active('chrony'), 'root_space_at_least_2_gib': shutil.disk_usage('/').free >= 2*1024**3,
        'initial_role_state_retained': all(retained.get(k) == c[k] for k in ('role', 'instance_id', 'deployment_id'))
            and all(v is True for v in retained['checks'].values())}
    forbidden = {'web': 'nginx', 'dns': 'bind9', 'db': 'postgresql-16'}
    if c['role'] in forbidden:
        status = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Status}', forbidden[c['role']]],
                                capture_output=True, text=True)
        checks['student_service_still_not_installed'] = status.stdout.strip() != 'installed'
    if c['role'] == 'bastion':
        checks.update(rdp_active=active('xrdp') and active('xrdp-sesman'),
            desktop_browser_dbus_present=all(shutil.which(p) for p in ('startxfce4', 'firefox', 'dbus-run-session')),
            labuser_not_sudo='sudo' not in subprocess.run(['id', '-nG', 'labuser'],
                capture_output=True, text=True).stdout.split())
    if c['role'] == 'repo':
        checks['repository_nginx_active'] = active('nginx')
    return {'role': c['role'], 'instance_id': c['instance_id'], 'checks': checks, 'network': network,
            'all_checks_passed': all(checks.values()) and all(network.values()),
            'probe_ipv4s': [c['s3_probe_ipv4'], c['direct_api_probe_ipv4']]}


def run(request):
    if os.geteuid() != 0:
        raise ValueError('Root check helper required')
    own = per_node(request)
    if request['role'] != 'bastion':
        return own
    user = pwd.getpwnam('labuser')
    root = Path('/home/labuser/.ssh/jdu-web-internal')
    private = root / 'id_ed25519'
    for path, mode, directory in [(root, 0o700, True), (private, 0o600, False)]:
        s = path.lstat()
        if (s.st_uid != user.pw_uid or stat.S_IMODE(s.st_mode) != mode
                or not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))):
            raise ValueError('Private key path protection changed')
    public = subprocess.run(['ssh-keygen', '-y', '-f', str(private)], capture_output=True,
                            text=True, check=True).stdout.strip().split()[:2]
    if ' '.join(public) != request['expected_public_key']:
        raise ValueError('Original enrolled key changed')
    source = base64.b64decode(request['guest_source_b64'], validate=True)
    code = "import base64;exec(base64.b64decode('" + base64.b64encode(source).decode() + "'))"
    def peer(role):
        payload = {k: request[k] for k in ('lab_id', 'deployment_id', 'network_source_sha256')}
        payload.update(role=role, instance_id=request['peers'][role])
        try:
            result = subprocess.run(['sudo', '-n', '-u', 'labuser', 'ssh', '-F', str(root / 'config'),
                role, 'sudo -n python3 -c ' + shlex.quote(code)], input=json.dumps(payload),
                capture_output=True, text=True, timeout=40)
            if result.returncode:
                raise ValueError('Persistent peer SSH/check failed')
            value = json.loads(result.stdout)
            if value['instance_id'] != payload['instance_id'] or value['role'] != role:
                raise ValueError('Unexpected SSH destination')
            return role, value
        except (ValueError, subprocess.TimeoutExpired):
            if request.get('allow_partial') is not True:
                raise
            checks = dict.fromkeys(('ssh_service_or_socket_ready', 'chrony_active',
                'root_space_at_least_2_gib', 'initial_role_state_retained',
                'repository_nginx_active' if role == 'repo' else 'student_service_still_not_installed'))
            return role, dict(role=role, instance_id=payload['instance_id'], checks=checks,
                network=dict.fromkeys(('repo_http', 's3_denied', 'direct_api_egress_denied', 'teacher_ingress_denied')),
                all_checks_passed=False, error_code='PEER_CHECK_UNAVAILABLE')
    if set(request['peers']) != {'web', 'dns', 'db', 'repo'}:
        raise ValueError('Exactly four internal peers required')
    with ThreadPoolExecutor(max_workers=4) as executor:
        nodes = dict(executor.map(peer, request['peers']))
    nodes['bastion'] = own
    return {'scope': 'fresh_post_stop_start_guest_acceptance', 'checked_at': datetime.now(timezone.utc).isoformat(),
        'lab_id': request['lab_id'], 'deployment_id': request['deployment_id'], 'nodes': nodes,
        'same_private_key_and_strict_host_pins_used': True, 'private_key_exported': False,
        'all_five_guest_checks_passed': all(v['all_checks_passed'] for v in nodes.values()),
        'gui_manually_retested_after_restart': False, 'class_ready': False}


if __name__ == '__main__':
    try:
        import sys
        print(json.dumps(run(json.loads(sys.stdin.read(65537))), separators=(',', ':')))
    except Exception as exc:
        print('POST_RESTART_CHECK_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
