"""Teacher-only D11 acceptance setup: internal HTTP/DNS/resolver/storage, no credentials.

Not included in student artifacts. Retains package/configuration snapshots and
refuses pre-existing student services or marker contents. Never changes SG/IAM,
SSH keys, RDP, grading credentials, EC2 identity, or disks.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path('/var/lib/jdu-web/d11-foundation-acceptance-r1')


def command(args, timeout=480):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout,
        env=dict(os.environ, DEBIAN_FRONTEND='noninteractive', LC_ALL='C')).stdout


def save_new(path, raw, mode=0o600):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(raw)


def packages():
    output = command(['dpkg-query', '-W', '-f=${Package}\t${db:Status-Status}\n'])
    return sorted(line.split('\t')[0] for line in output.splitlines() if line.endswith('\tinstalled'))


def install_internal(b, names, work):
    library = Path('/usr/local/lib/jdu-web') / b['release_id']
    sys.path.insert(0, str(library))
    from payload_runtime import signed_manifest
    _, sums = signed_manifest('/var/lib/jdu-web/initial/client-metadata',
        '/var/lib/jdu-web/initial/archive-key.asc', b['fingerprint'], b['release_id'], allow_package_candidate=True)
    prefix = 'http://10.20.2.30/releases/' + b['release_id'] + '/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    name = 'manifests/deb-packages.json'
    with opener.open(prefix + name, timeout=15) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != sums[name]:
        raise ValueError('Signed internal package manifest differs')
    versions = {p['package']: p['version'] for p in json.loads(raw)}
    source = work / 'internal.sources'
    save_new(source, ('Types: deb\nURIs: ' + prefix + 'apt/\nSuites: jdu-noble\nComponents: main\nArchitectures: amd64\n'
        'Signed-By: /usr/share/keyrings/jdu-web-archive-keyring.gpg\n').encode())
    for name in ('lists', 'cache'):
        (work / name).mkdir()
    apt = ['apt-get', '-o', 'Dir::Etc::sourcelist=' + str(source), '-o', 'Dir::Etc::sourceparts=-',
        '-o', 'Dir::State::lists=' + str(work / 'lists'), '-o', 'Dir::Cache::archives=' + str(work / 'cache'),
        '-o', 'Dpkg::Lock::Timeout=480']
    command(apt + ['update', '-o', 'APT::Update::Error-Mode=any'])
    command(apt + ['install', '-y', '--no-install-recommends', *[n + '=' + versions[n] for n in names]])


def replace_public(path, raw, work):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected regular package configuration')
    save_new(work / (path.name + '.before'), path.read_bytes())
    path.write_bytes(raw)


def inspect(b):
    result = dict(role=b['role'], instance_id=b['instance_id'], packages=[n for n in packages()
        if n in ('nginx', 'bind9', 'postgresql-16')])
    if b['role'] in ('bastion', 'web'):
        import yaml
        config = yaml.safe_load(command(['netplan', 'get']))
        network = config.get('network', config)
        result['ethernet_ids'] = sorted(network.get('ethernets', {}))
        result['resolver_dns'] = command(['resolvectl', 'dns'], timeout=15).strip()
    return result


def run(r):
    if os.geteuid() != 0:
        raise ValueError('Root fixture required')
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if any(b[k] != r[k] for k in ('lab_id', 'deployment_id', 'role', 'instance_id')):
        raise ValueError('Wrong retained deployment')
    op = r['operation']
    if op == 'inspect':
        return inspect(b)
    expected_role = {'http': 'web', 'dns': 'dns', 'storage': 'web'}
    if op in expected_role and b['role'] != expected_role[op] or op == 'resolver' and b['role'] not in ('bastion', 'web'):
        raise ValueError('Wrong fixture role')
    if op not in (*expected_role, 'resolver'):
        raise ValueError('Unknown fixture operation')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    if ROOT.is_symlink() or ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o077:
        raise ValueError('Unsafe fixture workspace')
    work = ROOT / op
    work.mkdir(mode=0o700, exist_ok=False)
    save_new(work / 'packages.before.json', json.dumps(packages()).encode())
    if op == 'http':
        if 'nginx' in packages() or 'nginx-common' in packages():
            raise ValueError('Existing student HTTP service retained')
        install_internal(b, ['nginx'], work)
        default = Path('/etc/nginx/sites-available/default')
        config = ('server { listen 80 default_server; server_name _; root /var/www/html; '
            'access_log /var/log/nginx/access.log; location / { try_files $uri $uri/ =404; } }\n')
        replace_public(default, config.encode(), work)
        root = Path('/var/www/html'); root.mkdir(mode=0o755, exist_ok=True)
        for name, body in r['http_files'].items():
            if name not in ('practice.txt', 'mission.txt'):
                raise ValueError('Unknown classroom HTTP file')
            save_new(root / name, body.encode(), 0o644)
        command(['nginx', '-t'], timeout=15)
        command(['systemctl', 'enable', '--now', 'nginx'], timeout=30)
        command(['systemctl', 'restart', 'nginx'], timeout=30)
    elif op == 'dns':
        if 'bind9' in packages():
            raise ValueError('Existing student DNS service retained')
        install_internal(b, ['bind9', 'bind9-utils'], work)
        options = '''acl "jdu_clients" { 127.0.0.1; 10.20.1.10; 10.20.1.20; };
options { directory "/var/cache/bind"; listen-on { 127.0.0.1; 10.20.2.10; }; listen-on-v6 { none; };
allow-query { jdu_clients; }; allow-recursion { jdu_clients; }; allow-query-cache { jdu_clients; };
recursion yes; forward only; forwarders { 10.20.0.2; }; dnssec-validation no; allow-transfer { none; }; };
'''
        replace_public('/etc/bind/named.conf.options', options.encode(), work)
        replace_public('/etc/bind/named.conf.local',
            b'zone "lab.test" { type primary; file "/etc/bind/zones/db.lab.test"; allow-transfer { none; }; allow-update { none; }; };\n', work)
        zone = Path('/etc/bind/zones'); zone.mkdir(mode=0o755, exist_ok=True)
        zone.chmod(0o755)
        text = ('$TTL 300\n@ IN SOA dns.lab.test. hostmaster.lab.test. (2026102301 3600 600 604800 300)\n@ IN NS dns.lab.test.\n'
            + ''.join(name.removesuffix('.lab.test') + ' IN A ' + address + '\n' for name, address in sorted(r['records'].items())))
        save_new(zone / 'db.lab.test', text.encode(), 0o644)
        command(['named-checkconf', '-z'], timeout=20)
        command(['systemctl', 'enable', '--now', 'named'], timeout=30)
        command(['systemctl', 'restart', 'named'], timeout=30)
        answer = command(['dig', '@127.0.0.1', 'web.lab.test', '+short'], timeout=10)
        if answer.strip() != '10.20.1.20':
            raise ValueError('DNS must answer before resolver changes')
    elif op == 'resolver':
        answer = command(['dig', '@10.20.2.10', 'web.lab.test', '+short'], timeout=10)
        if answer.strip() != '10.20.1.20':
            raise ValueError('Leave DHCP DNS until classroom DNS is ready')
        import yaml
        config = yaml.safe_load(command(['netplan', 'get']))
        network = config.get('network', config)
        ethernets = network.get('ethernets', {})
        if len(ethernets) != 1:
            raise ValueError('Review actual Netplan interfaces')
        identifier, old = next(iter(ethernets.items()))
        if old.get('dhcp4') is not True:
            raise ValueError('Retain DHCP address and routes')
        save_new(work / 'netplan.before.yaml', yaml.safe_dump(config).encode())
        value = {'network': {'version': 2, 'ethernets': {identifier: {'dhcp4-overrides': {'use-dns': False},
            'nameservers': {'addresses': ['10.20.2.10'], 'search': ['lab.test']}}}}}
        save_new(Path('/etc/netplan/90-jdu-d11-dns.yaml'), yaml.safe_dump(value).encode())
        resolved = Path('/etc/systemd/resolved.conf.d'); resolved.mkdir(mode=0o755, exist_ok=True)
        save_new(resolved / '90-jdu-d11-dns.conf', b'[Resolve]\nFallbackDNS=\n', 0o644)
        command(['netplan', 'generate'], timeout=30)
        command(['netplan', 'apply'], timeout=60)
        command(['systemctl', 'restart', 'systemd-resolved'], timeout=30)
        answer = command(['getent', 'ahostsv4', 'web.lab.test'], timeout=10)
        if not answer.strip() or any(line.split()[0] != '10.20.1.20' for line in answer.splitlines()):
            raise ValueError('Classroom resolver verification failed; retained backup available')
    elif op == 'storage':
        for task, item in r['markers'].items():
            if task not in ('P3', 'M3') or item['file'] != '/var/lib/jdu-web/' + ('practice' if task == 'P3' else 'mission') + '/storage.txt':
                raise ValueError('Unknown classroom marker')
            target = Path(item['file']); target.parent.mkdir(mode=0o755, exist_ok=True)
            if target.parent.is_symlink() or target.parent.stat().st_uid != 0 or target.parent.stat().st_mode & 0o022:
                raise ValueError('Marker parent must be root controlled')
            if target.parent.stat().st_mode & 0o777 != 0o755:
                raise ValueError('Retain an existing marker directory with different permissions')
            save_new(target, item['body_template'].format(lab_id=b['lab_id']).encode(), 0o644)
    result = dict(operation=op, role=b['role'], configured=True, credentials_created=False,
        network_permissions_changed=False, instance_id=b['instance_id'])
    save_new(work / 'complete.public.json', json.dumps(result).encode())
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin)), separators=(',', ':')))
    except Exception as exc:
        print('D11_FOUNDATION_FIXTURE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
