import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
sys.path[:0] = [str(ROOT / 'web_lab_assessment'), str(ROOT / 'web_lab_teacher')]
import progress_api as legacy
import grading
import registry
from grade_reader import student_grade


class Store:
    def __init__(self, row):
        self.row = row
        self.labs_calls = []

    def get(self, pk, sk):
        return self.row if pk == 'LAB#test-lab' and sk == 'META' else None

    def labs(self, only_lab=None):
        self.labs_calls.append(only_lab)
        return [self.row] if only_lab == 'test-lab' else []


class GradeTest(unittest.TestCase):
    def setUp(self):
        self.token = 'x' * 40
        self.row = {'lab_id': 'test-lab', 'deployment_id': 'same', 'active': True,
                    'token_hash': legacy.digest(self.token), 'results': []}
        for mid in registry.MISSIONS:
            self.row['results'].append({'sk': grading.grade_key(mid), 'deployment_id': 'same',
                'contract_sha256': registry.CONTRACT_SHA256, 'raw_earned': registry.TASKS[mid]['raw_points_max'],
                'received_at': '2026-10-23T00:00:00Z'})
        self.row['results'].append({'sk': grading.current_key('M5'), 'contract_sha256': registry.CONTRACT_SHA256,
                                    'evaluable': False, 'unresolved': 1})
        self.store = Store(self.row)
        self.service = legacy.ProgressService(self.store, 'unused', 'unused')

    def event(self, lab='test-lab', token=None):
        return {'body': json.dumps({'lab_id': lab}), 'headers': {'Authorization': 'Bearer ' + (token or self.token)}}

    def test_saved_score_and_unknown_current_use_existing_projection(self):
        result = student_grade(self.service, self.event())
        self.assertEqual((result['raw_earned'], result['raw_maximum']), (59, 61))
        self.assertIn('M5', result['current_unresolved'])
        self.assertEqual(result['selected']['M5']['raw_earned'], 13)
        self.assertEqual(self.store.labs_calls, ['test-lab'])
        self.assertNotIn('token_hash', json.dumps(result))

    def test_other_lab_and_wrong_token_cannot_read(self):
        for event in (self.event(lab='other-lab'), self.event(token='y' * 40)):
            with self.assertRaises(legacy.ApiError):
                student_grade(self.service, event)
        self.assertEqual(self.store.labs_calls, [])

    def test_revoked_or_rebound_after_authentication_cannot_read(self):
        original_labs = self.store.labs
        def revoked(only_lab=None):
            rows = original_labs(only_lab)
            return [dict(rows[0], active=False)]
        self.store.labs = revoked
        with self.assertRaises(legacy.ApiError):
            student_grade(self.service, self.event())

        def rebound(only_lab=None):
            rows = original_labs(only_lab)
            return [dict(rows[0], deployment_id='different')]
        self.store.labs = rebound
        with self.assertRaises(legacy.ApiError):
            student_grade(self.service, self.event())


if __name__ == '__main__':
    unittest.main()
