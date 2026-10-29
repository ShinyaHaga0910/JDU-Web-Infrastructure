"""Build a deterministic Web Function ZIP from the reviewed local source.

Run npm ci --omit=dev first. This script never deploys, never adds .env files,
and fails if a dependency path leaves node_modules or contains a symlink.
"""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

HERE = Path(__file__).resolve().parent
SOURCE = ('index.js', 'auth.mjs', 'router.mjs', 'grade-client.mjs', 'sessions.mjs', 'acceptance-health.mjs', 'secrets.mjs', 'enrollment-client.mjs', 'enrollment-page.mjs', 'bootstrap-link.mjs', 'bootstrap-artifact.mjs', 'request-body.mjs', 'package.json')


def build(destination):
    modules = HERE / 'node_modules'
    if not all((modules / name).is_dir() for name in ('jose', '@aws-sdk/client-lambda', '@aws-sdk/client-dynamodb', '@aws-sdk/client-secrets-manager', '@aws-sdk/client-s3')):
        raise ValueError('run npm ci --omit=dev first')
    files = [(name, HERE / name) for name in SOURCE]
    for path in modules.rglob('*'):
        relative = path.relative_to(HERE)
        if '.bin' in relative.parts or path.name == '.package-lock.json':
            continue
        if path.is_symlink():
            raise ValueError('symlink in dependencies')
        if not path.is_file():
            continue
        if any(part.startswith('.env') or part == '.git' for part in relative.parts):
            raise ValueError('unexpected secret or repository metadata in dependencies')
        if not path.resolve().is_relative_to(modules.resolve()):
            raise ValueError('dependency escapes package root')
        files.append((relative.as_posix(), path))
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED, compresslevel=9) as output:
        for name, path in sorted(files):
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes(), compresslevel=9)
    return hashlib.sha256(Path(destination).read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output))
