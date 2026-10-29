"""Read-only preparation for one student's status Lambda deployment.

Run inside that student's CloudShell. This reads the retained state and baseline
locally and verifies the AWS account, stack, five nodes and name collisions.
It does not create a resource, transfer secrets, or change existing servers.
"""
import argparse
import json
from pathlib import Path
import re

from botocore.exceptions import ClientError
import status


def _missing(call, expected_code):
    try:
        call()
    except ClientError as exc:
        if exc.response.get('Error', {}).get('Code') == expected_code:
            return True
        raise
    return False


def plan(state, baseline, expected_account, teacher_account, sts, cfn, ec2, ssm, lam):
    if (not isinstance(expected_account, str) or not re.fullmatch(r'[0-9]{12}', expected_account)
            or not isinstance(teacher_account, str) or not re.fullmatch(r'[0-9]{12}', teacher_account)
            or expected_account == teacher_account):
        raise ValueError('invalid account selection')
    if sts.get_caller_identity().get('Account') != expected_account:
        raise ValueError('wrong active AWS account')
    for field in ('account', 'lab_id', 'deployment_id', 'stack_id'):
        if not isinstance(state.get(field), str) or state[field] != baseline.get(field):
            raise ValueError('saved state and baseline differ')
    if state['account'] != expected_account:
        raise ValueError('saved state belongs to another account')
    binding = {k: baseline[k] for k in ('account', 'lab_id', 'deployment_id', 'stack_id', 'nodes')}
    observation = status.observe(sts, cfn, ec2, ssm, binding)
    function_name = 'jdu-web-status-' + state['lab_id']
    stack_name = 'jdu-web-portal-status-' + state['lab_id']
    if not _missing(lambda: lam.get_function(FunctionName=function_name), 'ResourceNotFoundException'):
        raise ValueError('status function name already exists; inspect before any change')
    try:
        cfn.describe_stacks(StackName=stack_name)
    except ClientError as exc:
        error = exc.response.get('Error', {})
        if error.get('Code') != 'ValidationError' or error.get('Message') != f'Stack with id {stack_name} does not exist':
            raise
    else:
        raise ValueError('status stack already exists; inspect before any change')
    return {'account': expected_account, 'lab_id': state['lab_id'], 'stack_name': stack_name,
            'function_arn': f'arn:aws:lambda:us-east-1:{expected_account}:function:{function_name}',
            'teacher_role': f'arn:aws:iam::{teacher_account}:role/LabRole',
            'nodes': [{'role': n['role'], 'ec2_state': n['ec2_state'], 'ssm_state': n['ssm_state']}
                      for n in observation['instances']],
            'action': 'plan-only; no AWS changes made'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--teacher-account', required=True)
    args = parser.parse_args()
    import boto3
    try:
        state = json.loads(args.state.read_text(encoding='utf-8'))
        baseline = json.loads(Path(str(args.state) + '.baseline.json').read_text(encoding='utf-8'))
        clients = [boto3.client(name, region_name='us-east-1') for name in ('sts', 'cloudformation', 'ec2', 'ssm', 'lambda')]
        print(json.dumps(plan(state, baseline, args.expected_account, args.teacher_account, *clients), ensure_ascii=False))
    except Exception:
        # Do not reveal private state, AWS credentials, or raw exception text.
        raise SystemExit('Plan could not be verified; no changes were made.') from None
