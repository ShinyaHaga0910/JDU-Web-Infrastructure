"""Guest actions for the CloudShell/SSM classroom installer."""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path('/var/lib/jdu-web-classroom')
SITE = Path('/srv/jdu-web-classroom')
RELEASE = 'web-2026-10-r1'
REPO = f'http://10.20.2.30/releases/{RELEASE}'
FILES = re.compile(r'[a-zA-Z0-9_.+%~:-]{1,200}')
HEX = re.compile(r'[a-f0-9]{64}')
ARCHIVE = re.compile(r'jdu-dependencies-[0-9]{4}\.tar')
MAX_ASSET = 200 * 1024 * 1024
PORT = 18974


def call(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Receiver(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def target(self):
        name = self.path.removeprefix('/')
        if not FILES.fullmatch(name) or name in ('.', '..'):
            raise ValueError('Invalid asset name')
        return ROOT / 'assets' / name

    def do_HEAD(self):
        try:
            target = self.target()
            expected = self.headers.get('X-Asset-SHA256', '')
            ready = HEX.fullmatch(expected) and target.is_file() and sha(target) == expected
        except (OSError, ValueError):
            ready = False
        self.send_response(200 if ready else 404)
        self.end_headers()

    def do_PUT(self):
        temp = None
        try:
            target = self.target()
            digest = self.headers.get('X-Asset-SHA256', '')
            size = int(self.headers.get('Content-Length', '0'))
            if not HEX.fullmatch(digest) or not 0 < size <= MAX_ASSET:
                raise ValueError('Invalid asset metadata')
            fd, name = tempfile.mkstemp(dir=target.parent)
            temp = Path(name)
            with os.fdopen(fd, 'wb') as stream:
                remaining = size
                self.connection.settimeout(60)
                while remaining:
                    part = self.rfile.read(min(remaining, 1024 * 1024))
                    if not part:
                        raise ValueError('Incomplete asset')
                    stream.write(part)
                    remaining -= len(part)
            if sha(temp) != digest:
                raise ValueError('Asset hash differs')
            temp.chmod(0o644)
            temp.replace(target)
            status = 201
        except (OSError, ValueError):
            status = 400
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        self.send_response(status)
        self.end_headers()


def source(uri, key):
    return (f'Types: deb\nURIs: {uri}\nSuites: jdu-noble\nComponents: main\n'
            f'Architectures: amd64\nSigned-By: {key}\n')


def apt(uri, key, packages):
    config = ROOT / 'classroom.sources'
    config.write_text(source(uri, key))
    args = ['apt-get', '-o', f'Dir::Etc::sourcelist={config}', '-o', 'Dir::Etc::sourceparts=-']
    call(*args, '-o', 'APT::Update::Error-Mode=any', 'update', stdout=sys.stderr)
    call(*args, '-y', '--no-install-recommends', 'install', *packages,
         env=dict(os.environ, DEBIAN_FRONTEND='noninteractive'), stdout=sys.stderr)


def signed_index(apt_root, gpg_home):
    index = apt_root / 'dists/jdu-noble/main/binary-amd64/Packages'
    index.parent.mkdir(parents=True, exist_ok=True)
    with index.open('w') as stream:
        for package in sorted((apt_root / 'pool').glob('*.deb')):
            info = call('dpkg-deb', '-f', str(package), capture_output=True, text=True).stdout.rstrip()
            stream.write(f'{info}\nFilename: pool/{package.name}\nSize: {package.stat().st_size}\nSHA256: {sha(package)}\n\n')
    data = (f'Origin: JDU Web Lab\nLabel: JDU Web Lab\nSuite: jdu-noble\nCodename: jdu-noble\n'
            f'Date: {format_datetime(datetime.now(timezone.utc), usegmt=True)}\n'
            f'Valid-Until: {format_datetime(datetime.now(timezone.utc) + timedelta(days=180), usegmt=True)}\n'
            f'Architectures: amd64\nComponents: main\nSHA256:\n'
            f' {sha(index)} {index.stat().st_size} main/binary-amd64/Packages\n')
    release_file = apt_root / 'dists/jdu-noble/Release'
    release_file.write_text(data)
    gpg = ['gpg', '--no-options', '--homedir', str(gpg_home), '--batch', '--yes', '--digest-algo', 'SHA256']
    call(*gpg, '--output', str(release_file.with_name('InRelease')), '--clearsign', str(release_file), stdout=sys.stderr)
    return call(*gpg, '--export', capture_output=True).stdout


def unpack_archives(directory, archives, inventory):
    remaining = set(inventory)
    for name, digest in archives.items():
        if not ARCHIVE.fullmatch(name) or name in inventory or not HEX.fullmatch(digest):
            raise ValueError('Invalid dependency archive name or digest')
        path = directory / name
        if not 0 < path.stat().st_size <= MAX_ASSET or sha(path) != digest:
            raise ValueError(f'Dependency archive hash differs: {name}')
        with tarfile.open(path, 'r:') as archive:
            for member in archive:
                filename = member.name
                if (not member.isfile() or filename not in remaining
                        or not 0 < member.size <= MAX_ASSET):
                    raise ValueError(f'Unexpected dependency archive member: {filename}')
                remaining.remove(filename)
                target = directory / filename
                if target.is_file() and sha(target) == inventory[filename]:
                    continue
                temp = None
                try:
                    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
                        temp = Path(stream.name)
                        with archive.extractfile(member) as contents:
                            shutil.copyfileobj(contents, stream, 1024 * 1024)
                    if sha(temp) != inventory[filename]:
                        raise ValueError(f'Dependency file hash differs: {filename}')
                    temp.chmod(0o644)
                    temp.replace(target)
                finally:
                    if temp is not None:
                        temp.unlink(missing_ok=True)
    if remaining:
        raise ValueError('Dependency archives do not cover the entire package inventory')


def repository(config):
    assets = ROOT / 'assets'
    # Validate the full pinned inventory before producing anything students can install.
    if not all((assets / name).is_file() and sha(assets / name) == value
               for name, value in config['assets'].items()):
        raise ValueError('Repository assets are missing or differ from the lock')
    home = ROOT / 'gnupg'
    home.mkdir(mode=0o700, exist_ok=True)
    if not call('gpg', '--homedir', str(home), '--batch', '--list-secret-keys',
                capture_output=True, text=True).stdout.strip():
        call('gpg', '--homedir', str(home), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
             '--quick-generate-key', 'JDU local classroom repository', 'rsa3072', 'sign', '180d', stdout=sys.stderr)
    public = SITE / 'releases' / RELEASE
    for name in config['assets']:
        path = 'apt/pool' if name.endswith('.deb') else 'artifacts/python/wheelhouse' if name.endswith('.whl') else 'artifacts/browser'
        target = public / path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            os.link(assets / name, target)
        elif sha(target) != config['assets'][name]:
            raise ValueError('Existing repository file differs')
    (public / 'artifacts/python/requirements.lock').write_text(config['requirements'])
    key = signed_index(public / 'apt', home)
    (public / 'archive.gpg').write_bytes(key)
    (ROOT / 'archive.gpg').write_bytes(key)
    apt((public / 'apt').as_uri(), ROOT / 'archive.gpg', config['packages'])
    sites = Path('/etc/nginx/sites-enabled')
    (sites / 'default').unlink(missing_ok=True)
    (sites / 'jdu-classroom').write_text(f'server {{ listen 80 default_server; root {SITE}; location / {{ try_files $uri =404; }} }}\n')
    call('nginx', '-t', stdout=sys.stderr)
    call('systemctl', 'enable', '--now', 'nginx', stdout=sys.stderr)
    call('systemctl', 'reload', 'nginx', stdout=sys.stderr)
    return {'key': __import__('base64').b64encode(key).decode()}


def configure(config):
    import base64
    import node_bootstrap

    role = config['role']
    call('cloud-init', 'status', '--wait', stdout=sys.stderr)
    if role == 'bastion':
        config['rdp_hash'] = (ROOT / 'rdp.hash').read_text().strip()
    key = Path('/usr/share/keyrings/jdu-web-archive-keyring.gpg')
    key.write_bytes(base64.b64decode(config['public_key'], validate=True))
    key.chmod(0o644)
    apt(REPO + '/apt', key, config['packages'])
    source_dir = Path('/etc/apt/sources.list.d')
    for file in (*source_dir.glob('*.list'), *source_dir.glob('*.sources'), Path('/etc/apt/sources.list')):
        if file.exists() and file.name != 'jdu-web.sources':
            target = file.with_name(file.name + '.jdu-disabled')
            if target.exists():
                raise ValueError('Existing APT source backup retained')
            file.rename(target)
    (source_dir / 'jdu-web.sources').write_text(source(REPO + '/apt', key))
    Path('/etc/chrony/conf.d/jdu-web.conf').write_text('server 169.254.169.123 prefer iburst minpoll 4 maxpoll 4\n')
    call('systemctl', 'enable', '--now', 'chrony', stdout=sys.stderr)
    call('systemctl', 'restart', 'chrony', stdout=sys.stderr)
    ssh_policy = Path('/etc/ssh/sshd_config.d/05-jdu-web-key-only.conf')
    if not ssh_policy.exists():
        node_bootstrap.configure_ssh(config)
    else:
        authorized = Path('/home/ubuntu/.ssh/authorized_keys').read_text().splitlines()
        if not any(line.split()[:2] == config['student_public_key'].split() for line in authorized):
            raise ValueError('Academy key differs')
        call('sshd', '-t')
        call('systemctl', 'restart', 'ssh', stdout=sys.stderr)
    if role == 'bastion':
        browser = config['firefox']
        target = ROOT / browser['filename']
        call('curl', '-q', '-fsS', REPO + '/artifacts/browser/' + browser['filename'], '-o', str(target))
        if sha(target) != browser['sha256']:
            raise ValueError('Firefox hash differs')
        call('tar', '-xJf', str(target), '--no-same-owner', '-C', '/opt')
        launcher = Path('/usr/local/bin/firefox')
        if not launcher.is_symlink():
            launcher.symlink_to('/opt/firefox/firefox')
        entry = Path('/usr/share/applications/jdu-firefox.desktop')
        entry.write_text('[Desktop Entry]\nType=Application\nName=Firefox\nExec=/usr/local/bin/firefox %u\nCategories=Network;WebBrowser;\n')
        policies = Path('/etc/firefox/policies/policies.json')
        if not policies.exists():
            node_bootstrap.configure_bastion(config)
        distribution = Path('/opt/firefox/distribution')
        distribution.mkdir(exist_ok=True)
        shutil.copyfile(policies, distribution / 'policies.json')
    state = {k: config[k] for k in ('lab_id', 'deployment_id', 'instance_id', 'role', 'release_id',
                                   'instances', 'grading_api_url', 'grading_ipv4')}
    (Path('/etc/jdu-web') / 'bootstrap.json').write_text(json.dumps(state))
    Path('/var/lib/jdu-web/bootstrap').mkdir(parents=True, exist_ok=True)
    (Path('/usr/local/lib/jdu-web') / RELEASE).mkdir(parents=True, exist_ok=True)
    return verify(config)


def verify(config):
    role = config['role']
    checks = {s: subprocess.run(['systemctl', 'is-active', '--quiet', s]).returncode == 0
              for s in ('ssh', 'chrony')}
    forbidden = {'web': 'nginx', 'dns': 'bind9', 'db': 'postgresql-16'}
    if role in forbidden:
        value = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Status}', forbidden[role]], capture_output=True)
        checks['student_service_unconfigured'] = value.stdout.strip() != b'installed'
    if role == 'bastion':
        checks['rdp'] = subprocess.run(['systemctl', 'is-active', '--quiet', 'xrdp']).returncode == 0
        user = pwd.getpwnam('labuser')
        checks['desktop'] = all(shutil.which(name) for name in ('startxfce4', 'firefox', 'gnome-terminal', 'dbus-run-session'))
        checks['desktop'] = checks['desktop'] and Path(user.pw_dir, '.xsession').is_file()
    result = subprocess.run(['curl', '-q', '-fsS', '--max-time', '15', REPO + '/apt/dists/jdu-noble/InRelease'], capture_output=True)
    checks['internal_repository'] = result.returncode == 0
    if not all(checks.values()):
        raise ValueError(f'Role check failed: {role}: {checks}')
    return {'role': role, 'instance_id': config['instance_id'], 'checks': checks}


def main():
    if sys.argv[1:] == ['receive']:
        (ROOT / 'assets').mkdir(mode=0o700, parents=True, exist_ok=True)
        ThreadingHTTPServer(('127.0.0.1', PORT), Receiver).serve_forever()
        return
    config = json.load(sys.stdin)
    if config['operation'] == 'repo':
        recipe = ROOT / 'assets/recipe.json'
        if sha(recipe) != config['recipe_sha256']:
            raise ValueError('Repository recipe hash differs')
        definition = json.loads(recipe.read_bytes())
        if not definition['assets'] or not all(
            FILES.fullmatch(name) and name not in ('.', '..', 'recipe.json') and HEX.fullmatch(digest)
            for name, digest in definition['assets'].items()
        ):
            raise ValueError('Invalid repository recipe')
        if 'archives' in definition:
            unpack_archives(recipe.parent, definition['archives'], definition['assets'])
        value = repository(definition)
    elif config['operation'] == 'configure':
        marker = ROOT / 'configured.json'
        identity = {k: config[k] for k in ('lab_id', 'deployment_id', 'instance_id', 'role')}
        if marker.exists():
            if json.loads(marker.read_text()) != identity:
                raise ValueError('Existing role belongs to another deployment')
            value = verify(config)
        else:
            value = configure(config)
            marker.write_text(json.dumps(identity))
            if config['role'] == 'bastion':
                (ROOT / 'rdp.hash').unlink(missing_ok=True)
    elif config['operation'] == 'submit':
        import web_progress

        credential = web_progress.private_json('/etc/jdu-web/progress.credentials.json')
        value = web_progress.submit(credential, config['report'])
    else:
        raise ValueError('Unknown guest operation')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
