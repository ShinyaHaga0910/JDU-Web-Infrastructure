"""Private verified-owner checker gateway and canonical grade submission."""
import json
import os
import re

import progress_api as legacy
from identity_grade import resolve_student
from identity_keys import subject_key
from assessment_command_jobs import checked_spec, JobDenied
from registry import CONTRACT_SHA256, TASKS


def serve(event, pepper, bindings, grades, client, submissions=None):
    base={'subject','operation','task_id','job_id'}
    if (type(event) is not dict or not base<=set(event)
            or set(event)-base-{'check_mode','sealed_password'}
            or ('sealed_password' in event)!=(event.get('operation')=='functional_start')
            or event.get('check_mode','read_only') not in ('read_only','storage','functional')
            or event['operation'] not in ('start','advance','result','submit','functional_context','functional_start','storage_observe','storage_resume')
            or not isinstance(event['task_id'], str) or event['task_id'] not in TASKS):
        return {'status': 'unauthorized'}
    try:
        context, meta = resolve_student(event['subject'], pepper, bindings, grades)
        person = bindings.get(subject_key(event['subject'], pepper), 'BINDING')
        # Old synthetic bindings without a teacher approval never gain command
        # execution just because the read-only viewer can resolve them.
        if not person or not person.get('approval_pk'):
            return {'status': 'unauthorized'}
        mode=event.get('check_mode','read_only')
        if event['operation'].startswith('functional_') and mode!='functional' or event['operation'].startswith('storage_') and mode!='storage':
            return {'status':'unauthorized'}
        spec = checked_spec({'job_id': event['job_id'], 'run_id': event['job_id'],
            'owner_hash': subject_key(event['subject'], pepper).removeprefix('SUBJECT#'),
            'account': context['account'], 'lab_id': context['lab_id'],
            'deployment_id': meta['deployment_id'], 'release_id': meta['release_id'],
            'instances': meta['instances'], 'task_id': event['task_id'], 'contract_sha256': CONTRACT_SHA256,
            **({'check_mode':mode} if mode!='read_only' else {})})
        arn = f"arn:aws:lambda:us-east-1:{context['account']}:function:jdu-web-check-{context['lab_id']}"
        def invoke(operation):
            value = client.invoke(FunctionName=arn, InvocationType='RequestResponse',
                Payload=json.dumps({'operation': operation, 'spec': spec,
                    **({'sealed_password':event['sealed_password']} if operation=='functional_start' else {})}).encode())
            if value.get('FunctionError') or value.get('StatusCode') != 200:
                raise RuntimeError('Student checker unavailable')
            raw = value['Payload'].read(65537)
            if len(raw) > 65536:
                raise RuntimeError('Student checker response too large')
            return json.loads(raw)
        answer = invoke('result' if event['operation'] == 'submit' else event['operation'])
        # Recheck current ownership after the remote read/command operation.
        current, latest = resolve_student(event['subject'], pepper, bindings, grades)
        if current != context or any(latest.get(k) != meta.get(k) for k in ('instances', 'deployment_id', 'release_id', 'token_hash')):
            return {'status': 'unauthorized'}
        if answer.get('status') not in ('ok', 'busy', 'unavailable'):
            return {'status': 'unavailable'}
        if answer['status'] == 'ok' and (answer.get('job', {}).get('job_id') != spec['job_id']
                or answer.get('job', {}).get('task_id') != spec['task_id']):
            return {'status': 'unavailable'}
        if submissions is not None and answer['status'] == 'ok' and answer['job'].get('phase') == 'report_ready':
            answer['result'].pop('saved_grade_changed', None)
            try:
                if event['operation'] == 'result':
                    # GET only reads an existing receipt; never saves a grade.
                    saved = submissions.lookup(spec, meta, answer['result']['request_id'])
                else:
                    original = invoke('report')
                    if (original.get('status') != 'ok' or original.get('job', {}).get('job_id') != spec['job_id']
                            or original.get('report', {}).get('request_id') != answer['result']['request_id']):
                        raise ValueError('Original report unavailable')
                    saved = submissions.save(spec, meta, original['report'])
                answer['submission'] = saved
            except legacy.ApiError as exc:
                if exc.status == 401:
                    raise
                answer['submission'] = {'status': 'pending'}
            except Exception:
                answer['submission'] = {'status': 'pending'}
            # A write changes result metadata, never the authorized identity.
            final, _ = resolve_student(event['subject'], pepper, bindings, grades)
            if final != context:
                return {'status': 'unauthorized'}
        return answer
    except (legacy.ApiError, JobDenied, ValueError, TypeError, KeyError):
        return {'status': 'unauthorized'}
    except Exception:
        return {'status': 'unavailable'}


def handler(event, context):
    try:
        import boto3
        from progress_api_v2 import AssessmentStore
        from portal_submission import PortalSubmissions
        secret = boto3.client('secretsmanager', region_name='us-east-1').get_secret_value(
            SecretId=os.environ['PORTAL_SUBJECT_KEY_SECRET_ARN']).get('SecretString', '')
        if not re.fullmatch(r'[a-f0-9]{64}', secret):
            return {'status': 'unavailable'}
        bindings = legacy.DynamoStore(os.environ['PORTAL_BINDING_TABLE'])
        grades = AssessmentStore(os.environ['GRADE_TABLE'])
        return serve(event, bytes.fromhex(secret), bindings, grades,
            boto3.client('lambda', region_name='us-east-1'), PortalSubmissions(bindings, grades))
    except Exception:
        return {'status': 'unavailable'}
