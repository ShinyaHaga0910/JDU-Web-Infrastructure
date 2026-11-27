"""Verify and unpack the provided app; optionally fetch signed wheels. Does not install or configure."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
APP_HASH = '212cc8faf7a37bf0b3227de69993f5e2c5fa4e403b9b815ce280bf408dd53d24'


def unpack(raw, registry):
    if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != APP_HASH or registry['application_archive_sha256'] != APP_HASH:
        raise ValueError('Wrong signed classroom app')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for item in archive:
            path = PurePosixPath(item.name)
            name = item.name.removeprefix('jdu-catalog/')
            if (not item.name.startswith('jdu-catalog/') or not item.isfile() or name in files
                    or any(x in ('', '.', '..') for x in name.split('/')) or '\\' in name or ':' in name
                    or not 0 <= item.size <= 262144 or len(files) >= 100):
                raise ValueError('Unsafe classroom archive')
            files[name] = archive.extractfile(item).read()
    manifest = json.loads(files['APP-MANIFEST.json'])
    if manifest != registry['application_manifest'] or set(files) != {x['path'] for x in manifest['files']} | {'APP-MANIFEST.json'}:
        raise ValueError('Wrong app inventory')
    for item in manifest['files']:
        raw = files[item['path']]
        if (len(raw), hashlib.sha256(raw).hexdigest()) != (item['size_bytes'], item['sha256']):
            raise ValueError('App resource differs')
    return files


def retain(path, raw):
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('Linked resources refused')
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise ValueError('Different existing resource retained')
        return
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644), 'wb') as f:
        os.fchmod(f.fileno(), 0o644)
        f.write(raw)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wheels', action='store_true')
    a = p.parse_args()
    if os.geteuid() != 0 or ROOT != Path('/var/lib/jdu-web/lesson-resources-r1'):
        raise ValueError('Use the public resource directory on your registered Web or DB server')
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if b['role'] not in ('web', 'db') or a.wheels and b['role'] != 'web':
        raise ValueError('Wheels are for the Web server only')
    registry = json.loads((ROOT / 'assessment-registry.json').read_text())
    for name, raw in unpack((ROOT / 'catalog-app.tar.gz').read_bytes(), registry).items():
        retain(ROOT / 'app' / name, raw)
    print('Complete: PUBLIC_APP_RESOURCES_VERIFIED')
    if not a.wheels:
        return
    if (ROOT / 'classroom-python-packages.json').is_file():
        # The CloudShell installer staged this lock from the same immutable GitHub commit.
        wheels = json.loads((ROOT / 'classroom-python-packages.json').read_text())
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        prefix = 'http://10.20.2.30/releases/' + b['release_id'] + '/artifacts/python/wheelhouse/'
        for wheel in wheels:
            name, size = wheel['filename'], wheel['size_bytes']
            if Path(name).name != name or not name.endswith('.whl') or not 0 < size <= 32 * 1024 * 1024:
                raise ValueError('Unsafe wheel lock')
            with opener.open(prefix + name, timeout=45) as response:
                raw = response.read(size + 1)
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != wheel['sha256']:
                raise ValueError('Offline wheel differs from the GitHub lock')
            retain(ROOT / 'wheels' / name, raw)
        retain(ROOT / 'requirements.lock', (ROOT / 'classroom-requirements.lock').read_bytes())
        print('OFFLINE_WHEELS_READY=' + str(len(wheels)) + '; pip has not been run')
        return
    sys.path.insert(0, '/usr/local/lib/jdu-web/' + b['release_id'])
    from payload_runtime import signed_manifest
    _, sums = signed_manifest('/var/lib/jdu-web/initial/client-metadata', '/var/lib/jdu-web/initial/archive-key.asc',
        b['fingerprint'], b['release_id'], allow_package_candidate=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prefix = 'http://10.20.2.30/releases/' + b['release_id'] + '/'
    def fetch(name, limit):
        with opener.open(prefix + name, timeout=45) as response:
            raw = response.read(limit + 1)
            if response.status != 200 or len(raw) > limit or hashlib.sha256(raw).hexdigest() != sums[name]:
                raise ValueError('Signed offline resource differs')
        return raw
    lock = fetch('artifacts/python/requirements.lock', 65536)
    wheels = json.loads(fetch('manifests/python-packages.json', 65536))
    for wheel in wheels:
        name = wheel['filename']
        if Path(name).name != name or not name.endswith('.whl'):
            raise ValueError('Unsafe wheel name')
        retain(ROOT / 'wheels' / name, fetch('artifacts/python/wheelhouse/' + name, wheel['size_bytes']))
    retain(ROOT / 'requirements.lock', lock)
    print('SIGNED_OFFLINE_WHEELS_READY=' + str(len(wheels)) + '; pip has not been run')


if __name__ == '__main__':
    main()
