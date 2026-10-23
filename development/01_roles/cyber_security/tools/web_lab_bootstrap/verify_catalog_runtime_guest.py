"""Teacher probe: verify the signed app and offline wheels on the actual Web OS.

Creates a separate, immutable candidate workspace. Does not configure/start the
classroom app, create DB/auth users, or alter the existing repository release.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import urllib.request


def extract_app(data, target):
    entries = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for m in archive:
            path = PurePosixPath(m.name)
            if (not m.isfile() or len(path.parts) < 2 or path.parts[0] != 'jdu-catalog'
                    or any(p in ('.', '..') for p in path.parts) or '\\' in m.name
                    or m.name in entries or len(entries) >= 100 or m.size > 256 * 1024 or m.size < 0):
                raise ValueError('Unsafe app archive member')
            total += m.size
            if total > 4 * 1024 * 1024:
                raise ValueError('App archive too large')
            entries[m.name] = archive.extractfile(m).read()
    manifest = json.loads(entries['jdu-catalog/APP-MANIFEST.json'])
    declared = {'jdu-catalog/' + x['path']: x for x in manifest['files']}
    if (manifest['artifact'] != 'jdu-catalog' or manifest['release_id'] != 'web-2026-10-r1'
            or len(declared) != len(manifest['files'])
            or set(entries) != set(declared) | {'jdu-catalog/APP-MANIFEST.json'}):
        raise ValueError('App inventory differs')
    for name, info in declared.items():
        if (hashlib.sha256(entries[name]).hexdigest(), len(entries[name])) != (info['sha256'], info['size_bytes']):
            raise ValueError('App file differs from signed inventory')
    target.mkdir(mode=0o755, exist_ok=False)
    for name, raw in entries.items():
        path = target.joinpath(*PurePosixPath(name).parts[1:])
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(raw)
        path.chmod(0o644)
    return len(declared)


def run(request):
    if os.geteuid() != 0:
        raise ValueError('Root Web probe required')
    sys.dont_write_bytecode = True
    c = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if c['role'] != 'web' or any(c[k] != request[k] for k in ('lab_id', 'deployment_id', 'instance_id')):
        raise ValueError('Wrong Web node')
    library = Path('/usr/local/lib/jdu-web/web-2026-10-r1')
    for name in ('payload_runtime.py', 'release_validation.py'):
        if hashlib.sha256((library / name).read_bytes()).hexdigest() != request['library_sha256'][name]:
            raise ValueError('Runtime verification library differs')
    sys.path.insert(0, str(library))
    from payload_runtime import signed_manifest
    from release_validation import verify_signature
    key = Path('/var/lib/jdu-web/initial/archive-key.asc')
    manifest, sums = signed_manifest('/var/lib/jdu-web/initial/client-metadata', key,
        c['fingerprint'], c['release_id'], allow_package_candidate=True)
    archive = base64.b64decode(request['archive_b64'], validate=True)
    signature = base64.b64decode(request['signature_b64'], validate=True)
    if hashlib.sha256(archive).hexdigest() != request['archive_sha256']:
        raise ValueError('App archive differs')
    verify_signature(archive, signature, key.read_bytes(), c['fingerprint'])
    workspace = Path('/var/lib/jdu-web/catalog-runtime-candidate-v1')
    workspace.mkdir(mode=0o755, exist_ok=False)
    app_files = extract_app(archive, workspace / 'app')
    prefix = 'http://10.20.2.30/releases/' + c['release_id'] + '/'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def fetch(name, limit):
        with opener.open(prefix + name, timeout=45) as r:
            raw = r.read(limit + 1)
            if r.status != 200 or len(raw) > limit or hashlib.sha256(raw).hexdigest() != sums[name]:
                raise ValueError('Signed internal resource differs')
            return raw
    wheels = json.loads(fetch('manifests/python-packages.json', 65536))
    wheelhouse = workspace / 'wheelhouse'; wheelhouse.mkdir(mode=0o755)
    for w in wheels:
        name = 'artifacts/python/wheelhouse/' + w['filename']
        if Path(w['filename']).name != w['filename']:
            raise ValueError('Invalid wheel filename')
        (wheelhouse / w['filename']).write_bytes(fetch(name, w['size_bytes']))
    lock = workspace / 'requirements.lock'
    lock.write_bytes(fetch('artifacts/python/requirements.lock', 65536))
    packages = json.loads(fetch('manifests/deb-packages.json', 4 * 1024 * 1024))
    versions = {x['package']: x['version'] for x in packages}
    lists = workspace / 'apt-lists'; lists.mkdir()
    cache = workspace / 'apt-archives'; cache.mkdir()
    source = workspace / 'internal.sources'
    source.write_text('Types: deb\nURIs: ' + prefix + 'apt/\nSuites: jdu-noble\nComponents: main\nArchitectures: amd64\nSigned-By: /usr/share/keyrings/jdu-web-archive-keyring.gpg\n')
    environment = dict(os.environ, DEBIAN_FRONTEND='noninteractive', LC_ALL='C')
    apt = ['apt-get', '-o', 'Dir::Etc::sourcelist=' + str(source), '-o', 'Dir::Etc::sourceparts=-',
           '-o', 'Dir::State::lists=' + str(lists), '-o', 'Dir::Cache::archives=' + str(cache),
           '-o', 'Dpkg::Lock::Timeout=600', '-o', 'Acquire::Retries=2']
    def command(args, **kwargs):
        return subprocess.run(args, capture_output=True, check=True, env=environment, timeout=300, **kwargs).stdout
    command(apt + ['update', '-o', 'APT::Update::Error-Mode=any'])
    command(apt + ['install', '-y', '--no-install-recommends',
        'python3-venv=' + versions['python3-venv'], 'python3-pip=' + versions['python3-pip']])
    venv = workspace / 'venv'
    command(['python3', '-m', 'venv', str(venv)])
    command([str(venv / 'bin/python'), '-m', 'pip', '--isolated', '--no-cache-dir', 'install', '--no-index',
             '--find-links=' + str(wheelhouse), '--only-binary=:all:', '--require-hashes', '-r', str(lock)])
    command([str(venv / 'bin/python'), '-m', 'pip', '--isolated', 'check'])
    result = json.loads(command([str(venv / 'bin/python'), '-c',
        "import django,gunicorn,psycopg,json;print(json.dumps(dict(django=django.get_version(),gunicorn=gunicorn.__version__,psycopg=psycopg.__version__)))"]))
    if result != {'django': '5.2.18', 'gunicorn': '26.2.0', 'psycopg': '3.3.6'}:
        raise ValueError('Installed runtime version differs')
    return dict(scope='actual_web_offline_runtime_candidate_not_app_service_acceptance',
        instance_id=c['instance_id'], deployment_id=c['deployment_id'], app_signature_verified=True,
        app_sha256=request['archive_sha256'], app_file_count=app_files, wheel_count=len(wheels),
        offline_pip_check=True, runtime_versions=result, private_credentials_created=False,
        classroom_app_configured=False, class_ready=False)


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.loads(sys.stdin.read(262145))), separators=(',', ':')))
    except Exception as exc:
        print('CATALOG_RUNTIME_PROBE_STOPPED=' + type(exc).__name__)
        if isinstance(exc, subprocess.CalledProcessError):
            print('COMMAND_EXIT_CODE=' + str(exc.returncode))
        raise SystemExit(2)
