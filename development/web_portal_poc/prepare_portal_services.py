"""Teacher CloudShell: prepare a CREATE change set, never execute it.

Only source is uploaded to an existing protected, versioned artifact bucket.
No secret is generated, access enabled or original Lab modified by preparation.
The private receipt records unknown outcomes and prevents blind re-creation.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

from botocore.exceptions import ClientError

ACCOUNT = '170126527713'
STACK = 'jdu-web-portal-services-20261029'
CHANGE = 'private-enrollment-and-grades'
ARTIFACT_STACK = 'jdu-web-portal-web-artifacts-20261029'
BINDINGS = 'jdu-web-portal-binding-poc-20261027-BindingTable-2AGM7NTN5PWU'
GRADES = 'jdu-web-progress-2026-ProgressTable-6D4AMSJ9A3U4'
ADDITIONS = {'SubjectKey':'AWS::SecretsManager::Secret', 'EnrollmentService':'AWS::Lambda::Function',
             'GradeReader':'AWS::Lambda::Function', 'EnrollmentLogs':'AWS::Logs::LogGroup', 'GradeLogs':'AWS::Logs::LogGroup'}


def private_write(path, value):
    with path.open('x', encoding='utf-8') as handle:
        os.chmod(path, 0o600)
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write('\n')


def assert_new_stack(cfn):
    try:
        cfn.describe_stacks(StackName=STACK)
    except ClientError as error:
        detail = error.response['Error']
        if detail.get('Code')=='ValidationError' and detail.get('Message')==f'Stack with id {STACK} does not exist':
            return
        raise
    raise ValueError('Stack exists: inspect it instead of retrying creation')


def inspect_change(value):
    changes = [item.get('ResourceChange', {}) for item in value.get('Changes', [])]
    if (value.get('Status')!='CREATE_COMPLETE' or value.get('ExecutionStatus')!='AVAILABLE'
            or len(changes)!=len(ADDITIONS)
            or {v.get('LogicalResourceId'):v.get('ResourceType') for v in changes}!=ADDITIONS
            or any(v.get('Action')!='Add' for v in changes)):
        raise ValueError('Unexpected change set; nothing executed')


def prepare(directory, output, clients):
    sts, cfn, s3, db = clients
    if sts.get_caller_identity()['Account']!=ACCOUNT:
        raise ValueError('Wrong teacher account')
    if output.exists():
        raise ValueError('Plan receipt exists: inspect it instead of retrying preparation')
    assert_new_stack(cfn)
    for name in (BINDINGS, GRADES):
        table=db.describe_table(TableName=name)['Table']
        if table.get('TableStatus')!='ACTIVE' or table.get('KeySchema')!=[
            {'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}]:
            raise ValueError('Unexpected existing table')
    template=(directory/'portal-services.template.json').read_text(encoding='utf-8')
    if {k:v['Type'] for k,v in json.loads(template)['Resources'].items()}!=ADDITIONS:
        raise ValueError('Unexpected template resources')
    cfn.validate_template(TemplateBody=template)
    artifact=cfn.describe_stacks(StackName=ARTIFACT_STACK)['Stacks'][0]
    if artifact['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):
        raise ValueError('Artifact stack unavailable')
    bucket={v['OutputKey']:v['OutputValue'] for v in artifact['Outputs']}['BucketName']
    owner={'Bucket':bucket,'ExpectedBucketOwner':ACCOUNT}
    block=s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration']
    if (not all(block.get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'))
            or s3.get_bucket_versioning(**owner).get('Status')!='Enabled'):
        raise ValueError('Artifact protection changed')
    code=(directory/'portal-services.zip').read_bytes()
    sha=hashlib.sha256(code).hexdigest()
    key='portal-internal/'+sha+'/portal-services.zip'
    receipt={'account':ACCOUNT,'stack_name':STACK,'change_set_name':CHANGE,'phase':'preparation-started',
        'code_sha256':sha,'template_sha256':hashlib.sha256(template.encode()).hexdigest(),
        'original_grade_writes':False,'ec2_changes':False,'public_endpoints':False,'additions':ADDITIONS}
    private_write(output,receipt)
    try:
        stored=s3.put_object(**owner,Key=key,Body=code,ServerSideEncryption='AES256',IfNoneMatch='*',
            ChecksumSHA256=base64.b64encode(hashlib.sha256(code).digest()).decode(),Metadata={'sha256':sha})
    except ClientError as error:
        if error.response['Error'].get('Code') not in ('PreconditionFailed','412'):
            raise
        stored=s3.head_object(**owner,Key=key,ChecksumMode='ENABLED')
    version=stored.get('VersionId')
    if not version or version=='null':
        raise ValueError('Versioned artifact required')
    fetched=s3.get_object(**owner,Key=key,VersionId=version)['Body'].read(len(code)+1)
    if hashlib.sha256(fetched).hexdigest()!=sha:
        raise ValueError('Artifact hash differs')
    parameters={'ArtifactBucket':bucket,'ArtifactKey':key,'ArtifactVersion':version,
        'LabRoleArn':f'arn:aws:iam::{ACCOUNT}:role/LabRole','GradeTableName':GRADES,
        'BindingTableName':BINDINGS,'SecretScope':'class193548-20261029'}
    request=cfn.create_change_set(StackName=STACK,ChangeSetName=CHANGE,ChangeSetType='CREATE',
        TemplateBody=template,Parameters=[{'ParameterKey':k,'ParameterValue':v} for k,v in parameters.items()],
        Tags=[{'Key':'Purpose','Value':'web-portal-private-services'}])
    cfn.get_waiter('change_set_create_complete').wait(ChangeSetName=request['Id'],StackName=request['StackId'],WaiterConfig={'Delay':5,'MaxAttempts':24})
    change=cfn.describe_change_set(ChangeSetName=request['Id'],StackName=request['StackId'])
    inspect_change(change)
    # Keep the start receipt if outcome is unknown; acceptance is a separate,
    # exclusive receipt. Do not overwrite either receipt on retry.
    accepted=output.with_name(output.stem+'.ready.json')
    private_write(accepted,{**receipt,'phase':'change-set-ready-not-executed','change_set_id':request['Id'],
                           'stack_id':request['StackId'],'parameters':parameters})
    print(json.dumps({'marker':'PORTAL_PRIVATE_SERVICES_PLAN_READY','account':ACCOUNT,'stack':STACK,
                      'additions':ADDITIONS,'executed':False,'code_sha256':sha}))


if __name__=='__main__':
    import boto3
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    try:
        prepare(args.directory,args.receipt,[boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3','dynamodb')])
    except Exception:
        raise SystemExit('PRIVATE_SERVICES_PLAN_NOT_CONFIRMED: inspect receipt and change set; nothing was executed') from None
