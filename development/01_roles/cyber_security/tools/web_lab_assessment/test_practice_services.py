"""Real practice DB/HTTP acceptance and mission/practice isolation in local WSL only."""
import importlib.util
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import psycopg
import app_probe
import db_observer
from prepare_local_practice import CACHE, SOCKET, RUNTIME_PASSWORD

APP = Path(__file__).resolve().parents[1] / 'web_lab_catalog'


def connection(database='jdu_catalog_practice'):
    return psycopg.connect(host=SOCKET, port=55439, user='fixture_owner', dbname=database)


def lookup(code, database='jdu_catalog_practice'):
    with connection(database) as conn:
        row = conn.execute("SELECT json_build_object('id',id,'code',code,'name',name,'quantity',quantity,"
            "'location',location,'is_public',is_public) FROM catalog_item WHERE code=%s", (code,)).fetchone()
        return row[0] if row else None


class PracticeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (CACHE / 'd11-practice-fixture.json').is_file():
            raise RuntimeError('Explicitly prepare the local fictional practice fixture first')
        spec = importlib.util.spec_from_file_location('practice_proxy_fixture', APP / 'tests/test_proxy.py')
        cls.fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.fixture)
        cls.fixture.ENV.update(DB_NAME='jdu_catalog_practice', DB_USER='catalog_practice_app', DB_PASSWORD=RUNTIME_PASSWORD)
        cls.fixture.ProxyAcceptance.setUpClass()
        cls.addClassCleanup(cls.fixture.ProxyAcceptance.doClassCleanups)

    def test_real_practice_login_create_edit_logout_keeps_mission_isolated(self):
        nonce = uuid.uuid4().hex
        code = 'CK-P-' + nonce[:12]
        client = lambda: app_probe.AdminClient('127.0.0.1', 55441)
        public = lambda code, expected: app_probe.public_match(code, expected, address='127.0.0.1', port=55440)
        result = app_probe.probe('practice', nonce, 'Fictional-Practice-Admin-Only-2026!', lookup,
            client_factory=client, public=public)
        self.assertEqual(result, {cid: True for cid in result}, result)
        self.assertEqual(lookup(code)['quantity'], 2)
        self.assertIsNone(lookup(code, 'jdu_catalog'))
        self.assertFalse(client().login('lab_admin', 'Fictional-Admin-Only-2026!'))

    def test_runtime_cannot_connect_to_mission(self):
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(host='127.0.0.1', port=55439, user='catalog_practice_app',
                password=RUNTIME_PASSWORD, dbname='jdu_catalog', connect_timeout=3)

    def test_practice_effective_grants_and_retired_setup(self):
        def readonly(query, database='postgres'):
            with connection(database) as conn:
                conn.execute('SET TRANSACTION READ ONLY')
                row = conn.execute(query).fetchone()
                return row[0] if row else None
        with patch.object(db_observer, 'admin_sql', readonly):
            self.assertTrue(db_observer.table_permissions('jdu_catalog_practice', 'catalog_practice_app',
                ['catalog_item'], {'SELECT', 'INSERT', 'UPDATE'}))
            self.assertTrue(db_observer.table_permissions('jdu_catalog_practice', 'catalog_practice_app',
                ['auth_user'], {'SELECT'}, ('last_login', 'password')))
            state = db_observer.role_basics('practice')
        setup = next(r for r in state['roles'] if r['name'] == 'catalog_practice_setup')
        self.assertFalse(setup['login'])
        self.assertTrue(setup['password_null'])
        self.assertEqual(setup['sessions'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
