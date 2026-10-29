"""Prepare the existing Web entry's authenticated enrollment/grade update.

Creates a reviewable change set only. Public application data access is not
enabled here; the operator must approve the concrete update before execution.
Google credentials, IAM, original EC2 and grades are not changed.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

ACCOUNT='170126527713'
STACK='jdu-web-portal-poc-20261029-r1'
ARTIFACT_STACK='jdu-web-portal-web-artifacts-20261029'
CHANGE='verified-student-enrollment-and-grades'
ORIGIN='https://d9r6gn83y8wkl4xl.gpb.lambda-web.us-east-1.on.aws'


def write_new(path,value):
    with path.open('x',encoding='utf-8') as f:
        os.chmod(path,0o600);json.dump(value,f,sort_keys=True,indent=2);f.write('\n')


def inspect(change):
    rows=[v.get('ResourceChange',{}) for v in change.get('Changes',[])]
    if (change.get('Status')!='CREATE_COMPLETE' or change.get('ExecutionStatus')!='AVAILABLE' or len(rows)!=2
            or {v.get('LogicalResourceId'):v.get('ResourceType') for v in rows}!=
               {'Revision':'AWS::Lambda::WebFunctionRevision','Endpoint':'AWS::Lambda::WebFunctionEndpoint'}
            or any(v.get('Action')!='Modify' for v in rows)):
        raise ValueError('Unexpected Web update')


def prepare(directory,code_path,services,template_digest,receipt,sts,cfn,s3,*,checker_arn=None):
    import re
    if (sts.get_caller_identity()['Account']!=ACCOUNT or receipt.exists()
            or services.get('phase')!='private-services-updated' or not re.fullmatch(r'[a-f0-9]{64}',template_digest)):
        raise ValueError('Wrong Web preparation context')
    stack=cfn.describe_stacks(StackName=STACK)['Stacks'][0]
    if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):raise ValueError('Web stack unavailable')
    previous={v['ParameterKey']:v['ParameterValue'] for v in stack['Parameters']}
    if (previous.get('PublicOrigin')!=ORIGIN or previous.get('LabRoleArn')!=f'arn:aws:iam::{ACCOUNT}:role/LabRole'
            or previous.get('PortalMode')!='enabled' or previous.get('AcceptanceEnabled')!='false'):
        raise ValueError('Existing Web identity changed')
    outputs=services['outputs']
    if any(not v.startswith(f'arn:aws:lambda:us-east-1:{ACCOUNT}:function:') for v in (outputs['EnrollmentArn'],outputs['GradeReaderArn'])):
        raise ValueError('Wrong internal service account')
    template=(directory/'portal-web.template.json').read_text(encoding='utf-8')
    parsed=json.loads(template)
    if ({k:v['Type'] for k,v in parsed['Resources'].items()}!=
        {'LogGroup':'AWS::Logs::LogGroup','Portal':'AWS::Lambda::WebFunction','Revision':'AWS::Lambda::WebFunctionRevision','Endpoint':'AWS::Lambda::WebFunctionEndpoint'}
            or parsed['Resources']['Endpoint']['Properties']['AuthType']!='ApplicationManaged'):
        raise ValueError('Unexpected Web template')
    cfn.validate_template(TemplateBody=template)
    bucket={v['OutputKey']:v['OutputValue'] for v in cfn.describe_stacks(StackName=ARTIFACT_STACK)['Stacks'][0]['Outputs']}['BucketName']
    if bucket!=previous['ArtifactBucket']:raise ValueError('Existing Web artifact bucket differs')
    owner={'Bucket':bucket,'ExpectedBucketOwner':ACCOUNT}
    block=s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration']
    if (not all(block.get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'))
            or s3.get_bucket_versioning(**owner).get('Status')!='Enabled'):
        raise ValueError('Artifact protection changed')
    code=code_path.read_bytes();sha=hashlib.sha256(code).hexdigest();key='portal/'+sha+'/portal.zip'
    write_new(receipt,{'phase':'preparation-started','account':ACCOUNT,'code_sha256':sha,'template_digest':template_digest})
    uploaded=s3.put_object(**owner,Key=key,Body=code,IfNoneMatch='*',ServerSideEncryption='AES256',
        ChecksumSHA256=base64.b64encode(hashlib.sha256(code).digest()).decode(),Metadata={'sha256':sha})
    version=uploaded.get('VersionId')
    if not version or version=='null':raise ValueError('Versioned Web code required')
    read=s3.get_object(**owner,Key=key,VersionId=version)['Body'].read(len(code)+1)
    if hashlib.sha256(read).hexdigest()!=sha:raise ValueError('Web code upload differs')
    overrides={'ArtifactKey':key,'ArtifactVersion':version,'ReleaseId':sha,
        'GradeReaderFunctionArn':outputs['GradeReaderArn'],'EnrollmentFunctionArn':outputs['EnrollmentArn'],
        'EnrollmentEnabled':'true','BootstrapTemplateUrl':'disabled','BootstrapTemplateDigest':template_digest}
    if checker_arn is not None:
        if checker_arn!=f'arn:aws:lambda:us-east-1:{ACCOUNT}:function:jdu-web-portal-checker-20261029':
            raise ValueError('Wrong fixed checker service')
        overrides.update(CheckerFunctionArn=checker_arn,CheckerEnabled='true')
    parameters=[]
    expected={}
    for name,definition in parsed['Parameters'].items():
        if name in overrides:
            value=overrides[name];parameters.append({'ParameterKey':name,'ParameterValue':value})
        elif name in previous:
            value=previous[name];parameters.append({'ParameterKey':name,'UsePreviousValue':True})
        elif 'Default' in definition:
            value=definition['Default'];parameters.append({'ParameterKey':name,'ParameterValue':value})
        else:raise ValueError('Missing explicit Web parameter')
        expected[name]=value
    request=cfn.create_change_set(StackName=STACK,ChangeSetName=CHANGE+'-'+sha[:12],ChangeSetType='UPDATE',TemplateBody=template,Parameters=parameters)
    cfn.get_waiter('change_set_create_complete').wait(ChangeSetName=request['Id'],StackName=request['StackId'],WaiterConfig={'Delay':5,'MaxAttempts':24})
    inspect(cfn.describe_change_set(ChangeSetName=request['Id'],StackName=request['StackId']))
    ready={'phase':'authenticated-enrollment-web-ready-not-executed','account':ACCOUNT,'stack_id':request['StackId'],
        'change_set_id':request['Id'],'parameters':expected,'code_sha256':sha,
        'template_sha256':hashlib.sha256(template.encode()).hexdigest(),'source_template_digest':template_digest,
        'origin':ORIGIN,'internal_services':outputs,'services_code_sha256':services['code_sha256'],
        'artifact':{'bucket':bucket,'key':key,'version':version}}
    write_new(receipt.with_name('enrollment-web.ready.private.json'),ready)
    print(json.dumps({'marker':'AUTHENTICATED_ENROLLMENT_WEB_PLAN_READY','executed':False,'changed_resources':2,
        'origin':ORIGIN,'code_sha256':sha,'source_template_digest':template_digest,
        'canonical_submission_enabled':checker_arn is not None}),flush=True)


if __name__=='__main__':
    import boto3
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--code',type=Path,required=True)
    parser.add_argument('--services',type=Path,required=True)
    parser.add_argument('--template-digest',required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--checker-arn')
    args=parser.parse_args()
    try:
        prepare(args.directory,args.code,json.loads(args.services.read_text()),args.template_digest,args.receipt,
                *(boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3')),checker_arn=args.checker_arn)
    except Exception:
        raise SystemExit('ENROLLMENT_WEB_PLAN_NOT_CONFIRMED: inspect receipts and change set; not executed') from None
