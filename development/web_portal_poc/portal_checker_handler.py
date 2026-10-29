"""Private teacher-side authorization for fixed student checks; no grade writes."""
import json
import os
import re

import progress_api as legacy
from identity_grade import resolve_student
from identity_keys import subject_key
from assessment_command_jobs import checked_spec, JobDenied
from registry import CONTRACT_SHA256, TASKS


def serve(event, pepper, bindings, grades, client):
    if (type(event) is not dict or set(event) != {'subject', 'operation', 'task_id', 'job_id'}
            or event['operation'] not in ('start', 'advance', 'result')
            or not isinstance(event['task_id'], str) or event['task_id'] not in TASKS):
        return {'status': 'unauthorized'}
    try:
        context, meta = resolve_student(event['subject'], pepper, bindings, grades)
        person = bindings.get(subject_key(event['subject'], pepper), 'BINDING')
        # Old synthetic bindings without a teacher approval never gain command
        # execution just because the read-only viewer can resolve them.
        if not person or not person.get('approval_pk'):
            return {'status': 'unauthorized'}
        spec = checked_spec({'job_id': event['job_id'], 'run_id': event['job_id'],
            'owner_hash': subject_key(event['subject'], pepper).removeprefix('SUBJECT#'),
            'account': context['account'], 'lab_id': context['lab_id'],
            'deployment_id': meta['deployment_id'], 'release_id': meta['release_id'],
            'instances': meta['instances'], 'task_id': event['task_id'], 'contract_sha256': CONTRACT_SHA256})
        arn = f"arn:aws:lambda:us-east-1:{context['account']}:function:jdu-web-check-{context['lab_id']}"
        value = client.invoke(FunctionName=arn, InvocationType='RequestResponse',
            Payload=json.dumps({'operation': event['operation'], 'spec': spec}).encode())
        if value.get('FunctionError') or value.get('StatusCode') != 200:
            return {'status': 'unavailable'}
        raw = value['Payload'].read(65537)
        if len(raw) > 65536:
            return {'status': 'unavailable'}
        answer = json.loads(raw)
        # Recheck current ownership after the remote read/command operation.
        current, latest = resolve_student(event['subject'], pepper, bindings, grades)
        if current != context or any(latest.get(k) != meta.get(k) for k in ('instances', 'deployment_id', 'release_id', 'token_hash')):
            return {'status': 'unauthorized'}
        if answer.get('status') not in ('ok', 'busy', 'unavailable'):
            return {'status': 'unavailable'}
        if answer['status'] == 'ok' and (answer.get('job', {}).get('job_id') != spec['job_id']
                or answer.get('job', {}).get('task_id') != spec['task_id']):
            return {'status': 'unavailable'}
        return answer
    except (legacy.ApiError, JobDenied, ValueError, TypeError, KeyError):
        return {'status': 'unauthorized'}
    except Exception:
        return {'status': 'unavailable'}


def handler(event, context):
    try:
        import boto3
        from progress_api_v2 import AssessmentStore
        secret = boto3.client('secretsmanager', region_name='us-east-1').get_secret_value(
            SecretId=os.environ['PORTAL_SUBJECT_KEY_SECRET_ARN']).get('SecretString', '')
        if not re.fullmatch(r'[a-f0-9]{64}', secret):
            return {'status': 'unavailable'}
        return serve(event, bytes.fromhex(secret), legacy.DynamoStore(os.environ['PORTAL_BINDING_TABLE']),
            AssessmentStore(os.environ['GRADE_TABLE']), boto3.client('lambda', region_name='us-east-1'))
    except Exception:
        return {'status': 'unavailable'}
