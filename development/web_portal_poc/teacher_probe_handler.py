"""Private IAM-only acceptance probe; never a student/browser API.

One teacher-approved test Lab is fixed in configuration. This checks the EC2-
independent grade projection and actual LabRole-to-LabRole status connection.
Google identity, enrollment and browser authorization are deliberately outside
this test, and must not be inferred from a successful result.
"""
import json
import os
import re

from grade_reader import project_student
from status_gateway import _sanitize, ROLES, INSTANCE


def serve(event, env, grades, student_lambda):
    if type(event) is not dict or event not in ({'operation': 'grade'}, {'operation': 'status'}):
        return {'status': 'unauthorized'}
    stage = 'resolve_lab'
    try:
        lab_id, account = env['LAB_ID'], env['STUDENT_ACCOUNT']
        deployment = env['DEPLOYMENT_ID']
        if (not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', lab_id)
                or not re.fullmatch(r'[0-9]{12}', account) or not deployment):
            raise ValueError('invalid test configuration')
        original = grades.get('LAB#' + lab_id, 'META')
        def matches(row):
            return (isinstance(row, dict) and row.get('active') is True
                    and row.get('lab_id') == lab_id and row.get('deployment_id') == deployment
                    and isinstance(row.get('token_hash'), str) and row.get('token_hash') == original.get('token_hash'))
        if not matches(original):
            raise ValueError('test Lab differs')
        if event['operation'] == 'grade':
            labs = grades.labs(lab_id)
            if len(labs) != 1 or not matches(labs[0]):
                raise ValueError('test grade differs')
            output = {'status': 'ok', 'grade': project_student(labs[0])}
        else:
            instances = original.get('instances')
            if (not isinstance(instances, dict) or set(instances) != ROLES
                    or any(not isinstance(i, str) or not INSTANCE.fullmatch(i) for i in instances.values())
                    or len(set(instances.values())) != 5):
                raise ValueError('invalid test instances')
            arn = f'arn:aws:lambda:us-east-1:{account}:function:jdu-web-status-{lab_id}'
            stage = 'student_invoke'
            response = student_lambda.invoke(FunctionName=arn, InvocationType='RequestResponse', Payload=b'{"operation":"status"}')
            stage = 'student_response'
            if response.get('StatusCode') != 200 or response.get('FunctionError'):
                raise ValueError('status call failed')
            raw = response['Payload'].read(65537)
            if len(raw) > 65536:
                raise ValueError('large status response')
            answer = json.loads(raw)
            if not isinstance(answer, dict) or answer.get('status') != 'ok':
                detail = answer.get('diagnostic') if isinstance(answer, dict) else None
                if isinstance(detail, dict) and set(detail) == {'code', 'operation'} and all(
                        isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9]{1,80}', v) for v in detail.values()):
                    return {'status': 'unavailable', 'diagnostic': {'stage': 'student_observation', **detail}}
                raise ValueError('status unavailable')
            output = {'status': 'ok', 'observation': _sanitize(answer.get('observation'),
                      {'account': account, 'lab_id': lab_id}, instances)}
        if grades.get('LAB#' + lab_id, 'META') != original:
            raise ValueError('test Lab changed during read')
        return output
    except Exception as exc:
        result = {'status': 'unavailable'}
        # This private IAM-only probe exposes bounded operation/error names,
        # never AWS messages, ARNs, credentials, input or original grade data.
        if event['operation'] == 'status':
            response = getattr(exc, 'response', {})
            code = response.get('Error', {}).get('Code') if isinstance(response, dict) else None
            result['diagnostic'] = {'stage': stage, 'code': code if isinstance(code, str)
                and re.fullmatch(r'[A-Za-z0-9]{1,80}', code) else 'Unspecified'}
        return result


def handler(event, context):
    try:
        import boto3
        from progress_api_v2 import AssessmentStore
        return serve(event, os.environ, AssessmentStore(os.environ['GRADE_TABLE']),
                     boto3.client('lambda', region_name='us-east-1'))
    except Exception:
        return {'status': 'unavailable'}
