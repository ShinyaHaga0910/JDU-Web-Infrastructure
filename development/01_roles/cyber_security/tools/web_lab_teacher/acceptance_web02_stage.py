"""Verify signed real checker output and exact teacher storage for one fixture stage."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    import boto3
    from boto3.dynamodb.types import TypeDeserializer
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=('initial','practice','wrong','mission','loopback','normal','restored','repo_unavailable','signed_command'))
    for name in ('command-state','expected-deployment','checker-command','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--defer-teacher-storage',action='store_true',
        help='Class193548 only: verify student fixtures now; independently verify teacher storage later')
    a=p.parse_args();sys.dont_write_bytecode=True
    out=Path(a.output)
    if out.exists():raise ValueError('Existing acceptance stage retained')
    state=json.loads(Path(a.command_state).read_text());pending=Path(state['pending_directory'])
    deployment=json.loads(Path(state['state']).read_text())
    baseline=json.loads(Path(state['baseline_plan']).read_text())
    if deployment['deployment_id']!=a.expected_deployment or baseline['deployment_id']!=a.expected_deployment:
        raise ValueError('Explicitly selected deployment differs; checker not run')
    controller_manifest=Path(state['bootstrap_tools'])/'CONTROLLER-MANIFEST.json'
    signed_controller_sha256=hashlib.sha256(controller_manifest.read_bytes()).hexdigest()
    if a.defer_teacher_storage:
        from cross_account_storage import STUDENT, MANIFEST, binding, summarize
        binding(deployment)
        if deployment['manifest_sha256']!=MANIFEST or boto3.client('sts').get_caller_identity()['Account']!=STUDENT:
            raise ValueError('Deferred storage is only for the accepted separate Class193548 student')
    else:
        cfn=boto3.client('cloudformation',region_name='us-east-1')
        outputs={x['OutputKey']:x['OutputValue'] for x in cfn.describe_stacks(StackName='jdu-web-progress-2026')['Stacks'][0]['Outputs']}
        db=boto3.client('dynamodb',region_name='us-east-1');d=TypeDeserializer()
    cases=['P1','M1'] if a.stage in ('initial','practice','restored','signed_command') else ['M1']
    results=[]
    for task in cases:
        before=set(pending.glob('*.report.json'))
        r=subprocess.run([a.checker_command,task],capture_output=True,text=True,timeout=120)
        added=set(pending.glob('*.report.json'))-before
        if len(added)!=1:raise ValueError('Expected exactly one fresh retained report')
        path=added.pop();report=json.loads(path.read_text());rid=report['request_id']
        if any(report[k]!=deployment[k] for k in ('lab_id','release_id','deployment_id')):
            raise ValueError('Fresh checker report belongs to another deployment')
        checks={c['id']:c['status'] for c in report['checks']}
        expected=dict.fromkeys(checks,'PASS')
        if a.stage in ('initial','restored'):
            expected={k:'PASS' if k in ('WEB02_IDENTITY','WEB02_REPO_PREREQUISITE') else 'FAIL' for k in checks}
        elif a.stage=='practice' and task=='M1':
            for k in ('WEB02_FILE','WEB02_LOCAL_HTTP','WEB02_BASTION_HTTP','WEB02_PUBLIC_HTTP','WEB02_ACCESS_LOG'):expected[k]='FAIL'
        elif a.stage=='wrong':
            for k in ('WEB02_FILE','WEB02_LOCAL_HTTP','WEB02_BASTION_HTTP','WEB02_PUBLIC_HTTP'):expected[k]='FAIL'
        elif a.stage=='loopback':
            for k in ('WEB02_LISTEN_80','WEB02_BASTION_HTTP','WEB02_PUBLIC_HTTP','WEB02_ACCESS_LOG'):expected[k]='FAIL'
        elif a.stage=='repo_unavailable':expected['WEB02_REPO_PREREQUISITE']='UNKNOWN'
        if checks!=expected or r.returncode!=(0 if all(v=='PASS' for v in expected.values()) else 1):
            print(r.stdout);raise ValueError('Checker result differs from actual fixture expectation')
        if 'SUBMISSION STORED' not in r.stdout:raise ValueError('Automatic submission was not stored')
        def read(sk):
            item=db.get_item(TableName=outputs['TableName'],Key={'pk':{'S':'LAB#'+deployment['lab_id']},'sk':{'S':sk}},ConsistentRead=True)['Item']
            return {k:d.deserialize(v) for k,v in item.items()}
        receipt=json.loads((pending/(rid+'.receipt.json')).read_text())
        canonical=json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        if a.defer_teacher_storage:
            summarize(report,receipt)  # Validate real receipt binding and independent exact-retry result.
        else:
            latest=read('LATEST#'+task);stored=read('REQUEST#'+rid)
            if (stored['report']!=report or stored['receipt']!=receipt['receipt']
                    or stored['body_sha256']!=hashlib.sha256(canonical).hexdigest()
                    or latest['request_id']!=rid or latest['checks']!=report['checks']):
                raise ValueError('Exact teacher storage/latest differs')
        observed=json.loads((pending/(rid+'.observation.json')).read_text())
        results.append(dict(task=task,request_id=rid,passed=sum(v=='PASS' for v in checks.values()),
            total=len(checks),checks=checks,expected_fixture_outcome_matched=True,
            automatic_submission=True,teacher_exact_body_and_latest=not a.defer_teacher_storage,
            teacher_storage_verification_pending=a.defer_teacher_storage,
            exact_retry_same_receipt=receipt['exact_retry_same_receipt'],observed_at=observed['checked_at']))
    public=dict(stage=a.stage,checked_at=datetime.now(timezone.utc).isoformat(),results=results,
        deployment_id=deployment['deployment_id'],lab_id=deployment['lab_id'],
        signed_controller_manifest_sha256=signed_controller_sha256,
        all_fixture_expectations_passed=True,teacher_storage_verification_pending=a.defer_teacher_storage,
        course_points_assigned=False,class_ready=False)
    with out.open('x') as f:json.dump(public,f,indent=2)
    print('WEB02_ACCEPTANCE_STAGE='+json.dumps(public,separators=(',',':')))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('WEB02_ACCEPTANCE_STOPPED='+type(exc).__name__);raise SystemExit(2)
