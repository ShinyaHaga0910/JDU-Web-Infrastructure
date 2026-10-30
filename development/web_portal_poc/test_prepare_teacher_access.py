import unittest
import uuid

import boto3
from moto import mock_aws
import test_grade_reader as source_paths  # Same source paths as the packaged reader.
from portal_enrollment import encoded, email_key
from identity_keys import subject_key
from prepare_teacher_access import plan, apply, get, preview
from teacher_progress import teacher_key


class TeacherAccessTest(unittest.TestCase):
    def setUp(self):
        self.mock = mock_aws()
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.db = boto3.client('dynamodb', region_name='us-east-1')
        for table in ('bindings', 'grades'):
            self.db.create_table(TableName=table, BillingMode='PAY_PER_REQUEST',
                AttributeDefinitions=[{'AttributeName': k, 'AttributeType': 'S'} for k in ('pk', 'sk')],
                KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}, {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        pepper = b'fictional-teacher-access-test-pepper'
        self.subject = subject_key('1234567890', pepper)
        self.email = 'teacher@jdu.uz'
        self.approval = email_key(self.email, pepper)
        self.teacher = teacher_key(self.email, pepper)
        self.meta = {'pk': 'LAB#source-lab', 'sk': 'META', 'lab_id': 'source-lab', 'active': True,
            'deployment_id': str(uuid.uuid4()), 'assessment_context': 'verification', 'token_hash': 'a' * 64,
            'instances': {r: 'i-' + str(i) * 17 for i, r in enumerate(('bastion', 'web', 'dns', 'db', 'repo'), 1)}}
        grant = {k: self.meta[k] for k in ('lab_id', 'deployment_id', 'token_hash', 'instances')}
        self.put('grades', self.meta)
        self.put('grades', {**self.meta, 'pk': 'LAB#course-lab', 'lab_id': 'course-lab', 'assessment_context': 'course'})
        self.put('bindings', {'pk': self.approval, 'sk': 'LAB', 'active': True, 'bound_subject': self.subject,
            'grant': dict(grant, account='965244652544')})
        self.put('bindings', {'pk': self.subject, 'sk': 'BINDING', 'active': True, 'lab_id': 'source-lab',
            'deployment_id': self.meta['deployment_id'], 'approval_pk': self.approval,
            'account': '965244652544', 'token_hash': self.meta['token_hash'], 'connector': 'b' * 64})
        self.put('bindings', {'pk': 'LAB#source-lab', 'sk': 'SUBJECT', 'subject_pk': self.subject})

    def put(self, table, row):
        self.db.put_item(TableName=table, Item=encoded(row))

    def plan(self):
        return plan(self.db, 'bindings', 'grades', 'source-lab', ['source-lab', 'course-lab'], '193548')

    def snapshots(self):
        return {table: sorted(self.db.scan(TableName=table)['Items'], key=lambda r: repr(r['pk'])) for table in ('grades', 'bindings')}

    def test_plan_is_read_only_and_grant_uses_existing_hashed_identity(self):
        before = self.snapshots()
        value = self.plan()
        self.assertEqual(self.snapshots(), before)
        self.assertEqual(value['row']['pk'], self.teacher)
        self.assertEqual(value['row']['subject_pk'], self.subject)
        self.assertNotIn(self.email, repr(value))
        self.assertNotIn('token_hash', repr(preview(value)))
        self.assertEqual(len(value['row']['labs']), 2)

    def test_apply_adds_only_teacher_access_and_preserves_all_grades(self):
        before = self.snapshots()
        value = self.plan()
        result = apply(self.db, value)
        self.assertTrue(result['applied'])
        self.assertEqual(self.snapshots()['grades'], before['grades'])
        self.assertEqual(len(self.snapshots()['bindings']), len(before['bindings']) + 1)
        self.assertEqual(get(self.db, 'bindings', self.teacher, 'ACCESS'), value['row'])

    def test_revoked_identity_or_changed_lab_prevents_access_transaction(self):
        for change in ('approval', 'metadata'):
            with self.subTest(change=change):
                value = self.plan()
                if change == 'approval':
                    row = get(self.db, 'bindings', self.approval, 'LAB')
                    self.put('bindings', {**row, 'active': False})
                else:
                    row = get(self.db, 'grades', 'LAB#course-lab', 'META')
                    self.put('grades', {**row, 'assessment_context': 'verification'})
                with self.assertRaises(self.db.exceptions.TransactionCanceledException):
                    apply(self.db, value)
                self.assertIsNone(get(self.db, 'bindings', self.teacher, 'ACCESS'))
                if change == 'approval':
                    self.put('bindings', {**row, 'active': True})

    def test_updates_cannot_overwrite_a_concurrent_teacher_scope_change(self):
        initial = self.plan()
        apply(self.db, initial)
        old_plan = self.plan()
        newer = self.plan()
        apply(self.db, newer)
        with self.assertRaises(self.db.exceptions.TransactionCanceledException):
            apply(self.db, old_plan)
        self.assertEqual(get(self.db, 'bindings', self.teacher, 'ACCESS'), newer['row'])

    def test_revocation_without_a_revision_change_is_not_overwritten(self):
        apply(self.db, self.plan())
        pending = self.plan()
        row = get(self.db, 'bindings', self.teacher, 'ACCESS')
        self.put('bindings', {**row, 'active': False})
        with self.assertRaises(self.db.exceptions.TransactionCanceledException):
            apply(self.db, pending)
        self.assertFalse(get(self.db, 'bindings', self.teacher, 'ACCESS')['active'])


if __name__ == '__main__':
    unittest.main()
