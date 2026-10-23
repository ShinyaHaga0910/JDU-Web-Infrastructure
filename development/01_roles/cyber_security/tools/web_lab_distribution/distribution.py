"""Signed D08 distribution and individual CloudShell delivery.

The immutable core controls AWS. This layer distributes it and keeps teacher
administration separate from each student's private delivery. It awards no points.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path, limit=1048576, private=False):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit
            or any(p.is_symlink() for p in path.absolute().parents)
            or (private and (info.st_uid != os.geteuid() or info.st_mode & 0o077))):
        raise ValueError('A bounded regular individual file is required')
    return path.read_bytes()


def save(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(data)


def save_json(path, value):
    save(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Timezone is required')
    return result


def window(value, now, maximum):
    created, expiry = timestamp(value['created_at']), timestamp(value['expires_at'])
    if not created <= now < expiry or not timedelta(0) < expiry - created <= maximum:
        raise ValueError('Expired, future dated or excessively long validity')
    return expiry


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(root, fingerprint):
    """Authenticate every file before importing the core or a progress client."""
    root = Path(root).absolute()
    if not re.fullmatch(r'[A-F0-9]{40}', fingerprint):
        raise ValueError('Independently confirmed full fingerprint required')
    raw = read(root / 'distribution-release.json')
    signature = read(root / 'distribution-release.json.asc', 65536)
    key = read(root / 'package-signing-public.asc', 262144)
    # GPG is the only external trust bootstrap; no bundled Python has been imported.
    with tempfile.TemporaryDirectory(prefix='jdu-distribution-gpg-') as home:
        os.chmod(home, 0o700)
        subprocess.run(['gpg', '--no-options', '--homedir', home, '--batch', '--no-autostart',
            '--import-options', 'import-minimal', '--import'], input=key, capture_output=True, check=True)
        status = subprocess.run(['gpg', '--no-options', '--homedir', home, '--batch', '--no-autostart',
            '--status-fd', '1', '--verify', str(root / 'distribution-release.json.asc'),
            str(root / 'distribution-release.json')], capture_output=True, check=True).stdout.decode()
        valid = [line.split() for line in status.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
        if (len(valid) != 1 or len(valid[0]) < 11 or fingerprint not in (valid[0][2], valid[0][-1])
                or int(valid[0][8]) not in (1, 3) or int(valid[0][9]) not in (8, 9, 10)
                or int(valid[0][4]) > int(datetime.now(timezone.utc).timestamp())
                or any(code in status for code in ('EXPKEYSIG', 'REVKEYSIG', 'KEYEXPIRED', 'SIGEXPIRED'))):
            raise ValueError('Release signature or independent signer differs')
    release = json.loads(raw)
    required = {'schema_version', 'scope', 'distribution_id', 'class_id', 'teacher_account',
        'teacher_stack', 'region', 'created_at', 'expires_at', 'core_manifest_sha256',
        'distribution_ready', 'class_ready', 'course_points_assigned', 'files'}
    if (set(release) != required or release['schema_version'] != 1
            or release['scope'] != 'd08_initial_environment_distribution'
            or release['distribution_ready'] is not True or release['class_ready'] is not False
            or release['course_points_assigned'] is not False or type(release['class_id']) is not int
            or release['class_id'] <= 0 or not re.fullmatch(r'[0-9]{12}', release['teacher_account'])
            or release['region'] != 'us-east-1'
            or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9-]{0,127}', release['teacher_stack'])):
        raise ValueError('Unexpected distribution scope')
    window(release, datetime.now(timezone.utc), timedelta(days=7))
    entries = release['files']
    names = set()
    for entry in entries:
        name = entry['path']
        if (set(entry) != {'path', 'sha256', 'size_bytes'} or name in names
                or not re.fullmatch(r'[a-zA-Z0-9_./-]+', name)
                or any(part in ('', '.', '..') for part in name.split('/'))):
            raise ValueError('Unsafe or duplicate distribution inventory')
        names.add(name)
        content = read(root / name, 4 * 1048576)
        if (digest(content), len(content)) != (entry['sha256'], entry['size_bytes']):
            raise ValueError('Distribution artifact differs')
    paths = list(root.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Linked distribution tree refused')
    actual = {str(p.relative_to(root)).replace(os.sep, '/') for p in paths if not p.is_dir()}
    if actual != names | {'distribution-release.json', 'distribution-release.json.asc'}:
        raise ValueError('Unexpected or missing distribution files')
    if read(Path(__file__)) != read(root / 'distribution.py'):
        raise ValueError('Running distribution tool is not bound to this release')
    core = root / 'core'
    validation = load_module('jdu_distribution_core_validation', core / 'release_validation.py')
    checked = validation.verify_release(core / 'deployment-manifest.json', core / 'deployment-manifest.json.asc',
        core / 'package-signing-public.asc', fingerprint, core, include_bundle=False)
    if (checked['manifest_sha256'] != release['core_manifest_sha256']
            or timestamp(release['expires_at']) > timestamp(checked['manifest']['expires_at'])):
        raise ValueError('Core identity or validity differs')
    runtime = load_module('jdu_distribution_controller_runtime', checked['files']['controller_validation'])
    data = checked['files']['controller_bundle'].read_bytes()
    installed = runtime.install_controller(data, Path.home() / '.local/share/jdu-web/controllers' / digest(data))
    sys.path.insert(0, str(installed))
    return dict(root=root, release=release, release_sha256=digest(raw), core=checked, controller=installed)


def account(session, expected):
    actual = session.client('sts').get_caller_identity()['Account']
    if expected is not None and actual != expected:
        raise ValueError('Wrong individual AWS account')
    return actual


def request_value(context, value, student_account, certificate_sha, now):
    release = context['release']
    fields = {'scope', 'distribution_sha256', 'class_id', 'teacher_account', 'student_account',
        'lab_id', 'release_id', 'created_at', 'expires_at', 'certificate_pem', 'certificate_sha256'}
    if (set(value) != fields or value['scope'] != 'individual_student_distribution_request'
            or value['distribution_sha256'] != context['release_sha256']
            or value['class_id'] != release['class_id'] or value['teacher_account'] != release['teacher_account']
            or value['student_account'] != student_account or student_account == release['teacher_account']
            or not re.fullmatch(r'[0-9]{12}', student_account)
            or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', value['lab_id'])
            or value['release_id'] != context['core']['manifest']['release_id']
            or value['certificate_sha256'] != certificate_sha
            or digest(value['certificate_pem'].encode()) != certificate_sha):
        raise ValueError('Recipient, Class, release or independently confirmed student differs')
    window(value, now, timedelta(days=1))
    return value


def credential_value(context, value, lab_id):
    manifest = context['core']['manifest']
    if (set(value) != {'schema_version', 'api_base_url', 'fixed_ingress_ipv4', 'release_id', 'lab_id', 'lab_token'}
            or value['schema_version'] != 1 or value['lab_id'] != lab_id
            or value['release_id'] != manifest['release_id']
            or value['api_base_url'] != 'https://' + manifest['grading']['fqdn']
            or value['fixed_ingress_ipv4'] != manifest['grading']['ipv4']
            or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', value['lab_token'])):
        raise ValueError('Only one student credential for the signed destination is allowed')
    return value


def envelope_value(context, value, request, now):
    fields = {'scope', 'request_sha256', 'distribution_sha256', 'created_at', 'expires_at', 'credentials', 'bootstrap_url'}
    if (set(value) != fields or value['scope'] != 'individual_student_distribution_envelope'
            or value['distribution_sha256'] != context['release_sha256']
            or value['request_sha256'] != digest(json.dumps(request, sort_keys=True).encode())):
        raise ValueError('Encrypted delivery identity differs')
    expiry = window(value, now, timedelta(hours=1))
    if expiry > min(timestamp(request['expires_at']), timestamp(context['release']['expires_at'])):
        raise ValueError('Delivery cannot outlive its request or signed distribution')
    from student_controller import validate_bootstrap_url
    manifest = context['core']['manifest']
    validate_bootstrap_url(value['bootstrap_url'], manifest, manifest['bootstrap']['release_prefix'] + 'repo-bundle.tar.gz')
    return credential_value(context, value['credentials'], request['lab_id'])


def recipient(context, session, args):
    student = account(session, None)
    if student == context['release']['teacher_account']:
        raise ValueError('Use the student individual CloudShell')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', args.lab_id or ''):
        raise ValueError('Teacher assigned anonymous Lab ID required')
    args.workspace.mkdir(mode=0o700, exist_ok=False)
    subprocess.run(['openssl', 'req', '-new', '-x509', '-newkey', 'rsa:3072', '-sha256', '-days', '1',
        '-nodes', '-keyout', str(args.workspace / 'recipient.key'), '-out', str(args.workspace / 'recipient.crt'),
        '-subj', '/CN=JDUIndividualSoftwareDelivery'], capture_output=True, check=True)
    for name in ('recipient.key', 'recipient.crt'):
        (args.workspace / name).chmod(0o600)
    cert = read(args.workspace / 'recipient.crt', private=True).decode()
    now = datetime.now(timezone.utc)
    value = dict(scope='individual_student_distribution_request', distribution_sha256=context['release_sha256'],
        class_id=context['release']['class_id'], teacher_account=context['release']['teacher_account'], student_account=student,
        lab_id=args.lab_id, release_id=context['core']['manifest']['release_id'], created_at=now.isoformat(),
        expires_at=min(now + timedelta(days=1), timestamp(context['release']['expires_at'])).isoformat(),
        certificate_pem=cert, certificate_sha256=digest(cert.encode()))
    request_value(context, value, student, value['certificate_sha256'], now)
    save_json(args.workspace / 'recipient-request.public.json', value)
    print('RECIPIENT_READY; share public request and independently confirm its certificate SHA256')


def check_payload(context, session):
    manifest = context['core']['manifest']
    from botocore.config import Config
    s3 = session.client('s3', region_name=manifest['region'], config=Config(signature_version='s3v4'))
    obj = dict(Bucket=manifest['bootstrap']['bucket'], Key=manifest['bootstrap']['release_prefix'] + 'repo-bundle.tar.gz')
    head = s3.head_object(**obj, ExpectedBucketOwner=context['release']['teacher_account'])
    artifact = manifest['artifacts']['repo_bundle']
    if (head['ContentLength'], head.get('Metadata', {}).get('sha256')) != (artifact['size_bytes'], artifact['sha256']):
        raise ValueError('Signed private payload differs')
    return s3, obj


def teacher_config(context, path):
    config = json.loads(read(path, private=True))
    manifest = context['core']['manifest']
    if any(config.get(k) != v for k, v in dict(api_base_url='https://' + manifest['grading']['fqdn'],
            fixed_ingress_ipv4=manifest['grading']['ipv4'], release_id=manifest['release_id']).items()):
        raise ValueError('Teacher configuration differs from the signed destination')
    return config


def metadata(context, session, lab_id):
    stacks = session.client('cloudformation', region_name=context['release']['region']).describe_stacks(
        StackName=context['release']['teacher_stack'])['Stacks']
    if len(stacks) != 1 or stacks[0]['StackStatus'] not in {'CREATE_COMPLETE', 'UPDATE_COMPLETE'}:
        raise ValueError('Teacher stack is not ready')
    outputs = {x['OutputKey']: x['OutputValue'] for x in stacks[0]['Outputs']}
    manifest = context['core']['manifest']
    if (outputs.get('ApiBaseUrl', '').rstrip('/') != 'https://' + manifest['grading']['fqdn']
            or outputs.get('FixedIngressIpv4') != manifest['grading']['ipv4']):
        raise ValueError('Teacher stack outputs differ from signed teacher')
    return session.client('dynamodb', region_name=context['release']['region']).get_item(
        TableName=outputs['TableName'], Key={'pk': {'S': 'LAB#' + lab_id}, 'sk': {'S': 'META'}},
        ConsistentRead=True).get('Item', {})


def existing(context, session, path, lab_id):
    original = read(path, private=True)
    value = credential_value(context, json.loads(original), lab_id)
    item = metadata(context, session, lab_id)
    if (item.get('lab_id') != {'S': lab_id} or item.get('release_id') != {'S': value['release_id']}
            or item.get('active') != {'BOOL': True}
            or not hmac.compare_digest(item.get('token_hash', {}).get('S', ''), digest(value['lab_token'].encode()))):
        raise ValueError('Existing student credential is inactive or differs from teacher storage')
    return value, original


def plan(context, session, args):
    account(session, context['release']['teacher_account'])
    now = datetime.now(timezone.utc)
    request = request_value(context, json.loads(read(args.request)), args.student_account, args.recipient_sha256, now)
    check_payload(context, session)
    if args.mode == 'reuse':
        existing(context, session, args.existing_credential, request['lab_id'])
    elif metadata(context, session, request['lab_id']):
        raise ValueError('Lab already exists; reuse its original credential instead of issuing again')
    save_json(args.plan, dict(scope='individual_distribution_reviewed_plan', distribution_sha256=context['release_sha256'],
        request=request, mode=args.mode, created_at=now.isoformat(),
        expires_at=min(now + timedelta(hours=1), timestamp(request['expires_at']),
            timestamp(context['release']['expires_at'])).isoformat()))
    print('DELIVERY_PLAN_READY; no credentials or AWS resources created')


def send(context, session, args):
    account(session, context['release']['teacher_account'])
    if not args.confirmed_access or not sys.stdin.isatty():
        raise ValueError('Human-reviewed send in individual CloudShell TTY required')
    reviewed = json.loads(read(args.plan, private=True))
    now = datetime.now(timezone.utc)
    window(reviewed, now, timedelta(hours=1))
    if (reviewed['scope'] != 'individual_distribution_reviewed_plan'
            or reviewed['distribution_sha256'] != context['release_sha256'] or reviewed['mode'] not in ('new', 'reuse')):
        raise ValueError('Reviewed plan differs')
    request = request_value(context, reviewed['request'], args.student_account, args.recipient_sha256, now)
    config = teacher_config(context, args.teacher_config)
    s3, obj = check_payload(context, session)
    preserved = None
    if reviewed['mode'] == 'reuse':
        credential, preserved = existing(context, session, args.existing_credential, request['lab_id'])
    elif metadata(context, session, request['lab_id']):
        raise ValueError('Existing Lab retained; use reuse with its original credential')
    args.workspace.mkdir(mode=0o700, exist_ok=False)
    save_json(args.workspace / 'intent.private.json', dict(plan_sha256=digest(read(args.plan)), mode=reviewed['mode']))
    if reviewed['mode'] == 'new':
        import web_progress
        web_progress.issue(config, request['lab_id'], args.workspace / 'own-student.credentials.json')
        credential, _ = existing(context, session, args.workspace / 'own-student.credentials.json', request['lab_id'])
    expiry = min(now + timedelta(hours=1), timestamp(request['expires_at']), timestamp(context['release']['expires_at']))
    value = dict(scope='individual_student_distribution_envelope', distribution_sha256=context['release_sha256'],
        request_sha256=digest(json.dumps(request, sort_keys=True).encode()), created_at=now.isoformat(),
        expires_at=expiry.isoformat(), credentials=credential,
        bootstrap_url=s3.generate_presigned_url('get_object', Params=obj, ExpiresIn=max(1, int((expiry - now).total_seconds()))))
    envelope_value(context, value, request, now)
    from enroll_five_node_progress import encrypt
    cipher = encrypt(request['certificate_pem'].encode(), json.dumps(value).encode())
    if preserved is not None and read(args.existing_credential, private=True) != preserved:
        raise ValueError('Existing credential changed during preparation')
    save(args.workspace / 'student-delivery.encrypted.cms', cipher)
    save_json(args.workspace / 'delivery.public.json', dict(scope='individual_distribution_delivery_sent',
        distribution_sha256=context['release_sha256'], class_id=context['release']['class_id'],
        student_account=request['student_account'], lab_id=request['lab_id'], mode=reviewed['mode'],
        expires_at=expiry.isoformat(), ciphertext_sha256=digest(cipher),
        teacher_admin_transferred=False, resources_created=False, class_ready=False))
    print('DELIVERY_SENT_ENCRYPTED; share ciphertext only; preserve issuance workspace')


def receive(context, session, args):
    student = account(session, None)
    if not args.confirmed_access or not sys.stdin.isatty():
        raise ValueError('Human receipt in individual student CloudShell TTY required')
    now = datetime.now(timezone.utc)
    request = request_value(context, json.loads(read(args.workspace / 'recipient-request.public.json', private=True)),
        student, args.recipient_sha256, now)
    cipher = read(args.ciphertext, 65536)
    if digest(cipher) != args.ciphertext_sha256:
        raise ValueError('Independently confirmed ciphertext differs')
    description = subprocess.run(['openssl', 'cms', '-cmsout', '-inform', 'DER', '-print'],
        input=cipher, capture_output=True, check=True).stdout
    if any(x not in description for x in (b'id-smime-ct-authEnvelopedData', b'aes-256-gcm', b'rsaesOaep')):
        raise ValueError('Authenticated transport required')
    read(args.workspace / 'recipient.key', private=True)
    clear = subprocess.run(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
        '-recip', str(args.workspace / 'recipient.crt'), '-inkey', str(args.workspace / 'recipient.key')],
        input=cipher, capture_output=True, check=True).stdout
    value = json.loads(clear)
    credential = envelope_value(context, value, request, datetime.now(timezone.utc))
    output = args.workspace / 'received'
    output.mkdir(mode=0o700, exist_ok=False)
    save_json(output / 'own-student.credentials.json', credential)
    save(output / 'bootstrap-url.private.txt', (value['bootstrap_url'] + '\n').encode())
    save_json(output / 'received.public.json', dict(scope='individual_distribution_received',
        distribution_sha256=context['release_sha256'], student_account=student, lab_id=request['lab_id'],
        expires_at=value['expires_at'], teacher_admin_received=False, resources_created=False))
    print('DELIVERY_RECEIVED; private credential and payload URL stay in this CloudShell')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'recipient', 'plan', 'send', 'receive', 'audit-existing'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--trusted-fingerprint', required=True)
    for name in ('workspace', 'request', 'plan', 'teacher-config', 'existing-credential', 'ciphertext'):
        parser.add_argument('--' + name, type=Path)
    for name in ('lab-id', 'student-account', 'recipient-sha256', 'ciphertext-sha256'):
        parser.add_argument('--' + name)
    parser.add_argument('--mode', choices=('new', 'reuse'), default='new')
    parser.add_argument('--confirmed-access', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    context = verify(args.root, args.trusted_fingerprint)
    if args.command == 'verify':
        print(json.dumps(dict(distribution_id=context['release']['distribution_id'],
            distribution_ready=True, class_ready=False, expires_at=context['release']['expires_at'],
            core_manifest_sha256=context['core']['manifest_sha256'], all_files_verified=True)))
        return
    import boto3
    session = boto3.Session(region_name=context['release']['region'])
    if args.command == 'audit-existing':
        account(session, context['release']['teacher_account'])
        existing(context, session, args.existing_credential, args.lab_id)
        check_payload(context, session)
        print('EXISTING_CREDENTIAL_AND_PAYLOAD_VERIFIED; no credentials issued or changed')
    else:
        globals()[args.command](context, session, args)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # HTTP/SDK/subprocess failures may contain a token, URL or decrypted body.
        print('DISTRIBUTION_STOPPED=' + type(exc).__name__ + '; preserve private files and inspect the completed stage')
        raise SystemExit(2)
