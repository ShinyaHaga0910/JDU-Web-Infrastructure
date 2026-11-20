import copy
import unittest

import test_grade_reader as fixture
from teacher_progress import read_teacher, teacher_key
from identity_keys import subject_key
from identity_grade_handler import serve


class Bindings:
    def __init__(self, pk, row):
        self.pk, self.row = pk, row

    def get(self, pk, sk):
        return copy.deepcopy(self.row) if (pk, sk) == (self.pk, 'ACCESS') else None


class Grades:
    def __init__(self, rows):
        self.rows, self.reads, self.hook = rows, [], None

    def get(self, pk, sk):
        return copy.deepcopy(self.rows.get(pk[4:])) if sk == 'META' else None

    def labs(self, lab):
        self.reads.append(lab)
        if self.hook:
            self.hook()
        return [copy.deepcopy(self.rows[lab])]


class TeacherProgressTest(unittest.TestCase):
    def setUp(self):
        source = fixture.GradeTest('test_saved_score_and_unknown_current_use_existing_projection')
        source.setUp()
        verification = dict(copy.deepcopy(source.row), assessment_context='verification')
        course = dict(copy.deepcopy(source.row), lab_id='course-student', assessment_context='course')
        other = dict(copy.deepcopy(course), lab_id='not-assigned')
        self.grades = Grades({'test-lab': verification, 'course-student': course, 'not-assigned': other})
        self.pepper = b'fictional-teacher-test-pepper-012345'
        self.subject, self.email = '1234567890', 'teacher@jdu.uz'
        self.grant = {'active': True, 'class_id': '193548', 'subject_pk': subject_key(self.subject, self.pepper),
                      'labs': [{'lab_id': r['lab_id'], 'deployment_id': r['deployment_id'], 'context': r['assessment_context']}
                               for r in (verification, course)]}
        self.bindings = Bindings(teacher_key(self.email, self.pepper), self.grant)

    def event(self, operation='teacher_list', **extra):
        base = dict(operation=operation, subject=self.subject, email=self.email)
        return {**base, **(dict(context='course', after='') if operation == 'teacher_list' else {}), **extra}

    def call(self, **extra):
        return read_teacher(self.event(**extra), self.pepper, self.bindings, self.grades)

    def test_course_and_verification_remain_separate_with_canonical_scores(self):
        result = self.call()
        self.assertEqual([r['lab_id'] for r in result['students']], ['course-student'])
        grade = result['students'][0]['grade']
        self.assertEqual((grade['raw_earned'], grade['selected']['M5']['raw_earned']), (59, 13))
        self.assertEqual(grade['current_unresolved'], ['M5'])
        self.assertEqual(self.grades.reads, ['course-student'])
        result = self.call(context='verification')
        self.assertEqual([r['lab_id'] for r in result['students']], ['test-lab'])
        self.assertNotIn('token_hash', repr(result))
        self.assertNotIn(self.email, repr(result))

    def test_school_email_or_student_binding_alone_is_not_a_teacher_role(self):
        for changes in ({'email': 'student@jdu.uz'}, {'subject': '99999999'}):
            result = serve(self.event(**changes), self.pepper, self.bindings, self.grades)
            self.assertEqual(result, {'status': 'unauthorized'})
        self.bindings.row['active'] = False
        self.assertEqual(serve(self.event(), self.pepper, self.bindings, self.grades), {'status': 'unauthorized'})
        self.assertEqual(self.grades.reads, [])

    def test_detail_and_cursors_cannot_read_an_unassigned_lab(self):
        for event in (self.event('teacher_detail', lab_id='not-assigned'), self.event(after='not-assigned')):
            self.assertEqual(serve(event, self.pepper, self.bindings, self.grades), {'status': 'unauthorized'})
        self.assertEqual(self.grades.reads, [])
        result = read_teacher(self.event('teacher_detail', lab_id='test-lab'), self.pepper, self.bindings, self.grades)
        self.assertEqual(result['student']['context'], 'verification')

    def test_revocation_during_read_prevents_return_of_the_page(self):
        self.grades.hook = lambda: self.grant.update(active=False)
        self.assertEqual(serve(self.event(), self.pepper, self.bindings, self.grades), {'status': 'unauthorized'})

    def test_unavailable_and_replaced_context_do_not_become_zero(self):
        self.grades.hook = lambda: self.grades.rows['course-student'].update(deployment_id='changed')
        row = self.call()['students'][0]
        self.assertEqual(row['status'], 'unavailable')
        self.assertNotIn('grade', row)
        self.grades.hook = None
        self.grades.rows['course-student']['deployment_id'] = 'same'
        self.grades.rows['course-student']['assessment_context'] = 'verification'
        self.assertNotIn('grade', self.call()['students'][0])

    def test_never_submitted_remains_missing_not_a_failing_grade(self):
        self.grades.rows['course-student']['results'] = []
        row = self.call()['students'][0]
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['grade']['selected'], {})
        self.assertEqual(row['grade']['missing_or_unresolved'], ['P0', 'M0', 'M1', 'M2', 'M4', 'M5', 'M6'])

    def test_pagination_is_fixed_to_permitted_labs(self):
        template = self.grades.rows['course-student']
        self.grant['labs'] = []
        for i in range(12):
            lab = f'course-{i:02}'
            self.grades.rows[lab] = dict(copy.deepcopy(template), lab_id=lab)
            self.grant['labs'].append(dict(lab_id=lab, deployment_id='same', context='course'))
        first = self.call()
        self.assertEqual(len(first['students']), 10)
        second = self.call(after=first['next_after'])
        self.assertEqual([r['lab_id'] for r in second['students']], ['course-10', 'course-11'])
        self.assertIsNone(second['next_after'])
        self.assertEqual(len(set(self.grades.reads)), 12)

    def test_read_only_protocol_rejects_self_declared_privileges_and_bad_context(self):
        for extra in ({'context': []}, {'role': 'teacher'}, {'account': '000000000000'}, {'operation': 'approve'}):
            self.assertEqual(serve(self.event(**extra), self.pepper, self.bindings, self.grades), {'status': 'unauthorized'})
        self.assertEqual(self.grades.reads, [])
        result = read_teacher(self.event('teacher_access'), self.pepper, self.bindings, self.grades)
        self.assertEqual(result, {'class_id': '193548'})


if __name__ == '__main__':
    unittest.main()
