"""Prepare/apply a code-only update to the already approved private services.

Uses the previous CloudFormation template. Secret, role, table and endpoint
settings cannot be changed here. Unknown execution outcomes are never retried.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from prepare_portal_services import ACCOUNT,ARTIFACT_STACK,private_write

FUNCTIONS={'EnrollmentService','GradeReader'}
CHANGE='browser-resume-code-20261029'


def inspect(value):
    changes=[r.get('ResourceChange',{}) for r in value.get('Changes',[])]
    if (value.get('Status')!='CREATE_COMPLETE' or value.get('ExecutionStatus')!='AVAILABLE'
            or len(changes)!=2 or {r.get('LogicalResourceId') for r in changes}!=FUNCTIONS
            or any(r.get('ResourceType')!='AWS::Lambda::Function' or r.get('Action')!='Modify'
                   or r.get('Replacement') not in ('False',False) or r.get('Scope')!=['Properties']
                   or not r.get('Details') or any(d.get('Target',{}).get('Attribute')!='Properties'
                       or d.get('Target',{}).get('Name')!='Code' for d in r['Details']) for r in changes)):
        raise ValueError('Unexpected code update')


def current(created,cfn,lam):
    stack=cfn.describe_stacks(StackName=created['stack_id'])['Stacks'][0]
    outputs={v['OutputKey']:v['OutputValue'] for v in stack['Outputs']}
    if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE') or outputs!=created['outputs']:
        raise ValueError('Original service stack changed')
    for name in ('EnrollmentArn','GradeReaderArn'):
        config=lam.get_function_configuration(FunctionName=outputs[name])
        if (config['State']!='Active' or config['Role']!=f'arn:aws:iam::{ACCOUNT}:role/LabRole'
                or base64.b64decode(config['CodeSha256']).hex()!=created['code_sha256']):
            raise ValueError('Original code or role changed')
    return stack


def prepare(created,code_path,receipt,clients):
    sts,cfn,s3,lam=clients
    if sts.get_caller_identity()['Account']!=ACCOUNT or receipt.exists():
        raise ValueError('Wrong account or existing update plan')
    stack=current(created,cfn,lam)
    parameters={v['ParameterKey']:v['ParameterValue'] for v in stack['Parameters']}
    artifact=cfn.describe_stacks(StackName=ARTIFACT_STACK)['Stacks'][0]
    bucket={v['OutputKey']:v['OutputValue'] for v in artifact['Outputs']}['BucketName']
    if parameters.get('ArtifactBucket')!=bucket:
        raise ValueError('Original artifact owner differs')
    owner={'Bucket':bucket,'ExpectedBucketOwner':ACCOUNT}
    block=s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration']
    if (not all(block.get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'))
            or s3.get_bucket_versioning(**owner).get('Status')!='Enabled'):
        raise ValueError('Artifact protection changed')
    code=code_path.read_bytes();sha=hashlib.sha256(code).hexdigest()
    key='portal-internal/'+sha+'/portal-services.zip'
    private_write(receipt,{'phase':'preparation-started','code_sha256':sha,'stack_id':created['stack_id'],'previous':created})
    uploaded=s3.put_object(**owner,Key=key,Body=code,IfNoneMatch='*',ServerSideEncryption='AES256',
        ChecksumSHA256=base64.b64encode(hashlib.sha256(code).digest()).decode(),Metadata={'sha256':sha})
    version=uploaded.get('VersionId')
    if not version or version=='null':raise ValueError('Versioned code required')
    fetched=s3.get_object(**owner,Key=key,VersionId=version)['Body'].read(len(code)+1)
    if hashlib.sha256(fetched).hexdigest()!=sha:raise ValueError('Uploaded code differs')
    updates={'ArtifactKey':key,'ArtifactVersion':version}
    request=cfn.create_change_set(StackName=created['stack_id'],ChangeSetName=CHANGE,ChangeSetType='UPDATE',UsePreviousTemplate=True,
        Parameters=[{'ParameterKey':k,'ParameterValue':updates[k]} if k in updates else {'ParameterKey':k,'UsePreviousValue':True} for k in parameters])
    cfn.get_waiter('change_set_create_complete').wait(ChangeSetName=request['Id'],StackName=created['stack_id'],WaiterConfig={'Delay':5,'MaxAttempts':24})
    change=cfn.describe_change_set(ChangeSetName=request['Id'],StackName=created['stack_id'])
    inspect(change)
    ready={**created,'phase':'code-update-ready','previous':created,'code_sha256':sha,'change_set_id':request['Id'],
           'artifact':{'bucket':bucket,'key':key,'version':version},'expected_parameters':{**parameters,**updates}}
    private_write(receipt.with_name('services-v2.ready.private.json'),ready)
    print(json.dumps({'marker':'PRIVATE_SERVICES_CODE_PLAN_READY','code_sha256':sha,'lambda_code_modifications':2,
                      'secret_role_table_changes':False,'executed':False}),flush=True)


def apply(plan,receipt,clients):
    sts,cfn,s3,lam=clients
    if sts.get_caller_identity()['Account']!=ACCOUNT or plan.get('phase')!='code-update-ready':
        raise ValueError('Wrong code update context')
    requested=receipt.with_name('services-v2.apply-requested.private.json')
    if requested.exists():raise ValueError('Inspect previous update before repeating')
    current(plan['previous'],cfn,lam)
    change=cfn.describe_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'])
    inspect(change)
    if {v['ParameterKey']:v['ParameterValue'] for v in change['Parameters']}!=plan['expected_parameters']:
        raise ValueError('Code update parameters changed')
    artifact=plan['artifact']
    raw=s3.get_object(Bucket=artifact['bucket'],Key=artifact['key'],VersionId=artifact['version'],ExpectedBucketOwner=ACCOUNT)['Body'].read()
    if hashlib.sha256(raw).hexdigest()!=plan['code_sha256']:raise ValueError('Code version differs')
    private_write(requested,{'change_set_id':plan['change_set_id'],'phase':'execute-request-recorded'})
    cfn.execute_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'],
        ClientRequestToken='portal-resume-'+hashlib.sha256(plan['change_set_id'].encode()).hexdigest()[:40])
    print('PRIVATE_SERVICES_CODE_UPDATE_REQUESTED',flush=True)
    cfn.get_waiter('stack_update_complete').wait(StackName=plan['stack_id'],WaiterConfig={'Delay':5,'MaxAttempts':60})
    updated={**plan['previous'],'phase':'private-services-updated','code_sha256':plan['code_sha256']}
    current(updated,cfn,lam)
    private_write(receipt.with_name('services-v2.updated.private.json'),updated)
    print('PRIVATE_SERVICES_CODE_UPDATE_COMPLETE',flush=True)


if __name__=='__main__':
    import boto3
    parser=argparse.ArgumentParser()
    parser.add_argument('--created',type=Path)
    parser.add_argument('--code',type=Path)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    try:
        clients=[boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3','lambda')]
        if args.apply:apply(json.loads(args.receipt.read_text()),args.receipt,clients)
        elif args.created and args.code:prepare(json.loads(args.created.read_text()),args.code,args.receipt,clients)
        else:raise ValueError('Preparation inputs required')
    except Exception:
        raise SystemExit('PRIVATE_CODE_UPDATE_NOT_CONFIRMED: inspect stack and receipts; never restart blindly') from None
