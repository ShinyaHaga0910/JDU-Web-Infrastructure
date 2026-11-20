import copy
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web_lab_teacher'))
import progress_api as legacy
from test_progress_api import MemoryStore
from grading import export_labs, grade_key, current_key, project_lab
from progress_api_v2 import AssessmentService
from registry import build_report, canonical_checks, score, TASKS, CONTRACT_ID, CONTRACT_SHA256, INTRO_MARKERS


@unittest.skipUnless(os.name == 'posix', 'Linux filesystem observation')
class MarkerTest(unittest.TestCase):
    def test_only_the_expected_student_file_counts(self):
        from system_observer import connection_marker

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            user = SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid())
            with patch('system_observer.pwd.getpwnam', return_value=user):
                for _, role, filename in INTRO_MARKERS.values():
                    marker = home / filename
                    self.assertIs(connection_marker(role, filename), False)
                    wrong_role = 'db' if role == 'web' else 'web'
                    marker.write_text(wrong_role + '\n')
                    self.assertIs(connection_marker(role, filename), False)
                    marker.write_text(role + '\nextra\n')
                    self.assertIs(connection_marker(role, filename), False)
                    marker.write_text(role + '\n')
                    self.assertIs(connection_marker(role, filename), True)
                    marker.rename(home / (role + '.txt'))
                    marker.symlink_to(home / (role + '.txt'))
                    self.assertIs(connection_marker(role, filename), False)


class Store(MemoryStore):
    def submit(self, meta, attempt, summary):
        if attempt['report']['schema_version'] == 1:
            return super().submit(meta, attempt, summary)
        old = self.get(attempt['pk'], attempt['sk'])
        if old:
            if old['body_sha256'] != attempt['body_sha256']:
                raise legacy.ApiError(409, 'conflict')
            return old['receipt']
        self.rows[attempt['pk'], attempt['sk']] = copy.deepcopy(attempt)
        latest = dict(copy.deepcopy(summary), pk=meta['pk'], sk=current_key(attempt['report']['mission_id'], summary['contract_sha256']),
                      checks=copy.deepcopy(attempt['report']['checks']))
        self.rows[latest['pk'], latest['sk']] = latest
        if summary.get('evaluable') and summary.get('counts_toward_assessment'):
            selected = dict(summary, pk=meta['pk'], sk=grade_key(attempt['report']['mission_id'], summary['contract_sha256']), checks=attempt['report']['checks'])
            self.rows[selected['pk'], selected['sk']] = copy.deepcopy(selected)
        return attempt['receipt']

    def classify(self, meta, context):
        self.rows[meta['pk'], 'META']['assessment_context'] = context

    def labs(self, only_lab=None):
        labs = super().labs(only_lab)
        for lab in labs:
            lab['results'] += [copy.deepcopy(v) for (pk, sk), v in self.rows.items()
                               if pk == lab['pk'] and sk.startswith('GRADE#')]
        return labs


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.admin, self.token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.app = AssessmentService(self.store, legacy.digest(self.admin), 'https://unit.invalid')
        self.identity = dict(lab_id='test-student', release_id='web-2026-10-r1', deployment_id=str(uuid.uuid4()),
            instances={r: 'i-' + format(i, '017x') for i, r in enumerate(sorted(legacy.ROLES), 1)})
        self.call('POST /api/web/admin/issue', dict(lab_id=self.identity['lab_id'], release_id=self.identity['release_id'], lab_token=self.token), self.admin)
        self.call('POST /api/web/register', self.identity)

    def call(self, route, body, token=None):
        return self.app.handle(dict(routeKey=route, body=json.dumps(body), headers={'authorization': 'Bearer ' + (token or self.token)}))

    def report(self, task='M1', changes=None, mode='functional', intro=False):
        observations = {c: True for c in canonical_checks(task, intro=intro)}
        observations.update(changes or {})
        return build_report(task, self.identity, observations, str(uuid.uuid4()), mode=mode,
                            checked_at=datetime.now(timezone.utc).isoformat(), intro=intro)

    def submit(self, report):
        result = self.call('POST /api/web/submit', report)
        self.assertEqual(result['statusCode'], 200, result)
        return json.loads(result['body'])

    def view(self):
        return project_lab(self.store.labs()[0])

    def test_shared_code_admits_a_student_to_the_current_grading_api(self):
        shared = secrets.token_urlsafe(32)
        self.app.enrollment_hash = legacy.digest(shared)
        self.identity.update(lab_id='new-student', deployment_id=str(uuid.uuid4()))
        admission = {key: self.identity[key] for key in ('lab_id', 'release_id')} | {'lab_token': self.token}
        self.assertEqual(self.call('POST /api/web/enroll', admission, shared)['statusCode'], 200)
        self.assertEqual(self.call('POST /api/web/register', self.identity)['statusCode'], 200)
        self.assertEqual(self.call('POST /api/web/submit', self.report(), shared)['statusCode'], 401)
        for task in ('M1', 'M2', 'M4', 'M5', 'M6'):
            self.submit(self.report(task))
        for task, (marker, _, _) in INTRO_MARKERS.items():
            missing = self.report(task, {marker: False}, mode='read_only', intro=True)
            self.assertEqual(score(missing)['raw_earned'], 0)
            self.assertFalse(score(missing)['complete'])
            self.submit(missing)
            self.submit(self.report(task, mode='read_only', intro=True))
            self.submit(self.report(task, mode='read_only'))  # An old observer cannot replace the new grade.
        classification = {key: self.identity[key] for key in ('lab_id', 'deployment_id')}
        classification.update(context='course', contract_id=CONTRACT_ID)
        self.assertEqual(self.call('POST /api/web/admin/assessment-context', classification, self.admin)['statusCode'], 200)
        export = json.loads(self.call('POST /api/web/admin/grades', {}, self.admin)['body'])
        row = export['students'][0]
        self.assertEqual((row['lab_id'], row['raw_earned'], export['raw_maximum']), ('new-student', 61, 61))
        for task in INTRO_MARKERS:
            self.assertEqual(row['missions'][task]['selected']['raw_earned'], 1)
        self.assertNotIn('M3', row['missions'])
        student_session = self.call('POST /api/web/student/session', {'lab_id': 'new-student'})
        url = json.loads(student_session['body'])['url']
        dashboard = self.app.handle({'routeKey': 'GET /dashboard', 'queryStringParameters': {'session': url.split('session=')[1]}})
        self.assertIn('61 / 61', dashboard['body'])
        self.assertNotIn('M3 /', dashboard['body'])

    def test_all_missions_exactly_62_and_preparation_zero(self):
        for mid in ('M0', *['M' + str(i) for i in range(1, 7)]):
            self.submit(self.report(mid))
        view = self.view()
        self.assertEqual((view['raw_earned'], view['raw_maximum']), (62, 62))
        self.assertEqual(len(view['selected']), 6)
        self.assertNotIn('M7', TASKS)

    def test_initial_http_two_of_ten_is_zero_of_eight(self):
        failures = {cid: False for cid in TASKS['M1']['progress_scored_checks']}
        self.submit(self.report(changes=failures))
        self.assertEqual(self.view()['raw_earned'], 0)
        self.assertEqual(self.view()['selected']['M1']['raw_maximum'], 8)
        self.assertEqual(self.view()['raw_maximum'], 62)

    def test_unknown_preserves_selected_but_latest_health_visible(self):
        first = self.report()
        self.submit(first)
        later = self.report(changes={'WEB02_PUBLIC_HTTP': None})
        self.submit(later)
        view = self.view()
        self.assertEqual(view['selected']['M1']['request_id'], first['request_id'])
        self.assertEqual(view['current']['M1']['request_id'], later['request_id'])
        self.assertEqual(view['current_unresolved'], ['M1'])

    def test_latest_failure_replaces_selected_no_highest_or_union(self):
        self.submit(self.report(changes={'WEB02_FILE': False}))
        last = self.report(changes={'WEB02_LOCAL_HTTP': False, 'WEB02_PUBLIC_HTTP': False})
        self.submit(last)
        self.assertEqual(self.view()['raw_earned'], 6)
        self.assertEqual(self.view()['selected']['M1']['request_id'], last['request_id'])

    def test_preparation_failure_cannot_become_evaluable_grade(self):
        self.submit(self.report(changes={'WEB02_IDENTITY': False}))
        view = self.view()
        self.assertEqual(view['selected'], {})
        self.assertFalse(view['current']['M1']['evaluable'])

    def test_practice_passes_do_not_add_to_mission_total(self):
        for mid in ['P' + str(i) for i in range(7)]:
            self.submit(self.report(mid))
        self.assertEqual(self.view()['raw_earned'], 0)
        self.assertEqual(self.view()['raw_maximum'], 62)

    def test_reject_missing_duplicate_extra_wrong_role_and_forged_weights(self):
        good = self.report()
        mutations = []
        missing = copy.deepcopy(good); missing['checks'].pop(); mutations.append(missing)
        duplicate = copy.deepcopy(good); duplicate['checks'][-1] = duplicate['checks'][0]; mutations.append(duplicate)
        extra = copy.deepcopy(good); extra['checks'][0]['id'] = 'WEB_FAKE'; mutations.append(extra)
        role = copy.deepcopy(good); role['checks'][0]['role'] = 'repo'; role['checks'][0]['instance_id'] = self.identity['instances']['repo']; mutations.append(role)
        points = copy.deepcopy(good); points['raw_earned'] = 62; mutations.append(points)
        contract = copy.deepcopy(good); contract['contract_sha256'] = '0' * 64; mutations.append(contract)
        for bad in mutations:
            self.assertEqual(self.call('POST /api/web/submit', bad)['statusCode'], 400)

    def test_readonly_cannot_claim_real_login(self):
        body = self.report('M5'); body['mode'] = 'read_only'
        self.assertEqual(self.call('POST /api/web/submit', body)['statusCode'], 400)
        for c in body['checks']:
            if c['id'] in ('WEB06_PASSWORD_LOGIN', 'WEB06_CREATE_REFLECT', 'WEB06_EDIT_REFLECT', 'WEB06_LOGOUT'):
                c['status'] = 'UNKNOWN'
        self.submit(body)
        self.assertNotIn('M5', self.view()['selected'])

    def test_retry_same_receipt_and_changed_body_rejected(self):
        report = self.report(); first = self.submit(report)
        self.assertEqual(self.submit(report), first)
        report['checks'][1]['status'] = 'FAIL'
        self.assertEqual(self.call('POST /api/web/submit', report)['statusCode'], 409)

    def test_fixture_excluded_until_teacher_classifies_course(self):
        self.submit(self.report())
        self.assertEqual(export_labs(self.store.labs())['students'], [])
        body = dict(lab_id=self.identity['lab_id'], deployment_id=self.identity['deployment_id'],
                    contract_id=CONTRACT_ID, context='course')
        self.assertEqual(self.call('POST /api/web/admin/assessment-context', body)['statusCode'], 401)
        self.assertEqual(self.call('POST /api/web/admin/assessment-context', body, self.admin)['statusCode'], 200)
        export = self.call('POST /api/web/admin/grades', {}, self.admin)
        data = json.loads(export['body'])
        self.assertEqual(data['students'][0]['raw_maximum'], 62)
        self.assertFalse(data['normalized_course_points_included'])

    def test_export_serializes_real_dynamo_numeric_types(self):
        self.submit(self.report())
        self.call('POST /api/web/admin/assessment-context', dict(lab_id=self.identity['lab_id'],
            deployment_id=self.identity['deployment_id'], contract_id=CONTRACT_ID, context='course'), self.admin)
        for row in self.store.rows.values():
            for key in ('raw_earned', 'raw_maximum', 'unresolved'):
                if key in row:
                    row[key] = Decimal(row[key])
        result = self.call('POST /api/web/admin/grades', {}, self.admin)
        self.assertEqual(result['statusCode'], 200, result)
        data = json.loads(result['body'])
        mission = data['students'][0]['missions']['M1']
        for row in (mission['current'], mission['selected']):
            self.assertEqual((row['raw_earned'], row['raw_maximum'], row['unresolved']), (8, 8, 0))
            self.assertIs(type(row['raw_earned']), int)
            self.assertIs(type(row['readiness_ok']), bool)

    def test_legacy_report_stored_without_implicit_grading(self):
        old = {k: self.identity[k] for k in ('lab_id', 'release_id', 'deployment_id')}
        old.update(schema_version=1, kind='assessment', mission_id='M1', request_id=str(uuid.uuid4()),
                   checks=[dict(id='WEB02_FILE', role='web', instance_id=self.identity['instances']['web'], status='PASS')])
        self.submit(old)
        self.assertEqual(self.view()['selected'], {})

    def test_legacy_command_cannot_overwrite_d11_current_or_grade(self):
        good = self.report(); self.submit(good)
        old = {k: self.identity[k] for k in ('lab_id', 'release_id', 'deployment_id')}
        old.update(schema_version=1, kind='assessment', mission_id='M1', request_id=str(uuid.uuid4()),
                   checks=[dict(id='WEB02_FILE', role='web', instance_id=self.identity['instances']['web'], status='FAIL')])
        self.submit(old)
        self.assertEqual(self.view()['current']['M1']['request_id'], good['request_id'])
        self.assertEqual(self.view()['selected']['M1']['raw_earned'], 8)

    def test_localized_dashboard_has_all_six_fixed_columns_and_unknown(self):
        from dashboard import render
        self.submit(self.report(changes={'WEB02_PUBLIC_HTTP': None}))
        for language in ('ja', 'uz', 'ru'):
            page = render(self.store.labs(), 'teacher', 'fictional-token', language, paused=True)
            self.assertIn('<html lang="' + language + '">', page)
            self.assertIn('M6 / 16', page)
            self.assertIn(' / 62', page)
            self.assertIn('UNKNOWN', page)
            self.assertNotIn('http-equiv="refresh"', page)
            self.assertIn('<caption>', page)
            self.assertIn('scope="col"', page)


if __name__ == '__main__':
    unittest.main(verbosity=2)
