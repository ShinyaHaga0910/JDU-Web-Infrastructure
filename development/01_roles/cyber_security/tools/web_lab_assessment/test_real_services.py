"""Rootless PostgreSQL16 + real Nginx/Gunicorn acceptance. Never targets AWS."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch

import psycopg

import app_probe
import db_observer
from http_guest_v2 import current_log_matches

APP = Path(__file__).resolve().parents[1] / 'web_lab_catalog'
CACHE = Path.home() / '.cache/jdu-web-builds/2026-10-15'
SOCKET = str(CACHE / 'catalog-pg-socket')


def connection(database='postgres'):
    return psycopg.connect(host=SOCKET, port=55439, user='fixture_owner', dbname=database)


def readonly(query, database='postgres'):
    try:
        with connection(database) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            row = conn.execute(query).fetchone()
            return row[0] if row else None
    except psycopg.Error:
        return None


class SQLIntegration(unittest.TestCase):
    def test_effective_table_and_column_privileges_on_postgresql16(self):
        with patch.object(db_observer, 'admin_sql', readonly):
            self.assertTrue(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['catalog_item'], {'SELECT', 'INSERT', 'UPDATE'}))
            self.assertTrue(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['auth_user'], {'SELECT'}, ('last_login', 'password')))
            self.assertTrue(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['django_migrations'], set()))
            self.assertTrue(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['django_session'], {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}))
            self.assertTrue(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['django_admin_log'], {'SELECT', 'INSERT'}))
            self.assertFalse(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['auth_user'], {'SELECT', 'UPDATE'}))

    def test_role_metadata_returns_only_password_null_boolean(self):
        with patch.object(db_observer, 'admin_sql', readonly):
            data = db_observer.role_basics('mission')
        self.assertIsNotNone(data)
        self.assertEqual(data['database_owner'], 'catalog_setup')
        roles = {r['name']: r for r in data['roles']}
        self.assertTrue(roles['catalog_setup']['password_null'])
        self.assertFalse(roles['catalog_setup']['login'])
        self.assertNotIn('rolpassword', str(data))

    def test_column_grant_escalation_is_detected_and_rolled_back(self):
        with connection('jdu_catalog') as conn:
            # One private transaction: no changed grant is committed to the fixture.
            conn.execute('GRANT UPDATE(is_superuser) ON auth_user TO catalog_app')
            def same_transaction(query, database):
                return conn.execute(query).fetchone()[0]
            with patch.object(db_observer, 'admin_sql', same_transaction):
                self.assertFalse(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['auth_user'], {'SELECT'}, ('last_login', 'password')))
            conn.rollback()
        with patch.object(db_observer, 'admin_sql', readonly):
            self.assertTrue(db_observer.table_permissions('jdu_catalog', 'catalog_app', ['auth_user'], {'SELECT'}, ('last_login', 'password')))


class HTTPIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('catalog_proxy_fixture', APP / 'tests/test_proxy.py')
        cls.fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.fixture)
        cls.fixture.ProxyAcceptance.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.ProxyAcceptance.doClassCleanups()

    def test_real_login_create_edit_db_public_logout_and_denial(self):
        def lookup(code):
            with connection('jdu_catalog') as conn:
                row = conn.execute("SELECT json_build_object('id',id,'code',code,'name',name,'quantity',quantity,"
                    "'location',location,'is_public',is_public) FROM catalog_item WHERE code=%s", (code,)).fetchone()
                return row[0] if row else None
        client = lambda: app_probe.AdminClient('127.0.0.1', 55441)
        public = lambda code, expected: app_probe.public_match(code, expected, address='127.0.0.1', port=55440)
        nonce = uuid.uuid4().hex
        result = app_probe.probe('mission', nonce, 'Fictional-Admin-Only-2026!', lookup, client_factory=client, public=public)
        self.assertEqual(result, {cid: True for cid in result}, result)
        self.assertEqual(lookup('CK-M-' + nonce[:12])['quantity'], 2)
        self.assertIsNone(lookup('CK-D-' + nonce[:12]))
        self.assertNotIn('Fictional-Admin-Only-2026!', str(result))

    def test_http_mission_static_route_and_nonce_log_survive_catalog_proxy(self):
        nonce = uuid.uuid4().hex
        status, _, body = self.fixture.ProxyAcceptance.request(55440, '/mission.txt?jdu_check=' + nonce)
        self.assertEqual(status, 200)
        self.assertEqual(body, 'JDU WEB-02 mission: independent HTTP delivery.\n')
        request = dict(bastion_ip='127.0.0.1', nonce=nonce)
        logs = [self.fixture.WORK / 'access.log', self.fixture.WORK / 'jdu-catalog-public.access.log']
        self.assertTrue(current_log_matches(request, {'path': '/mission.txt'}, paths=logs))
        self.assertFalse(current_log_matches(dict(request, nonce=uuid.uuid4().hex), {'path': '/mission.txt'}, paths=logs))
        self.assertFalse(current_log_matches(dict(request, bastion_ip='10.20.1.10'), {'path': '/mission.txt'}, paths=logs))


if __name__ == '__main__':
    unittest.main(verbosity=2)
