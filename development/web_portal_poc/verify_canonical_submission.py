"""CloudShell read-only acceptance against the private pre-update Lab backup.

Prints only technical result IDs/counts and scores. Original records and identity
metadata stay in the teacher account; this never changes any grade or binding.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
from zipfile import ZipFile


def verify(backup, code, jobs):
    import boto3
    session=boto3.session.Session(region_name='us-east-1')
    if session.client('sts').get_caller_identity()['Account']!='170126527713':
        raise ValueError('Wrong teacher account')
    saved=json.loads(backup.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as directory:
        ZipFile(code).extractall(directory)
        sys.path.insert(0,directory)
        from assessment_command_jobs import native
        from boto3.dynamodb.types import TypeDeserializer
        from registry import validate_report,score,CONTRACT_SHA256,MAXIMUM
        from grading import current_key,grade_key
        import progress_api as legacy
        de=TypeDeserializer()
        def decode(row):return native({k:de.deserialize(v) for k,v in row.items()})
        before={decode(r)['sk']:decode(r) for r in saved['rows']}
        meta=before['META']; lab=meta['lab_id']
        if lab!='class193548-test1':raise ValueError('Wrong verification Lab')
        client=session.client('dynamodb'); rows=[]; cursor=None
        while True:
            args={'TableName':saved['table'],'KeyConditionExpression':'pk=:p',
                'ExpressionAttributeValues':{':p':{'S':meta['pk']}},'ConsistentRead':True}
            if cursor:args['ExclusiveStartKey']=cursor
            answer=client.query(**args);rows+=answer['Items'];cursor=answer.get('LastEvaluatedKey')
            if not cursor:break
        after={decode(r)['sk']:decode(r) for r in rows}
        new_keys=set(after)-set(before)
        if set(before)-set(after) or any(not k.startswith('REQUEST#') for k in new_keys):
            raise ValueError('Original rows removed or unexpected additions')
        attempts=[after[k] for k in new_keys]
        if {r.get('portal_job_id') for r in attempts}!=set(jobs) or len(attempts)!=len(jobs):
            raise ValueError('Unexpected original request additions')
        result=[]; allowed={'META'}; by_task={}
        for row in attempts:
            report=row['report']; validate_report(report,meta['instances'])
            if (any(report[k]!=meta[k] for k in ('lab_id','release_id','deployment_id'))
                    or row['body_sha256']!=legacy.digest(legacy.encoded(report))
                    or row['receipt'].get('stored') is not True
                    or row['receipt'].get('request_id')!=report['request_id']):
                raise ValueError('Original report or receipt mismatch')
            task=report['mission_id']; points=score(report)
            allowed.add(current_key(task))
            if points['counts_toward_assessment'] and points['evaluable']:allowed.add(grade_key(task))
            by_task.setdefault(task,[]).append(row)
            result.append({'job_id':row['portal_job_id'],'task_id':task,'request_id':report['request_id'],
                'received_at':row['received_at'],'report_sha256':row['body_sha256'],**points})
        for key in set(before)&set(after):
            if key not in allowed and before[key]!=after[key]:raise ValueError('Unrelated original row changed')
        for name in set(meta)|set(after['META']):
            if name not in ('updated_at','last_result') and meta.get(name)!=after['META'].get(name):
                raise ValueError('Original registration metadata changed')
        for task,values in by_task.items():
            latest=max(values,key=lambda r:r['received_at']); report=latest['report']
            if after[current_key(task)]['request_id']!=report['request_id']:raise ValueError('Latest observation mismatch')
            eligible=[r for r in values if score(r['report'])['counts_toward_assessment'] and score(r['report'])['evaluable']]
            if eligible:
                selected=max(eligible,key=lambda r:r['received_at'])
                if after[grade_key(task)]['request_id']!=selected['report']['request_id']:raise ValueError('Selected grade mismatch')
            elif before.get(grade_key(task))!=after.get(grade_key(task)):
                raise ValueError('Unconfirmed or practice observation changed selected grade')
        earned=sum(int(row['raw_earned']) for key,row in after.items() if key.startswith('GRADE#'+CONTRACT_SHA256))
        return {'verified_at':datetime.now(timezone.utc).isoformat(),'before_rows':len(before),'after_rows':len(after),
            'canonical_requests_added':len(attempts),'old_requests_and_unrelated_rows_preserved':True,
            'original_registration_metadata_preserved':True,'latest_and_selected_rules_verified':True,
            'raw_earned':earned,'raw_maximum':MAXIMUM,'requests':sorted(result,key=lambda r:(r['task_id'],r['received_at']))}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backup',type=Path,required=True);p.add_argument('--code',type=Path,required=True)
    p.add_argument('--job',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        result=verify(a.backup,a.code,a.job);os.umask(0o077)
        with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps(result))
    except Exception as exc:
        print('CANONICAL_SUBMISSION_ACCEPTANCE_NOT_CONFIRMED='+type(exc).__name__,flush=True)
        raise SystemExit(2) from None
