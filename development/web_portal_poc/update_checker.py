"""Code-only repair of an existing checker; preserve all resources and config."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path


def inspect(value):
    rows=[r['ResourceChange'] for r in value.get('Changes',[])]
    functions=[r for r in rows if r.get('LogicalResourceId')=='Checker']
    # CloudFormation also marks the unchanged Permission's GetAtt as Dynamic
    # when its function's code changes. This is the same function ARN and the
    # same teacher principal; accept only that exact dependent reference.
    permissions=[r for r in rows if r.get('LogicalResourceId')=='TeacherInvoke']
    for row in permissions:
        details=row.get('Details',[])
        if (row.get('ResourceType')!='AWS::Lambda::Permission' or row.get('Action')!='Modify'
                or row.get('Replacement')!='Conditional' or not details
                or any(d.get('Target',{}).get('Name')!='FunctionName'
                    or d.get('ChangeSource')!='ResourceAttribute' or d.get('CausingEntity')!='Checker.Arn' for d in details)):
            raise ValueError('Invoke permission must remain the same function and principal')
    if (value.get('Status')!='CREATE_COMPLETE' or value.get('ExecutionStatus')!='AVAILABLE'
            or len(functions)!=1 or len(permissions)>1 or len(rows)!=len(functions)+len(permissions)
            or functions[0].get('ResourceType')!='AWS::Lambda::Function' or functions[0].get('Action')!='Modify'
            or functions[0].get('Replacement')!='False'):
        raise ValueError('Only existing checker Code may change')


def run(mode, created_path, code_path, receipt):
    import boto3
    os.umask(0o077)
    old=json.loads(created_path.read_text(encoding='utf-8'))
    sts,cfn,s3,lam=[boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3','lambda')]
    if sts.get_caller_identity()['Account']!=old['account']:
        raise ValueError('Wrong account')
    if mode=='prepare':
        if receipt.exists():raise ValueError('Inspect existing update receipt')
        stack=cfn.describe_stacks(StackName=old['stack_id'])['Stacks'][0]
        if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):
            raise ValueError('Existing stack unavailable')
        previous={v['ParameterKey']:v['ParameterValue'] for v in stack['Parameters']}
        raw=code_path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        key='checks/'+digest+'/checks.zip';owner={'Bucket':previous['ArtifactBucket'],'ExpectedBucketOwner':old['account']}
        upload=s3.put_object(**owner,Key=key,Body=raw,ServerSideEncryption='AES256',IfNoneMatch='*')
        version=upload['VersionId']
        if hashlib.sha256(s3.get_object(**owner,Key=key,VersionId=version)['Body'].read(len(raw)+1)).hexdigest()!=digest:
            raise ValueError('Code bytes differ')
        template=cfn.get_template(StackName=old['stack_id'],TemplateStage='Original')['TemplateBody']
        if not isinstance(template,str):template=json.dumps(template)
        parameters=[{'ParameterKey':k,'ParameterValue':v} if k in ('ArtifactKey','ArtifactVersion') else
            {'ParameterKey':k,'UsePreviousValue':True} for k,v in {**previous,'ArtifactKey':key,'ArtifactVersion':version}.items()]
        plan=cfn.create_change_set(StackName=old['stack_id'],ChangeSetName='checker-code-'+digest[:12],ChangeSetType='UPDATE',TemplateBody=template,Parameters=parameters)
        with receipt.open('x',encoding='utf-8') as f:
            json.dump({**old,'change_set_id':plan['Id'],'code_sha256':digest,'previous_code_sha256':old['code_sha256']},f,indent=2)
        cfn.get_waiter('change_set_create_complete').wait(ChangeSetName=plan['Id'],WaiterConfig={'Delay':5,'MaxAttempts':24})
        inspect(cfn.describe_change_set(ChangeSetName=plan['Id']))
        print('CHECKER_CODE_ONLY_UPDATE_READY',digest,flush=True)
    else:
        plan=json.loads(receipt.read_text(encoding='utf-8'))
        inspect(cfn.describe_change_set(ChangeSetName=plan['change_set_id']))
        cfn.execute_change_set(ChangeSetName=plan['change_set_id'],ClientRequestToken='checker-code-'+plan['code_sha256'][:40])
        print('CHECKER_CODE_UPDATE_REQUESTED',flush=True)
        cfn.get_waiter('stack_update_complete').wait(StackName=plan['stack_id'],WaiterConfig={'Delay':5,'MaxAttempts':60})
        fn=lam.get_function_configuration(FunctionName=old['outputs']['CheckerArn'])
        if base64.b64decode(fn['CodeSha256']).hex()!=plan['code_sha256'] or fn['State']!='Active':
            raise ValueError('Updated code differs')
        with receipt.with_name(plan['side']+'-checks.updated.private.json').open('x',encoding='utf-8') as f:
            json.dump({**plan,'stack_status':'UPDATE_COMPLETE'},f,indent=2)
        print('CHECKER_CODE_UPDATE_COMPLETE',plan['code_sha256'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','apply'))
    p.add_argument('--created',type=Path,required=True);p.add_argument('--code',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args()
    try:run(a.mode,a.created,a.code,a.receipt)
    except Exception as exc:
        print('CHECKER_CODE_UPDATE_NOT_CONFIRMED='+type(exc).__name__,flush=True)
        raise SystemExit(2) from None
