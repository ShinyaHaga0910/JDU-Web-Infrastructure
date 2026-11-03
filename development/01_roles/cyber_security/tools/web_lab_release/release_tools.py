"""Verify a signed course kit before importing its immutable foundation/checkers."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile

sys.dont_write_bytecode = True
VERIFIER_SHA256 = 'e9aebc2f1ed3d54df70e862e5a9aabe8e08970004106c8a89a6260da9e34096c'
MAXIMUM = 8 * 1024 * 1024
POINTS = dict(M1=8, M2=13, M3=3, M4=9, M5=13, M6=16)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path, private=False, limit=MAXIMUM):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Linked files are not supported')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit
                or private and (info.st_uid != os.geteuid() or info.st_mode & 0o077)):
            raise ValueError('Bounded regular personal file required')
        return stream.read(limit + 1)


def parse(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    def invalid(_):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()


def save(path, data, mode=0o600):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as f:
        os.fchmod(f.fileno(), mode)
        f.write(data)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def time_value(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('UTC offset required')
    return result


def verifier(root):
    path = root / 'foundation/core/release_validation.py'
    if digest(read(path)) != VERIFIER_SHA256:
        raise ValueError('Independently pinned signature verifier differs')
    return load('jdu_course_trusted_signature', path)


def verify(root, fingerprint):
    root = Path(root).absolute()
    if not re.fullmatch('[A-F0-9]{40}', fingerprint):
        raise ValueError('Independent full signing fingerprint required')
    raw = read(root / 'course-release.json')
    validation = verifier(root)
    key_expiry = validation.verify_signature(raw, read(root / 'course-release.json.asc'),
        read(root / 'package-signing-public.asc'), fingerprint)
    value = parse(raw)
    fields = {'schema_version', 'scope', 'distribution_id', 'class_id', 'teacher_account', 'region',
        'created_at', 'expires_at', 'foundation_distribution_sha256', 'core_manifest_sha256',
        'assessment_archive_sha256', 'assessment_manifest_sha256', 'contract_id', 'contract_sha256',
        'raw_maximum', 'distribution_ready', 'class_ready', 'files'}
    if (set(value) != fields or value['schema_version'] != 1 or value['scope'] != 'web_course_distribution'
            or not re.fullmatch('[a-z0-9][a-z0-9-]{2,79}', value['distribution_id'])
            or type(value['class_id']) is not int or value['class_id'] <= 0
            or not re.fullmatch('[0-9]{12}', value['teacher_account']) or value['region'] != 'us-east-1'
            or value['raw_maximum'] != 62 or value['distribution_ready'] is not True or value['class_ready'] is not False):
        raise ValueError('Unexpected course distribution scope')
    created, expiry = map(time_value, (value['created_at'], value['expires_at']))
    if (not created <= datetime.now(timezone.utc) < expiry or not timedelta(0) < expiry - created <= timedelta(days=120)
            or expiry.timestamp() > key_expiry):
        raise ValueError('Expired or future dated distribution; keep existing state')
    names = set()
    for entry in value['files']:
        name = entry['path']
        if (set(entry) != {'path', 'sha256', 'size_bytes'} or name in names
                or not re.fullmatch('[A-Za-z0-9_./-]+', name)
                or any(p in ('', '.', '..') for p in name.split('/'))):
            raise ValueError('Unexpected course inventory')
        names.add(name)
        data = read(root / name)
        if (digest(data), len(data)) != (entry['sha256'], entry['size_bytes']):
            raise ValueError('Course file differs from signature')
    paths = list(root.rglob('*'))
    actual = {p.relative_to(root).as_posix() for p in paths if not p.is_dir()}
    if any(p.is_symlink() for p in paths) or actual != names | {'course-release.json', 'course-release.json.asc'}:
        raise ValueError('Missing, extra or linked course file')
    if read(Path(__file__)) != read(root / 'release_tools.py'):
        raise ValueError('Running course tool belongs to a different release')
    foundation_tool = load('jdu_course_foundation', root / 'foundation/distribution.py')
    foundation = foundation_tool.verify(root / 'foundation', fingerprint)
    old = foundation['release']
    if (foundation['release_sha256'] != value['foundation_distribution_sha256']
            or foundation['core']['manifest_sha256'] != value['core_manifest_sha256']
            or old['class_id'] != value['class_id'] or old['teacher_account'] != value['teacher_account']
            or expiry > time_value(old['expires_at'])):
        raise ValueError('Foundation identity or lifetime differs')
    archive = read(root / 'assessment.tar.gz')
    if digest(archive) != value['assessment_archive_sha256']:
        raise ValueError('Accepted assessment archive differs')
    validation.verify_signature(archive, read(root / 'assessment.tar.gz.asc'),
        read(root / 'package-signing-public.asc'), fingerprint)
    assessment_tool = load('jdu_course_assessment_archive', root / 'assessment/candidate_install.py')
    files, manifest = assessment_tool.checked_archive(archive)
    if (digest(files['D11-MANIFEST.json']) != value['assessment_manifest_sha256']
            or manifest['contract_id'] != value['contract_id'] or manifest['contract_sha256'] != value['contract_sha256']
            or any(read(root / 'assessment' / name) != data for name, data in files.items())):
        raise ValueError('Accepted checker tree differs')
    registry = parse(files['assessment-registry.json'])
    if registry['raw_points_by_mission'] != POINTS:
        raise ValueError('Fixed 62-point registry required')
    return dict(root=root, release=value, sha256=digest(raw), fingerprint=fingerprint, foundation=foundation)


def compatible_core(context, manifest_sha256):
    """Accept only an explicitly signed renewal of the same executable runtime.

    `context` must come from verify(), which authenticates RENEWAL.json as part
    of the entire release before this function reads it. No old expiry is
    ignored by the original runtime; the new signed release authorizes using
    its unchanged controller with retained state, without editing that state.
    """
    if manifest_sha256 == context['release']['core_manifest_sha256']:
        return True
    path = context['root'] / 'RENEWAL.json'
    if not path.is_file():
        return False
    row = parse(read(path))
    return (row.get('scope') == 'same_runtime_validity_renewal'
            and row.get('original_core_manifest_sha256') == manifest_sha256
            and row.get('renewed_core_manifest_sha256') == context['release']['core_manifest_sha256']
            and row.get('runtime_artifacts_unchanged') is True
            and row.get('assessment_archive_sha256') == context['release']['assessment_archive_sha256'])


def tree(root):
    return {p.relative_to(root).as_posix(): read(p) for p in root.rglob('*') if p.is_file()}


def checked_archive(data):
    files, total = {}, 0
    if len(data) > MAXIMUM:
        raise ValueError('Course archive too large')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for item in archive:
            name = item.name.removeprefix('jdu-web-course/')
            if (not item.name.startswith('jdu-web-course/') or not item.isfile() or name in files
                    or not re.fullmatch('[A-Za-z0-9_./-]+', name)
                    or any(p in ('', '.', '..') for p in name.split('/'))
                    or not 0 <= item.size <= MAXIMUM or len(files) >= 200):
                raise ValueError('Unsafe course archive member')
            total += item.size
            if total > MAXIMUM:
                raise ValueError('Expanded course archive too large')
            files[name] = archive.extractfile(item).read()
    return files
