"""Read-only, fixed-fixture canonical audit; run only in teacher CloudShell.

The existing pinned checker validates its original reports. No email, Google
subject, password, token, private binding or full grade partition is exported.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from zipfile import ZipFile

import boto3
from boto3.dynamodb.types import TypeDeserializer

OLD, NEW = 'class193548-test1', 'class193548-retest1'
DEPLOYMENT = '1e757ad7-b719-49d6-be80-209c24df052f'
TABLE = 'jdu-web-progress-2026-ProgressTable-6D4AMSJ9A3U4'
BINDINGS = 'jdu-web-portal-binding-poc-20261027-BindingTable-2AGM7NTN5PWU'
EXPECTED = {
    'e605cdc4-edcb-4dcf-9d1c-5c4cc9629364': ('P1', 8, False),
    '388a2569-9cce-47c7-b5c3-09d32fc4a24d': ('M1', 3, True),
    'ac4c9f27-fb33-46f3-83f6-4721b095f701': ('M1', 8, True),
    '6a761aed-d181-4e01-9439-44100e5cb9ca': ('M0', 0, False),
}


def main():
    work = Path.home() / 'jdu-web-renewal-20261103-r3'
    assert boto3.client('sts').get_caller_identity()['Account'] == '170126527713'
    db = boto3.client('dynamodb', region_name='us-east-1')
    de = TypeDeserializer()

    def decode(row):
        return native({k: de.deserialize(v) for k, v in row.items()})

    def query(lab):
        args = dict(TableName=TABLE, KeyConditionExpression='pk=:p',
                    ExpressionAttributeValues={':p': {'S': 'LAB#' + lab}}, ConsistentRead=True)
        rows = []
        while True:
            answer = db.query(**args)
            rows += answer['Items']
            if not answer.get('LastEvaluatedKey'):
                return rows
            args['ExclusiveStartKey'] = answer['LastEvaluatedKey']

    def binding(pk, sk):
        row = db.get_item(TableName=BINDINGS, Key={'pk': {'S': pk}, 'sk': {'S': sk}},
                          ConsistentRead=True).get('Item')
        assert row
        return decode(row)

    before = (work / 'fresh-before-identity-old-grades.private.json').read_bytes()
    old_rows = query(OLD)
    old_raw = json.dumps(sorted(old_rows, key=lambda r: r['sk']['S']),
                         sort_keys=True, separators=(',', ':')).encode()
    assert old_raw == before and len(old_rows) == 84
    assert hashlib.sha256(old_raw).hexdigest() == 'e002a20219523e3e29314a6dd36cb0fc14f9f0267ed3e22de69e25b3e289642e'
    archive = work / 'fresh-checks.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '9c245021d6857304ac0f51ab202e439648cac1ebb4dc1b1e248b2b10d0f456e1'
    with tempfile.TemporaryDirectory() as directory:
        ZipFile(archive).extractall(directory)
        sys.path.insert(0, directory)
        from assessment_command_jobs import native
        from registry import CONTRACT_SHA256, MAXIMUM, score, validate_report
        from grading import current_key, grade_key
        import progress_api as legacy

        rows = {r['sk']['S']: decode(r) for r in query(NEW)}
        meta = rows['META']
        assert meta['lab_id'] == NEW and meta['deployment_id'] == DEPLOYMENT
        assert meta['active'] is True and meta['assessment_context'] == 'verification'
        attempts = [r for r in rows.values() if r.get('portal_job_id')]
        assert len(attempts) == 4 and {r['portal_job_id'] for r in attempts} == set(EXPECTED)
        accepted = []
        for row in attempts:
            report = row['report']
            validate_report(report, meta['instances'])
            task, earned, counts = EXPECTED[row['portal_job_id']]
            points = score(report)
            assert report['lab_id'] == NEW and report['deployment_id'] == DEPLOYMENT
            assert report['mission_id'] == task and points['raw_earned'] == earned
            assert points['counts_toward_assessment'] is counts and points['evaluable'] is True
            if task == 'M0':
                assert len(report['checks']) == 3 and all(c['status'] == 'PASS' for c in report['checks'])
            assert row['body_sha256'] == legacy.digest(legacy.encoded(report))
            assert row['receipt']['stored'] is True and row['receipt']['request_id'] == report['request_id']
            accepted.append({'job_id': row['portal_job_id'], 'task_id': task,
                'request_id': report['request_id'], 'report_sha256': row['body_sha256'],
                'received_at': row['received_at'], **points})
        selected = rows[grade_key('M1')]
        latest = rows[current_key('M1')]
        completed = next(r for r in attempts if r['portal_job_id'] == 'ac4c9f27-fb33-46f3-83f6-4721b095f701')
        assert selected['raw_earned'] == 8 and selected['request_id'] == completed['report']['request_id']
        assert latest['request_id'] == selected['request_id']
        assert {k for k in rows if k.startswith('GRADE#')} == {grade_key('M1')}
        assert sum(int(r['raw_earned']) for k, r in rows.items() if k.startswith('GRADE#')) == 8
        assert sum(int(decode(r)['raw_earned']) for r in old_rows
                   if r['sk']['S'].startswith('GRADE#' + CONTRACT_SHA256)) == 62

    mirror = binding('LAB#' + NEW, 'SUBJECT')
    person = binding(mirror['subject_pk'], 'BINDING')
    assert person['lab_id'] == NEW and person['account'] == '965244652544'
    assert person['deployment_id'] == DEPLOYMENT and person['token_hash'] == meta['token_hash']
    approval = binding(person['approval_pk'], 'LAB')
    assert approval['bound_subject'] == person['pk'] and approval['grant']['lab_id'] == NEW
    access = binding(person['approval_pk'].replace('APPROVAL#', 'TEACHER#', 1), 'ACCESS')
    assert {r['lab_id'] for r in access['labs']} == {OLD, NEW}
    assert all(r['context'] == 'verification' for r in access['labs'])
    result = {'verified_at': datetime.now(timezone.utc).isoformat(), 'lab_id': NEW,
        'original_grade_rows': 84, 'original_grade_bytes_unchanged': True,
        'original_raw_earned': 62, 'new_grade_rows': len(rows), 'new_raw_earned': 8,
        'raw_maximum': MAXIMUM, 'selected_latest_m1_matches': True,
        'practice_and_m0_grade_rows_absent': True, 'fresh_identity_bound': True,
        'teacher_old_and_new_verification_scope': True,
        'requests': sorted(accepted, key=lambda r: r['received_at'])}
    with (work / 'fresh-canonical.accepted.public.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print('FRESH_CANONICAL_ACCEPTED=' + json.dumps(result, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
