"""Prototype student-only projection using the existing D11 Python rules.

This is not a public endpoint or a browser login mechanism. The caller must
invoke it inside a secured teacher-side service with an existing lab token.
"""
import hmac

import progress_api as legacy
from grading import project_course_lab


def project_student(lab):
    """Apply the existing grading contract and return only student-safe fields."""
    projected = project_course_lab(lab)
    fields = ('raw_earned', 'raw_maximum', 'evaluable', 'complete', 'checked_at', 'received_at', 'unresolved')
    def compact(row):
        return {k: int(row[k]) if k in ('raw_earned', 'raw_maximum', 'unresolved') else row[k]
                for k in fields if k in row} if row else None
    return {k: projected[k] for k in ('lab_id', 'contract_id', 'raw_earned', 'raw_maximum',
            'fully_evaluated', 'complete', 'missing_or_unresolved', 'current_unresolved', 'curriculum_id')} | {
        'current': {k: compact(v) for k, v in projected['current'].items()},
        'selected': {k: compact(v) for k, v in projected['selected'].items()}}


def student_grade(service, event):
    body = legacy.parse_body(event)
    legacy.require_keys(body, ('lab_id',))
    authenticated = service.lab(event, body)
    labs = service.store.labs(authenticated['lab_id'])
    if len(labs) != 1:
        raise legacy.ApiError(503, 'grade unavailable')
    lab = labs[0]
    if (not lab.get('active') or lab.get('lab_id') != authenticated['lab_id']
            or lab.get('deployment_id') != authenticated.get('deployment_id')
            or not hmac.compare_digest(lab.get('token_hash', ''), authenticated['token_hash'])):
        raise legacy.ApiError(401, 'unauthorized')
    return project_student(lab)
