"""Private IAM-only adapter. No teacher approval operation is exposed here.

begin/status claims come only from the portal's verified Google session.
complete transports a fresh signed STS request; never log events or exceptions.
Existing LabRole is broader than this application's intended operations.
"""
import os
import re

from identity_proof import ProofError
from portal_enrollment import PortalEnrollment, EnrollmentDenied
from portal_preparation import PortalPreparation

HEX = re.compile(r'[a-f0-9]{64}\Z')
IDENTITY = {'subject', 'email', 'session_id', 'token_hash'}


def valid(event):
    if type(event) is not dict:
        return False
    operation = event.get('operation')
    if isinstance(operation, str) and operation.startswith('prepare_'):
        # Explicit whitelist below still rejects approve/revoke/worker actions.
        operation = operation.removeprefix('prepare_')
        if operation not in ('begin', 'status', 'complete', 'confirm', 'plan', 'create','advance','registration_context','register'):
            return False
    if operation == 'complete':
        return (set(event) == {'operation', 'pair_id', 'proof_url'}
                and isinstance(event['pair_id'], str) and HEX.fullmatch(event['pair_id'])
                and isinstance(event['proof_url'], str) and len(event['proof_url']) <= 8192)
    extra = {'request_id'} if operation == 'begin' else {'plan_digest', 'password', 'confirmation'} if operation == 'create' else {'delivery'} if operation=='register' else set()
    if (operation not in ('begin', 'status', 'confirm', 'plan', 'create','advance','registration_context','register')
            or operation in ('confirm', 'plan', 'create','advance','registration_context','register') and event['operation'] != 'prepare_' + operation
            or set(event) != IDENTITY | {'operation'} | extra):
        return False
    if operation=='register' and event['delivery'] is not None:
        try:
            from initial_registration import checked_delivery
            checked_delivery(event['delivery'])
        except (EnrollmentDenied,ValueError):return False
    if operation == 'create' and (not isinstance(event['plan_digest'], str) or not HEX.fullmatch(event['plan_digest'])
            or any(not isinstance(event[k], str) or not 12 <= len(event[k]) <= 128 for k in ('password', 'confirmation'))):
        return False
    return (isinstance(event['subject'], str) and re.fullmatch(r'[0-9]{1,128}', event['subject'])
            and isinstance(event['email'], str) and event['email'].isascii()
            and re.fullmatch(r'[^@\s]{1,64}@jdu\.uz', event['email'], flags=re.I)
            and all(isinstance(event[k], str) and HEX.fullmatch(event[k])
                    for k in ('session_id', 'token_hash') + (('request_id',) if operation == 'begin' else ())))


def serve(event, service, preparation=None):
    if not valid(event):
        return {'status': 'unauthorized'}
    try:
        operation = event['operation']
        values = {k: v for k, v in event.items() if k != 'operation'}
        if operation.startswith('prepare_'):
            if preparation is None:
                return {'status': 'unavailable'}
            result = getattr(preparation, operation.removeprefix('prepare_'))(**values)
            return {'status': 'ok', 'preparation': result}
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
        from initial_gateway import InitialGateway
        from botocore.config import Config
        initial = InitialGateway(boto3.client('lambda', region_name='us-east-1', config=Config(
            connect_timeout=3, read_timeout=100, retries={'total_max_attempts':1})))
        return serve(event, service, PortalPreparation(service, initial))
    except Exception:
        return {'status': 'unavailable'}
