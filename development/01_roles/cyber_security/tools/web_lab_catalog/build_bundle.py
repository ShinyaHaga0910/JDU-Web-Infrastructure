"""Build an immutable, deterministic catalog archive from an explicit public file list."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import stat
import tarfile

FILES = (
    'manage.py', 'configuration.py', 'manage_secure.py', 'profile_sql.py',
    'jdu_catalog/__init__.py', 'jdu_catalog/settings.py', 'jdu_catalog/urls.py',
    'jdu_catalog/wsgi.py', 'jdu_catalog/middleware.py',
    'catalog/__init__.py', 'catalog/apps.py', 'catalog/models.py', 'catalog/views.py', 'catalog/admin.py',
    'catalog/migrations/__init__.py', 'catalog/migrations/0001_initial.py',
    'catalog/management/__init__.py', 'catalog/management/password_input.py',
    'catalog/management/commands/__init__.py', 'catalog/management/commands/create_lab_admin.py',
    'catalog/management/commands/seed_catalog.py', 'catalog/management/commands/set_lab_password.py',
    'catalog/static/catalog/inventory.css', 'templates/catalog/inventory.html', 'templates/admin/base_site.html',
    'config/app.env.example', 'config/jdu-catalog.service', 'config/jdu-catalog.nginx.conf',
    'sql/01_create_roles.sql', 'sql/02_prepare_schema.sql', 'sql/03_runtime_grants.sql',
    'sql/04_disable_setup.sql', 'sql/check_item.sql', 'README.md',
)


def bundle(root):
    root = Path(root).resolve()
    files = {}
    for name in FILES:
        path = root / name
        if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent and root in [p, *p.parents]):
            raise ValueError('Archive source links are forbidden')
        s = path.stat()
        if not stat.S_ISREG(s.st_mode) or s.st_size > 256 * 1024:
            raise ValueError('Archive source must be a small regular public file')
        files[name] = path.read_bytes()
    manifest = dict(schema_version=1, artifact='jdu-catalog', release_id='web-2026-10-r1',
        scope='catalog_app_candidate_not_os_acceptance', credentials_included=False,
        files=[dict(path=k, sha256=hashlib.sha256(v).hexdigest(), size_bytes=len(v)) for k, v in sorted(files.items())])
    files['APP-MANIFEST.json'] = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo('jdu-catalog/' + name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            archive.addfile(info, io.BytesIO(data))
    return gzip.compress(tar.getvalue(), mtime=0), manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    data, manifest = bundle(Path(__file__).resolve().parent)
    with Path(a.output).open('xb') as f:
        f.write(data)
    print(json.dumps(dict(artifact='jdu-catalog', sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data), file_count=len(manifest['files']), student_release_ready=False)))


if __name__ == '__main__': main()
