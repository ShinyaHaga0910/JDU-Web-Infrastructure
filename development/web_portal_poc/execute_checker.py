"""Execute exactly the prepared additions after the concrete operator approval."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path


def execute(receipt):
    import boto3
    os.umask(0o077)
    plan=json.loads(receipt.read_text(encoding='utf-8'))
    sts,cfn,lam=[boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','lambda')]
    if sts.get_caller_identity()['Account']!=plan['account']:
        raise ValueError('Wrong account')
    ready=cfn.describe_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'])
    rows=[r['ResourceChange'] for r in ready['Changes']]
    template=cfn.get_template(StackName=plan['stack_id'],ChangeSetName=plan['change_set_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(template,str):template=json.loads(template)
    # CloudFormation can normalize JSON formatting; compare parsed structure.
    expected=json.loads((Path(__file__).parent/(plan['side']+'-checker.template.json')).read_text(encoding='utf-8'))
    if (template!=expected or ready['Status']!='CREATE_COMPLETE' or ready['ExecutionStatus']!='AVAILABLE'
            or {r['LogicalResourceId']:r['ResourceType'] for r in rows}!=plan['expected_adds']
            or any(r['Action']!='Add' for r in rows)):
        raise ValueError('Prepared plan changed or already executed')
    cfn.execute_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'])
    print('CHECKER_CREATE_REQUESTED',flush=True)
    cfn.get_waiter('stack_create_complete').wait(StackName=plan['stack_id'],WaiterConfig={'Delay':5,'MaxAttempts':60})
    stack=cfn.describe_stacks(StackName=plan['stack_id'])['Stacks'][0]
    outputs={r['OutputKey']:r['OutputValue'] for r in stack['Outputs']}
    fn=lam.get_function_configuration(FunctionName=outputs['CheckerArn'])
    if (fn['State']!='Active' or base64.b64decode(fn['CodeSha256']).hex()!=plan['code_sha256']
            or fn['Role']!=f"arn:aws:iam::{plan['account']}:role/LabRole"):
        raise ValueError('Created code differs')
    try:
        lam.get_function_url_config(FunctionName=outputs['CheckerArn'])
    except lam.exceptions.ResourceNotFoundException:
        pass
    else:
        raise ValueError('Unexpected function URL')
    with receipt.with_name(plan['side']+'-checks.created.private.json').open('x',encoding='utf-8') as f:
        json.dump({**plan,'outputs':outputs,'stack_status':stack['StackStatus']},f,indent=2)
    print(json.dumps({'marker':'CHECKER_CREATE_COMPLETE','side':plan['side'],'code_sha256':plan['code_sha256'],'public_url':False}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True)
    try:execute(p.parse_args().receipt)
    except Exception as exc:
        print('CHECKER_CREATE_NOT_CONFIRMED='+type(exc).__name__,flush=True)
        raise SystemExit(2) from None
