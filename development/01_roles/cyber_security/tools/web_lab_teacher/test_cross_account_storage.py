import copy
from decimal import Decimal
import unittest
import uuid

import cross_account_storage as storage


class CrossAccountStorageTests(unittest.TestCase):
    def setUp(self):
        self.binding = dict(lab_id=storage.LAB, deployment_id=storage.DEPLOYMENT, release_id=storage.RELEASE)
        self.nodes = {r: 'i-' + format(i + 1, '017x') for i, r in enumerate(sorted(storage.ROLES))}
        self.report = dict(self.binding, schema_version=1, kind='assessment', mission_id='P1',
            request_id=str(uuid.uuid4()), checks=[dict(id='WEB02_CHECK_' + str(i), role='web',
            instance_id=self.nodes['web'], status='PASS') for i in range(10)])
        self.receipt = dict(self.binding, request_id=self.report['request_id'], received_at='2026-10-22T10:00:00+00:00',
            kind='assessment', ok=True, stored=True)
        self.ack = dict(receipt=self.receipt, exact_retry_same_receipt=True)
        row = storage.summarize(self.report, self.ack)
        self.expected = dict(self.binding, scope='cross_account_anonymous_storage_expectations',
            teacher_account=storage.TEACHER, student_account=storage.STUDENT,
            manifest_sha256=storage.MANIFEST, credentials_exported=False, reports=[row])
        self.db = {'META': dict(self.binding, active=True, instances=self.nodes),
            'REQUEST#' + row['request_id']: dict(report=copy.deepcopy(self.report), receipt=self.receipt,
            body_sha256=storage.digest(self.report)), 'LATEST#P1': {k: row[k] for k in ('request_id', 'checks', 'passed', 'total')}}

    def verify(self):
        return storage.verify_rows(self.expected, lambda key, fields: {k: self.db[key][k] for k in fields})

    def test_exact_teacher_body_receipt_latest_and_decimal_numbers(self):
        self.db['REQUEST#' + self.report['request_id']]['report']['schema_version'] = Decimal(1)
        self.assertTrue(self.verify()['exact_bodies_and_receipts'])
        self.assertEqual(self.verify()['latest']['P1']['passed'], 10)

    def test_changed_teacher_body_or_receipt_is_rejected(self):
        saved = self.db['REQUEST#' + self.report['request_id']]
        saved['report']['checks'][0]['status'] = 'FAIL'
        with self.assertRaises(ValueError): self.verify()
        saved['report'] = self.report
        saved['receipt'] = dict(self.receipt, received_at='2026-10-22T10:00:01+00:00')
        with self.assertRaises(ValueError): self.verify()

    def test_changed_latest_or_registration_is_rejected(self):
        self.db['LATEST#P1']['passed'] = 9
        with self.assertRaises(ValueError): self.verify()
        self.db['LATEST#P1']['passed'] = 10
        self.db['META']['instances'] = dict(self.nodes, web='i-' + 'f' * 17)
        with self.assertRaises(ValueError): self.verify()

    def test_foreign_deployment_duplicate_and_unverified_retry_are_rejected(self):
        bad = dict(self.report, deployment_id=str(uuid.uuid4()))
        with self.assertRaises(ValueError): storage.summarize(bad, self.ack)
        with self.assertRaises(ValueError): storage.summarize(self.report, dict(self.ack, exact_retry_same_receipt=False))
        self.expected['reports'] *= 2
        with self.assertRaises(ValueError): self.verify()

    def test_latest_is_ordered_by_server_receipt_time(self):
        later = copy.deepcopy(self.report); later['request_id'] = str(uuid.uuid4())
        later['checks'][0]['status'] = 'FAIL'
        receipt = dict(self.receipt, request_id=later['request_id'], received_at='2026-10-22T10:01:00+00:00')
        row = storage.summarize(later, dict(receipt=receipt, exact_retry_same_receipt=True))
        self.expected['reports'].insert(0, row)
        self.db['REQUEST#' + row['request_id']] = dict(report=later, receipt=receipt, body_sha256=storage.digest(later))
        self.db['LATEST#P1'] = {k: row[k] for k in ('request_id', 'checks', 'passed', 'total')}
        self.assertEqual(self.verify()['latest']['P1']['passed'], 9)


if __name__ == '__main__':
    unittest.main()
