"""IAM-only Lambda adapter for the portal's already-verified student identity.

Do not attach a public Function URL, API Gateway route, or caller-supplied
identity authorizer to this function. The invoking service is responsible for
verifying the Google token and must be the only application principal allowed
to invoke it. Lambda logs must never include events or exceptions: the input
contains a Google subject, and the runtime fetches a secret pepper.
"""
import os
import re

import progress_api as legacy
from identity_grade import identity_grade
from status_gateway import student_status
from registry import COURSE_TASKS
from teacher_progress import read_teacher, valid as valid_teacher


def valid(event):
    return type(event) is dict and (set(event) == {'subject'} or
        (set(event) == {'subject', 'task_id'} and isinstance(event['task_id'], str) and event['task_id'] in COURSE_TASKS) or
        (set(event) == {'subject', 'operation'} and event['operation'] == 'status') or valid_teacher(event))


def serve(event, pepper, bindings, grades, student_lambda=None):
    """Accept only a subject from the trusted invoking service; fail closed."""
    if not valid(event):
        return {'status': 'unauthorized'}
    try:
        if event.get('operation', '').startswith('teacher_'):
            return {'status': 'ok', 'teacher': read_teacher(event, pepper, bindings, grades)}
        if event.get('operation') == 'status':
            if student_lambda is None:
                return {'status': 'unavailable'}
            return student_status(event['subject'], pepper, bindings, grades, student_lambda)
        result = identity_grade(event['subject'], pepper, bindings, grades, event.get('task_id'))
        return {'status': 'ok', 'grade': result}
    except legacy.ApiError as exc:
        return {'status': 'unauthorized' if exc.status == 401 else 'unavailable'}
    except Exception:
        return {'status': 'unavailable'}


def handler(event, context):
    """Resolve strongly consistent stores and a stable secret from AWS."""
    if not valid(event):
        return {'status': 'unauthorized'}
    try:
        import boto3
        from progress_api_v2 import AssessmentStore
        secret_arn = os.environ['PORTAL_SUBJECT_KEY_SECRET_ARN']
        if not re.fullmatch(r'arn:aws:secretsmanager:us-east-1:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]+', secret_arn):
            return {'status': 'unavailable'}
        secret = boto3.client('secretsmanager', region_name='us-east-1').get_secret_value(SecretId=secret_arn)
        encoded = secret.get('SecretString', '')
        if not isinstance(encoded, str) or not re.fullmatch(r'[a-f0-9]{64}', encoded):
            return {'status': 'unavailable'}
        pepper = bytes.fromhex(encoded)
        bindings = legacy.DynamoStore(os.environ['PORTAL_BINDING_TABLE'])
        grades = AssessmentStore(os.environ['GRADE_TABLE'])
        student_lambda = boto3.client('lambda', region_name='us-east-1') if event.get('operation') == 'status' else None
        return serve(event, pepper, bindings, grades, student_lambda)
    except Exception:
        # No input, secrets, AWS errors or stack traces in the response or log.
        return {'status': 'unavailable'}
