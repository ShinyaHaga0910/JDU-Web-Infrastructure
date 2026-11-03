import copy
import unittest
from unittest.mock import Mock

from portal_enrollment import PortalEnrollment
import reassign_verification_identity as r


class ReassignmentTests(unittest.TestCase):
    def setUp(self):
        self.rows = {}
        metas = []
        for lab, dep, digit in ((r.OLD, r.OLD_DEPLOYMENT, '1'), (r.NEW, r.NEW_DEPLOYMENT, '2')):
            meta = {'pk': 'LAB#' + lab, 'sk': 'META', 'active': True, 'lab_id': lab,
                    'deployment_id': dep, 'assessment_context': 'verification', 'token_hash': digit * 64,
                    'instances': {role: 'i-' + digit * 16 + str(i)
                                  for i, role in enumerate(('bastion', 'web', 'dns', 'db', 'repo'))}}
            metas.append(meta)
            self.rows[(r.GRADES, meta['pk'], meta['sk'])] = meta
        subject, approval = 'SUBJECT#' + 'a' * 64, 'APPROVAL#' + 'b' * 64
        grant = {'account': r.STUDENT, **{k: metas[0][k] for k in ('lab_id', 'deployment_id', 'token_hash', 'instances')}}
        for row in PortalEnrollment.binding_records(subject, grant, approval):
            self.rows[(r.BINDINGS, row['pk'], row['sk'])] = row
        self.rows[(r.BINDINGS, approval, 'LAB')] = {'pk': approval, 'sk': 'LAB', 'active': True,
            'bound_subject': subject, 'grant': grant}
        teacher = approval.replace('APPROVAL#', 'TEACHER#')
        self.rows[(r.BINDINGS, teacher, 'ACCESS')] = {'pk': teacher, 'sk': 'ACCESS', 'active': True,
            'class_id': '193548', 'subject_pk': subject, 'revision': 'original',
            'labs': [{'lab_id': r.OLD, 'deployment_id': r.OLD_DEPLOYMENT, 'context': 'verification'}]}
        self.db = Mock()
        self.db.get_item.side_effect = self.read

    def read(self, TableName, Key, ConsistentRead):
        row = self.rows.get((TableName, Key['pk']['S'], Key['sk']['S']))
        return {'Item': r.encoded(row)} if row else {}

    def test_plan_preserves_grades_and_requires_original_rows_atomically(self):
        before = copy.deepcopy(self.rows)
        value = r.plan(self.db, now=1000)
        self.assertEqual(self.rows, before)
        self.db.transact_write_items.assert_not_called()
        transactions = value['transactions']
        self.assertEqual(len(transactions), 8)
        for entry in transactions:
            operation, change = next(iter(entry.items()))
            self.assertIn('ConditionExpression', change)
            if operation != 'ConditionCheck':
                self.assertEqual(change['TableName'], r.BINDINGS)
        self.assertEqual(len([t for t in transactions if 'Delete' in t]), 4)
        self.assertNotIn('bound_subject', value['new_approval'])
        self.assertEqual(value['new_approval']['grant']['lab_id'], r.NEW)
        self.assertEqual([v['lab_id'] for v in value['new_access']['labs']], [r.OLD, r.NEW])

    def test_changed_registration_or_scope_stops_without_writes(self):
        self.rows[(r.GRADES, 'LAB#' + r.NEW, 'META')]['assessment_context'] = 'course'
        with self.assertRaises(ValueError):
            r.plan(self.db, now=1000)
        self.db.transact_write_items.assert_not_called()

    def test_stale_plan_stops_before_transaction(self):
        value = r.plan(self.db, now=1000)
        with self.assertRaises(ValueError):
            r.apply(self.db, value, now=5000)
        self.db.transact_write_items.assert_not_called()

    def test_apply_changes_binding_scope_and_preserves_original_grade_metadata(self):
        value = r.plan(self.db, now=1000)
        grades_before = {k: copy.deepcopy(v) for k, v in self.rows.items() if k[0] == r.GRADES}

        def transaction(TransactItems, ClientRequestToken):
            for entry in TransactItems:
                if 'Put' in entry:
                    put = entry['Put']
                    row = {k: r.DES.deserialize(v) for k, v in put['Item'].items()}
                    self.rows[(put['TableName'], row['pk'], row['sk'])] = row
                elif 'Delete' in entry:
                    delete = entry['Delete']
                    self.rows.pop((delete['TableName'], delete['Key']['pk']['S'], delete['Key']['sk']['S']))

        self.db.transact_write_items.side_effect = transaction
        result = r.apply(self.db, value, now=1001)
        self.assertTrue(result['applied'])
        self.assertEqual({k: v for k, v in self.rows.items() if k[0] == r.GRADES}, grades_before)
        self.assertNotIn((r.BINDINGS, 'LAB#' + r.OLD, 'SUBJECT'), self.rows)
        self.db.transact_write_items.assert_called_once()


if __name__ == '__main__':
    unittest.main()
