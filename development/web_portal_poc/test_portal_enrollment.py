import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
sys.path[:0] = [str(ROOT / 'web_lab_assessment'), str(ROOT / 'web_lab_teacher')]
MOTO = importlib.util.find_spec('moto') is not None
if MOTO:
    import boto3
    from moto import mock_aws
    from portal_enrollment import PortalEnrollment, EnrollmentDenied, encoded, key, digest, email_key


@unittest.skipUnless(MOTO, 'install pairing-test-requirements.txt for transaction emulation')
class PortalEnrollmentTest(unittest.TestCase):
    def setUp(self):
        self.mock = mock_aws()
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.db = boto3.client('dynamodb', region_name='us-east-1',
            aws_access_key_id='EXAMPLE', aws_secret_access_key='synthetic-test-only')
        for table in ('bindings', 'grades'):
            self.db.create_table(TableName=table, BillingMode='PAY_PER_REQUEST',
                AttributeDefinitions=[{'AttributeName': n, 'AttributeType': 'S'} for n in ('pk', 'sk')],
                KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}, {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        self.now = datetime(2026, 10, 29, 8, 0, 0, tzinfo=timezone.utc).timestamp()
        self.subject, self.email, self.pepper = '987654321987654321', 'student1@jdu.uz', b'x' * 32
        self.sid, self.token_hash, self.operation = 'a' * 64, digest('synthetic-google-token'), 'e' * 64
        self.grant = {'account': '123456789012', 'lab_id': 'test-lab',
            'deployment_id': '12345678-1234-1234-1234-123456789012', 'token_hash': 'c' * 64,
            'instances': {r: 'i-' + str(i) * 17 for i, r in enumerate(('bastion', 'web', 'dns', 'db', 'repo'), 1)}}
        self.meta = {'pk': 'LAB#test-lab', 'sk': 'META', 'active': True, **{k: v for k, v in self.grant.items() if k != 'account'}}
        self.db.put_item(TableName='grades', Item=encoded(self.meta))
        self.db.put_item(TableName='bindings', Item=encoded({'pk': 'SESSION#' + digest(self.sid), 'sk': 'PORTAL',
            'active': True, 'token_hash': self.token_hash, 'expires_at': int(self.now) + 600}))
        self.fetch_calls = []
        def fetch(path, nonce):
            self.fetch_calls.append((path, nonce))
            return self.grant['account']
        self.service = PortalEnrollment(self.db, 'bindings', 'grades', self.pepper, clock=lambda: self.now, fetch=fetch)
        self.service.approve(self.email, self.grant)

    def begin(self, **overrides):
        values = dict(subject=self.subject, email=self.email, session_id=self.sid,
                      token_hash=self.token_hash, request_id=self.operation)
        values.update(overrides)
        return self.service.begin(**values)

    def proof(self, **overrides):
        stamp = datetime.fromtimestamp(self.now, timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        values = {'Action': 'GetCallerIdentity', 'Version': '2011-06-15', 'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
            'X-Amz-Credential': 'EXAMPLE/' + stamp[:8] + '/us-east-1/sts/aws4_request',
            'X-Amz-Date': stamp, 'X-Amz-Expires': '60', 'X-Amz-SignedHeaders': 'host;x-jdu-nonce', 'X-Amz-Signature': 'b' * 64}
        values.update(overrides)
        return 'https://sts.us-east-1.amazonaws.com/?' + urlencode(values)

    def read(self, pk, sk):
        return self.service.get('bindings', pk, sk)

    def unchanged(self):
        self.assertEqual(self.service.get('grades', 'LAB#test-lab', 'META'), self.meta)

    def bindings(self):
        return [r for r in self.db.scan(TableName='bindings')['Items'] if r['sk']['S'] in ('BINDING', 'SUBJECT')]

    def revoke_session(self):
        self.db.update_item(TableName='bindings', Key=key('SESSION#' + digest(self.sid), 'PORTAL'),
            UpdateExpression='SET #active=:no', ExpressionAttributeNames={'#active': 'active'},
            ExpressionAttributeValues=encoded({':no': False}))

    def test_self_link_requires_live_session_correct_lab_code_and_student_checker(self):
        from lab_link_code import signed_code
        lab = 'lab-' + '1' * 20
        new_meta = dict(self.meta, pk='LAB#' + lab, lab_id=lab)
        self.db.put_item(TableName='grades', Item=encoded(new_meta))
        account = self.grant['account']
        email = 'self-linked@jdu.uz'
        code = signed_code(self.operation, lab, account, int(self.now), new_meta['token_hash'])
        calls = []
        def check_student(a, l):
            calls.append((a, l))
            return (a, l) == (account, lab)

        values = dict(subject=self.subject, email=email, session_id=self.sid, token_hash=self.token_hash,
                      request_id=self.operation, code=code, check_student=check_student)
        for bad in ({'request_id': 'b' * 64}, {'session_id': 'b' * 64}, {'email': 'outside@example.org'},
                    {'code': signed_code(self.operation, lab, account, int(self.now) - 601, new_meta['token_hash'])}):
            with self.subTest(bad=bad), self.assertRaises(EnrollmentDenied):
                self.service.claim(**{**values, **bad})
        self.assertEqual(calls, [])
        with self.assertRaises(EnrollmentDenied):
            self.service.claim(**{**values, 'check_student': lambda *_: False})
        self.assertEqual(self.bindings(), [])
        self.assertTrue(self.service.claim(**values)['registered'])
        self.assertTrue(self.service.claim(**values)['registered'])
        self.assertEqual(calls, [(account, lab)])
        self.assertTrue(self.service.status(self.subject, email, self.sid, self.token_hash)['registered'])
        with self.assertRaises(EnrollmentDenied):
            self.service.claim(**{**values, 'email': 'another@jdu.uz', 'subject': '123'})
        self.assertEqual(self.service.get('grades', 'LAB#' + lab, 'META'), new_meta)

    def test_complete_creates_both_identity_and_account_mapping_atomically(self):
        pending = self.begin()
        result = self.service.complete(pending['pair_id'], self.proof())
        self.assertTrue(result['registered'])
        self.assertFalse(result['reused'])
        self.assertTrue(self.read('PAIR#' + digest(pending['pair_id']), 'IDENTITY')['used'])
        self.assertEqual(len(self.bindings()), 4)
        self.assertTrue(self.service.status(self.subject, self.email, self.sid, self.token_hash)['registered'])
        self.unchanged()

    def test_same_browser_operation_and_completion_retries_are_idempotent(self):
        first, second = self.begin(), self.begin()
        self.assertEqual(first, second)
        self.service.complete(first['pair_id'], self.proof())
        after = self.db.scan(TableName='bindings')['Items']
        self.assertTrue(self.service.complete(first['pair_id'], self.proof())['reused'])
        self.assertEqual(self.db.scan(TableName='bindings')['Items'], after)
        self.assertTrue(self.begin()['registered'])
        self.unchanged()

    def test_unapproved_email_or_wrong_browser_session_never_issues_pair(self):
        for changes in ({'email': 'other@jdu.uz'}, {'email': 'student1@jdu.uz.attacker.test'},
                        {'session_id': 'f' * 64}, {'token_hash': 'd' * 64}):
            with self.subTest(changes=changes), self.assertRaises(EnrollmentDenied):
                self.begin(**changes)
        self.assertFalse(any(i['pk']['S'].startswith('PAIR#') for i in self.db.scan(TableName='bindings')['Items']))

    def test_revoked_and_expired_session_cannot_complete(self):
        pair = self.begin()
        self.revoke_session()
        with self.assertRaises(EnrollmentDenied):
            self.service.complete(pair['pair_id'], self.proof())
        self.assertEqual(self.fetch_calls, [])
        self.assertEqual(self.bindings(), [])
        self.assertFalse(self.read('PAIR#' + digest(pair['pair_id']), 'IDENTITY')['used'])

    def test_wrong_aws_account_or_ssrf_target_cannot_consume_pair(self):
        pair = self.begin()
        self.service.fetch = lambda *_: '999999999999'
        with self.assertRaises(EnrollmentDenied):
            self.service.complete(pair['pair_id'], self.proof())
        self.assertEqual(self.bindings(), [])
        self.assertFalse(self.read('PAIR#' + digest(pair['pair_id']), 'IDENTITY')['used'])
        self.service.fetch = lambda *_: self.fail('untrusted URL was fetched')
        for url in (self.proof().replace('sts.us-east-1.amazonaws.com', 'attacker.test'),
                    self.proof(**{'X-Amz-Expires': '61'})):
            with self.assertRaises(ValueError):
                self.service.complete(pair['pair_id'], url)

    def test_expired_pair_requires_new_browser_operation_without_restarting_any_resource(self):
        pair = self.begin()
        self.now += 301
        with self.assertRaises(EnrollmentDenied):
            self.service.complete(pair['pair_id'], self.proof())
        with self.assertRaises(EnrollmentDenied):
            self.begin()
        new = self.begin(request_id='d' * 64)
        self.assertNotEqual(new['pair_id'], pair['pair_id'])
        self.assertEqual(self.bindings(), [])
        self.unchanged()

    def test_original_change_during_proof_keeps_all_binding_writes_uncommitted(self):
        pair = self.begin()
        def changed(*_):
            self.db.update_item(TableName='grades', Key=key('LAB#test-lab', 'META'),
                UpdateExpression='SET deployment_id=:d', ExpressionAttributeValues=encoded({':d': 'changed'}))
            return self.grant['account']
        self.service.fetch = changed
        with self.assertRaises(EnrollmentDenied):
            self.service.complete(pair['pair_id'], self.proof())
        self.assertEqual(self.bindings(), [])
        self.assertFalse(self.read('PAIR#' + digest(pair['pair_id']), 'IDENTITY')['used'])

    def test_logout_during_external_verification_prevents_registration(self):
        pair = self.begin()
        def logged_out(*_):
            self.revoke_session()
            return self.grant['account']
        self.service.fetch = logged_out
        with self.assertRaises(EnrollmentDenied):
            self.service.complete(pair['pair_id'], self.proof())
        self.assertEqual(self.bindings(), [])

    def test_transaction_condition_rejects_session_revoked_after_prechecks(self):
        pair = self.begin()
        original = self.db.transact_write_items
        def race(**kwargs):
            if len(kwargs['TransactItems']) == 10:
                self.revoke_session()
            return original(**kwargs)
        self.db.transact_write_items = race
        with self.assertRaises(EnrollmentDenied):
            self.service.complete(pair['pair_id'], self.proof())
        self.assertEqual(self.bindings(), [])
        self.assertFalse(self.read('PAIR#' + digest(pair['pair_id']), 'IDENTITY')['used'])
        self.assertNotIn('bound_subject', self.read(email_key(self.email, self.pepper), 'LAB'))

    def test_existing_account_binding_rolls_back_subject_and_nonce_changes(self):
        pair = self.begin()
        self.db.put_item(TableName='bindings', Item=encoded({'pk': 'ACCOUNT#' + self.grant['account'], 'sk': 'BINDING', 'lab_id': 'another-lab'}))
        with self.assertRaises(EnrollmentDenied):
            self.service.complete(pair['pair_id'], self.proof())
        self.assertEqual(len(self.bindings()), 1)
        self.assertFalse(self.read('PAIR#' + digest(pair['pair_id']), 'IDENTITY')['used'])
        self.assertNotIn('bound_subject', self.read(email_key(self.email, self.pepper), 'LAB'))
        self.unchanged()

    def test_teacher_approval_and_bound_identity_cannot_be_silently_replaced(self):
        with self.assertRaises(EnrollmentDenied):
            self.service.approve(self.email, self.grant)
        pair = self.begin()
        self.service.complete(pair['pair_id'], self.proof())
        with self.assertRaises(EnrollmentDenied):
            self.begin(subject='111111111111111111')
        self.unchanged()

    def test_stored_approval_and_pair_exclude_raw_email_google_subject_and_browser_credentials(self):
        pair = self.begin()
        text = json.dumps(self.db.scan(TableName='bindings')['Items'])
        for value in (self.email, self.subject, self.sid, self.operation, pair['pair_id'], 'synthetic-google-token'):
            self.assertNotIn(value, text)

    def test_status_and_a_new_form_resume_the_same_pending_operation_without_writes(self):
        first = self.begin()
        before = self.db.scan(TableName='bindings')['Items']
        self.assertEqual(first, self.service.status(self.subject,self.email,self.sid,self.token_hash))
        self.assertEqual(first, self.begin(request_id='f'*64))
        self.assertEqual(before, self.db.scan(TableName='bindings')['Items'])

    def test_concurrent_different_forms_return_the_single_committed_operation(self):
        original = self.db.transact_write_items
        winning = []
        def raced(**kwargs):
            if len(kwargs['TransactItems']) == 5 and not winning:
                self.db.transact_write_items = original
                winning.append(self.begin(request_id='f'*64))
                self.db.transact_write_items = raced
            return original(**kwargs)
        self.db.transact_write_items = raced
        result = self.begin()
        self.assertEqual(result, winning[0])
        pairs = [r for r in self.db.scan(TableName='bindings')['Items'] if r['sk']['S']=='IDENTITY']
        self.assertEqual(len(pairs),1)
        self.assertEqual(self.bindings(),[])

    def test_missing_pending_pointer_cannot_revive_or_commit_a_partial_operation(self):
        pair = self.begin()
        self.db.delete_item(TableName='bindings',Key=key('SESSION#'+digest(self.sid),'ENROLLMENT'))
        with self.assertRaises(EnrollmentDenied): self.begin()
        with self.assertRaises(EnrollmentDenied): self.service.complete(pair['pair_id'],self.proof())
        self.assertEqual(self.bindings(),[])
        self.assertFalse(self.read('PAIR#'+digest(pair['pair_id']),'IDENTITY')['used'])

    def test_pointer_changed_during_proof_rolls_back_all_registration_writes(self):
        pair = self.begin()
        def changed(*_):
            self.db.update_item(TableName='bindings',Key=key('SESSION#'+digest(self.sid),'ENROLLMENT'),
                UpdateExpression='SET pair_pk=:other',ExpressionAttributeValues=encoded({':other':'PAIR#'+'f'*64}))
            return self.grant['account']
        self.service.fetch = changed
        with self.assertRaises(EnrollmentDenied): self.service.complete(pair['pair_id'],self.proof())
        self.assertEqual(self.bindings(),[])
        self.assertFalse(self.read('PAIR#'+digest(pair['pair_id']),'IDENTITY')['used'])
        self.assertNotIn('bound_subject',self.read(email_key(self.email,self.pepper),'LAB'))

    def test_new_atomic_mapping_drives_current_61_point_reader_and_rejects_other_identity(self):
        from identity_grade import identity_grade
        import test_grade_reader as fixtures
        fixture = fixtures.GradeTest('test_saved_score_and_unknown_current_use_existing_projection')
        fixture.setUp()
        fixture.row.update(deployment_id=self.grant['deployment_id'], token_hash=self.grant['token_hash'], instances=self.grant['instances'])
        for row in fixture.row['results']:
            if 'deployment_id' in row:
                row['deployment_id'] = self.grant['deployment_id']
        pair = self.begin()
        self.service.complete(pair['pair_id'], self.proof())
        service = self.service
        class BindingStore:
            def get(self, pk, sk): return service.get('bindings', pk, sk)
        result = identity_grade(self.subject, self.pepper, BindingStore(), fixture.store)
        self.assertEqual((result['raw_earned'], result['raw_maximum']), (59, 123))
        self.assertIn('M5', result['current_unresolved'])
        with self.assertRaises(fixtures.legacy.ApiError):
            identity_grade('111111111111111111', self.pepper, BindingStore(), fixture.store)
        approval_pk = email_key(self.email, self.pepper)
        self.db.update_item(TableName='bindings', Key=key(approval_pk, 'LAB'),
            UpdateExpression='SET #active=:no', ExpressionAttributeNames={'#active':'active'},
            ExpressionAttributeValues=encoded({':no':False}))
        with self.assertRaises(fixtures.legacy.ApiError):
            identity_grade(self.subject, self.pepper, BindingStore(), fixture.store)
        self.unchanged()


if __name__ == '__main__':
    unittest.main()
