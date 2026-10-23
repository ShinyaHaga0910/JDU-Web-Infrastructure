"""SSM/SSH guest helper. All input/output is public; private keys stay on bastion.

Invoked by the CloudShell enrollment tool with a deployment-bound JSON request.
Never invoke init from an agent browser without the required credential handoff.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess

ROLES = {'web': '10.20.1.20', 'dns': '10.20.2.10', 'db': '10.20.2.20', 'repo': '10.20.2.30'}


def public_key(value):
    if not isinstance(value, str) or not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', value):
        raise ValueError('Expected plain Ed25519 public key')
    raw = base64.b64decode(value.split()[1], validate=True)
    if len(raw) != 51 or raw[:19] != b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20':
        raise ValueError('Invalid Ed25519 public key wire format')
    return value


def safe_path(path, uid, mode, directory=False):
    s = path.lstat()
    if (s.st_uid != uid or stat.S_IMODE(s.st_mode) != mode
            or not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
            or (not directory and s.st_nlink != 1)):
        raise ValueError('Unsafe owner, mode or file type')


def ensure_ssh_dir(home, uid, gid):
    safe_path(home, uid, stat.S_IMODE(home.lstat().st_mode), directory=True)
    if home.lstat().st_mode & 0o022:
        raise ValueError('Home directory writable by another user')
    path = home / '.ssh'
    if not path.exists() and not path.is_symlink():
        path.mkdir(mode=0o700)
        os.chown(path, uid, gid)
    safe_path(path, uid, 0o700, directory=True)
    return path


def write_new(path, data, uid, gid, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    os.chown(path, uid, gid)


def pins(request):
    peers = request['peers']
    if set(peers) != set(ROLES):
        raise ValueError('Exactly four internal roles required')
    known, config = [], []
    base = Path('/home/labuser/.ssh/jdu-web-internal')
    for role, ip in ROLES.items():
        peer = peers[role]
        if peer['private_ip'] != ip or not re.fullmatch(r'i-[a-f0-9]{17}', peer['instance_id']):
            raise ValueError('Wrong peer identity')
        known.append(ip + ' ' + public_key(peer['host_key']))
        config.extend([f'Host {role}', f' HostName {ip}', ' User ubuntu',
            f' IdentityFile {base}/id_ed25519', f' UserKnownHostsFile {base}/known_hosts',
            ' StrictHostKeyChecking yes', ' IdentitiesOnly yes', ' BatchMode yes',
            ' PasswordAuthentication no', ' KbdInteractiveAuthentication no',
            ' ForwardAgent no', ' ClearAllForwardings yes', ' ConnectTimeout 10',
            ' HostKeyAlgorithms ssh-ed25519', ' LogLevel ERROR'])
    return ('\n'.join(known) + '\n').encode(), ('\n'.join(config) + '\n').encode()


def identity(request, role):
    c = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if (c['role'] != role or c['lab_id'] != request['lab_id']
            or c['deployment_id'] != request['deployment_id']
            or c['instance_id'] != request['instance_id']):
        raise ValueError('Guest is another deployment or role')
    return c


def init_bastion(request):
    identity(request, 'bastion')
    known, config = pins(request)
    user = pwd.getpwnam('labuser')
    parent = ensure_ssh_dir(Path(user.pw_dir), user.pw_uid, user.pw_gid)
    root = parent / 'jdu-web-internal'
    owner = (user.pw_uid, user.pw_gid)
    public_state = {k: request[k] for k in ('lab_id', 'deployment_id', 'instance_id', 'peers')}
    state_data = (json.dumps(public_state, sort_keys=True) + '\n').encode()
    if root.exists() or root.is_symlink():
        safe_path(root, owner[0], 0o700, directory=True)
        for name in ('identity.json', 'id_ed25519', 'known_hosts', 'config'):
            safe_path(root / name, owner[0], 0o600)
        safe_path(root / 'id_ed25519.pub', owner[0], 0o644)
        if ((root / 'identity.json').read_bytes() != state_data
                or (root / 'known_hosts').read_bytes() != known
                or (root / 'config').read_bytes() != config):
            raise ValueError('Existing enrollment belongs to another plan; retained')
    else:
        # Stage root-only; a failed/interrupted generation is retained, never adopted.
        stage = parent / '.jdu-web-internal.staging'
        stage.mkdir(mode=0o700)
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C',
                        'jdu-web-' + request['deployment_id'], '-f', str(stage / 'id_ed25519')],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for name, value in [('identity.json', state_data), ('known_hosts', known), ('config', config)]:
            write_new(stage / name, value, *owner)
        for name, mode in [('id_ed25519', 0o600), ('id_ed25519.pub', 0o644)]:
            os.chmod(stage / name, mode)
            os.chown(stage / name, *owner)
        os.chown(stage, *owner)
        stage.rename(root)
    pub = public_key(' '.join((root / 'id_ed25519.pub').read_text().split()[:2]))
    derived = subprocess.run(['ssh-keygen', '-y', '-f', str(root / 'id_ed25519')],
                             check=True, capture_output=True, text=True).stdout.strip()
    if public_key(' '.join(derived.split()[:2])) != pub:
        raise ValueError('Existing private/public pair mismatch; retained')
    launcher = Path('/usr/local/bin/lab-ssh')
    launcher_bytes = (b'#!/bin/sh\nset -eu\n[ "$#" = 1 ] || exit 2\n'
        b'case "$1" in web|dns|db|repo) ;; *) exit 2 ;; esac\n'
        b'exec /usr/bin/ssh -F /home/labuser/.ssh/jdu-web-internal/config "$1"\n')
    if launcher.exists() or launcher.is_symlink():
        safe_path(launcher, 0, 0o755)
        if launcher.read_bytes() != launcher_bytes:
            raise ValueError('Existing launcher retained')
    else:
        write_new(launcher, launcher_bytes, 0, 0, mode=0o755)
    return {'public_key': pub, 'private_key_exported': False}


def append_public(path, line, uid, gid):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+b') as f:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX)
        s = os.fstat(f.fileno())
        if s.st_uid != uid or stat.S_IMODE(s.st_mode) != 0o600 or s.st_nlink != 1:
            # New root-created files are handled by the caller before opening.
            raise ValueError('Unsafe authorized_keys file; retained')
        content = f.read(262145)
        if len(content) > 262144:
            raise ValueError('Unexpected authorized_keys size')
        if line.encode() not in content.splitlines():
            body = line.split('ssh-ed25519 ', 1)[1].split()[0].encode()
            if body in content.split():
                raise ValueError('Key exists with other restrictions; retained')
            f.seek(0, 2)
            f.write((b'\n' if content and not content.endswith(b'\n') else b'') + line.encode() + b'\n')
            f.flush()
            os.fsync(f.fileno())


def authorize_peer(request):
    role = request['role']
    if role not in ROLES:
        raise ValueError('Internal role required')
    identity(request, role)
    key = public_key(request['public_key'])
    user = pwd.getpwnam('ubuntu')
    parent = ensure_ssh_dir(Path(user.pw_dir), user.pw_uid, user.pw_gid)
    path = parent / 'authorized_keys'
    if request['command'] != 'verify-peer' and not path.exists() and not path.is_symlink():
        write_new(path, b'', user.pw_uid, user.pw_gid)
    line = ('from="10.20.1.10",no-agent-forwarding,no-port-forwarding,no-X11-forwarding '
            + key + ' jdu-web-' + request['deployment_id'])
    if request['command'] == 'verify-peer':
        safe_path(path, user.pw_uid, 0o600)
        if line.encode() not in path.read_bytes().splitlines():
            raise ValueError('Persistent restricted public key missing')
    else:
        append_public(path, line, user.pw_uid, user.pw_gid)
    return {'role': role, 'instance_id': request['instance_id'], 'authorized': True}


def connect_peer(request):
    identity(request, 'bastion')
    role = request['peer_role']
    if role not in ROLES:
        raise ValueError('Internal role required')
    peer_request = {k: request[k] for k in ('lab_id', 'deployment_id', 'public_key')}
    peer_request.update(command='verify-peer' if request.get('verify_only') else 'authorize',
                        role=role, instance_id=request['peer_instance_id'])
    source = Path(__file__).read_bytes() if '__file__' in globals() else base64.b64decode(request['helper_b64'])
    remote = "import base64;exec(base64.b64decode('" + base64.b64encode(source).decode() + "'))"
    command = ['sudo', '-n', '-u', 'labuser', 'ssh', '-F',
               '/home/labuser/.ssh/jdu-web-internal/config', role,
               'sudo -n python3 -c ' + __import__('shlex').quote(remote)]
    result = subprocess.run(command, input=json.dumps(peer_request), capture_output=True, text=True, timeout=40)
    if result.returncode != 0:
        raise ValueError('Pinned peer SSH or public enrollment failed')
    output = json.loads(result.stdout)
    if output != {'role': role, 'instance_id': request['peer_instance_id'], 'authorized': True}:
        raise ValueError('Wrong peer acknowledgment')
    return output


def run(request):
    if os.geteuid() != 0:
        raise ValueError('Root helper required')
    command = request['command']
    if command == 'init':
        return init_bastion(request)
    if command in ('authorize', 'verify-peer'):
        return authorize_peer(request)
    if command == 'connect':
        return connect_peer(request)
    raise ValueError('Unknown guest command')


if __name__ == '__main__':
    try:
        import sys
        request = json.loads(sys.stdin.read(65537))
        print(json.dumps(run(request), separators=(',', ':')))
    except Exception as exc:
        print('JDU_INTERNAL_SSH_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
