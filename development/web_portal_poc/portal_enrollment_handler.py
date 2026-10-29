"""Private IAM-only adapter. No teacher approval operation is exposed here.

begin/status claims come only from the portal's verified Google session.
complete transports a fresh signed STS request; never log events or exceptions.
Existing LabRole is broader than this application's intended operations.
"""
import os
import re

from identity_proof import ProofError
from portal_enrollment import PortalEnrollment, EnrollmentDenied

HEX = re.compile(r'[a-f0-9]{64}\Z')
IDENTITY = {'subject', 'email', 'session_id', 'token_hash'}


def valid(event):
    if type(event) is not dict:
        return False
    operation = event.get('operation')
    if operation == 'complete':
        return (set(event) == {'operation', 'pair_id', 'proof_url'}
                and isinstance(event['pair_id'], str) and HEX.fullmatch(event['pair_id'])
                and isinstance(event['proof_url'], str) and len(event['proof_url']) <= 8192)
    if operation not in ('begin', 'status') or set(event) != IDENTITY | {'operation'} | ({'request_id'} if operation == 'begin' else set()):
        return False
    return (isinstance(event['subject'], str) and re.fullmatch(r'[0-9]{1,128}', event['subject'])
            and isinstance(event['email'], str) and event['email'].isascii()
            and re.fullmatch(r'[^@\s]{1,64}@jdu\.uz', event['email'], flags=re.I)
            and all(isinstance(event[k], str) and HEX.fullmatch(event[k])
                    for k in ('session_id', 'token_hash') + (('request_id',) if operation == 'begin' else ())))


def serve(event, service):
    if not valid(event):
        return {'status': 'unauthorized'}
    try:
        operation = event['operation']
        values = {k: v for k, v in event.items() if k != 'operation'}
        if operation == 'complete':
            result = service.complete(values['pair_id'], values['proof_url'])
        else:
            result = getattr(service, operation)(**values)
        return {'status': 'ok', 'enrollment': result}
    except (EnrollmentDenied, ProofError, ValueError):
        return {'status': 'unauthorized'}
    except Exception:
        return {'status': 'unavailable'}


def handler(event, context):
    if not valid(event):
        return {'status': 'unauthorized'}
    try:
        import boto3
        account = os.environ['PORTAL_AWS_ACCOUNT_ID']
        arn = os.environ['PORTAL_SUBJECT_KEY_SECRET_ARN']
        if (not re.fullmatch(r'[0-9]{12}', account)
                or not re.fullmatch(r'arn:aws:secretsmanager:us-east-1:' + account
                                   + r':secret:jdu/web-portal/[a-z0-9-]+/subject-key-[A-Za-z0-9]{6}', arn)):
            return {'status': 'unavailable'}
        secret = boto3.client('secretsmanager', region_name='us-east-1').get_secret_value(SecretId=arn, VersionStage='AWSCURRENT')
        value = secret.get('SecretString', '')
        if not isinstance(value, str) or not HEX.fullmatch(value):
            return {'status': 'unavailable'}
        service = PortalEnrollment(boto3.client('dynamodb', region_name='us-east-1'),
            os.environ['PORTAL_BINDING_TABLE'], os.environ['GRADE_TABLE'], bytes.fromhex(value))
        return serve(event, service)
    except Exception:
        return {'status': 'unavailable'}
