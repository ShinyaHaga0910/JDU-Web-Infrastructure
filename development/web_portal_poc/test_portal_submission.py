"""Moto checks of the real canonical grade transaction and owned browser flow."""
import copy
from datetime import datetime, timezone
import json
import unittest
import uuid

import test_browser_checks as fixtures
from assessment_command_jobs import encoded, native
import progress_api as legacy
from progress_api_v2 import AssessmentStore, assessment_attempt
from portal_submission import PortalSubmissions
from portal_checker_handler import serve
from registry import build_report, canonical_checks, COURSE_INTRO_MARKERS
from grading import grade_key, current_key, project_lab, project_course_lab


class SubmissionTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.BrowserChecksTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.db = self.f.f.fixture.db
        for table in ('grades', 'bindings'):
            self.db.create_table(TableName=table, BillingMode='PAY_PER_REQUEST',
                AttributeDefinitions=[{'AttributeName': n, 'AttributeType': 'S'} for n in ('pk','sk')],
                KeySchema=[{'AttributeName':'pk','KeyType':'HASH'}, {'AttributeName':'sk','KeyType':'RANGE'}])
        self.grades, self.bindings = AssessmentStore('grades'), legacy.DynamoStore('bindings')
        self.meta = dict(self.f.meta, sk='META', updated_at='2026-01-01T00:00:00+00:00')
        self.db.put_item(TableName='grades', Item=encoded(self.meta))
        for (pk, sk), row in self.f.bindings.rows.items():
            self.db.put_item(TableName='bindings', Item=encoded({**row, 'pk':pk, 'sk':sk}))
        self.spec = copy.deepcopy(self.f.spec)
        self.saver = PortalSubmissions(self.bindings, self.grades)
        # Existing full grades, saved through the unchanged canonical mechanism.
        for task in ('M1','M2','M3','M4','M5','M6'):
            report = self.report(task, functional=True)
            attempt, summary = assessment_attempt(self.meta, report)
            self.grades.submit(self.meta, attempt, summary)
        self.original = self.rows()

    def report(self, task='M1', functional=False, observations=None, *, intro=False):
        values = {c: True for c in canonical_checks(task, intro=intro)}
        if not functional:
            for c in ('WEB06_PASSWORD_LOGIN','WEB06_CREATE_REFLECT','WEB06_EDIT_REFLECT','WEB06_LOGOUT',
                      'WEB07_ANONYMOUS_DENIED','WEB07_BAD_PASSWORD_DENIED'):
                if c in values: values[c] = None
        values.update(observations or {})
        return build_report(task, self.meta, values, self.spec['run_id'],
            mode='functional' if functional else 'read_only', checked_at=datetime.now(timezone.utc).isoformat(), intro=intro)

    def rows(self):
        values = self.db.query(TableName='grades',KeyConditionExpression='pk=:p',
            ExpressionAttributeValues=encoded({':p':self.meta['pk']}),ConsistentRead=True)['Items']
        return copy.deepcopy(values)

    def save(self, report, spec=None):
        return self.saver.save(spec or self.spec, self.grades.get(self.meta['pk'],'META'), report)

    def new_spec(self, task):
        spec = copy.deepcopy(self.spec)
        spec.update(task_id=task, job_id=str(uuid.uuid4()), run_id=str(uuid.uuid4()))
        return spec

    def test_browser_functional_report_uses_the_same_original_62_point_submission(self):
        spec=self.new_spec('M5');spec['check_mode']='functional'
        report=self.report('M5',functional=True);report['run_id']=spec['run_id']
        first=self.save(report,spec);self.assertEqual(first['status'],'saved');self.assertTrue(first['evaluable'])
        self.assertEqual(self.save(report,spec),first)
        stored=self.grades.get(self.meta['pk'],'REQUEST#'+report['request_id'])
        self.assertEqual(stored['report']['mode'],'functional')
        self.assertEqual(stored['report'],report)

    def test_evaluable_report_updates_canonical_request_current_and_selected_grade(self):
        report = self.report()
        receipt = self.save(report)
        self.assertEqual(receipt['status'],'saved')
        self.assertTrue(receipt['evaluable'])
        for sk in ('REQUEST#'+report['request_id'], current_key('M1'), grade_key('M1')):
            row = self.grades.get(self.meta['pk'],sk)
            self.assertEqual(row.get('request_id',row.get('report',{}).get('request_id')),report['request_id'])
        self.assertEqual(native(self.grades.get(self.meta['pk'],'REQUEST#'+report['request_id'])['report']),report)
        self.assertEqual(project_lab(self.grades.labs(self.meta['lab_id'])[0])['raw_earned'],62)

    def test_unknown_keeps_selected_grade_but_saves_current_and_receipt(self):
        spec = self.new_spec('M5')
        self.spec = spec
        report = self.report('M5')
        before = self.grades.get(self.meta['pk'],grade_key('M5'))
        receipt = self.save(report)
        self.assertFalse(receipt['evaluable'])
        self.assertEqual(self.grades.get(self.meta['pk'],grade_key('M5')),before)
        current = self.grades.get(self.meta['pk'],current_key('M5'))
        self.assertEqual(current['request_id'],report['request_id'])
        view = project_lab(self.grades.labs(self.meta['lab_id'])[0])
        self.assertEqual(view['raw_earned'],62)
        self.assertIn('M5',view['current_unresolved'])

    def test_practice_and_preparation_never_create_selected_grade(self):
        for task in ('P1','M0'):
            self.spec = self.new_spec(task)
            receipt = self.save(self.report(task))
            self.assertFalse(receipt['counts_toward_assessment'])
            self.assertIsNone(self.grades.get(self.meta['pk'],grade_key(task)))
        self.assertEqual(project_lab(self.grades.labs(self.meta['lab_id'])[0])['raw_earned'],62)

    def test_connection_grades_use_student_evidence_and_preserve_legacy_scores(self):
        for task, markers in COURSE_INTRO_MARKERS.items():
            self.spec = self.new_spec(task)
            missing = self.report(task, observations={marker: False for marker, _, _ in markers}, intro=True)
            self.assertTrue(self.save(missing)['counts_toward_assessment'])
            self.assertEqual(self.grades.get(self.meta['pk'], grade_key(task, missing['contract_sha256']))['raw_earned'], 0)
            self.spec = self.new_spec(task)
            report = self.report(task, intro=True)
            first = self.save(report)
            self.assertEqual(self.save(report), first)
            self.spec = self.new_spec(task)
            self.assertFalse(self.save(self.report(task))['counts_toward_assessment'])
        lab = self.grades.labs(self.meta['lab_id'])[0]
        # Old-root M1 remains historical; the new rubric needs a fresh result.
        self.assertEqual(project_course_lab(lab)['raw_earned'], 56)
        self.assertEqual(project_lab(lab)['raw_earned'], 62)

    def test_retry_returns_first_receipt_without_reordering_a_newer_lower_grade(self):
        first = self.report()
        receipt = self.save(first)
        old_spec = copy.deepcopy(self.spec)
        self.spec = self.new_spec('M1')
        lower = self.report(observations={'WEB02_FILE':False})
        self.save(lower)
        before = self.rows()
        self.assertEqual(self.save(first,old_spec),receipt)
        self.assertEqual(self.rows(),before)
        self.assertEqual(self.grades.get(self.meta['pk'],grade_key('M1'))['raw_earned'],7)

    def test_changed_report_or_foreign_owner_task_run_and_mode_are_rejected(self):
        report = self.report()
        self.save(report)
        bad = copy.deepcopy(report); bad['checks'][1]['status']='FAIL'
        with self.assertRaises(legacy.ApiError): self.save(bad)
        for field, value in (('owner_hash','f'*64), ('task_id','M2'), ('run_id',str(uuid.uuid4()))):
            spec = {**self.spec,field:value}
            with self.assertRaises((legacy.ApiError,ValueError)): self.save(report,spec)
        functional = self.report(functional=True)
        with self.assertRaises(legacy.ApiError): self.save(functional)

    def test_revocation_during_commit_prevents_all_grade_writes(self):
        report = self.report(); before = self.rows()
        original = self.grades.client.transact_write_items
        def revoke(**kwargs):
            self.db.update_item(TableName='bindings', Key=encoded({'pk':self.f.approval,'sk':'LAB'}),
                UpdateExpression='SET #a=:no',ExpressionAttributeNames={'#a':'active'},ExpressionAttributeValues=encoded({':no':False}))
            return original(**kwargs)
        self.grades.client.transact_write_items = revoke
        with self.assertRaises(legacy.ApiError): self.save(report)
        self.assertEqual(self.rows(),before)

    def test_retry_receipt_also_requires_current_authorization_at_transaction_time(self):
        report = self.report(); self.save(report); before = self.rows()
        original = self.grades.client.transact_write_items
        def revoke(**kwargs):
            self.db.update_item(TableName='bindings',Key=encoded({'pk':self.f.person_pk,'sk':'BINDING'}),
                UpdateExpression='SET #a=:no',ExpressionAttributeNames={'#a':'active'},ExpressionAttributeValues=encoded({':no':False}))
            return original(**kwargs)
        self.grades.client.transact_write_items = revoke
        with self.assertRaises(Exception): self.save(report)
        self.assertEqual(self.rows(),before)

    def call(self, operation):
        return serve({'subject':self.f.subject,'operation':operation,'task_id':self.f.spec['task_id'],'job_id':self.f.spec['job_id']},
            self.f.pepper,self.bindings,self.grades,self.f.client,self.saver)

    def test_owned_browser_flow_auto_saves_without_report_or_token_in_browser(self):
        self.f.f.fixture.ssm.output = json.dumps(self.f.f.legacy_http())
        self.assertEqual(self.call('start')['job']['phase'],'observing')
        before = self.rows(); self.assertEqual(self.call('result')['job']['phase'],'observing'); self.assertEqual(self.rows(),before)
        answer = self.call('advance')
        self.assertEqual(answer['submission']['status'],'saved')
        self.assertNotIn('report',answer)
        self.assertNotIn('token_hash',json.dumps(answer))
        before = self.rows()
        self.assertEqual(self.call('result')['submission'],answer['submission'])
        self.assertEqual(self.call('submit')['submission'],answer['submission'])
        self.assertEqual(self.rows(),before)
        self.assertEqual(len(self.f.f.fixture.ssm.sends),1)

    def test_committed_but_lost_ack_is_found_by_get_without_a_second_grade_write(self):
        self.f.f.fixture.ssm.output = json.dumps(self.f.f.legacy_http()); self.call('start')
        original = self.grades.client.transact_write_items
        def lost(**kwargs):
            original(**kwargs)
            raise TimeoutError('synthetic transport failure after commit')
        self.grades.client.transact_write_items = lost
        answer = self.call('advance')
        self.assertEqual(answer['submission']['status'],'pending')
        before = self.rows()
        self.assertEqual(self.call('result')['submission']['status'],'saved')
        self.assertEqual(self.rows(),before)
        self.assertEqual(len(self.f.f.fixture.ssm.sends),1)


if __name__=='__main__': unittest.main()
