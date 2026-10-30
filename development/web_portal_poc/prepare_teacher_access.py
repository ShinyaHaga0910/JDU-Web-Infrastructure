"""Teacher CloudShell only: plan one read-only, explicitly assigned teacher role.

The existing approved school identity supplies an email HMAC and optional
subject pin; no email, Google subject, key or password is copied. Planning is
read-only. Apply is a separate operator-approved transaction, never a Web route.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid

from portal_enrollment import DESERIALIZER, encoded, key
from teacher_progress import checked_assignment

ACCOUNT = '170126527713'


def get(db, table, pk, sk):
    row = db.get_item(TableName=table, Key=key(pk, sk), ConsistentRead=True).get('Item')
    return {k: DESERIALIZER.deserialize(v) for k, v in row.items()} if row else None


def condition(table, pk, sk, fields):
    return {'ConditionCheck': {'TableName': table, 'Key': key(pk, sk),
        'ConditionExpression': ' AND '.join(f'#f{i}=:v{i}' for i in range(len(fields))),
        'ExpressionAttributeNames': {f'#f{i}': name for i, name in enumerate(fields)},
        'ExpressionAttributeValues': encoded({f':v{i}': value for i, value in enumerate(fields.values())})}}


def plan(db, bindings, grades, source_lab, labs, class_id):
    if (bindings == grades or not re.fullmatch(r'[0-9]{1,12}', class_id)
            or not 1 <= len(labs) <= 50 or len(set(labs)) != len(labs)
            or any(not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', v) for v in [source_lab, *labs])):
        raise ValueError('Invalid teacher scope')
    mirror = get(db, bindings, 'LAB#' + source_lab, 'SUBJECT') or {}
    subject = mirror.get('subject_pk', '')
    if not re.fullmatch(r'SUBJECT#[a-f0-9]{64}', subject):
        raise ValueError('Existing verified teacher identity required')
    person = get(db, bindings, subject, 'BINDING') or {}
    approval_pk = person.get('approval_pk', '')
    if (person.get('active') is not True or person.get('lab_id') != source_lab
            or not re.fullmatch(r'APPROVAL#[a-f0-9]{64}', approval_pk)):
        raise ValueError('Existing approved teacher identity required')
    approval = get(db, bindings, approval_pk, 'LAB') or {}
    grant = approval.get('grant', {})
    source = get(db, grades, 'LAB#' + source_lab, 'META') or {}
    if (approval.get('active') is not True or approval.get('bound_subject') != subject
            or source.get('active') is not True or grant.get('lab_id') != source_lab
            or person.get('deployment_id') != source.get('deployment_id')
            or any(grant.get(k) != source.get(k) for k in ('lab_id', 'deployment_id', 'token_hash', 'instances'))):
        raise ValueError('Original teacher identity registration changed')
    guards = [condition(bindings, 'LAB#' + source_lab, 'SUBJECT', {'subject_pk': subject}),
        condition(bindings, subject, 'BINDING', {k: person[k] for k in ('active', 'lab_id', 'deployment_id', 'approval_pk', 'account', 'token_hash', 'connector')}),
        condition(bindings, approval_pk, 'LAB', {k: approval[k] for k in ('active', 'bound_subject', 'grant')})]
    assigned = []
    # A source Lab might also be assigned: one condition per item in a transaction.
    guarded = set()
    for lab in [source_lab, *sorted(labs)]:
        meta = get(db, grades, 'LAB#' + lab, 'META') or {}
        if (meta.get('active') is not True or meta.get('lab_id') != lab
                or meta.get('assessment_context') not in ('course', 'verification') or not meta.get('deployment_id')):
            raise ValueError('Accepted original Lab and grading context required')
        if lab not in guarded:
            names = ('active', 'lab_id', 'deployment_id', 'assessment_context') + (('token_hash', 'instances') if lab == source_lab else ())
            guards.append(condition(grades, 'LAB#' + lab, 'META', {k: meta[k] for k in names}))
            guarded.add(lab)
        if lab in labs:
            assigned.append({'lab_id': lab, 'deployment_id': meta['deployment_id'], 'context': meta['assessment_context']})
    # Deduplicate the source when it appears in the assigned list.
    assigned = sorted({r['lab_id']: r for r in assigned}.values(), key=lambda r: r['lab_id'])
    teacher_pk = approval_pk.replace('APPROVAL#', 'TEACHER#', 1)
    previous = get(db, bindings, teacher_pk, 'ACCESS')
    if previous:
        checked_assignment(previous)
        if not re.fullmatch(r'[a-f0-9-]{36}', previous.get('revision', '')):
            raise ValueError('Unversioned existing access; inspect before changing')
    revision = str(uuid.uuid4())
    row = {'pk': teacher_pk, 'sk': 'ACCESS', 'active': True, 'class_id': class_id, 'subject_pk': subject,
           'labs': assigned, 'revision': revision, 'updated_at': datetime.now(timezone.utc).isoformat()}
    checked_assignment(row)
    return {'account': ACCOUNT, 'binding_table': bindings, 'source_lab': source_lab, 'row': row,
            'previous': previous, 'guards': guards, 'request_id': revision}


def preview(value):
    return {'teacher_source_lab': value['source_lab'], 'class_id': value['row']['class_id'],
            'assigned_labs': value['row']['labs'], 'replaces_existing_access': value['previous'] is not None,
            'read_only_progress': True, 'original_grade_writes': False, 'new_resources': 0}


def apply(db, value):
    checked_assignment(value['row'])
    if value['account'] != ACCOUNT:
        raise ValueError('Wrong teacher context')
    write = {'TableName': value['binding_table'], 'Item': encoded(value['row']),
             'ConditionExpression': 'attribute_not_exists(pk)'}
    if value['previous'] is not None:
        expected = {k: v for k, v in value['previous'].items() if k not in ('pk', 'sk')}
        write.update(ConditionExpression=' AND '.join(f'#p{i}=:p{i}' for i in range(len(expected))),
            ExpressionAttributeNames={f'#p{i}': name for i, name in enumerate(expected)},
            ExpressionAttributeValues=encoded({f':p{i}': v for i, v in enumerate(expected.values())}))
    db.transact_write_items(TransactItems=[{'Put': write}, *value['guards']], ClientRequestToken=value['request_id'])
    if get(db, value['binding_table'], value['row']['pk'], 'ACCESS') != value['row']:
        raise ValueError('Access not confirmed')
    return {**preview(value), 'applied': True}


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        os.chmod(path, 0o600)
        json.dump(value, f, indent=2, default=int)


if __name__ == '__main__':
    import boto3
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('plan', 'apply'))
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--binding-table')
    parser.add_argument('--grade-table')
    parser.add_argument('--teacher-source-lab')
    parser.add_argument('--lab-id', action='append')
    parser.add_argument('--class-id')
    args = parser.parse_args()
    try:
        if boto3.client('sts', region_name='us-east-1').get_caller_identity()['Account'] != ACCOUNT:
            raise ValueError('Wrong teacher account')
        db = boto3.client('dynamodb', region_name='us-east-1')
        if args.mode == 'plan':
            value = plan(db, args.binding_table, args.grade_table, args.teacher_source_lab, args.lab_id, args.class_id)
            save(args.receipt, value)
            print('TEACHER_ACCESS_PLAN_READY', json.dumps(preview(value)))
        else:
            value = json.loads(args.receipt.read_text(encoding='utf-8'))
            requested = args.receipt.with_name('teacher-access.apply-requested.private.json')
            save(requested, {'request_id': value['request_id']})
            result = apply(db, value)
            save(args.receipt.with_name('teacher-access.applied.private.json'), result)
            print('TEACHER_ACCESS_APPLIED', json.dumps(result))
    except Exception:
        raise SystemExit('TEACHER_ACCESS_NOT_CONFIRMED: inspect receipts; never recreate blindly') from None
