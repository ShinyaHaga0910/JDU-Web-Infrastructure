"""Recover public first-boot records and host keys, with fresh read-only checks.

Executed only through the temporarily approved SSM recovery. No private.json,
password, private SSH key, token, signal URL or whole log is read or exported.
The initial role timestamp stays unchanged; current checks are separate.
"""
from datetime import datetime, timezone
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
DEPLOYMENT = 'fc335855-7034-427c-8494-6d7a0491ddf1'
IDS = {'bastion': 'i-049b9086584a4e6df', 'web': 'i-08012a39f3101c7db',
    'dns': 'i-06eb7eea745fa53d3', 'db': 'i-01ef765664432f107', 'repo': 'i-004fb2b85da079a6a'}


def public_role(config, retained):
    fields = ('lab_id', 'deployment_id', 'release_id', 'role', 'instance_id', 'expected_scope')
    if (config['deployment_id'] != DEPLOYMENT or config['lab_id'] != 'teacher-c4-probe'
            or IDS.get(config['role']) != config['instance_id']
            or any(retained.get(k) != config[k] for k in fields)
            or retained.get('stage') != 'ROLE_PREPARED'
            or retained.get('student_release_ready') is not False):
        raise ValueError('Wrong retained role identity')
    checks = {'ssh_active', 'chrony_active', 'pinned_role_packages_installed',
        'root_free_space', 'initial_global_apt_cache_empty'}
    if config['role'] in ('web', 'dns', 'db'): checks.add('student_service_not_installed')
    if config['role'] == 'repo': checks.add('repo_http_manifest_served')
    if config['role'] == 'bastion': checks.update(('rdp_active', 'desktop_browser_and_dbus_present', 'rdp_user_not_admin'))
    if set(retained['checks']) != checks or any(v is not True for v in retained['checks'].values()):
        raise ValueError('Initial role checks did not pass')
    return dict({k: retained[k] for k in fields}, stage='ROLE_PREPARED', checks=retained['checks'],
        checked_at=retained['checked_at'], student_release_ready=False)


def active(unit):
    return subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode == 0


def main():
    config = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    retained = json.loads(Path('/var/lib/jdu-web/bootstrap/role-state.json').read_text())
    initial = public_role(config, retained)
    release = config['release_id']; library = Path('/usr/local/lib/jdu-web') / release
    sys.path.insert(0, str(library))
    import payload_runtime
    root = (Path('/srv/jdu-repo/releases') / release if config['role'] == 'repo'
            else Path('/var/lib/jdu-web/initial/client-metadata'))
    manifest, entries = payload_runtime.signed_manifest(root,
        Path('/var/lib/jdu-web/initial/archive-key.asc'), config['fingerprint'], release,
        allow_package_candidate=False)
    data = (root / 'manifests/deb-packages.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != entries['manifests/deb-packages.json']:
        raise ValueError('Signed package metadata differs')
    versions = {p['package']: p['version'] for p in json.loads(data)}
    packages = set(manifest['role_packages']['common'])
    if config['role'] in ('bastion', 'repo'): packages.update(manifest['role_packages'][config['role']])
    result = subprocess.run(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${db:Status-Status}\n',
        *sorted(packages)], capture_output=True, text=True, check=True)
    installed = {p[0]: (p[1], p[2]) for line in result.stdout.splitlines() if len(p := line.split('\t')) == 3}
    checks = dict(ssh_service_or_socket_ready=active('ssh') or active('ssh.socket'), chrony_active=active('chrony'),
        pinned_role_packages_installed=all(installed.get(p) == (versions[p], 'installed') for p in packages),
        root_space_at_least_2_gib=shutil.disk_usage('/').free >= 2 * 1024**3)
    role = config['role']
    if role in ('web', 'dns', 'db'):
        package = {'web': 'nginx', 'dns': 'bind9', 'db': 'postgresql-16'}[role]
        checks['student_service_not_installed'] = subprocess.run(['dpkg-query', '-W',
            '-f=${db:Status-Status}', package], capture_output=True, text=True).stdout.strip() != 'installed'
    if role == 'bastion':
        checks.update(rdp_active=active('xrdp') and active('xrdp-sesman'),
            desktop_browser_dbus_present=all(shutil.which(p) for p in ('startxfce4', 'firefox', 'dbus-run-session')),
            labuser_not_sudo='sudo' not in subprocess.run(['id', '-nG', 'labuser'],
                capture_output=True, text=True).stdout.split())
    if role == 'repo': checks['repository_nginx_active'] = active('nginx')
    probe_path = library / 'network_probe.py'
    if hashlib.sha256(probe_path.read_bytes()).hexdigest() != '0720fff6f8b1b9271bdb363f937bfea8addd977040324f6adcad252100f26d27':
        raise ValueError('Installed network probe differs from signed source')
    spec = importlib.util.spec_from_file_location('network_probe', probe_path)
    probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
    probe.main()
    network = json.loads(Path('/var/lib/jdu-web/bootstrap/network-probe.json').read_text())
    if (any(network.get(k) != config[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id'))
            or not all(network['checks'].values()) or network['s3_tcp_reachable'] is not True):
        raise ValueError('Fresh bootstrap network check failed')
    if not all(checks.values()): raise ValueError('Fresh service checks failed')
    key = ' '.join(Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()[:2])
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', key): raise ValueError('Invalid public host key')
    raw = base64.b64decode(key.split()[1], validate=True)
    if len(raw) != 51 or raw[:19] != b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20':
        raise ValueError('Invalid Ed25519 public wire format')
    with Path('/dev/ttyS0').open('a') as serial:
        serial.write('\nJDU_NODE_ROLE_RESULT=' + json.dumps(initial) + '\n')
        serial.write('JDU_NODE_NETWORK_RESULT=' + json.dumps(network) + '\n')
        serial.write('BEGIN SSH HOST KEY KEYS\n' + key + '\nEND SSH HOST KEY KEYS\n'); serial.flush()
    print(json.dumps(dict(role=role, instance_id=config['instance_id'], deployment_id=DEPLOYMENT,
        initial_role_checked_at=initial['checked_at'], fresh_checked_at=datetime.now(timezone.utc).isoformat(),
        fresh_checks=checks, network_checks=network['checks'], public_host_key=key,
        bootstrap_s3_reachable=True, all_fresh_checks_passed=True, private_data_exported=False, class_ready=False)))


if __name__ == '__main__': main()
