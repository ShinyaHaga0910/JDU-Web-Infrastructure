"""Final operator action after reviewing the private-services change set.

Creates a new secret and two application functions with existing LabRole;
therefore browser workflows hand this final execution to the human operator.
Never enables Web enrollment, creates approvals or modifies original grades.
"""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_portal_services import ACCOUNT, STACK, inspect_change, private_write


def apply(receipt, clients):
    sts,cfn,s3,lam=clients
    plan=json.loads(receipt.read_text(encoding='utf-8'))
    if (sts.get_caller_identity()['Account']!=ACCOUNT or plan.get('account')!=ACCOUNT
            or plan.get('stack_name')!=STACK or plan.get('phase')!='change-set-ready-not-executed'):
        raise ValueError('Wrong plan or account')
    requested=receipt.with_name('apply-requested.private.json')
    if requested.exists():
        raise ValueError('Previous apply request exists; inspect it instead of repeating')
    change=cfn.describe_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'])
    inspect_change(change)
    if change.get('StackId')!=plan['stack_id'] or {v['ParameterKey']:v['ParameterValue'] for v in change['Parameters']}!=plan['parameters']:
        raise ValueError('Change set parameters differ')
    template=cfn.get_template(StackName=plan['stack_id'],ChangeSetName=plan['change_set_id'],TemplateStage='Original')['TemplateBody']
    template_bytes=(receipt.parent/'portal-services.template.json').read_bytes()
    if hashlib.sha256(template_bytes).hexdigest()!=plan['template_sha256']:
        raise ValueError('Local template hash differs')
    expected=json.loads(template_bytes)
    if isinstance(template,str): template=json.loads(template)
    if template!=expected:
        raise ValueError('Change set template differs')
    p=plan['parameters']
    code=s3.get_object(Bucket=p['ArtifactBucket'],Key=p['ArtifactKey'],VersionId=p['ArtifactVersion'],ExpectedBucketOwner=ACCOUNT)['Body'].read()
    if hashlib.sha256(code).hexdigest()!=plan['code_sha256']:
        raise ValueError('Artifact code differs')
    private_write(requested,{'phase':'execute-request-recorded','change_set_id':plan['change_set_id'],'stack_id':plan['stack_id']})
    cfn.execute_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'],
        ClientRequestToken='portal-services-'+hashlib.sha256(plan['change_set_id'].encode()).hexdigest()[:40])
    print('PORTAL_PRIVATE_SERVICES_CREATE_REQUESTED',flush=True)
    cfn.get_waiter('stack_create_complete').wait(StackName=plan['stack_id'],WaiterConfig={'Delay':5,'MaxAttempts':60})
    outputs={v['OutputKey']:v['OutputValue'] for v in cfn.describe_stacks(StackName=plan['stack_id'])['Stacks'][0]['Outputs']}
    import base64
    for name in ('EnrollmentArn','GradeReaderArn'):
        config=lam.get_function_configuration(FunctionName=outputs[name])
        if (config['State']!='Active' or config['Role']!=f'arn:aws:iam::{ACCOUNT}:role/LabRole'
                or base64.b64decode(config['CodeSha256']).hex()!=plan['code_sha256']):
            raise ValueError('Deployed service differs')
    private_write(receipt.with_name('services-created.private.json'),{'phase':'private-services-created',
        'stack_id':plan['stack_id'],'code_sha256':plan['code_sha256'],'outputs':outputs,
        'web_enrollment_enabled':False,'student_approvals_created':False})
    print('PORTAL_PRIVATE_SERVICES_CREATE_COMPLETE',flush=True)


if __name__=='__main__':
    import boto3
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    try:
        apply(args.receipt,[boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3','lambda')])
    except Exception:
        raise SystemExit('PRIVATE_SERVICES_APPLICATION_NOT_CONFIRMED: inspect stack and receipts; do not repeat blindly') from None
