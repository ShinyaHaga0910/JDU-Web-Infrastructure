"""Verify signature and exact inventory before extracting or running checker code.

Does not create credentials or replace commands. The caller binds a verified
directory to deployment-specific configuration in their personal CloudShell.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile


def checked_archive(data):
    files = {}; total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        for m in tar:
            p = PurePosixPath(m.name)
            if (not m.isfile() or not m.name.startswith('jdu-web-checker/') or len(p.parts) < 2
                    or any(x in ('', '.', '..') for x in m.name.split('/')) or '\\' in m.name or ':' in m.name
                    or m.name.removeprefix('jdu-web-checker/') in files or not 0 <= m.size <= 256 * 1024 or len(files) >= 100):
                raise ValueError('Unsafe checker archive')
            total += m.size
            if total > 4 * 1024 * 1024: raise ValueError('Checker archive too large')
            files[m.name.removeprefix('jdu-web-checker/')] = tar.extractfile(m).read()
    manifest = json.loads(files['CHECKER-MANIFEST.json'])
    entries = {e['path']: e for e in manifest['files']}
    if (manifest['schema_version'] != 1 or manifest['artifact'] != 'jdu-web-checker'
            or manifest['release_id'] != 'web-2026-10-r1' or manifest['credentials_included'] is not False
            or manifest['scope'] != 'student_checker_candidate_web02_only'
            or manifest['supported_tasks'] != ['bootstrap', 'P1', 'M1']
            or manifest['student_release_ready'] is not False or manifest['class_ready'] is not False
            or len(entries) != len(manifest['files'])
            or set(files) != set(entries) | {'CHECKER-MANIFEST.json'}):
        raise ValueError('Wrong checker inventory or scope')
    for name, e in entries.items():
        if (hashlib.sha256(files[name]).hexdigest(), len(files[name])) != (e['sha256'], e['size_bytes']):
            raise ValueError('Checker inventory hash differs')
    return files, manifest


def install(archive, signature, key, fingerprint, destination, allow_candidate=False):
    # This verifier is supplied separately and must be trusted before use.
    from release_validation import verify_signature
    if not allow_candidate:
        raise ValueError('Candidate requires explicit --allow-candidate; no formal student release exists')
    data = Path(archive).read_bytes()
    if len(data) > 4 * 1024 * 1024: raise ValueError('Checker bundle too large')
    verify_signature(data, Path(signature).read_bytes(), Path(key).read_bytes(), fingerprint)
    files, manifest = checked_archive(data)
    target = Path(destination)
    if any(p.is_symlink() for p in [target, *target.parents]):
        raise ValueError('Linked install path refused')
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, raw in files.items():
        p = target / name; p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with p.open('xb') as f: f.write(raw)
        p.chmod(0o600)
    return dict(signature_verified=True, exact_inventory_verified=True,
        archive_sha256=hashlib.sha256(data).hexdigest(), file_count=len(manifest['files']),
        supported_tasks=manifest['supported_tasks'], credential_created=False,
        student_release_ready=False, class_ready=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'signature', 'key', 'fingerprint', 'destination'): p.add_argument('--' + name, required=True)
    p.add_argument('--allow-candidate', action='store_true')
    a = p.parse_args(); os.umask(0o077)
    print('CHECKER_INSTALL=' + json.dumps(install(**vars(a)), separators=(',', ':')))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('CHECKER_INSTALL_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
