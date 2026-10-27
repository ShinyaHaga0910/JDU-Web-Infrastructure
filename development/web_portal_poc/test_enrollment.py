import copy
import importlib.util
import threading
import unittest

from challenge_store import ChallengeStore
from enrollment import EnrollmentError, enroll
from test_identity_proof import ACCOUNT, NOW, url


class Cancelled(Exception):
    pass


class MemoryDynamo:
    """Atomic fake with the conditional effects required by this experiment."""
    class exceptions:
        TransactionCanceledException = Cancelled
    def __init__(self, meta):
        self.rows = {}
        self.meta = copy.deepcopy(meta)
        self.lock = threading.Lock()
    def put_item(self, TableName, Item, ConditionExpression):
        self.rows[(TableName, Item['pk']['S'], Item['sk']['S'])] = copy.deepcopy(Item)
    def get_item(self, TableName, Key, ConsistentRead):
        item = self.rows.get((TableName, Key['pk']['S'], Key['sk']['S']))
        return {'Item': copy.deepcopy(item)} if item else {}
    def transact_write_items(self, TransactItems):
        check, update, lab, account = [next(iter(item.values())) for item in TransactItems]
        with self.lock:
            vals = check['ExpressionAttributeValues']
            key = (update['TableName'], update['Key']['pk']['S'], update['Key']['sk']['S'])
            row = self.rows.get(key)
            dests = [(p['TableName'], p['Item']['pk']['S'], p['Item']['sk']['S']) for p in (lab, account)]
            u = update['ExpressionAttributeValues']
            if (not self.meta['active'] or self.meta['token_hash'] != vals[':token']['S']
                    or self.meta['deployment_id'] != vals[':deployment']['S']
                    or self.meta['instances'] != {k: v['S'] for k, v in vals[':instances']['M'].items()}
                    or not row or row['used']['BOOL'] or int(row['expires_at']['N']) <= int(u[':now']['N'])
                    or any(row[k] != u[':' + v] for k, v in
                           [('session', 'session'), ('account', 'account'), ('lab', 'lab'), ('connector', 'connector')])
                    or any(d in self.rows for d in dests)):
                raise Cancelled()
            self.rows[key]['used']['BOOL'] = True
            for key, p in zip(dests, (lab, account)):
                self.rows[key] = copy.deepcopy(p['Item'])


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.grant = {'account': ACCOUNT, 'lab_id': 'test-lab', 'deployment_id': 'deployment',
                      'token_hash': 'c' * 64,
                      'instances': {r: 'i-' + str(i) * 17 for i, r in enumerate(
                          ('bastion', 'web', 'dns', 'db', 'repo'), 1)}}
        self.client = MemoryDynamo(dict(self.grant, active=True))
        self.store = ChallengeStore(self.client, 'bindings', 'test-lab', 'known-connector', clock=lambda: 1000)
        self.nonce = self.store.issue('session', ACCOUNT)
    def run_enroll(self, fetch=lambda *_: ACCOUNT):
        return enroll(self.client, self.store, 'grade-table', self.grant, 'session', self.nonce,
                      url(), now=NOW, fetch=fetch)

    def test_success_preserves_grade_metadata_and_replay_is_refused(self):
        before = copy.deepcopy(self.client.meta)
        self.assertTrue(self.run_enroll()['bound'])
        self.assertEqual(self.client.meta, before)
        with self.assertRaises(EnrollmentError):
            self.run_enroll()
        self.assertIn(('bindings', 'LAB#test-lab', 'BINDING'), self.client.rows)

    def test_changed_original_deployment_does_not_consume_challenge(self):
        self.client.meta['deployment_id'] = 'changed'
        with self.assertRaises(EnrollmentError):
            self.run_enroll()
        self.assertTrue(self.store.is_pending(self.nonce, 'session', ACCOUNT))
        self.assertNotIn(('bindings', 'LAB#test-lab', 'BINDING'), self.client.rows)

    def test_wrong_account_does_not_consume_challenge(self):
        with self.assertRaises(EnrollmentError):
            self.run_enroll(lambda *_: '999999999999')
        self.assertTrue(self.store.is_pending(self.nonce, 'session', ACCOUNT))

    def test_account_cannot_bind_to_another_lab(self):
        self.run_enroll()
        other = dict(self.grant, lab_id='another-lab')
        self.client.meta = dict(other, active=True)
        other_store = ChallengeStore(self.client, 'bindings', 'another-lab', 'known-connector', clock=lambda: 1000)
        nonce = other_store.issue('second-session', ACCOUNT)
        with self.assertRaises(EnrollmentError):
            enroll(self.client, other_store, 'grade-table', other, 'second-session', nonce,
                   url(), now=NOW, fetch=lambda *_: ACCOUNT)
        self.assertTrue(other_store.is_pending(nonce, 'second-session', ACCOUNT))
        self.assertNotIn(('bindings', 'LAB#another-lab', 'BINDING'), self.client.rows)

    def test_two_concurrent_attempts_create_only_one_binding(self):
        barrier = threading.Barrier(2)
        def fetch(*_):
            barrier.wait(timeout=5)
            return ACCOUNT
        results = []
        def worker():
            try:
                self.run_enroll(fetch)
                results.append('success')
            except EnrollmentError:
                results.append('rejected')
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=7)
        self.assertCountEqual(results, ['success', 'rejected'])
        self.assertEqual(len([k for k in self.client.rows if k[2] == 'BINDING']), 2)


@unittest.skipUnless(importlib.util.find_spec('botocore'), 'botocore required')
class AwsSdkShapeTests(unittest.TestCase):
    def test_transaction_request_matches_dynamodb_sdk_schema(self):
        from botocore.session import Session
        from botocore.stub import Stubber
        client = Session().create_client('dynamodb', region_name='us-east-1',
                                         aws_access_key_id='EXAMPLE', aws_secret_access_key='synthetic-secret')
        challenge = ChallengeStore(client, 'bindings', 'test-lab', 'known-connector', clock=lambda: 1000)
        grant = {'account': ACCOUNT, 'lab_id': 'test-lab', 'deployment_id': 'deployment',
                 'token_hash': 'c' * 64,
                 'instances': {r: 'i-' + str(i) * 17 for i, r in enumerate(
                     ('bastion', 'web', 'dns', 'db', 'repo'), 1)}}
        from challenge_store import _hash
        nonce = 'a' * 64
        item = {'session': {'S': _hash('session')}, 'account': {'S': ACCOUNT},
                'lab': {'S': 'test-lab'}, 'connector': {'S': _hash('known-connector')},
                'used': {'BOOL': False}, 'expires_at': {'N': '1060'}}
        with Stubber(client) as stub:
            stub.add_response('get_item', {'Item': item})
            stub.add_response('transact_write_items', {})
            result = enroll(client, challenge, 'grade-table', grant, 'session', nonce,
                            url(), now=NOW, fetch=lambda *_: ACCOUNT)
            self.assertTrue(result['bound'])
            stub.assert_no_pending_responses()


if __name__ == '__main__':
    unittest.main()
