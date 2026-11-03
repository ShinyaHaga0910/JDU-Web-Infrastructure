"""CloudShell-only reassignment of the explicitly approved Class193548 fixture.

No public reset route and no grade writes. The old verified school identity is
reused without exporting its email, subject, HMAC or credentials. Plan/backup
stay in the teacher CloudShell. Apply conditionally replaces only the fixture's
four binding rows, approval and teacher read scope; original grade history stays.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

TEACHER = '170126527713'
STUDENT = '965244652544'
OLD = 'class193548-test1'
NEW = 'class193548-retest1'
OLD_DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'
NEW_DEPLOYMENT = '1e757ad7-b719-49d6-be80-209c24df052f'
BINDINGS = 'jdu-web-portal-binding-poc-20261027-BindingTable-2AGM7NTN5PWU'
GRADES = 'jdu-web-progress-2026-ProgressTable-6D4AMSJ9A3U4'
SER, DES = TypeSerializer(), TypeDeserializer()


def encoded(row):
    return {k: SER.serialize(v) for k, v in row.items()}


def get(db, table, pk, sk):
    item = db.get_item(TableName=table, Key=encoded({'pk': pk, 'sk': sk}),
                       ConsistentRead=True).get('Item')
    return {k: DES.deserialize(v) for k, v in item.items()} if item else None


def guard(row):
    expected = {k: v for k, v in row.items() if k not in ('pk', 'sk')}
    if not expected:
        raise ValueError('Complete original row required')
    return {'ConditionExpression': ' AND '.join(f'#f{i}=:v{i}' for i in range(len(expected))),
            'ExpressionAttributeNames': {f'#f{i}': k for i, k in enumerate(expected)},
            'ExpressionAttributeValues': encoded({f':v{i}': v for i, v in enumerate(expected.values())})}


def plan(db, now=None):
    import hashlib
    import re
    now = int(time.time()) if now is None else now
    old = get(db, GRADES, 'LAB#' + OLD, 'META') or {}
    new = get(db, GRADES, 'LAB#' + NEW, 'META') or {}
    for meta, lab, deployment in ((old, OLD, OLD_DEPLOYMENT), (new, NEW, NEW_DEPLOYMENT)):
        nodes = meta.get('instances', {})
        if (meta.get('active') is not True or meta.get('lab_id') != lab
                or meta.get('deployment_id') != deployment or meta.get('assessment_context') != 'verification'
                or set(nodes) != {'bastion', 'web', 'dns', 'db', 'repo'}
                or len(set(nodes.values())) != 5
                or any(not re.fullmatch(r'i-[a-f0-9]{17}', v) for v in nodes.values())
                or not re.fullmatch(r'[a-f0-9]{64}', meta.get('token_hash', ''))):
            raise ValueError('Registered verification fixture differs')
    if set(old['instances'].values()) & set(new['instances'].values()):
        raise ValueError('Fresh instances required')
    mirror = get(db, BINDINGS, 'LAB#' + OLD, 'SUBJECT') or {}
    subject = mirror.get('subject_pk', '')
    if not re.fullmatch(r'SUBJECT#[a-f0-9]{64}', subject):
        raise ValueError('Old verified subject required')
    person = get(db, BINDINGS, subject, 'BINDING') or {}
    approval_pk = person.get('approval_pk', '')
    if not re.fullmatch(r'APPROVAL#[a-f0-9]{64}', approval_pk):
        raise ValueError('Old verified approval required')
    approval = get(db, BINDINGS, approval_pk, 'LAB') or {}
    old_grant = {'account': STUDENT, **{k: old[k] for k in ('lab_id', 'deployment_id', 'token_hash', 'instances')}}
    if (approval.get('active') is not True or approval.get('bound_subject') != subject
            or approval.get('grant') != old_grant):
        raise ValueError('Old approved fixture changed')
    rows = [mirror, person]
    for pk in ('LAB#' + OLD, 'ACCOUNT#' + STUDENT):
        rows.append(get(db, BINDINGS, pk, 'BINDING') or {})
    if person.get('active') is not True or person.get('token_hash') != old['token_hash']:
        raise ValueError('Old verified person changed')
    connector = hashlib.sha256(f'arn:aws:lambda:us-east-1:{STUDENT}:function:jdu-web-status-{OLD}'.encode('ascii')).hexdigest()
    for row in rows[1:]:
        if (row.get('account') != STUDENT or row.get('connector') != connector
                or row.get('lab_id') != OLD or row.get('deployment_id') != OLD_DEPLOYMENT):
            raise ValueError('Old identity/account mirrors differ')
    if get(db, BINDINGS, 'LAB#' + NEW, 'BINDING') or get(db, BINDINGS, 'LAB#' + NEW, 'SUBJECT'):
        raise ValueError('Fresh Lab is already bound')
    teacher_pk = approval_pk.replace('APPROVAL#', 'TEACHER#', 1)
    access = get(db, BINDINGS, teacher_pk, 'ACCESS') or {}
    old_access = [{'lab_id': OLD, 'deployment_id': OLD_DEPLOYMENT, 'context': 'verification'}]
    if (access.get('active') is not True or access.get('class_id') != '193548'
            or access.get('subject_pk') != subject or access.get('labs') != old_access):
        raise ValueError('Teacher fixture scope differs')
    grant = {'account': STUDENT, **{k: new[k] for k in ('lab_id', 'deployment_id', 'token_hash', 'instances')}}
    replacement = {'pk': approval_pk, 'sk': 'LAB', 'active': True, 'grant': grant,
                   'grant_digest': hashlib.sha256(json.dumps(grant, sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest(),
                   'enrollment_deadline': now + 604800, 'created_at': now}
    new_access = {**access, 'labs': old_access + [{'lab_id': NEW, 'deployment_id': NEW_DEPLOYMENT, 'context': 'verification'}],
                  'revision': str(uuid.uuid4()), 'updated_at': datetime.fromtimestamp(now, timezone.utc).isoformat()}
    transactions = [{'Delete': {'TableName': BINDINGS,
        'Key': encoded({k: row[k] for k in ('pk', 'sk')}), **guard(row)}} for row in rows]
    transactions += [{'Put': {'TableName': BINDINGS, 'Item': encoded(value), **guard(previous)}}
                     for value, previous in ((replacement, approval), (new_access, access))]
    transactions += [{'ConditionCheck': {'TableName': GRADES,
        'Key': encoded({k: meta[k] for k in ('pk', 'sk')}), **guard(meta)}} for meta in (old, new)]
    return {'teacher_account': TEACHER, 'request_id': str(uuid.uuid4()), 'created_at': now,
            'backup': {'bindings': rows + [approval, access], 'grade_meta_read_only': [old, new]},
            'transactions': transactions, 'new_approval': replacement, 'new_access': new_access}


def apply(db, value, now=None):
    now = int(time.time()) if now is None else now
    if value['teacher_account'] != TEACHER or not 0 <= now - value['created_at'] <= 3600:
        raise ValueError('Fresh teacher plan required')
    db.transact_write_items(TransactItems=value['transactions'], ClientRequestToken=value['request_id'])
    for row in (value['new_approval'], value['new_access']):
        if get(db, BINDINGS, row['pk'], row['sk']) != row:
            raise ValueError('Inspect reassignment receipt before retry')
    return {'scope': 'approved_verification_identity_reassignment', 'old_lab': OLD, 'new_lab': NEW,
            'original_grade_writes': False, 'old_teacher_history_retained': True,
            'new_browser_enrollment_required': True, 'applied': True}


def save(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, default=int)


if __name__ == '__main__':
    import boto3
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'apply'))
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    try:
        assert boto3.client('sts').get_caller_identity()['Account'] == TEACHER
        db = boto3.client('dynamodb', region_name='us-east-1')
        if args.mode == 'plan':
            value = plan(db)
            save(args.receipt, value)
            print('VERIFICATION_REASSIGNMENT_PLAN_READY; private backup saved; no change applied', flush=True)
        else:
            value = json.loads(args.receipt.read_text(encoding='utf-8'))
            save(args.receipt.with_name('reassignment-requested.private.json'), {'request_id': value['request_id']})
            result = apply(db, value)
            save(args.receipt.with_name('reassignment.accepted.public.json'), result)
            print('VERIFICATION_REASSIGNMENT_COMPLETE=' + json.dumps(result), flush=True)
    except Exception as exc:
        raise SystemExit('VERIFICATION_REASSIGNMENT_NOT_CONFIRMED=' + type(exc).__name__ + '; inspect private receipt') from None
