"""Trusted teacher CloudShell only; default is read-only assignment preview.

No public endpoint calls this. --apply records one teacher-approved school
email/Lab assignment without changing original grades. Email uses hidden TTY
input, not arguments, history, files or output. The original Lab supplies the
deployment, grading token hash and five existing instances.
"""
import argparse
import getpass
import json
import re
import sys

from portal_enrollment import PortalEnrollment, checked_grant


def original_grant(client, table, lab, account):
    from portal_enrollment import key, DESERIALIZER
    item = client.get_item(TableName=table, Key=key('LAB#'+lab, 'META'), ConsistentRead=True).get('Item')
    row = {k: DESERIALIZER.deserialize(v) for k, v in item.items()} if item else {}
    if row.get('active') is not True or row.get('lab_id')!=lab:
        raise ValueError('Original Lab unavailable')
    return checked_grant({'account':account, **{k:row.get(k) for k in ('lab_id','deployment_id','token_hash','instances')}})


def main():
    import boto3
    parser = argparse.ArgumentParser()
    for name in ('teacher-account','student-account','lab-id','grade-table','binding-table','subject-key-secret-arn'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if (not re.fullmatch(r'[0-9]{12}', args.teacher_account) or not re.fullmatch(r'[0-9]{12}', args.student_account)
            or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', args.lab_id)
            or args.grade_table == args.binding_table
            or not re.fullmatch(r'arn:aws:secretsmanager:us-east-1:'+args.teacher_account
                               +r':secret:jdu/web-portal/[a-z0-9-]+/subject-key-[A-Za-z0-9]{6}', args.subject_key_secret_arn)):
        raise ValueError('Invalid assignment configuration')
    if boto3.client('sts',region_name='us-east-1').get_caller_identity()['Account'] != args.teacher_account:
        raise ValueError('Wrong teacher AWS account')
    db = boto3.client('dynamodb', region_name='us-east-1')
    grant = original_grant(db, args.grade_table, args.lab_id, args.student_account)
    preview = {'mode':'apply' if args.apply else 'preview', 'lab_id':grant['lab_id'], 'account':grant['account'],
               'existing_instances':5, 'original_grade_writes':False, 'resources_created':False}
    if not args.apply:
        print(json.dumps(preview))
        return
    if not sys.stdin.isatty():
        raise ValueError('Hidden TTY entry required')
    email = getpass.getpass('Approved school Google email (hidden): ')
    value = boto3.client('secretsmanager',region_name='us-east-1').get_secret_value(
        SecretId=args.subject_key_secret_arn,VersionStage='AWSCURRENT').get('SecretString','')
    if not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('Invalid subject key')
    service = PortalEnrollment(db,args.binding_table,args.grade_table,bytes.fromhex(value))
    result = service.approve(email,grant)
    email = value = None
    print(json.dumps({**preview,**result}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Never expose email, secret, AWS error context or original records.
        print('APPROVAL_NOT_CONFIRMED',file=sys.stderr)
        raise SystemExit(1)
