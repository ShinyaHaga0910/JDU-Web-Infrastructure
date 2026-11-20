import copy
import json
import unittest

# Sets up the same source paths and realistic 59-point grading fixture.
from test_grade_reader import GradeTest, legacy
from identity_grade import identity_grade, subject_key


class Bindings:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)
        self.calls = []
        self.after_first_subject = None

    def get(self, pk, sk):
        self.calls.append((pk, sk))
        row = copy.deepcopy(self.rows.get((pk, sk)))
        if pk.startswith('SUBJECT#') and self.after_first_subject:
            self.after_first_subject()
            self.after_first_subject = None
        return row


class IdentityGradeTest(unittest.TestCase):
    def setUp(self):
        fixture = GradeTest('test_saved_score_and_unknown_current_use_existing_projection')
        fixture.setUp()
        self.store, self.meta = fixture.store, fixture.row
        self.pepper = b'synthetic-key-only-for-testing!!'
        self.subject, self.other = '12345678901234567890', '98765432109876543210'
        self.pk = subject_key(self.subject, self.pepper)
        context = {'lab_id': 'test-lab', 'account': '123456789012', 'deployment_id': 'same',
                   'connector': 'b' * 64}
        self.person = dict(context, active=True, token_hash=self.meta['token_hash'])
        self.rows = {(self.pk, 'BINDING'): self.person,
                     ('LAB#test-lab', 'BINDING'): context,
                     ('LAB#test-lab', 'SUBJECT'): {'subject_pk': self.pk},
                     ('ACCOUNT#123456789012', 'BINDING'): context}
        self.bindings = Bindings(self.rows)

    def read(self, subject=None):
        return identity_grade(subject or self.subject, self.pepper, self.bindings, self.store)

    def test_verified_subject_reads_only_own_existing_grade(self):
        view = self.read()
        self.assertEqual((view['raw_earned'], view['raw_maximum']), (59, 61))
        self.assertIn('M5', view['current_unresolved'])
        self.assertEqual(self.store.labs_calls, ['test-lab'])
        self.assertNotIn(self.subject, json.dumps(view))
        self.assertNotIn(self.meta['token_hash'], json.dumps(view))
        self.assertNotIn('token_hash', json.dumps(view))

    def test_unknown_subject_cannot_choose_another_lab(self):
        with self.assertRaises(legacy.ApiError) as error:
            self.read(self.other)
        self.assertEqual(error.exception.status, 401)
        self.assertEqual(self.store.labs_calls, [])

    def test_disconnected_or_revoked_links_cannot_read(self):
        for pk, field, value in [(self.pk, 'active', False),
                                 ('LAB#test-lab', 'connector', 'e' * 64),
                                 ('ACCOUNT#123456789012', 'lab_id', 'other-lab')]:
            with self.subTest(pk=pk):
                b = Bindings(self.rows)
                b.rows[(pk, 'BINDING')][field] = value
                with self.assertRaises(legacy.ApiError):
                    identity_grade(self.subject, self.pepper, b, self.store)
                self.assertEqual(self.store.labs_calls, [])

    def test_replaced_or_disabled_grade_identity_is_rejected(self):
        for field, value in [('deployment_id', 'different'), ('token_hash', 'a' * 64), ('active', False)]:
            with self.subTest(field=field):
                original = self.meta[field]
                self.meta[field] = value
                with self.assertRaises(legacy.ApiError):
                    self.read()
                self.meta[field] = original
        self.assertEqual(self.store.labs_calls, [])

    def test_revocation_during_grade_read_is_rechecked(self):
        get_labs = self.store.labs
        def revoke(lab):
            result = get_labs(lab)
            self.bindings.rows[(self.pk, 'BINDING')]['active'] = False
            return result
        self.store.labs = revoke
        with self.assertRaises(legacy.ApiError):
            self.read()

    def test_pepper_and_subject_are_never_used_without_validation(self):
        for subject, pepper in [('bad subject', self.pepper), (self.subject, b'short'), ('', self.pepper)]:
            with self.assertRaises(legacy.ApiError):
                identity_grade(subject, pepper, self.bindings, self.store)
        self.assertEqual(self.bindings.calls, [])
        self.assertNotIn(self.subject, self.pk)
        self.assertNotEqual(self.pk, subject_key(self.subject, b'a different synthetic pepper key!!'))


if __name__ == '__main__':
    unittest.main()
