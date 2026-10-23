import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from db_observer import hba_policy
from network_checks import named_blocks, named_policy, axfr_refused, inventory
from system_observer import root_volume, sudo_policy_denied
from build_teacher import build, inline_source, legacy_build, validate_upgrade
from upgrade_teacher import propose, review


class ObserverTests(unittest.TestCase):
    def test_sudo_whole_policy_denial_is_not_inferred_from_exit_status(self):
        denied = 'User catalog is not allowed to run sudo on ip-10-20-1-20.\n'
        for status in (0, 1):
            self.assertIs(sudo_policy_denied(CompletedProcess([], status, denied, '')), True)
        for grant in ('(ALL) NOPASSWD: ALL', '(root) /usr/bin/cat'):
            allowed = 'User catalog may run the following commands on host:\n    ' + grant
            self.assertIs(sudo_policy_denied(CompletedProcess([], 0, allowed, '')), False)
        self.assertIsNone(sudo_policy_denied(CompletedProcess([], 1, '', 'policy parse error')))
        self.assertIsNone(sudo_policy_denied(CompletedProcess([], 0, '', '')))
        self.assertIsNone(sudo_policy_denied(None))

    def test_bind_acl_and_forwarding_nested_names(self):
        good = '''acl "clients" { localhost; 10.20.1.10; 10.20.1.20; };
        options { allow-query { clients; }; allow-recursion { clients; };
        allow-query-cache { clients; }; forward only; forwarders { 10.20.0.2; }; };'''
        self.assertEqual(named_policy(named_blocks(good)), (True, True))
        wide = good.replace('10.20.1.20;', '10.20.0.0/16;')
        self.assertFalse(named_policy(named_blocks(wide))[0])
        self.assertFalse(named_policy(named_blocks(good.replace('forward only', 'forward first')))[1])
        self.assertFalse(named_policy(named_blocks(good + ' zone "lab.test" { type primary; allow-query { 0.0.0.0/0; }; };'))[0])

    def test_explicit_axfr_refusal_and_success_against_real_tcp_peer(self):
        for rcode, expected in ((5, True), (9, True), (0, False)):
            with socket.socket() as server:
                server.bind(('127.0.0.1', 0)); server.listen()
                def reply():
                    with server.accept()[0] as connection:
                        size = struct.unpack('!H', connection.recv(2))[0]
                        data = connection.recv(size)
                        transaction = struct.unpack('!H', data[:2])[0]
                        response = struct.pack('!HHHHHH', transaction, 0x8000 | rcode, 0, 0, 0, 0)
                        connection.sendall(struct.pack('!H', len(response)) + response)
                worker = threading.Thread(target=reply); worker.start()
                self.assertIs(axfr_refused('127.0.0.1', server.getsockname()[1]), expected)
                worker.join()
        with patch('network_checks.socket.create_connection', side_effect=TimeoutError):
            self.assertIsNone(axfr_refused())

    def test_hba_requires_exact_source_and_profile_pairs_not_broad_allow(self):
        rows = [dict(error=None, type='local', auth_method='peer', user_name=['postgres'], database=['all'])]
        for name in ('catalog_setup', 'catalog_app'):
            rows.append(dict(error=None, type='host', auth_method='scram-sha-256', user_name=[name],
                             database=['jdu_catalog'], address='10.20.1.20', netmask='255.255.255.255'))
        self.assertTrue(hba_policy(rows, 'mission'))
        self.assertFalse(hba_policy(rows, 'practice'))
        rows[-1]['netmask'] = '255.255.255.0'
        self.assertFalse(hba_policy(rows, 'mission'))

    def test_ebs_mapping_follows_root_partition(self):
        disks = [dict(serial='vol0123456789abcdef0', children=[dict(mountpoints=['/'])]),
                 dict(serial='vol11111111111111111', mountpoints=['/data'])]
        self.assertEqual(root_volume(disks), 'vol-0123456789abcdef0')
        self.assertIsNone(root_volume([dict(serial='unrelated', mountpoints=['/'])]))

    def test_public_inventory_decodes_escaped_text_without_accepting_duplicate_codes(self):
        html = '<table><tr><th>A</th><td>&lt;safe&gt;</td><td>2</td><td>Shelf</td><td>—</td></tr></table>'
        self.assertEqual(inventory(html)['A'][:3], ['<safe>', '2', 'Shelf'])
        with self.assertRaises(ValueError):
            inventory(html + html)

    def test_inline_teacher_bundle_runs_and_only_code_two_routes_change(self):
        old, new = legacy_build(), build()
        validate_upgrade(old, new)
        self.assertLess(len(json.dumps(new).encode()), 51200)
        namespace = {}
        exec(compile(inline_source(), '<teacher-inline>', 'exec'), namespace)
        self.assertTrue(callable(namespace['handler']))
        bad = json.loads(json.dumps(new))
        bad['Resources']['ProgressFunction']['Properties']['Timeout'] = 60
        with self.assertRaises(ValueError):
            validate_upgrade(old, bad)

    def test_existing_routes_are_retained_for_code_only_upgrade(self):
        old = build()
        old['Resources']['ProgressFunction']['Properties']['Code'] = {'ZipFile': 'previous-code'}
        new = propose(old)
        validate_upgrade(old, new)
        self.assertEqual(new['Resources']['Route8'], old['Resources']['Route8'])
        change = dict(Status='CREATE_COMPLETE', ExecutionStatus='AVAILABLE', Changes=[dict(ResourceChange=dict(
            LogicalResourceId='ProgressFunction', Action='Modify', ResourceType='AWS::Lambda::Function',
            Replacement='False', Details=[{'Target': {'Name': 'Code'}}]))])
        review(change, old)
        bad = json.loads(json.dumps(change))
        bad['Changes'][0]['ResourceChange']['Details'][0]['Target']['Name'] = 'Role'
        with self.assertRaises(ValueError):
            review(bad, old)
        bad = json.loads(json.dumps(old))
        bad['Resources']['Route8']['Properties']['ApiId'] = {'Ref': 'AnotherApi'}
        with self.assertRaises(ValueError):
            propose(bad)
        bad = json.loads(json.dumps(new))
        bad['Resources']['Route9']['Properties']['RouteKey'] = 'GET /public/grades'
        with self.assertRaises(ValueError):
            validate_upgrade(old, bad)

    def test_initial_upgrade_review_requires_exact_additions(self):
        old = legacy_build()
        changes = [dict(ResourceChange=dict(LogicalResourceId='ProgressFunction', Action='Modify',
            ResourceType='AWS::Lambda::Function', Replacement='False', Details=[{'Target': {'Name': 'Code'}}]))]
        for index in (8, 9):
            changes.append(dict(ResourceChange=dict(LogicalResourceId='Route' + str(index), Action='Add',
                ResourceType='AWS::ApiGatewayV2::Route')))
        change = dict(Status='CREATE_COMPLETE', ExecutionStatus='AVAILABLE', Changes=changes)
        review(change, old)
        with self.assertRaises(ValueError):
            review(dict(change, Changes=changes[:1]), old)


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = Path(__file__).resolve().parents[1] / 'web_lab_catalog'
        spec = importlib.util.spec_from_file_location('catalog_config_under_test', app / 'configuration.py')
        cls.config = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.config)

    def test_practice_profile_accepts_only_its_own_role(self):
        config = dict(DJANGO_SECRET_KEY='fictional-test-' + 'x' * 50,
                      DJANGO_ALLOWED_HOSTS='web.lab.test,admin.lab.test,10.20.1.20',
                      DB_HOST='db.lab.test', DB_PORT='5432', DB_NAME='jdu_catalog_practice', DB_USER='catalog_practice_app',
                      DB_PASSWORD='fictional-test-password-2026', DJANGO_STATIC_ROOT='/var/lib/jdu-catalog/static', CATALOG_SITE_NAME='Fixture')
        self.assertEqual(self.config.profile_of(self.config.decode(self.config.encode(config, 'runtime'), 'runtime')), 'practice')
        config['DB_USER'] = 'catalog_app'
        with self.assertRaises(ValueError):
            self.config.validate(config, 'runtime')

    @unittest.skipUnless(os.geteuid() == 0, 'real root-owned temporary files only')
    def test_explicit_profile_switch_preserves_both_and_refuses_live_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); profiles = root / 'profiles'; profiles.mkdir(mode=0o700)
            configs = {}
            for profile, values in self.config.PROFILES.items():
                config = dict(DJANGO_SECRET_KEY='fictional-' + profile + '-' + 'x' * 50,
                    DJANGO_ALLOWED_HOSTS='web.lab.test,admin.lab.test,10.20.1.20', DB_HOST='db.lab.test', DB_PORT='5432',
                    DB_NAME=values[0], DB_USER=values[2], DB_PASSWORD='fictional-' + profile + '-runtime-2026',
                    DJANGO_STATIC_ROOT='/var/lib/jdu-catalog/static', CATALOG_SITE_NAME='Fixture')
                self.config.private_create(profiles / (profile + '.app.env'), config, 'runtime')
                configs[profile] = config
            self.config.private_create(root / 'app.env', configs['practice'], 'runtime')
            class Inactive:
                returncode = 3
            with patch('subprocess.run', return_value=Inactive()):
                self.config.activate_profile(root, 'mission')
                self.assertEqual(self.config.private_read(root / 'app.env', 'runtime'), configs['mission'])
                self.assertEqual(self.config.private_read(profiles / 'practice.app.env', 'runtime'), configs['practice'])
                setup = dict(configs['mission'], DB_USER='catalog_setup')
                self.config.private_create(root / 'setup.env', setup, 'setup')
                with self.assertRaises(ValueError):
                    self.config.activate_profile(root, 'practice')
                self.assertEqual(self.config.private_read(root / 'app.env', 'runtime'), configs['mission'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
