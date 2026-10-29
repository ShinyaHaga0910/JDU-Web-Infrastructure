"""Teacher-side read-only invocation of a registered student's status Lambda.

The caller must provide a verified portal identity, not browser-supplied
targets. CONNECTOR records are trusted teacher-side configuration; this module
does not create or authorize them. The student's function is still separately
responsible for validating its own CloudFormation stack and EC2 tags.
"""
from datetime import datetime
import hashlib
import ipaddress
import json
import re

import progress_api as legacy
from identity_grade import resolve_student

ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}
INSTANCE = re.compile(r'i-[0-9a-f]{17}\Z')
STATES = {'pending', 'running', 'shutting-down', 'terminated', 'stopping', 'stopped', 'unknown'}
SSM = {'Online', 'ConnectionLost', 'Inactive', 'unknown'}


def _timestamp(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('invalid timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp without zone')
    return value


def _address(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('invalid address')
    return str(ipaddress.ip_address(value))


def _sanitize(answer, context, instances):
    if (not isinstance(answer, dict) or answer.get('account') != context['account']
            or answer.get('lab_id') != context['lab_id'] or not isinstance(answer.get('instances'), list)
            or len(answer['instances']) != 5):
        raise ValueError('invalid observation')
    stamp = _timestamp(answer.get('observed_at'))
    if stamp is None:
        raise ValueError('missing observation time')
    stack = answer.get('stack_status')
    if not isinstance(stack, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,64}', stack):
        raise ValueError('invalid stack status')
    clean, seen = [], set()
    for row in answer['instances']:
        if not isinstance(row, dict):
            raise ValueError('invalid instance')
        role, instance_id = row.get('role'), row.get('instance_id')
        if (role not in ROLES or role in seen or instance_id != instances.get(role)
                or row.get('ec2_state') not in STATES or row.get('ssm_state') not in SSM):
            raise ValueError('instance mismatch')
        seen.add(role)
        clean.append({'role': role, 'instance_id': instance_id, 'ec2_state': row['ec2_state'],
            'ssm_state': row['ssm_state'], 'ssm_last_ping': _timestamp(row.get('ssm_last_ping')),
            'public_ip': _address(row.get('public_ip')), 'private_ip': _address(row.get('private_ip'))})
    if seen != ROLES:
        raise ValueError('incomplete observation')
    return {'lab_id': context['lab_id'], 'observed_at': stamp, 'stack_status': stack, 'instances': clean}


def student_status(verified_subject, pepper, bindings, grade_store, lambda_client):
    """Return only a verified student's registered five-node observation."""
    try:
        context, lab = resolve_student(verified_subject, pepper, bindings, grade_store)
        instances = lab.get('instances')
        if (not isinstance(instances, dict) or set(instances) != ROLES
                or any(not isinstance(v, str) or not INSTANCE.fullmatch(v) for v in instances.values())
                or len(set(instances.values())) != 5):
            raise ValueError('invalid retained instances')
        connector = bindings.get('CONNECTOR#' + context['connector'], 'META')
        expected_arn = f"arn:aws:lambda:us-east-1:{context['account']}:function:jdu-web-status-{context['lab_id']}"
        if (not isinstance(connector, dict) or connector.get('active') is not True
                or connector.get('arn') != expected_arn or connector.get('account') != context['account']
                or connector.get('lab_id') != context['lab_id'] or connector.get('deployment_id') != context['deployment_id']
                or hashlib.sha256(expected_arn.encode('ascii')).hexdigest() != context['connector']):
            raise ValueError('untrusted connector')
        result = lambda_client.invoke(FunctionName=expected_arn, InvocationType='RequestResponse',
                                      Payload=b'{"operation":"status"}')
        if result.get('StatusCode') != 200 or result.get('FunctionError') or 'Payload' not in result:
            raise ValueError('connector unavailable')
        raw = result['Payload'].read(65537)
        if len(raw) > 65536:
            raise ValueError('response too large')
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get('status') != 'ok':
            raise ValueError('connector unavailable')
        clean = _sanitize(value.get('observation'), context, instances)
        # Check that identity and registered connector were not revoked while
        # the remote function was running before returning its response.
        again, latest = resolve_student(verified_subject, pepper, bindings, grade_store)
        if again != context or latest.get('instances') != instances or bindings.get('CONNECTOR#' + context['connector'], 'META') != connector:
            raise ValueError('binding changed')
        return {'status': 'ok', 'observation': clean}
    except legacy.ApiError as exc:
        return {'status': 'unauthorized' if exc.status == 401 else 'unavailable'}
    except Exception:
        return {'status': 'unavailable'}
