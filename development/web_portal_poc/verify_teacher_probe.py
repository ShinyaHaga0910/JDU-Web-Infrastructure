"""Read-only CloudShell acceptance after an explicitly operated stop/End Lab.

The baseline file stays in teacher CloudShell and contains only an earlier
grade projection, whole-Lab partition digest and the private probe ARN. This
script never starts/stops instances, writes grades or prints private records.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from botocore.exceptions import ClientError


def verify(baseline, account, code_hash, teacher_instance, student_state, sts, lam, db, ec2):
    if (not re.fullmatch(r'[0-9]{12}', account) or not re.fullmatch(r'[a-f0-9]{64}', code_hash)
            or not re.fullmatch(r'i-[a-f0-9]{17}', teacher_instance)
            or student_state not in {'running', 'stopped'}):
        raise ValueError('invalid verification selection')
    if sts.get_caller_identity()['Account'] != account:
        raise ValueError('wrong active account')
    arn = baseline['function_arn']
    if not arn.startswith(f'arn:aws:lambda:us-east-1:{account}:function:'):
        raise ValueError('wrong probe account')
    config = lam.get_function_configuration(FunctionName=arn)
    if (config['Role'] != f'arn:aws:iam::{account}:role/LabRole'
            or config['Handler'] != 'teacher_probe_handler.handler'
            or base64.b64decode(config['CodeSha256']).hex() != code_hash):
        raise ValueError('probe code or role differs')
    try:
        lam.get_function_url_config(FunctionName=arn)
    except ClientError as exc:
        if exc.response['Error']['Code'] != 'ResourceNotFoundException':
            raise
    else:
        raise ValueError('probe must not have a public endpoint')
    env = config['Environment']['Variables']
    lab = env['LAB_ID']
    if baseline['grade']['lab_id'] != lab:
        raise ValueError('wrong baseline Lab')

    def fingerprint():
        rows = [row for page in db.get_paginator('query').paginate(TableName=env['GRADE_TABLE'],
            KeyConditionExpression='pk=:p', ExpressionAttributeValues={':p': {'S': 'LAB#' + lab}},
            ConsistentRead=True) for row in page.get('Items', [])]
        return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def teacher_state():
        return ec2.describe_instances(InstanceIds=[teacher_instance])['Reservations'][0]['Instances'][0]['State']['Name']

    def read(event):
        response = lam.invoke(FunctionName=arn, Payload=json.dumps(event).encode())
        if response.get('StatusCode') != 200 or response.get('FunctionError'):
            raise ValueError('probe failed')
        raw = response['Payload'].read(65537)
        if len(raw) > 65536:
            raise ValueError('oversized probe response')
        return json.loads(raw)

    if fingerprint() != baseline['partition_sha256'] or teacher_state() != 'stopped':
        raise ValueError('baseline changed or teacher EC2 is not stopped')
    grade, status = read({'operation': 'grade'}), read({'operation': 'status'})
    if grade.get('status') != 'ok' or grade.get('grade') != baseline['grade'] or status.get('status') != 'ok':
        raise ValueError('grade or status differs')
    nodes = status['observation']['instances']
    if len(nodes) != 5 or any(n['ec2_state'] != student_state for n in nodes):
        raise ValueError('student instances not in expected state')
    for event in ({'operation': 'start'}, {'operation': 'grade', 'lab_id': 'another-lab'}):
        if read(event) != {'status': 'unauthorized'}:
            raise ValueError('invalid request was accepted')
    if fingerprint() != baseline['partition_sha256'] or teacher_state() != 'stopped':
        raise ValueError('data or teacher state changed during read')
    return {'verified_at': datetime.now(timezone.utc).isoformat(), 'teacher_ec2': 'stopped',
        'grade': {'raw_earned': grade['grade']['raw_earned'], 'raw_maximum': grade['grade']['raw_maximum']},
        'full_grade_projection_unchanged': True, 'whole_lab_partition_unchanged': True,
        'no_probe_public_endpoint': True, 'invalid_requests_rejected': True,
        'student_nodes': [{k: n[k] for k in ('role', 'ec2_state', 'ssm_state')} for n in nodes]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--expected-code-sha256', required=True)
    parser.add_argument('--teacher-instance', required=True)
    parser.add_argument('--expected-student-state', required=True, choices=('running', 'stopped'))
    args = parser.parse_args()
    import boto3
    try:
        clients = [boto3.client(n, region_name='us-east-1') for n in ('sts', 'lambda', 'dynamodb', 'ec2')]
        result = verify(json.loads(args.baseline.read_text()), args.expected_account,
                        args.expected_code_sha256, args.teacher_instance, args.expected_student_state, *clients)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        raise SystemExit('Read-only acceptance did not pass; inspect account, probe, baseline and stopped states. No changes were made.') from None
