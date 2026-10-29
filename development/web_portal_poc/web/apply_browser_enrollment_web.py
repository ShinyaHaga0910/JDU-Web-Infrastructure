"""Execute only after operator approval of the concrete authenticated Web plan.

Rechecks code, parameters, private services and the published source artifact.
Never changes OAuth credentials, IAM, EC2, grades or student assignments.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from prepare_browser_enrollment_web import ACCOUNT,ORIGIN,inspect,write_new


def apply(plan,receipt,directory,clients):
    sts,cfn,s3,lam=clients
    if (sts.get_caller_identity()['Account']!=ACCOUNT or plan.get('account')!=ACCOUNT
            or plan.get('phase')!='authenticated-enrollment-web-ready-not-executed' or plan.get('origin')!=ORIGIN):
        raise ValueError('Wrong Web execution context')
    requested=receipt.with_name('enrollment-web.apply-requested.private.json')
    if requested.exists():raise ValueError('Inspect previous execution instead of retrying')
    change=cfn.describe_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'])
    inspect(change)
    if {v['ParameterKey']:v['ParameterValue'] for v in change['Parameters']}!=plan['parameters']:
        raise ValueError('Web parameters changed')
    local=(directory/'portal-web.template.json').read_bytes()
    if hashlib.sha256(local).hexdigest()!=plan['template_sha256']:raise ValueError('Web template hash changed')
    actual=cfn.get_template(StackName=plan['stack_id'],ChangeSetName=plan['change_set_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(actual,str):actual=json.loads(actual)
    if actual!=json.loads(local):raise ValueError('Web template differs')
    artifact=plan['artifact']
    raw=s3.get_object(Bucket=artifact['bucket'],Key=artifact['key'],VersionId=artifact['version'],ExpectedBucketOwner=ACCOUNT)['Body'].read()
    if hashlib.sha256(raw).hexdigest()!=plan['code_sha256']:raise ValueError('Web artifact changed')
    digest=plan['source_template_digest'];bucket=f'jdu-web-portal-bootstrap-{ACCOUNT}-{digest[:12]}'
    source=s3.get_object(Bucket=bucket,Key=f'bootstrap/{digest}/account-link.template.json',ExpectedBucketOwner=ACCOUNT)
    code=source['Body'].read(51201)
    if not source.get('VersionId') or source['VersionId']=='null' or len(code)>51200 or hashlib.sha256(code).hexdigest()!=digest:
        raise ValueError('Student source artifact unavailable or different')
    block=s3.get_public_access_block(Bucket=bucket,ExpectedBucketOwner=ACCOUNT)['PublicAccessBlockConfiguration']
    if (not all(block.get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'))
            or s3.get_bucket_policy_status(Bucket=bucket,ExpectedBucketOwner=ACCOUNT)['PolicyStatus']['IsPublic'] is not False):
        raise ValueError('Student artifact access changed')
    for name in ('EnrollmentArn','GradeReaderArn'):
        config=lam.get_function_configuration(FunctionName=plan['internal_services'][name])
        if (config['State']!='Active' or config['Role']!=f'arn:aws:iam::{ACCOUNT}:role/LabRole'
                or base64.b64decode(config['CodeSha256']).hex()!=plan['services_code_sha256']):
            raise ValueError('Internal services changed')
    write_new(requested,{'phase':'execute-request-recorded','change_set_id':plan['change_set_id']})
    cfn.execute_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'],
        ClientRequestToken='enrollment-web-'+plan['code_sha256'][:40])
    print('AUTHENTICATED_ENROLLMENT_WEB_UPDATE_REQUESTED',flush=True)
    cfn.get_waiter('stack_update_complete').wait(StackName=plan['stack_id'],WaiterConfig={'Delay':5,'MaxAttempts':60})
    stack=cfn.describe_stacks(StackName=plan['stack_id'])['Stacks'][0]
    if {v['ParameterKey']:v['ParameterValue'] for v in stack['Parameters']}!=plan['parameters']:
        raise ValueError('Deployed Web configuration differs')
    write_new(receipt.with_name('enrollment-web.updated.private.json'),{**plan,'phase':'authenticated-enrollment-web-updated'})
    print('AUTHENTICATED_ENROLLMENT_WEB_UPDATE_COMPLETE',flush=True)


if __name__=='__main__':
    import boto3
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    try:
        apply(json.loads(args.receipt.read_text()),args.receipt,args.directory,
            [boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3','lambda')])
    except Exception:
        raise SystemExit('ENROLLMENT_WEB_APPLICATION_NOT_CONFIRMED: inspect stack and receipts; no automatic retry') from None
