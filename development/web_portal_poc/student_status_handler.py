"""Student-account, read-only status Lambda; never accepts targets from callers.

The teacher's approved IAM role invokes this function. The deployed binding is
fixed in Lambda configuration and is checked against the actual AWS account,
CloudFormation resources and EC2 tags before any observations are returned.
No API here can start, stop, create or modify instances, or run a command.
"""
import os

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
    except Exception:
        # No raw event, credentials, private address or AWS error in logs.
        return {'status': 'unavailable'}


def handler(event, context):
    try:
        import boto3
        return serve(event, os.environ, *(boto3.client(name, region_name='us-east-1')
            for name in ('sts', 'cloudformation', 'ec2', 'ssm')))
    except Exception:
        return {'status': 'unavailable'}
