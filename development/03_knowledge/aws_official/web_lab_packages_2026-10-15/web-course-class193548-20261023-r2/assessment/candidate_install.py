"""Verify before extraction. Existing state/launchers/credentials are never overwritten."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile


def checked_archive(raw):
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Candidate archive exceeds limit')
    files = {}; total = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for item in archive:
            relative = item.name.removeprefix('jdu-web-d11/')
            if (not item.name.startswith('jdu-web-d11/') or not item.isfile() or not relative
                    or any(p in ('', '.', '..') for p in relative.split('/')) or '\\' in relative or ':' in relative
                    or relative in files or not 0 <= item.size <= 256 * 1024 or len(files) > 100):
                raise ValueError('Unsafe candidate member')
            total += item.size
            if total > 4 * 1024 * 1024:
                raise ValueError('Candidate expanded size exceeds limit')
            files[relative] = archive.extractfile(item).read()
    manifest = json.loads(files['D11-MANIFEST.json'])
    entries = {e['path']: e for e in manifest['files']}
    if (manifest['artifact'] != 'jdu-web-d11' or manifest['scope'] != 'candidate_62_raw_points'
            or manifest['raw_points_max'] != 62 or manifest['credentials_included'] is not False
            or manifest['class_ready'] is not False or len(entries) != len(manifest['files'])
            or set(files) != set(entries) | {'D11-MANIFEST.json'}):
        raise ValueError('Wrong candidate inventory')
    for name, entry in entries.items():
        if (len(files[name]), hashlib.sha256(files[name]).hexdigest()) != (entry['size_bytes'], entry['sha256']):
            raise ValueError('Candidate file differs')
    if hashlib.sha256(files['assessment-registry.json']).hexdigest() != manifest['contract_sha256']:
        raise ValueError('Wrong registry hash')
    return files, manifest


def install(archive, signature, public_key, fingerprint, destination):
    # Supply this verifier from the separately trusted D08 tools before invoking.
    from release_validation import verify_signature
    raw = Path(archive).read_bytes()
    verify_signature(raw, Path(signature).read_bytes(), Path(public_key).read_bytes(), fingerprint)
    files, manifest = checked_archive(raw)
    target = Path(destination)
    if any(p.is_symlink() for p in [target, *target.parents]):
        raise ValueError('Linked destination refused')
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in files.items():
        p = target / name; p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with p.open('xb') as stream:
            stream.write(data)
        p.chmod(0o600)
    return dict(signature_verified=True, file_count=len(manifest['files']), contract_sha256=manifest['contract_sha256'],
                existing_state_changed=False, class_ready=False)
