"""Existing checker source/contract integration; no shell or live network runs."""
import ast
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
sys.path[:0] = [str(ROOT / 'web_lab_assessment'), str(ROOT / 'web_lab_teacher')]
import test_assessment_command_jobs as fixtures
from assessment_command_jobs import CommandJobs, JobDenied, sha
from assessment_observation import Observation, checked_snapshot
from registry import REGISTRY_BYTES, build_report, canonical_checks, score
from http_guest_v2 import LEGACY_SHA256, CONTRACT_SHA256 as HTTP_SHA256


class ObservationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CommandJobsTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.spec = copy.deepcopy(self.fixture.spec)
        self.spec['task_id'] = 'M1'
        raw_key = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + b'x' * 32
        self.snapshot = {'spec_sha256': sha(self.spec),
            'private_ips': {'bastion': '10.20.1.10', 'web': '10.20.1.20',
                           'dns': '10.20.2.10', 'db': '10.20.2.20', 'repo': '10.20.2.30'},
            'public_web_ipv4': '93.184.216.34', 'network_baseline': True,
            'expected_public_key': 'ssh-ed25519 ' + base64.b64encode(raw_key).decode(),
            'root_volumes': {r: ['vol-' + format(i, '017x')] for i, r in enumerate(self.spec['instances'], 1)}}
        self.probes, self.http_calls = [], []
        self.probe_result, self.http_status = True, 403

    def observer(self):
        def probe(*args):
            self.probes.append(args)
            return self.probe_result
        def http(address, path, **kwargs):
            self.http_calls.append((address, path, kwargs))
            status = 200 if path == '/' else self.http_status
            return None if status is None else (status, {}, 'unretained response body')
        return Observation(self.spec, self.snapshot, http_probe=probe, http=http)

    def select(self, task):
        self.spec['task_id'] = task
        self.snapshot['spec_sha256'] = sha(self.spec)

    def legacy_http(self):
        return {'mission_id': self.spec['task_id'], 'lab_id': self.spec['lab_id'],
            'deployment_id': self.spec['deployment_id'], 'instance_id': self.spec['instances']['web'],
            'nonce': self.spec['run_id'].replace('-', ''),
            'checked_at': datetime.fromtimestamp(self.fixture.now, timezone.utc).isoformat(),
            'checks': {cid: True for cid in canonical_checks(self.spec['task_id'])}}

    def generic(self):
        values = {cid: True for cid in canonical_checks(self.spec['task_id'])}
        for cid in ('WEB06_PASSWORD_LOGIN', 'WEB06_CREATE_REFLECT', 'WEB06_EDIT_REFLECT',
                    'WEB06_LOGOUT', 'WEB07_ANONYMOUS_DENIED', 'WEB07_BAD_PASSWORD_DENIED'):
            if cid in values:
                values[cid] = None
        return build_report(self.spec['task_id'], self.spec, values, self.spec['run_id'],
            checked_at=datetime.fromtimestamp(self.fixture.now, timezone.utc).isoformat())

    def unpack(self, command):
        self.assertTrue(command.startswith('python3 -c '))
        script = shlex.split(command)[2]
        match = re.search(r'base64\.b64decode\((\x27[^\x27]*\x27)\)', script)
        self.assertIsNotNone(match)
        return json.loads(zlib.decompress(base64.b64decode(ast.literal_eval(match[1]))))

    def test_http_compiler_retains_original_sources_and_pinned_internal_access(self):
        package = self.unpack(self.observer().command(self.spec))
        request = package['request']
        self.assertEqual(request['mission_id'], 'M1')
        self.assertEqual(request['instance_id'], self.spec['instances']['bastion'])
        self.assertEqual(request['web_id'], self.spec['instances']['web'])
        self.assertEqual(request['expected_public_key'], self.snapshot['expected_public_key'])
        self.assertEqual(request['nonce'], self.spec['run_id'].replace('-', ''))
        self.assertEqual(hashlib.sha256(base64.b64decode(request['contract_source_b64'])).hexdigest(), HTTP_SHA256)
        source = base64.b64decode(request['guest_source_b64']).decode()
        legacy = ast.literal_eval(source.splitlines()[0].split('=', 1)[1])
        self.assertEqual(hashlib.sha256(base64.b64decode(legacy)).hexdigest(), LEGACY_SHA256)
        self.assertEqual(package['source'], source)
        self.assertNotIn('owner_hash', request)
        self.assertNotIn('password', request)

    def test_generic_compiler_uses_exact_existing_registry_and_source_transport(self):
        self.select('M2')
        package = self.unpack(self.observer().command(self.spec))
        self.assertEqual(package['sources']['assessment-registry.json'].encode(), REGISTRY_BYTES)
        self.assertEqual(package['request']['operation'], 'collect')
        self.assertEqual(package['request']['task_id'], 'M2')
        self.assertEqual(package['request']['instances'], self.spec['instances'])
        self.assertEqual(package['request']['root_volumes'], self.snapshot['root_volumes'])
        self.assertNotIn('fixture', ' '.join(package['sources']))
        self.assertNotIn('password', package['request'])

    def test_http_completion_adds_actual_external_entry_test_and_existing_eight_points(self):
        output = self.observer().finish(self.spec, json.dumps(self.legacy_http()))
        self.assertEqual(score(output['report'])['raw_earned'], 8)
        self.assertEqual(output['report']['run_id'], self.spec['run_id'])
        self.assertEqual(self.probes[0][0:2], ('93.184.216.34', '/mission.txt'))
        self.assertEqual(self.probes[0][-1], self.spec['run_id'].replace('-', ''))

    def test_practice_http_uses_its_own_fixed_body_and_stays_ungraded(self):
        self.select('P1')
        result = self.observer().finish(self.spec, json.dumps(self.legacy_http()))
        self.assertEqual(self.probes[0][1], '/practice.txt')
        self.assertFalse(score(result['report'])['counts_toward_assessment'])

    def test_external_failure_and_unknown_are_not_silently_passed(self):
        self.probe_result = False
        report = self.observer().finish(self.spec, json.dumps(self.legacy_http()))['report']
        self.assertEqual(score(report)['raw_earned'], 7)
        self.probe_result = None
        report = self.observer().finish(self.spec, json.dumps(self.legacy_http()))['report']
        self.assertFalse(score(report)['evaluable'])
        self.assertEqual(score(report)['unresolved'], 1)

    def test_missing_public_address_is_unknown_without_a_probe(self):
        self.snapshot['public_web_ipv4'] = None
        report = self.observer().finish(self.spec, json.dumps(self.legacy_http()))['report']
        self.assertFalse(score(report)['evaluable'])
        self.assertEqual(self.probes, [])

    def test_http_result_must_match_lab_web_task_nonce_and_complete_contract(self):
        good = self.legacy_http()
        for change in ({'lab_id': 'other-lab'}, {'instance_id': self.spec['instances']['dns']},
                       {'mission_id': 'P1'}, {'nonce': '0' * 32}, {'checks': {}},
                       {'checks': {**good['checks'], 'arbitrary-score': True}}):
            with self.assertRaises((ValueError, JobDenied)):
                self.observer().finish(self.spec, json.dumps({**good, **change}))
        self.assertEqual(self.probes, [])

    def test_snapshot_rejects_cross_operation_and_secret_fields(self):
        for change in ({'spec_sha256': '0' * 64}, {'password': 'not-allowed'},
                       {'network_baseline': 'yes'}, {'expected_public_key': 'PRIVATE KEY'},
                       {'private_ips': {**self.snapshot['private_ips'], 'web': '169.254.169.254'}},
                       {'root_volumes': {r: ['vol-' + '1' * 17] for r in self.spec['instances']}}):
            with self.assertRaises(JobDenied):
                checked_snapshot(self.spec, {**self.snapshot, **change})

    def test_public_probe_cannot_target_private_metadata_loopback_dns_or_ipv6(self):
        for address in ('127.0.0.1', '169.254.169.254', '10.20.1.20', 'localhost', '::1', '2606:4700:4700::1111'):
            with self.assertRaises(JobDenied):
                checked_snapshot(self.spec, {**self.snapshot, 'public_web_ipv4': address})
        self.assertEqual(self.probes, [])

    def test_m6_public_entry_failure_wins_and_unknown_does_not_upgrade_internal_result(self):
        self.select('M6')
        good = self.generic()
        self.http_status = 200
        report = self.observer().finish(self.spec, json.dumps({'report': good}))['report']
        selected = {c['id']: c['status'] for c in report['checks']}
        self.assertEqual(selected['WEB07_PUBLIC_ADMIN_DENIED'], 'FAIL')
        self.assertEqual(selected['WEB07_SECRET_HTTP_DENIED'], 'FAIL')
        self.http_status = None
        report = self.observer().finish(self.spec, json.dumps({'report': good}))['report']
        selected = {c['id']: c['status'] for c in report['checks']}
        self.assertEqual(selected['WEB07_PUBLIC_ADMIN_DENIED'], 'UNKNOWN')
        self.http_status = 403
        for c in good['checks']:
            if c['id'] == 'WEB07_PUBLIC_ADMIN_DENIED':
                c['status'] = 'FAIL'
        report = self.observer().finish(self.spec, json.dumps({'report': good}))['report']
        self.assertEqual(next(c['status'] for c in report['checks'] if c['id'] == 'WEB07_PUBLIC_ADMIN_DENIED'), 'FAIL')
        self.assertTrue(all(x[0] == self.snapshot['public_web_ipv4'] for x in self.http_calls))

    def test_noninteractive_collector_cannot_assert_password_login_or_foreign_run(self):
        self.select('M5')
        report = self.generic()
        for c in report['checks']:
            if c['id'] == 'WEB06_PASSWORD_LOGIN':
                c['status'] = 'PASS'
        with self.assertRaises(ValueError):
            self.observer().finish(self.spec, json.dumps({'report': report}))
        self.select('M2')
        report = self.generic()
        report['run_id'] = str(__import__('uuid').uuid4())
        with self.assertRaises(JobDenied):
            self.observer().finish(self.spec, json.dumps({'report': report}))

    def test_real_adapter_and_durable_outbox_keep_first_request_id_on_retry(self):
        obs = self.observer()
        f = self.fixture
        f.ssm.output = json.dumps(self.legacy_http())
        jobs = CommandJobs(f.db, 'jobs', f.ssm, obs.command, lambda _: True,
            clock=lambda: f.now, finish_observation=obs.finish)
        jobs.enqueue(self.spec)
        jobs.advance(self.spec)
        self.assertEqual(jobs.advance(self.spec)['phase'], 'report_ready')
        original = jobs.retained_report(self.spec)
        self.assertEqual(score(original)['raw_earned'], 8)
        for _ in range(3):
            jobs.advance(self.spec)
            self.assertEqual(jobs.retained_report(self.spec), original)
        self.assertEqual(len(self.probes), 1)
        self.assertEqual(len(f.ssm.sends), 1)


if __name__ == '__main__':
    unittest.main()
