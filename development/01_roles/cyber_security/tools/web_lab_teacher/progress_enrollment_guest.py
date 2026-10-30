"""Encrypted SSM delivery of a Lab token; never print plaintext credentials.

The RSA key is a local envelope-decryption key, not an authentication key.
The teacher admin credential is never accepted by this guest helper.
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}


def safe(path, mode, directory=False):
    s = path.lstat()
    if (s.st_uid != 0 or stat.S_IMODE(s.st_mode) != mode
            or not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
            or (not directory and s.st_nlink != 1)):
        raise ValueError('Unsafe enrollment path')


def mkdir(path):
    if not path.exists() and not path.is_symlink():
        path.mkdir(mode=0o700)
    safe(path, 0o700, True)


def write_once(path, data):
    if path.exists() or path.is_symlink():
        safe(path, 0o600)
        if path.read_bytes() != data:
            raise ValueError('Existing configuration retained')
        return
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as f:
        f.write(data)


def bootstrap(request):
    c = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if (c['role'] != 'bastion' or any(c[k] != request[k]
            for k in ('lab_id', 'release_id', 'deployment_id', 'instance_id'))
            or set(c.get('instances', {})) != ROLES
            or len(set(c['instances'].values())) != 5
            or c['instances']['bastion'] != c['instance_id']):
        raise ValueError('Wrong bastion deployment')
    return c


def recipient_directory(c):
    # Parents already belong to the root-owned Web bootstrap namespace.
    parent = Path('/var/lib/jdu-web/progress-enrollment')
    mkdir(parent)
    root = parent / c['deployment_id']
    mkdir(root)
    return root


def recipient(root, deployment_id):
    key, cert = root / 'recipient.key', root / 'recipient.crt'
    if key.exists() or cert.exists() or key.is_symlink() or cert.is_symlink():
        safe(key, 0o600)
        safe(cert, 0o600)
    else:
        with tempfile.TemporaryDirectory(prefix='recipient-', dir=root) as t:
            k, c = Path(t) / 'key', Path(t) / 'cert'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-noenc', '-batch',
                '-days', '1', '-subj', '/CN=jdu-web-envelope-' + deployment_id,
                '-keyout', str(k), '-out', str(c)], check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            write_once(key, k.read_bytes())
            write_once(cert, c.read_bytes())
    return {'certificate_pem': cert.read_text(),
            'certificate_sha256': hashlib.sha256(cert.read_bytes()).hexdigest()}


def decrypt(root, ciphertext):
    safe(root / 'recipient.key', 0o600)
    safe(root / 'recipient.crt', 0o600)
    if not 128 <= len(ciphertext) <= 16384:
        raise ValueError('Invalid envelope size')
    description = subprocess.run(['openssl', 'cms', '-cmsout', '-inform', 'DER', '-print'],
                                 input=ciphertext, capture_output=True, check=True).stdout
    if (b'id-smime-ct-authEnvelopedData' not in description
            or b'aes-256-gcm' not in description or b'rsaesOaep' not in description):
        raise ValueError('Authenticated AES-GCM/RSA-OAEP envelope required')
    result = subprocess.run(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
        '-recip', str(root / 'recipient.crt'), '-inkey', str(root / 'recipient.key')],
        input=ciphertext, capture_output=True)
    if result.returncode != 0 or len(result.stdout) > 8192:
        raise ValueError('Envelope authentication failed')
    return json.loads(result.stdout)


def decrypt_oaep(root, ciphertext, c):
    """Portal delivery of one compact, context-bound token (not a CMS change)."""
    safe(root / 'recipient.key', 0o600)
    safe(root / 'recipient.crt', 0o600)
    if len(ciphertext) != 384:
        raise ValueError('RSA3072 envelope required')
    result = subprocess.run(['openssl', 'pkeyutl', '-decrypt', '-inkey', str(root / 'recipient.key'),
        '-pkeyopt', 'rsa_padding_mode:oaep', '-pkeyopt', 'rsa_oaep_md:sha256',
        '-pkeyopt', 'rsa_mgf1_md:sha256'], input=ciphertext, capture_output=True)
    if result.returncode != 0 or len(result.stdout) > 318:
        raise ValueError('Envelope authentication failed')
    value = json.loads(result.stdout)
    if (type(value) is not list or len(value) != 6 or value[0] != 'jdu-progress-oaep-v1'
            or value[1:5] != [c[k] for k in ('lab_id','release_id','deployment_id','instance_id')]
            or not isinstance(value[5],str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',value[5])):
        raise ValueError('Envelope belongs to another deployment or purpose')
    return dict(schema_version=1, purpose='progress_registration',
        **{k:c[k] for k in ('lab_id','release_id','deployment_id','instance_id')}, credentials={
            'schema_version':1,'api_base_url':c['grading_api_url'],'fixed_ingress_ipv4':c['grading_ipv4'],
            'lab_id':c['lab_id'],'release_id':c['release_id'],'lab_token':value[5]})


def validate_envelope(value, c, probe=False):
    fields = {'schema_version', 'purpose', 'lab_id', 'release_id', 'deployment_id', 'instance_id',
              'probe' if probe else 'credentials'}
    if (set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['purpose'] != ('transport_probe' if probe else 'progress_registration')
            or any(value[k] != c[k] for k in ('lab_id', 'release_id', 'deployment_id', 'instance_id'))):
        raise ValueError('Envelope belongs to another deployment or purpose')
    if probe:
        if not re.fullmatch(r'[a-f0-9]{64}', value['probe']):
            raise ValueError('Invalid public probe')
        return value['probe']
    config = value['credentials']
    expected = {'schema_version', 'api_base_url', 'fixed_ingress_ipv4', 'release_id', 'lab_id', 'lab_token'}
    if (type(config) is not dict or set(config) != expected or config['schema_version'] != 1
            or config['api_base_url'] != c['grading_api_url'] or config['fixed_ingress_ipv4'] != c['grading_ipv4']
            or config['lab_id'] != c['lab_id'] or config['release_id'] != c['release_id']
            or not isinstance(config['lab_token'], str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', config['lab_token'])):
        raise ValueError('Only this Lab student credential is accepted')
    return config


def load_client(request):
    source = base64.b64decode(request['client_source_b64'], validate=True)
    if hashlib.sha256(source).hexdigest() != request['client_sha256']:
        raise ValueError('Client source differs')
    target = Path('/usr/local/lib/jdu-web/web-2026-10-r1/web_progress.py')
    if target.exists() or target.is_symlink():
        safe(target, 0o644)
        if target.read_bytes() != source:
            raise ValueError('Existing client retained')
    else:
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644), 'wb') as f:
            f.write(source)
        target.chmod(0o644)
    spec = importlib.util.spec_from_file_location('web_progress', target)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    return client


def run(request):
    if os.geteuid() != 0:
        raise ValueError('Root helper required')
    c = bootstrap(request)
    command = request['command']
    root = recipient_directory(c)
    if command == 'status':
        return {'credential_present': Path('/etc/jdu-web/progress.credentials.json').exists(),
                'registration_present': Path('/var/lib/jdu-web/bootstrap/progress-registration.json').exists(),
                'transport_private_key_present': (root / 'recipient.key').exists()}
    if command == 'recipient':
        return recipient(root, c['deployment_id'])
    if command in ('probe', 'register', 'register_oaep'):
        ciphertext = base64.b64decode(request['ciphertext_b64'], validate=True)
        if command == 'register_oaep':
            safe(root / 'recipient.crt', 0o600)
            if hashlib.sha256((root / 'recipient.crt').read_bytes()).hexdigest() != request['certificate_sha256']:
                raise ValueError('Recipient certificate differs')
            value = decrypt_oaep(root, ciphertext, c)
        else:
            value = decrypt(root, ciphertext)
        validated = validate_envelope(value, c, probe=command == 'probe')
        if command == 'probe':
            return {'transport_probe': validated, 'plaintext_credential_written': False}
        config = validated
        write_once(Path('/etc/jdu-web/progress.credentials.json'),
                   (json.dumps(config, sort_keys=True) + '\n').encode())
    elif command in ('verify', 'complete'):
        path = Path('/etc/jdu-web/progress.credentials.json')
        safe(path, 0o600)
        config = validate_envelope(dict(schema_version=1, purpose='progress_registration',
            **{k: c[k] for k in ('lab_id', 'release_id', 'deployment_id', 'instance_id')},
            credentials=json.loads(path.read_text())), c)
    else:
        raise ValueError('Unknown enrollment operation')
    client = load_client(request)
    receipt = client.register(config, c)
    write_once(Path('/var/lib/jdu-web/bootstrap/progress-registration.json'),
               (json.dumps(receipt, sort_keys=True) + '\n').encode())
    if command in ('register', 'register_oaep', 'complete'):
        safe(root / 'recipient.key', 0o600)
        (root / 'recipient.key').unlink()  # Retire only this tool's one-use transport key.
    answer = dict(receipt, private_credential_exported=False, instance_count=len(c['instances']),
                  transport_private_key_retired=not (root / 'recipient.key').exists())
    if command == 'register_oaep':
        answer['token_hash'] = hashlib.sha256(config['lab_token'].encode('ascii')).hexdigest()
    return answer


if __name__ == '__main__':
    try:
        import sys
        os.umask(0o077)
        print(json.dumps(run(json.loads(sys.stdin.read(65537))), separators=(',', ':')))
    except Exception as exc:
        print('PROGRESS_ENROLLMENT_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
