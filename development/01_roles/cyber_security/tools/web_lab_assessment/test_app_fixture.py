"""Local-only app fixture data creation with real PostgreSQL, never AWS."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

import psycopg
from psycopg import sql

from app_fixture_guest import extract_app, SETUP_CHILD
from app_fixture_manager import create_private, read_private
from freeze_registry import application_bundle
from registry import REGISTRY

CACHE = Path.home() / '.cache/jdu-web-builds/2026-10-15'
SOCKET = str(CACHE / 'catalog-pg-socket')
APP = Path(__file__).resolve().parents[1] / 'web_lab_catalog'


def connection(database='postgres', **kwargs):
    return psycopg.connect(host=SOCKET, port=55439, user='fixture_owner', dbname=database, **kwargs)


class AppFixtureAcceptance(unittest.TestCase):
    def test_application_bytes_are_bound_to_the_frozen_manifest(self):
        raw, manifest = application_bundle()
        request = dict(application_b64=base64.b64encode(raw).decode(), registry=REGISTRY)
        files = extract_app(request)
        self.assertEqual(len(files), len(manifest['files']) + 1)
        bad = copy.deepcopy(request)
        bad['application_b64'] = base64.b64encode(raw + b'altered').decode()
        with self.assertRaises(ValueError):
            extract_app(bad)
        bad = copy.deepcopy(request)
        bad['registry']['application_manifest']['files'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            extract_app(bad)

    def test_actual_fixed_migrations_samples_staff_and_required_records(self):
        name = 'd11_fixture_' + uuid.uuid4().hex[:12]
        with connection(autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE DATABASE {} OWNER fixture_owner').format(sql.Identifier(name)))
        try:
            profile = REGISTRY['profiles']['practice']
            config = dict(DJANGO_SECRET_KEY='fictional-local-fixture-child-' + 'x' * 50,
                DJANGO_ALLOWED_HOSTS='admin.lab.test,web.lab.test,127.0.0.1', DB_HOST=SOCKET, DB_PORT='55439',
                DB_NAME=name, DB_USER='fixture_owner', DB_PASSWORD='fictional-unused-unix-socket-only',
                DJANGO_STATIC_ROOT=str(CACHE / 'catalog-proxy-fixture/static'))
            data = dict(config=config, admin=profile['app_admin'], password='Fictional-Child-Admin-Only-2026!', records=profile['records'])
            # Local rootless fixture uses the current uid; actual AWS performs the catalog privilege drop.
            prefix = ("import os,pwd,types\npwd.getpwnam=lambda _:types.SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())\n"
                "os.setgroups=lambda _:None\n")
            result = subprocess.run([sys.executable, '-B', '-c', prefix + SETUP_CHILD], input=json.dumps(data),
                capture_output=True, text=True, cwd=APP, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            with connection(name) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0], 11)
                self.assertEqual(conn.execute('SELECT count(*) FROM catalog_item').fetchone()[0], 5)
                self.assertEqual(conn.execute("SELECT is_staff,is_superuser,is_active FROM auth_user WHERE username='practice_admin'").fetchone(), (True, False, True))
                self.assertEqual(conn.execute('SELECT count(*) FROM auth_user_user_permissions').fetchone()[0], 3)
                self.assertEqual(conn.execute("SELECT quantity,is_public FROM catalog_item WHERE code='P5-PRIVATE-001'").fetchone(), (2, False))
        finally:
            # Only this newly created, explicitly disposable local test database is removed.
            with connection(autocommit=True) as conn:
                conn.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


class PrivateFiles(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0, 'root-owned temporary fixture files')
    def test_private_credential_container_preserves_existing_and_refuses_links_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.private.json'
            value = {'fictional_data_only': 'not-an-issued-credential'}
            create_private(path, value)
            self.assertEqual(read_private(path), value)
            with self.assertRaises(FileExistsError):
                create_private(path, {'replacement': True})
            self.assertEqual(read_private(path), value)
            linked = Path(temp) / 'linked.json'; linked.symlink_to(path)
            with self.assertRaises(OSError):
                read_private(linked)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                read_private(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
