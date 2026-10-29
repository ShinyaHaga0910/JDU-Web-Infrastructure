"""Student-account, read-only status Lambda; never accepts targets from callers.

The teacher's approved IAM role invokes this function. The deployed binding is
fixed in Lambda configuration and is checked against the actual AWS account,
CloudFormation resources and EC2 tags before any observations are returned.
No API here can start, stop, create or modify instances, or run a command.
"""
import os
import re

import status


def read_binding(env):
    """Build trusted configuration from the student's own deployment."""
    return {'account': env['STUDENT_ACCOUNT'], 'lab_id': env['LAB_ID'],
            'deployment_id': env['DEPLOYMENT_ID'], 'stack_id': env['STACK_ARN'],
            'nodes': {role: {'instance_id': env['INSTANCE_' + role.upper()]} for role in status.ROLES}}


def serve(event, env, sts, cloudformation, ec2, ssm):
    if type(event) is not dict or event != {'operation': 'status'}:
        return {'status': 'unauthorized'}
    try:
        binding = read_binding(env)
        observation = status.observe(sts, cloudformation, ec2, ssm, binding)
        return {'status': 'ok', 'observation': observation}
    except Exception as exc:
        # No raw event, credentials, private address or AWS error in logs.
        answer = {'status': 'unavailable'}
        response = getattr(exc, 'response', {})
        code = response.get('Error', {}).get('Code') if isinstance(response, dict) else None
        operation = getattr(exc, 'operation_name', None)
        if (isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9]{1,80}', code)
                and isinstance(operation, str) and re.fullmatch(r'[A-Za-z0-9]{1,80}', operation)):
            # Only the approved IAM caller receives these bounded names.
            # The public status gateway discards diagnostics entirely.
            answer['diagnostic'] = {'code': code, 'operation': operation}
        return answer


def handler(event, context):
    try:
        import boto3
        return serve(event, os.environ, *(boto3.client(name, region_name='us-east-1')
            for name in ('sts', 'cloudformation', 'ec2', 'ssm')))
    except Exception:
        return {'status': 'unavailable'}
