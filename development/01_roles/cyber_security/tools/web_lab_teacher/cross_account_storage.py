"""Compare anonymous student report hashes with the separate teacher's database.

Export carries no token, credential file, report body, or dashboard URL. Teacher
verification uses existing IAM read access; no administrator credential is read.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

STUDENT = '965244652544'
TEACHER = '170126527713'
LAB = 'class193548-test1'
DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'
MANIFEST = 'a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2'
RELEASE = 'web-2026-10-r1'
ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}


def digest(value):
    def number(item):
        if isinstance(item, Decimal) and item == item.to_integral_value():
            return int(item)
        raise ValueError('Only integral database report numbers are supported')
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=number).encode()
    return hashlib.sha256(data).hexdigest()


def binding(value):
    if any(value.get(k) != v for k, v in dict(lab_id=LAB, deployment_id=DEPLOYMENT, release_id=RELEASE).items()):
        raise ValueError('Another Lab or deployment')


def summarize(report, ack):
    binding(report)
    rid = report['request_id']
    if str(uuid.UUID(rid, version=4)) != rid:
        raise ValueError('Expected original request UUID')
    if report['kind'] not in {'bootstrap', 'assessment'}:
        raise ValueError('Unsupported report kind')
    task = 'BOOTSTRAP' if report['kind'] == 'bootstrap' else report['mission_id']
    if task not in {'BOOTSTRAP', 'P1', 'M1'} or ack['exact_retry_same_receipt'] is not True:
        raise ValueError('Unsupported task or unverified retry')
    receipt = ack['receipt']; binding(receipt)
    if receipt['request_id'] != rid or receipt['ok'] is not True or receipt['stored'] is not True:
        raise ValueError('Receipt belongs to another report')
    if receipt['kind'] != report['kind']:
        raise ValueError('Receipt kind differs')
    stamp = datetime.fromisoformat(receipt['received_at'])
    if stamp.tzinfo is None:
        raise ValueError('Receipt timestamp unavailable')
    checks = report['checks']
    expected_count = 47 if task == 'BOOTSTRAP' else 10
    if len(checks) != expected_count:
        raise ValueError('Incomplete check set')
    seen = set()
    for check in checks:
        if (set(check) != {'id', 'role', 'instance_id', 'status'} or check['role'] not in ROLES
                or not re.fullmatch(r'[A-Z][A-Z0-9_-]{1,47}', check['id'])
                or not re.fullmatch(r'i-[0-9a-f]{17}', check['instance_id'])
                or check['status'] not in {'PASS', 'FAIL', 'UNKNOWN'}
                or (check['role'], check['id']) in seen):
            raise ValueError('Invalid or duplicated check')
        seen.add((check['role'], check['id']))
    return dict(request_id=rid, task=task, received_at=receipt['received_at'],
        report_sha256=digest(report), receipt_sha256=digest(receipt), checks=checks,
        passed=sum(c['status'] == 'PASS' for c in checks), total=len(checks),
        exact_retry_same_receipt=True)


def export(session, config_path):
    if session.client('sts').get_caller_identity()['Account'] != STUDENT:
        raise ValueError('Student account required')
    config = json.loads(config_path.read_text())
    state = json.loads(Path(config['state']).read_text()); binding(state)
    if state['account'] != STUDENT or state['manifest_sha256'] != MANIFEST:
        raise ValueError('Wrong student signed state')
    rows = []
    for path in Path(config['pending_directory']).glob('*.report.json'):
        ack_path = path.with_name(path.name.replace('.report.json', '.receipt.json'))
        if not ack_path.is_file():
            raise ValueError('Pending submission must be resolved first')
        rows.append(summarize(json.loads(path.read_text()), json.loads(ack_path.read_text())))
    if not rows:
        raise ValueError('No actual submissions')
    rows.sort(key=lambda row: row['received_at'])
    if len({r['request_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate request')
    return dict(scope='cross_account_anonymous_storage_expectations', lab_id=LAB,
        deployment_id=DEPLOYMENT, release_id=RELEASE, student_account=STUDENT,
        teacher_account=TEACHER, manifest_sha256=MANIFEST, reports=rows,
        exported_at=datetime.now(timezone.utc).isoformat(), credentials_exported=False, class_ready=False)


def verify_rows(expected, read):
    binding(expected)
    if (expected['scope'] != 'cross_account_anonymous_storage_expectations'
            or expected['teacher_account'] != TEACHER or expected['student_account'] != STUDENT
            or expected['manifest_sha256'] != MANIFEST or expected['credentials_exported'] is not False
            or not expected['reports']):
        raise ValueError('Wrong cross-account evidence')
    meta = read('META', ['lab_id', 'deployment_id', 'release_id', 'active', 'instances'])
    binding(meta)
    if meta['active'] is not True or set(meta['instances']) != ROLES:
        raise ValueError('Inactive or incomplete registration')
    latest = {}
    seen = set()
    for row in expected['reports']:
        rid = row['request_id']
        if rid in seen:
            raise ValueError('Duplicate expected request')
        seen.add(rid)
        stored = read('REQUEST#' + rid, ['report', 'receipt', 'body_sha256'])
        observed = summarize(stored['report'], {'receipt': stored['receipt'], 'exact_retry_same_receipt': True})
        if observed != row or stored['body_sha256'] != row['report_sha256']:
            raise ValueError('Teacher body or receipt differs')
        if any(meta['instances'][c['role']] != c['instance_id'] for c in row['checks']):
            raise ValueError('Check instance differs from actual registration')
        previous = latest.get(row['task'])
        if previous is None or row['received_at'] > previous['received_at']:
            latest[row['task']] = row
    for task, row in latest.items():
        saved = read('LATEST#' + task, ['request_id', 'checks', 'passed', 'total'])
        if any(saved[k] != row[k] for k in ('request_id', 'checks', 'passed', 'total')):
            raise ValueError('Latest task progress differs')
    return dict(scope='actual_cross_account_teacher_storage_verified', lab_id=LAB,
        deployment_id=DEPLOYMENT, release_id=RELEASE, teacher_account=TEACHER,
        student_account=STUDENT, report_count=len(seen), exact_bodies_and_receipts=True,
        exact_latest_task_progress=True, latest={k: {f: r[f] for f in ('request_id', 'passed', 'total')}
        for k, r in latest.items()}, checked_at=datetime.now(timezone.utc).isoformat(), class_ready=False)


def verify(session, expected):
    if session.client('sts').get_caller_identity()['Account'] != TEACHER:
        raise ValueError('Teacher account required')
    from boto3.dynamodb.types import TypeDeserializer
    stack = session.client('cloudformation').describe_stacks(StackName='jdu-web-progress-2026')['Stacks'][0]
    if stack['StackStatus'] not in {'CREATE_COMPLETE', 'UPDATE_COMPLETE'}:
        raise ValueError('Teacher stack unavailable')
    table = {i['OutputKey']: i['OutputValue'] for i in stack['Outputs']}['TableName']
    db = session.client('dynamodb'); decode = TypeDeserializer()
    def read(sk, fields):
        row = db.get_item(TableName=table, Key={'pk': {'S': 'LAB#' + LAB}, 'sk': {'S': sk}},
            ConsistentRead=True, ProjectionExpression=','.join('#f' + str(i) for i in range(len(fields))),
            ExpressionAttributeNames={'#f' + str(i): field for i, field in enumerate(fields)})['Item']
        return {k: decode.deserialize(v) for k, v in row.items()}
    return verify_rows(expected, read)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('student-export', 'teacher-verify'))
    parser.add_argument('--command-state', type=Path)
    parser.add_argument('--expectations', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); os.umask(0o077)
    if args.output.exists():
        raise ValueError('Existing evidence retained')
    import boto3
    session = boto3.Session(region_name='us-east-1')
    value = export(session, args.command_state) if args.operation == 'student-export' else verify(
        session, json.loads(args.expectations.read_text()))
    with args.output.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
    print('CROSS_ACCOUNT_STORAGE_' + args.operation.upper().replace('-', '_') + '_PASSED')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('CROSS_ACCOUNT_STORAGE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
