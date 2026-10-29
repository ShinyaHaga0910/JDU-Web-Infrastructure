import unittest
from unittest.mock import patch

from test_identity_grade import IdentityGradeTest
import identity_grade_handler as api


class HandlerTest(unittest.TestCase):
    def setUp(self):
        fixture = IdentityGradeTest('test_verified_subject_reads_only_own_existing_grade')
        fixture.setUp()
        self.fixture = fixture

    def serve(self, event):
        f = self.fixture
        return api.serve(event, f.pepper, f.bindings, f.store)

    def test_verified_identity_gets_student_safe_existing_score(self):
        result = self.serve({'subject': self.fixture.subject})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual((result['grade']['raw_earned'], result['grade']['raw_maximum']), (62, 62))
        self.assertNotIn('token_hash', repr(result))
        self.assertNotIn(self.fixture.subject, repr(result))

    def test_unmapped_or_extra_input_is_rejected_without_reading_grades(self):
        for event in ({'subject': '98765432109876543210'}, {'subject': self.fixture.subject, 'lab_id': 'other'},
                      {}, None, 'bad'):
            with self.subTest(event=event):
                self.assertEqual(self.serve(event), {'status': 'unauthorized'})
        self.assertEqual(self.fixture.store.labs_calls, [])

    def test_store_failure_is_generic(self):
        self.fixture.bindings.get = lambda *_: (_ for _ in ()).throw(RuntimeError('sensitive example'))
        self.assertEqual(self.serve({'subject': self.fixture.subject}), {'status': 'unavailable'})

    def test_missing_or_invalid_aws_configuration_fails_closed(self):
        with patch.dict(api.os.environ, {}, clear=True):
            self.assertEqual(api.handler({'subject': self.fixture.subject}, None), {'status': 'unavailable'})

    def test_status_without_registered_client_fails_closed(self):
        f = self.fixture
        self.assertEqual(api.serve({'subject': f.subject, 'operation': 'status'}, f.pepper, f.bindings, f.store), {'status': 'unavailable'})
        self.assertEqual(api.serve({'subject': f.subject, 'operation': 'start'}, f.pepper, f.bindings, f.store), {'status': 'unauthorized'})
