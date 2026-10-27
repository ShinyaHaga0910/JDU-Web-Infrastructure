import copy
import importlib.util
import threading
import unittest

from test_grade_reader import GradeTest, legacy
from identity_grade import identity_grade, subject_key
from subject_binding import bind_subject, SubjectBindingError


class Conflict(Exception):
    pass


class Store:
    class exceptions:
        TransactionCanceledException = Conflict

    def __init__(self, meta, binding):
        self.meta, self.binding = copy.deepcopy(meta), copy.deepcopy(binding)
        self.rows, self.lock = {}, threading.Lock()

    def transact_write_items(self, TransactItems):
        checks = [entry['ConditionCheck'] for entry in TransactItems[:3]]
        puts = [entry['Put'] for entry in TransactItems[3:]]
        with self.lock:
            v = checks[0]['ExpressionAttributeValues']
            grade_match = (self.meta['active'] and self.meta['lab_id'] == v[':lab']['S']
                           and self.meta['deployment_id'] == v[':deployment']['S']
                           and self.meta['token_hash'] == v[':token']['S'])
            binding_match = True
            # The two pre-existing rows may change independently.
            for check in checks[1:]:
                row = self.binding.get(check['Key']['pk']['S'])
                vals = check['ExpressionAttributeValues']
                binding_match = binding_match and row is not None and all(row.get(field) == vals[name]['S'] for field, name in
                    [('lab_id', ':lab'), ('account', ':account'), ('deployment_id', ':deployment'), ('connector', ':connector')])
            keys = [(p['Item']['pk']['S'], p['Item']['sk']['S']) for p in puts]
            if not grade_match or not binding_match or any(k in self.rows for k in keys):
                raise Conflict()
            for key, put in zip(keys, puts):
                self.rows[key] = copy.deepcopy(put['Item'])


class SubjectBindingTest(unittest.TestCase):
    def setUp(self):
        self.subject, self.pepper = '1234567890', b'synthetic-key-only-for-testing!!'
        self.context = {'lab_id': 'test-lab', 'account': '123456789012', 'deployment_id': 'd',
                        'token_hash': 'c' * 64, 'connector': 'b' * 64}
        self.meta = dict(self.context, active=True)
        bound = {k: v for k, v in self.context.items() if k != 'token_hash'}
        self.db = Store(self.meta, {'LAB#test-lab': dict(bound), 'ACCOUNT#123456789012': dict(bound)})

    def bind(self, subject=None, context=None):
        return bind_subject(self.db, 'bindings', 'grades', subject or self.subject, self.pepper, context or self.context)

    def test_success_is_atomic_and_grade_remains_untouched(self):
        before = copy.deepcopy(self.db.meta)
        self.assertTrue(self.bind()['bound'])
        self.assertEqual(self.db.meta, before)
        pk = subject_key(self.subject, self.pepper)
        self.assertEqual(self.db.rows[('LAB#test-lab', 'SUBJECT')]['subject_pk']['S'], pk)
        self.assertEqual(self.db.rows[(pk, 'BINDING')]['active']['BOOL'], True)
        with self.assertRaises(SubjectBindingError):
            self.bind('9999999999')
        self.assertEqual(len(self.db.rows), 2)

    def test_stale_grade_or_account_binding_never_registers(self):
        for field, value in [('active', False), ('deployment_id', 'changed'), ('token_hash', 'a' * 64)]:
            with self.subTest(field=field):
                original = self.db.meta[field]
                self.db.meta[field] = value
                with self.assertRaises(SubjectBindingError): self.bind()
                self.assertEqual(self.db.rows, {})
                self.db.meta[field] = original
        self.db.binding['ACCOUNT#123456789012']['connector'] = 'f' * 64
        with self.assertRaises(SubjectBindingError): self.bind()
        self.assertEqual(self.db.rows, {})

    def test_two_simultaneous_subjects_cannot_claim_same_lab(self):
        outcomes = []
        def worker(subject):
            try:
                self.bind(subject)
                outcomes.append('bound')
            except SubjectBindingError:
                outcomes.append('denied')
        jobs = [threading.Thread(target=worker, args=(s,)) for s in (self.subject, '22222222')]
        for job in jobs: job.start()
        for job in jobs: job.join(5)
        self.assertCountEqual(outcomes, ['bound', 'denied'])
        self.assertEqual(len(self.db.rows), 2)

    def test_invalid_context_never_calls_dynamo(self):
        bad = dict(self.context, account='not-an-account')
        with self.assertRaises(SubjectBindingError): self.bind(context=bad)
        self.assertEqual(self.db.rows, {})

    def test_created_mapping_drives_existing_grade_reader(self):
        fixture = GradeTest('test_saved_score_and_unknown_current_use_existing_projection')
        fixture.setUp()
        self.context['deployment_id'] = 'same'
        self.context['token_hash'] = fixture.row['token_hash']
        self.db.meta.update(self.context)
        for row in self.db.binding.values():
            row['deployment_id'] = 'same'
        self.bind()
        # Convert the transaction's synthetic DynamoDB values to normal rows.
        rows = {key: {name: next(iter(value.values())) for name, value in item.items()}
                for key, item in self.db.rows.items()}
        rows[('LAB#test-lab', 'BINDING')] = self.db.binding['LAB#test-lab']
        rows[('ACCOUNT#123456789012', 'BINDING')] = self.db.binding['ACCOUNT#123456789012']
        class Bindings:
            def get(self, pk, sk): return copy.deepcopy(rows.get((pk, sk)))
        view = identity_grade(self.subject, self.pepper, Bindings(), fixture.store)
        self.assertEqual((view['raw_earned'], view['raw_maximum']), (62, 62))
        self.assertIn('M5', view['current_unresolved'])
        with self.assertRaises(legacy.ApiError):
            identity_grade('22222222', self.pepper, Bindings(), fixture.store)


@unittest.skipUnless(importlib.util.find_spec('botocore'), 'botocore required')
class SchemaTest(unittest.TestCase):
    def test_dynamodb_request_accepted_by_sdk(self):
        from botocore.session import Session
        from botocore.stub import Stubber
        client = Session().create_client('dynamodb', region_name='us-east-1',
                                         aws_access_key_id='EXAMPLE', aws_secret_access_key='synthetic-secret')
        context = {'lab_id': 'test-lab', 'account': '123456789012', 'deployment_id': 'd',
                   'token_hash': 'c' * 64, 'connector': 'b' * 64}
        with Stubber(client) as stub:
            stub.add_response('transact_write_items', {})
            self.assertTrue(bind_subject(client, 'bindings', 'grades', '1234567890',
                                         b'synthetic-key-only-for-testing!!', context)['bound'])
            stub.assert_no_pending_responses()
