"""Current curriculum excludes retired tasks without deleting old signed rows."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
TOOLS = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
sys.path[:0] = [str(TOOLS / 'web_lab_assessment'), str(TOOLS / 'web_lab_teacher')]
from registry import (CONTRACT_SHA256, INTRO_CONTRACT_SHA256, MISSIONS, TASKS, COURSE_ID, COURSE_TASKS,
                      COURSE_MISSIONS, COURSE_MAXIMUM, COURSE_POINTS, INTRO_MARKERS)
from grading import grade_key, current_key, project_lab, project_course_lab
from portal_checker_handler import serve

class RetirementTest(unittest.TestCase):
    def full_history(self):
        lab = {'lab_id': 'synthetic-course', 'deployment_id': 'same', 'results': []}
        for mid in MISSIONS:
            row = {'contract_sha256': CONTRACT_SHA256, 'deployment_id': 'same',
                   'raw_earned': TASKS[mid]['raw_points_max'], 'evaluable': True, 'complete': True}
            lab['results'] += [dict(row, sk=grade_key(mid)), dict(row, sk=current_key(mid))]
        return lab

    def add_connection_grades(self, lab):
        for task in INTRO_MARKERS:
            row = {'contract_sha256': INTRO_CONTRACT_SHA256, 'deployment_id': 'same',
                   'raw_earned': 1, 'evaluable': True, 'complete': True}
            lab['results'] += [dict(row, sk=grade_key(task, INTRO_CONTRACT_SHA256)),
                               dict(row, sk=current_key(task, INTRO_CONTRACT_SHA256))]

    def test_historical_full_score_is_59_in_current_course_without_row_changes(self):
        lab = self.full_history(); before = copy.deepcopy(lab)
        self.assertEqual(project_lab(lab)['raw_earned'], 62)
        view = project_course_lab(lab)
        self.assertEqual((view['raw_earned'], view['raw_maximum']), (59, 61))
        self.assertEqual(set(view['selected']), set(COURSE_MISSIONS))
        self.assertFalse(view['complete']); self.assertFalse(view['fully_evaluated'])
        self.assertEqual(view['missing_or_unresolved'], ['P0', 'M0'])
        self.assertEqual(lab, before); self.assertNotIn('M3', view['current'])

    def test_missing_or_unknown_retired_task_never_blocks_completion(self):
        lab = self.full_history()
        self.add_connection_grades(lab)
        lab['results'] = [r for r in lab['results'] if r['sk'] != grade_key('M3')]
        next(r for r in lab['results'] if r['sk'] == current_key('M3')).update(evaluable=False, complete=False)
        view = project_course_lab(lab)
        self.assertEqual(view['raw_earned'], 61)
        self.assertEqual(view['missing_or_unresolved'], [])
        self.assertEqual(view['current_unresolved'], []); self.assertTrue(view['complete'])

    def test_missing_active_task_still_blocks_completion(self):
        lab = self.full_history()
        self.add_connection_grades(lab)
        lab['results'] = [r for r in lab['results'] if r['sk'] != grade_key('M4')]
        view = project_course_lab(lab)
        self.assertEqual(view['raw_earned'], 52)
        self.assertEqual(view['missing_or_unresolved'], ['M4']); self.assertFalse(view['complete'])

    def test_retired_requests_are_rejected_before_identity_or_aws_calls(self):
        with patch('portal_checker_handler.resolve_student') as resolve:
            for tid in ('P3', 'M3'):
                for mode in ('read_only', 'storage'):
                    event = {'subject': '123', 'operation': 'start', 'task_id': tid,
                             'job_id': '11111111-1111-4111-8111-111111111111', 'check_mode': mode}
                    self.assertEqual(serve(event, b'x'*32, Mock(), Mock(), Mock()), {'status': 'unauthorized'})
            resolve.assert_not_called()

    def test_runtime_matches_the_authoring_curriculum(self):
        p = json.loads((Path(__file__).resolve().parents[2] / 'course/curriculum.json').read_text())
        self.assertEqual(p['curriculum_id'], COURSE_ID)
        self.assertEqual(p['raw_maximum'], COURSE_MAXIMUM)
        self.assertEqual(set(p['active_order']), set(COURSE_TASKS))
        self.assertEqual(p['mission_points'], {t: TASKS[t]['raw_points_max'] for t in COURSE_MISSIONS})
        self.assertEqual(p['intro_points'] | p['mission_points'], COURSE_POINTS)

if __name__ == '__main__': unittest.main()
