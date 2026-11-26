"""Read-only teacher view of an operator-assigned set of anonymous Labs.

Google claims come only from the trusted portal. A verified school domain alone
never grants a teacher role. No table scan, student token, EC2 call or grade
write is used. Verification Labs remain separate from course grades.
"""
import hashlib
import hmac
import re

import progress_api as legacy
from grade_reader import project_student
from registry import COURSE_GRADED_TASKS
from identity_keys import subject_key

CONTEXTS = {'course', 'verification'}
PAGE_SIZE = 10


def teacher_key(email, pepper):
    if (not isinstance(email, str) or not email.isascii()
            or not re.fullmatch(r'[^@\s]{1,64}@jdu\.uz', email, re.I)
            or not isinstance(pepper, bytes) or len(pepper) < 32):
        raise ValueError('Invalid verified teacher identity')
    # Same HMAC email identity as existing approval; a separate ACCESS row.
    return 'TEACHER#' + hmac.new(pepper, b'email-v1\0' + email.casefold().encode('ascii'), hashlib.sha256).hexdigest()


def checked_assignment(row):
    if (not isinstance(row, dict) or row.get('active') is not True
            or not isinstance(row.get('class_id'), str) or not re.fullmatch(r'[0-9]{1,12}', row['class_id'])
            or type(row.get('labs')) is not list or not 1 <= len(row['labs']) <= 100):
        raise legacy.ApiError(401, 'unauthorized')
    seen = set()
    for lab in row['labs']:
        if (type(lab) is not dict or set(lab) != {'lab_id', 'deployment_id', 'context'}
                or not isinstance(lab['lab_id'], str) or not legacy.LAB_RE.fullmatch(lab['lab_id'])
                or not isinstance(lab['deployment_id'], str) or not 1 <= len(lab['deployment_id']) <= 64
                or lab['context'] not in CONTEXTS or lab['lab_id'] in seen):
            raise legacy.ApiError(401, 'unauthorized')
        seen.add(lab['lab_id'])
    return row


def classroom_assignment(scope, lab_id, grades):
    meta = grades.get('LAB#' + lab_id, 'META')
    if (not meta or meta.get('active') is not True or meta.get('lab_id') != lab_id
            or meta.get('classroom_scope') != scope or not meta.get('deployment_id')
            or meta.get('assessment_context', 'course') not in CONTEXTS):
        return None
    return {'lab_id': lab_id, 'deployment_id': meta['deployment_id'],
            'context': meta.get('assessment_context', 'course')}


def valid(event):
    if type(event) is not dict:
        return False
    op = event.get('operation')
    fields = {'operation', 'subject', 'email'}
    if op == 'teacher_list':
        fields |= {'context', 'after'}
    elif op == 'teacher_detail':
        fields |= {'lab_id'}
        if 'task_id' in event:
            if not isinstance(event['task_id'], str) or event['task_id'] not in COURSE_GRADED_TASKS:
                return False
            fields.add('task_id')
    elif op != 'teacher_access':
        return False
    return (set(event) == fields and isinstance(event['subject'], str)
            and re.fullmatch(r'[0-9]{1,128}', event['subject'])
            and isinstance(event['email'], str) and event['email'].isascii()
            and re.fullmatch(r'[^@\s]{1,64}@jdu\.uz', event['email'], re.I)
            and (op != 'teacher_list' or (isinstance(event['context'], str) and event['context'] in CONTEXTS and isinstance(event['after'], str)
                 and (event['after'] == '' or legacy.LAB_RE.fullmatch(event['after']))))
            and (op != 'teacher_detail' or (isinstance(event['lab_id'], str) and legacy.LAB_RE.fullmatch(event['lab_id']))))


def read_teacher(event, pepper, bindings, grades):
    if not valid(event):
        raise legacy.ApiError(401, 'unauthorized')
    pk = teacher_key(event['email'], pepper)
    key = 'CLASSROOM_ACCESS'
    row = bindings.get(pk, key)
    if row is None:
        key = 'ACCESS'
        row = checked_assignment(bindings.get(pk, key))
        scope = None
        label = {'class_id': row['class_id']}
    else:
        scope = row.get('classroom_scope')
        if row.get('active') is not True or not isinstance(scope, str) or not re.fullmatch(r'[a-f0-9]{64}', scope):
            raise legacy.ApiError(401, 'unauthorized')
        label = {'classroom': True}
    # Optional subject pin is set by the existing-bound-identity operator path.
    # A generic teacher email grant still requires the verified Google email.
    if row.get('subject_pk') is not None and row['subject_pk'] != subject_key(event['subject'], pepper):
        raise legacy.ApiError(401, 'unauthorized')

    def finish(value):
        if bindings.get(pk, key) != row:
            raise legacy.ApiError(401, 'unauthorized')
        return value

    if event['operation'] == 'teacher_access':
        return finish(label)

    def project(assigned):
        lab_id = assigned['lab_id']
        base = {'lab_id': lab_id, 'context': assigned['context'], 'status': 'unavailable'}
        try:
            meta = grades.get('LAB#' + lab_id, 'META')
            if (not meta or meta.get('active') is not True or any(meta.get(k) != v for k, v in
                    [('lab_id', lab_id), ('deployment_id', assigned['deployment_id'])])
                    or meta.get('assessment_context', 'course') != assigned['context']
                    or (scope and meta.get('classroom_scope') != scope)):
                return base
            values = grades.labs(lab_id)  # Always a named permitted Lab, never a scan.
            if (len(values) != 1 or values[0].get('active') is not True
                    or any(values[0].get(k) != meta.get(k)
                           for k in ('lab_id', 'deployment_id', 'assessment_context', 'classroom_scope'))):
                return base
            grade = project_student(values[0], event.get('task_id'))
            current = grades.get('LAB#' + lab_id, 'META')
            if not current or current.get('active') is not True or any(current.get(k) != meta.get(k)
                    for k in ('lab_id', 'deployment_id', 'assessment_context', 'classroom_scope')):
                return base
            return {**base, 'status': 'ok', 'grade': grade}
        except Exception:
            return base  # Unavailable is not an invented zero or missing submission.

    if scope:
        if event['operation'] == 'teacher_detail':
            selected = classroom_assignment(scope, event['lab_id'], grades)
            if selected is None:
                raise legacy.ApiError(401, 'unauthorized')
            return finish({**label, 'student': project(selected)})
        page = []
        for lab_id in grades.classroom_members(scope, event['after']):
            selected = classroom_assignment(scope, lab_id, grades)
            if selected and selected['context'] == event['context']:
                page.append(selected)
                if len(page) > PAGE_SIZE:
                    break
        return finish({**label, 'context': event['context'],
                       'students': [project(r) for r in page[:PAGE_SIZE]],
                       'next_after': page[PAGE_SIZE - 1]['lab_id'] if len(page) > PAGE_SIZE else None})

    assigned = sorted(row['labs'], key=lambda r: r['lab_id'])
    if event['operation'] == 'teacher_detail':
        selected = next((r for r in assigned if r['lab_id'] == event['lab_id']), None)
        if selected is None:
            raise legacy.ApiError(401, 'unauthorized')
        return finish({**label, 'student': project(selected)})
    selected = [r for r in assigned if r['context'] == event['context']]
    after = event['after']
    if after and after not in {r['lab_id'] for r in selected}:
        raise legacy.ApiError(401, 'unauthorized')
    remaining = [r for r in selected if r['lab_id'] > after]
    page = remaining[:PAGE_SIZE]
    return finish({**label, 'context': event['context'],
                   'students': [project(r) for r in page],
                   'next_after': page[-1]['lab_id'] if len(remaining) > PAGE_SIZE else None})
