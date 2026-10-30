"""R1 pre-provisioning transactions. Moto AWS; STS fetch is explicitly fake."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch, Mock
from urllib.parse import urlencode

import boto3
from moto import mock_aws

from identity_keys import subject_key
from portal_enrollment import PortalEnrollment, EnrollmentDenied, digest, email_key, encoded, key
from portal_preparation import PortalPreparation
from portal_enrollment_handler import serve


class PreparationTest(unittest.TestCase):
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
        self.now = datetime(2026, 10, 30, 8, 0, 0, tzinfo=timezone.utc).timestamp()
        self.pepper, self.subject, self.email = b'x' * 32, '123456789', 'synthetic@jdu.uz'
        self.account, self.lab = '123456789012', 'new-student'
        self.sid, self.token = 'a' * 64, 'b' * 64
        self.session = 'SESSION#' + digest(self.sid)
        self.put('bindings', {'pk': self.session, 'sk': 'PORTAL', 'active': True,
                              'expires_at': int(self.now) + 3600, 'token_hash': self.token})
        self.fetches = []
        def fetch(path, nonce):
            self.fetches.append((path, nonce))
            return self.account
        self.auth = PortalEnrollment(self.db, 'bindings', 'grades', self.pepper, clock=lambda: self.now, fetch=fetch)
        self.prep = PortalPreparation(self.auth)
        self.release = {'release_id': 'web-course-synthetic-r3', 'manifest_sha256': 'c' * 64,
                        'template_sha256': 'd' * 64, 'expires_at': int(self.now) + 86400}
        # An unrelated existing Lab/score must survive all initial preparation.
        self.existing = {'pk': 'LAB#existing-student', 'sk': 'META', 'selected_score': 62, 'active': True}
        self.put('grades', self.existing)
        self.approved = self.prep.approve(self.email, self.account, self.lab, self.release)

    def put(self, table, row):
        self.db.put_item(TableName=table, Item=encoded(row))

    def claims(self):
        return {'subject': self.subject, 'email': self.email, 'session_id': self.sid, 'token_hash': self.token}

    def begin(self, request='e' * 64):
        return self.prep.begin(**self.claims(), request_id=request)

    def row(self):
        return self.prep.get(email_key(self.email, self.pepper), 'PREPARATION')

    def snapshot(self):
        return {t: sorted(self.db.scan(TableName=t)['Items'], key=lambda r: (r['pk']['S'], r['sk']['S']))
                for t in ('bindings', 'grades')}

    def proof(self):
        stamp = datetime.fromtimestamp(self.now, timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        values = {'Action': 'GetCallerIdentity', 'Version': '2011-06-15', 'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
                  'X-Amz-Credential': 'EXAMPLE/' + stamp[:8] + '/us-east-1/sts/aws4_request',
                  'X-Amz-Date': stamp, 'X-Amz-Expires': '60', 'X-Amz-SignedHeaders': 'host;x-jdu-nonce',
                  'X-Amz-Signature': 'f' * 64}
        return 'https://sts.us-east-1.amazonaws.com/?' + urlencode(values)

    def confirmed(self):
        pair = self.begin()
        result = self.prep.complete(pair['pair_id'], self.proof())
        self.assertTrue(result['aws_confirmed'])
        return pair

    def test_initial_assignment_requires_no_existing_nodes_or_grade_meta(self):
        status = self.prep.status(**self.claims())
        self.assertEqual(status['stage'], 'APPROVED')
        self.assertFalse(status['resources_created'])
        self.assertIsNone(self.auth.get('grades', 'LAB#' + self.lab, 'META'))
        self.assertEqual(self.auth.get('grades', self.existing['pk'], 'META'), self.existing)
        snapshot = self.snapshot()
        self.prep.status(**self.claims())
        self.assertEqual(self.snapshot(), snapshot)  # GET cannot enqueue/create.

    def test_account_proof_then_confirm_makes_exactly_one_immutable_request(self):
        pair = self.confirmed()
        self.assertEqual(self.prep.complete(pair['pair_id'], self.proof())['stage'], 'AWS_CONFIRMED')
        first = self.prep.confirm(**self.claims())
        after = self.snapshot()
        self.assertEqual(self.prep.confirm(**self.claims()), first)
        self.assertEqual(self.prep.status(**self.claims())['stage'], 'CREATE_REQUESTED')
        self.assertEqual(self.snapshot(), after)
        requests = [r for r in after['bindings'] if r['sk']['S'] == 'REQUEST']
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]['initial_state']['S'], 'foundation_only')
        self.assertEqual(requests[0]['grant']['M']['deployment_id']['S'], self.approved['deployment_id'])
        self.assertFalse(first['resources_created'])
        self.assertEqual(self.auth.get('grades', self.existing['pk'], 'META'), self.existing)
        self.assertFalse(any(r['sk']['S'] == 'BINDING' for r in after['bindings']))

    def test_reloaded_forms_return_same_challenge_and_expiry_allows_new_form(self):
        first = self.begin()
        self.assertEqual(first, self.begin('f' * 64))
        self.now += 301
        with self.assertRaises(EnrollmentDenied): self.prep.complete(first['pair_id'], self.proof())
        with self.assertRaises(EnrollmentDenied): self.begin()
        second = self.begin('f' * 64)
        self.assertNotEqual(first['pair_id'], second['pair_id'])
        self.assertEqual(self.row()['stage'], 'APPROVED')

    def test_cannot_confirm_before_aws_proof_or_from_other_identity(self):
        before = self.snapshot()
        with self.assertRaises(EnrollmentDenied): self.prep.confirm(**self.claims())
        self.assertEqual(self.snapshot(), before)
        self.confirmed()
        with self.assertRaises(EnrollmentDenied):
            self.prep.confirm(**dict(self.claims(), subject='987654321'))
        with self.assertRaises(EnrollmentDenied):
            self.prep.status(**dict(self.claims(), email='other@jdu.uz'))

    def test_wrong_aws_and_untrusted_url_cannot_consume_confirmation(self):
        pair = self.begin()
        self.auth.fetch = lambda *_: '999999999999'
        with self.assertRaises(EnrollmentDenied): self.prep.complete(pair['pair_id'], self.proof())
        self.auth.fetch = lambda *_: self.fail('Untrusted destination fetched')
        with self.assertRaises(ValueError):
            self.prep.complete(pair['pair_id'], self.proof().replace('sts.us-east-1.amazonaws.com', 'attacker.test'))
        self.assertEqual(self.row()['stage'], 'APPROVED')
        self.assertFalse(self.prep.get('PREPARE-PAIR#' + digest(pair['pair_id']), 'IDENTITY')['used'])

    def test_session_or_assignment_revoked_while_sts_is_fetched_never_confirms(self):
        pair = self.begin()
        original = self.auth.fetch
        def revoke(path, nonce):
            value = original(path, nonce)
            row = self.row()
            row['active'] = False
            self.put('bindings', row)
            return value
        self.auth.fetch = revoke
        with self.assertRaises(EnrollmentDenied): self.prep.complete(pair['pair_id'], self.proof())
        self.assertFalse(self.prep.get('PREPARE-PAIR#' + digest(pair['pair_id']), 'IDENTITY')['used'])

    def test_expired_release_is_visible_but_cannot_queue_creation(self):
        self.confirmed()
        self.now += 86401
        # Renew the synthetic session, not the signed release.
        self.put('bindings', {'pk': self.session, 'sk': 'PORTAL', 'active': True,
                              'expires_at': int(self.now) + 3600, 'token_hash': self.token})
        self.assertFalse(self.prep.status(**self.claims())['can_continue'])
        with self.assertRaises(EnrollmentDenied): self.prep.confirm(**self.claims())
        self.assertEqual(self.row()['stage'], 'AWS_CONFIRMED')

    def test_account_and_lab_reservations_do_not_allow_second_assignment(self):
        before = self.snapshot()
        for account, lab in ((self.account, 'different-lab'), ('999999999999', self.lab)):
            with self.assertRaises(EnrollmentDenied):
                self.prep.approve('other@jdu.uz', account, lab, self.release)
        self.assertEqual(self.snapshot(), before)

    def test_existing_grade_and_account_binding_are_never_replaced(self):
        for sk, table in (('META', 'grades'), ('BINDING', 'bindings')):
            pk = 'LAB#used-lab' if table == 'grades' else 'ACCOUNT#999999999999'
            self.put(table, {'pk': pk, 'sk': sk, 'original': True})
        before = self.snapshot()
        with self.assertRaises(EnrollmentDenied):
            self.prep.approve('other@jdu.uz', '999999999999', 'used-lab', self.release)
        self.assertEqual(self.snapshot(), before)
        self.confirmed()
        self.put('bindings', {'pk': subject_key(self.subject, self.pepper), 'sk': 'BINDING', 'original': True})
        with self.assertRaises(EnrollmentDenied): self.prep.confirm(**self.claims())

    def test_context_created_between_read_and_write_rolls_back_entire_request(self):
        self.confirmed()
        original = self.db.transact_write_items
        def interleave(**kwargs):
            self.put('grades', {'pk': 'LAB#' + self.lab, 'sk': 'META', 'original': True})
            return original(**kwargs)
        with patch.object(self.db, 'transact_write_items', side_effect=interleave):
            with self.assertRaises(EnrollmentDenied): self.prep.confirm(**self.claims())
        self.assertEqual(self.row()['stage'], 'AWS_CONFIRMED')
        self.assertIsNone(self.prep.get('PREPARATION#' + self.approved['deployment_id'], 'REQUEST'))

    def test_handler_has_exact_student_fields_and_no_approval_route(self):
        event = {'operation': 'prepare_begin', **self.claims(), 'request_id': 'e' * 64}
        response = serve(event, self.auth, self.prep)
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(response['preparation']['stage'], 'APPROVED')
        for change in ({'operation': 'prepare_approve'}, {'operation': 'prepare_create'}, {'account': self.account},
                       {'operation': 'confirm'}, {'operation': 'prepare_confirm', 'grant': {}},
                       {'email': 'other@example.com'}):
            self.assertEqual(serve(dict(event, **change), self.auth, self.prep), {'status': 'unauthorized'})
        # A proof is sent by the existing account helper, not with Google claims.
        result = serve({'operation': 'prepare_complete', 'pair_id': response['preparation']['pair_id'],
                        'proof_url': self.proof()}, self.auth, self.prep)
        self.assertEqual(result['preparation']['stage'], 'AWS_CONFIRMED')
        result = serve({'operation': 'prepare_confirm', **self.claims()}, self.auth, self.prep)
        self.assertEqual(result['preparation']['stage'], 'CREATE_REQUESTED')

    def test_pending_status_resumes_same_proof_without_writing(self):
        pending = self.begin()
        snapshot = self.snapshot()
        view = self.prep.status(**self.claims())
        self.assertEqual(view['pair_id'], pending['pair_id'])
        self.assertEqual(view['expires_at'], pending['expires_at'])
        self.assertEqual(self.snapshot(), snapshot)

    def test_initial_gateway_only_receives_the_bound_assignment_after_confirmation(self):
        initial = Mock(return_value={'stage':'PLAN_READY'})
        self.prep.initial = initial
        with self.assertRaises(EnrollmentDenied): self.prep.plan(**self.claims())
        initial.assert_not_called()
        self.confirmed()
        self.prep.plan(**self.claims())
        self.assertEqual(initial.call_args.args, (self.row()['grant'], 'plan'))
        self.prep.status(**self.claims())
        self.assertEqual(initial.call_args.args, (self.row()['grant'], 'observe'))
        initial.return_value = {'stage':'CREATE_REQUESTED','resources_created':None}
        result = self.prep.create(**self.claims(), plan_digest='f'*64,
            password='DisposableFixtureOnly23', confirmation='DisposableFixtureOnly23')
        self.assertIsNone(result['resources_created'])
        self.assertEqual(initial.call_args.args, (self.row()['grant'], 'create'))
        self.assertEqual(initial.call_args.kwargs['plan_digest'],'f'*64)

    def test_advance_requires_live_own_confirmed_request_and_forwards_no_commands(self):
        initial=Mock(return_value={'stage':'SETUP_PENDING','setup_phase':'ssh_init','lab_ready':False})
        self.prep.initial=initial
        with self.assertRaises(EnrollmentDenied):self.prep.advance(**self.claims())
        self.confirmed();self.prep.confirm(**self.claims())
        event={'operation':'prepare_advance',**self.claims()}
        self.assertEqual(serve(event,self.auth,self.prep)['preparation']['initial']['setup_phase'],'ssh_init')
        self.assertEqual(initial.call_args.args,(self.row()['grant'],'advance'))
        self.assertEqual(initial.call_args.kwargs,{})
        initial.reset_mock()
        self.assertEqual(serve({**event,'commands':['anything']},self.auth,self.prep),{'status':'unauthorized'})
        self.assertEqual(serve({**event,'subject':'987654321'},self.auth,self.prep),{'status':'unauthorized'})
        initial.assert_not_called()


if __name__ == '__main__': unittest.main()
