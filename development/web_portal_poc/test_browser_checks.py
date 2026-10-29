"""Owned browser checks through real job/observer code with Moto and fake AWS."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import test_assessment_observation as observation_fixtures
from test_identity_grade import Bindings
from identity_keys import subject_key
from portal_checker_handler import serve
from student_checker_handler import StudentChecker
import build_checker_package


class BrowserChecksTest(unittest.TestCase):
    def setUp(self):
        f = observation_fixtures.ObservationTest()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.fixture.doCleanups)
        self.f, self.spec = f, f.spec
        self.spec['run_id'] = self.spec['job_id']
        self.pepper, self.subject = b'synthetic-pepper-for-test-only!!!', '98765432109876543210'
        self.person_pk = subject_key(self.subject, self.pepper)
        self.spec['owner_hash'] = self.person_pk.removeprefix('SUBJECT#')
        from assessment_command_jobs import sha
        f.snapshot['spec_sha256'] = sha(self.spec)
        self.config = {'state': {k: self.spec[k] for k in ('account', 'lab_id', 'deployment_id', 'release_id')},
            'baseline': {'nodes': {r: {'instance_id': v} for r, v in self.spec['instances'].items()}}}
        self.student = StudentChecker(self.config, f.fixture.db, 'jobs', None, None, None, f.fixture.ssm)
        self.student.snapshot = lambda spec: copy.deepcopy(f.snapshot)
        self.context = {k: self.spec[k] for k in ('account', 'lab_id', 'deployment_id')}
        self.context['connector'] = 'b' * 64
        self.meta = {'pk': 'LAB#' + self.spec['lab_id'], 'active': True, 'token_hash': 'c' * 64,
            **{k: self.spec[k] for k in ('lab_id', 'deployment_id', 'release_id', 'instances')}}
        self.approval = 'APPROVAL#' + 'd' * 64
        self.bindings = Bindings({
            (self.person_pk, 'BINDING'): {**self.context, 'active': True, 'token_hash': 'c' * 64, 'approval_pk': self.approval},
            ('LAB#' + self.spec['lab_id'], 'SUBJECT'): {'subject_pk': self.person_pk},
            ('LAB#' + self.spec['lab_id'], 'BINDING'): self.context,
            ('ACCOUNT#' + self.spec['account'], 'BINDING'): self.context,
            (self.approval, 'LAB'): {'active': True, 'bound_subject': self.person_pk,
                'grant': {**{k: self.meta[k] for k in ('lab_id', 'deployment_id', 'token_hash', 'instances')}, 'account': self.spec['account']}}})
        meta = self.meta
        class Grades:
            def get(self, pk, sk):
                return copy.deepcopy(meta) if pk == meta['pk'] and sk == 'META' else None
            def labs(self, lab):
                return [copy.deepcopy(meta)] if lab == meta['lab_id'] else []
        self.grades = Grades()
        self.calls = []
        outer = self
        class Client:
            def invoke(self, **kwargs):
                outer.calls.append(kwargs)
                event = json.loads(kwargs['Payload'])
                with patch('student_checker_handler.Observation', side_effect=lambda spec, snapshot: f.observer()):
                    answer = outer.student.serve(event)
                return {'StatusCode': 200, 'Payload': io.BytesIO(json.dumps(answer).encode())}
        self.client = Client()

    def call(self, operation='start', **extra):
        return serve({'subject': self.subject, 'operation': operation,
            'task_id': self.spec['task_id'], 'job_id': self.spec['job_id'], **extra},
            self.pepper, self.bindings, self.grades, self.client)

    def test_real_job_flow_owned_check_to_saved_result_without_grade_changes(self):
        original = copy.deepcopy(self.meta)
        self.f.fixture.ssm.output = json.dumps(self.f.legacy_http())
        start = self.call()
        self.assertEqual(start['job']['phase'], 'observing')
        self.assertNotIn('result', self.call('result'))
        result = self.call('advance')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['job']['phase'], 'report_ready')
        self.assertEqual(result['result']['score']['raw_earned'], 8)
        self.assertFalse(result['result']['saved_grade_changed'])
        for _ in range(3):
            self.assertEqual(self.call('result')['result'], result['result'])
        self.assertEqual(len(self.f.fixture.ssm.sends), 1)
        self.assertEqual(self.meta, original)
        payload = json.loads(self.calls[0]['Payload'])
        self.assertEqual(payload['spec']['owner_hash'], self.spec['owner_hash'])
        self.assertNotIn(self.subject, json.dumps(payload))
        self.assertNotIn('token_hash', json.dumps(payload))
        self.assertTrue(self.calls[0]['FunctionName'].endswith(':function:jdu-web-check-' + self.spec['lab_id']))

    def test_unknown_identity_unapproved_and_revoked_never_invoke_student(self):
        self.assertEqual(self.call(subject='999')['status'], 'unauthorized')
        self.bindings.rows[(self.approval, 'LAB')]['active'] = False
        self.assertEqual(self.call()['status'], 'unauthorized')
        self.bindings.rows[(self.approval, 'LAB')]['active'] = True
        self.bindings.rows[(self.person_pk, 'BINDING')].pop('approval_pk')
        self.assertEqual(self.call()['status'], 'unauthorized')
        self.assertEqual(self.calls, [])

    def test_no_free_targets_scores_shell_or_noncanonical_job_id(self):
        for extra in ({'command':'whoami'}, {'account':'999999999999'}, {'score':62}, {'job_id':'bad'}, {'task_id':'M7'}):
            self.assertEqual(self.call(**extra)['status'], 'unauthorized')
        self.assertEqual(self.calls, [])

    def test_get_cannot_create_job_and_student_fixed_deployment_is_enforced(self):
        self.assertEqual(self.call('result')['status'], 'unavailable')
        wrong = copy.deepcopy(self.spec)
        wrong['instances']['web'] = 'i-' + 'f' * 17
        self.assertEqual(self.student.serve({'operation':'start','spec':wrong})['status'], 'unavailable')
        self.assertEqual(self.f.fixture.ssm.sends, [])

    def test_lab_unavailable_does_not_send_or_create_grade(self):
        def unavailable(spec):
            raise PermissionError('synthetic-private-value')
        self.student.snapshot = unavailable
        self.assertEqual(self.call()['status'], 'unavailable')
        self.assertEqual(self.f.fixture.ssm.sends, [])
        self.assertNotIn('synthetic-private-value', json.dumps(self.call()))

    def test_package_flat_imports_pinned_assets_and_contains_no_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'checks.zip'
            build_checker_package.build(archive)
            with ZipFile(archive) as z:
                self.assertNotIn('CHECK_CONFIG', z.namelist())
                self.assertFalse(any('test_' in name or 'fixture' in name or 'private.json' in name for name in z.namelist()))
                z.extractall(Path(directory) / 'code')
            result = subprocess.run([sys.executable, '-B', '-c',
                'import sys,types; sys.modules.setdefault("pwd",types.ModuleType("pwd")); import student_checker_handler,portal_checker_handler,setup_internal_ssh,aws_readiness; from assessment_observation import ASSESSMENT,TEACHER; assert (ASSESSMENT/"assessment-registry.json").is_file(); assert (TEACHER/"http_task_guest.py").is_file()'],
                cwd=Path(directory) / 'code', capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
