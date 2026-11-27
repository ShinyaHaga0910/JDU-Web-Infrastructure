"""Current curriculum excludes retired tasks without deleting old signed rows."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
TOOLS = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
sys.path[:0] = [str(TOOLS / 'web_lab_assessment'), str(TOOLS / 'web_lab_teacher')]
from registry import (CONTRACT_SHA256, INTRO_CONTRACT_SHA256, M0_CONTRACT_SHA256, MISSIONS, TASKS, COURSE_ID, COURSE_TASKS,
                      COURSE_MISSIONS, COURSE_MAXIMUM, COURSE_POINTS, INTRO_MARKERS, HTTP_CONTRACT_SHA256)
from grading import grade_key, current_key, project_lab, project_course_lab
from portal_checker_handler import serve

class RetirementTest(unittest.TestCase):
    def full_history(self):
        lab = {'lab_id': 'synthetic-course', 'deployment_id': 'same', 'results': []}
        for mid in MISSIONS:
            row = {'contract_sha256': CONTRACT_SHA256, 'deployment_id': 'same',
                   'raw_earned': TASKS[mid]['raw_points_max'], 'evaluable': True, 'complete': True}
            lab['results'] += [dict(row, sk=grade_key(mid)), dict(row, sk=current_key(mid))]
        http = {'contract_sha256': HTTP_CONTRACT_SHA256, 'deployment_id': 'same',
                'raw_earned': 8, 'raw_maximum': 8, 'evaluable': True, 'complete': True}
        lab['results'] += [dict(http, sk=grade_key('M1', HTTP_CONTRACT_SHA256)),
                           dict(http, sk=current_key('M1', HTTP_CONTRACT_SHA256))]
        return lab

    def test_old_http_scores_remain_history_without_passing_the_new_rubric(self):
        lab = self.full_history()
        lab['results'] = [row for row in lab['results'] if row['contract_sha256'] != HTTP_CONTRACT_SHA256]
        before = copy.deepcopy(lab)
        view = project_course_lab(lab)
        self.assertEqual(view['raw_earned'], 51)
        self.assertNotIn('M1', view['selected'])
        self.assertIn('M1', view['missing_or_unresolved'])
        self.assertEqual(project_lab(lab)['raw_earned'], 62)
        self.assertEqual(lab, before)

    def add_connection_grades(self, lab, *, legacy=False):
        for task in INTRO_MARKERS:
            contract = M0_CONTRACT_SHA256 if task == 'M0' and not legacy else INTRO_CONTRACT_SHA256
            row = {'contract_sha256': contract, 'deployment_id': 'same',
                   'raw_earned': COURSE_POINTS[task] if not legacy else 1, 'evaluable': True, 'complete': True}
            lab['results'] += [dict(row, sk=grade_key(task, contract)), dict(row, sk=current_key(task, contract))]

    def add_practice_grades(self, lab):
        for task in ('P1', 'P2', 'P4', 'P5', 'P6'):
            contract = HTTP_CONTRACT_SHA256 if task == 'P1' else CONTRACT_SHA256
            row = {'contract_sha256': contract, 'deployment_id': 'same', 'raw_earned': COURSE_POINTS[task],
                   'raw_maximum': COURSE_POINTS[task], 'evaluable': True, 'complete': True}
            lab['results'] += [dict(row, sk=grade_key(task, contract)), dict(row, sk=current_key(task, contract))]

    def test_previous_m0_point_is_kept_until_the_four_servers_are_checked(self):
        lab = self.full_history()
        self.add_connection_grades(lab, legacy=True)
        before = copy.deepcopy(lab)
        view = project_course_lab(lab)
        self.assertEqual((view['raw_earned'], view['raw_maximum']), (61, 123))
        self.assertEqual(view['current_unresolved'], ['M0'])
        self.assertFalse(view['complete'])
        self.assertEqual(lab, before)
        self.add_connection_grades(lab)
        self.assertEqual(project_course_lab(lab)['raw_earned'], 64)

    def test_historical_full_score_is_59_in_current_course_without_row_changes(self):
        lab = self.full_history(); before = copy.deepcopy(lab)
        self.assertEqual(project_lab(lab)['raw_earned'], 62)
        view = project_course_lab(lab)
        self.assertEqual((view['raw_earned'], view['raw_maximum']), (59, 123))
        self.assertEqual(set(view['selected']), set(COURSE_MISSIONS))
        self.assertFalse(view['complete']); self.assertFalse(view['fully_evaluated'])
        self.assertEqual(view['missing_or_unresolved'], ['P0', 'M0', 'P1', 'P2', 'P4', 'P5', 'P6'])
        self.assertEqual(lab, before); self.assertNotIn('M3', view['current'])

    def test_missing_or_unknown_retired_task_never_blocks_completion(self):
        lab = self.full_history()
        self.add_connection_grades(lab)
        self.add_practice_grades(lab)
        lab['results'] = [r for r in lab['results'] if r['sk'] != grade_key('M3')]
        next(r for r in lab['results'] if r['sk'] == current_key('M3')).update(evaluable=False, complete=False)
        view = project_course_lab(lab)
        self.assertEqual(view['raw_earned'], 123)
        self.assertEqual(view['missing_or_unresolved'], [])
        self.assertEqual(view['current_unresolved'], []); self.assertTrue(view['complete'])

    def test_missing_active_task_still_blocks_completion(self):
        lab = self.full_history()
        self.add_connection_grades(lab)
        self.add_practice_grades(lab)
        lab['results'] = [r for r in lab['results'] if r['sk'] != grade_key('M4')]
        view = project_course_lab(lab)
        self.assertEqual(view['raw_earned'], 114)
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
        p = json.loads((Path(__file__).resolve().parents[2] / 'course/curriculum.json').read_text(encoding='utf-8'))
        self.assertEqual(p['curriculum_id'], COURSE_ID)
        self.assertEqual(p['raw_maximum'], COURSE_MAXIMUM)
        self.assertEqual(set(p['active_order']), set(COURSE_TASKS))
        self.assertEqual(p['mission_points'], {t: TASKS[t]['raw_points_max'] for t in COURSE_MISSIONS})
        self.assertEqual(p['intro_points'] | p['practice_points'] | p['mission_points'], COURSE_POINTS)

    def test_existing_p1_result_is_counted_without_regrading_or_mutating_history(self):
        lab = self.full_history()
        lab['results'] = [r for r in lab['results'] if r['sk'].endswith('#M1')]
        self.add_connection_grades(lab)
        practice = {'sk': current_key('P1', HTTP_CONTRACT_SHA256), 'contract_sha256': HTTP_CONTRACT_SHA256,
                    'deployment_id': 'same', 'raw_earned': 8, 'raw_maximum': 8, 'evaluable': True,
                    'counts_toward_assessment': False, 'complete': True}
        lab['results'].append(practice)
        before = copy.deepcopy(lab)
        view = project_course_lab(lab)
        self.assertEqual((view['raw_earned'], view['raw_maximum']), (21, 123))
        self.assertEqual(view['selected']['P1']['raw_earned'], 8)
        self.assertEqual(lab, before)
        # Unresolved and foreign-deployment observations never award points.
        lab['results'].append({**practice, 'sk': current_key('P2'), 'contract_sha256': CONTRACT_SHA256,
                               'raw_earned': 12, 'raw_maximum': 13, 'evaluable': False})
        lab['results'].append({**practice, 'sk': current_key('P4'), 'contract_sha256': CONTRACT_SHA256,
                               'raw_earned': 9, 'raw_maximum': 9, 'deployment_id': 'foreign'})
        self.assertEqual(project_course_lab(lab)['raw_earned'], 21)

if __name__ == '__main__': unittest.main()
