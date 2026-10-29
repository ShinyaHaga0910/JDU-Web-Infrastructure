"""Prepare reviewable checker additions only; execute is a separate approved step.

Run inside the appropriate AWS CloudShell. Retained state/credentials stay there.
The generated config contains only original resource IDs, public IPs and a
public SSH key. No secret generation, IAM edits, EC2 changes or grade writes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCOUNTS = {'student':'965244652544', 'teacher':'170126527713'}


def private_read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError('Retained private file required')
    return json.loads(path.read_text(encoding='utf-8'))


def prepare(side, code_path, command_state, receipt):
    import boto3
    os.umask(0o077)
    sts, cfn, s3 = [boto3.client(n, region_name='us-east-1') for n in ('sts','cloudformation','s3')]
    account = sts.get_caller_identity()['Account']
    if account != ACCOUNTS[side] or receipt.exists():
        raise ValueError('Wrong account or existing preparation; inspect receipt')
    parameters = {}
    if side == 'student':
        command = private_read(command_state)
        state, baseline, enrollment = [private_read(command[k]) for k in ('state','baseline_plan','ssh_enrollment')]
        state.setdefault('release_id','web-2026-10-r1')
        if state['account'] != account or any(state[k] != baseline[k] for k in ('account','deployment_id','stack_id')):
            raise ValueError('Wrong retained deployment')
        config = {'state':{k:state[k] for k in ('account','lab_id','deployment_id','release_id','stack_id')},
            'baseline':{k:baseline[k] for k in ('nodes','proposed_sha256')}, 'public_key':enrollment['public_key']}
        # CLI performs account/template/tag/root/running identity checks again
        # at execution. Plan can be prepared while servers are still starting.
        parameters.update(LabId=state['lab_id'], CheckConfig=json.dumps(config,separators=(',',':')),
            TeacherRoleArn='arn:aws:iam::170126527713:role/LabRole')
        artifact_stack='jdu-web-portal-status-artifacts'
        stack_name='jdu-web-portal-check-'+state['lab_id']
        expected={'Results':'AWS::DynamoDB::Table','Checker':'AWS::Lambda::Function','Logs':'AWS::Logs::LogGroup','TeacherInvoke':'AWS::Lambda::Permission'}
    else:
        services=cfn.describe_stacks(StackName='jdu-web-portal-services-20261029')['Stacks'][0]
        outputs={v['OutputKey']:v['OutputValue'] for v in services['Outputs']}
        env=boto3.client('lambda',region_name='us-east-1').get_function_configuration(FunctionName=outputs['GradeReaderArn'])['Environment']['Variables']
        parameters.update(SubjectKeyArn=env['PORTAL_SUBJECT_KEY_SECRET_ARN'],BindingTable=env['PORTAL_BINDING_TABLE'],GradeTable=env['GRADE_TABLE'])
        artifact_stack='jdu-web-portal-web-artifacts-20261029'
        stack_name='jdu-web-portal-checker-20261029'
        expected={'Checker':'AWS::Lambda::Function','Logs':'AWS::Logs::LogGroup'}
    artifact=cfn.describe_stacks(StackName=artifact_stack)['Stacks'][0]
    outputs={v['OutputKey']:v['OutputValue'] for v in artifact['Outputs']}
    bucket=outputs['BucketName']
    owner={'Bucket':bucket,'ExpectedBucketOwner':account}
    if not all(s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration'].values()) or s3.get_bucket_versioning(**owner).get('Status')!='Enabled':
        raise ValueError('Protected versioned source required')
    code=code_path.read_bytes();digest=hashlib.sha256(code).hexdigest();object_key='checks/'+digest+'/checks.zip'
    # Unique content key + version; reruns recover only the same bytes.
    try:
        uploaded=s3.put_object(**owner,Key=object_key,Body=code,ServerSideEncryption='AES256',IfNoneMatch='*')
        version=uploaded['VersionId']
    except s3.exceptions.ClientError as exc:
        if exc.response.get('Error',{}).get('Code') not in ('PreconditionFailed','412'):
            raise
        version=s3.head_object(**owner,Key=object_key)['VersionId']
    if hashlib.sha256(s3.get_object(**owner,Key=object_key,VersionId=version)['Body'].read(len(code)+1)).hexdigest()!=digest:
        raise ValueError('Source differs')
    parameters.update(ArtifactBucket=bucket,ArtifactKey=object_key,ArtifactVersion=version)
    template=(HERE/(side+'-checker.template.json')).read_text(encoding='utf-8')
    cfn.validate_template(TemplateBody=template)
    plan=cfn.create_change_set(StackName=stack_name,ChangeSetName='browser-checks-'+digest[:12],ChangeSetType='CREATE',
        TemplateBody=template,Parameters=[{'ParameterKey':k,'ParameterValue':v} for k,v in parameters.items()],Tags=[{'Key':'Purpose','Value':'web-course-browser-checks'}])
    with receipt.open('x',encoding='utf-8') as f:
        json.dump({'account':account,'side':side,'stack_id':plan['StackId'],'change_set_id':plan['Id'],
            'code_sha256':digest,'template_sha256':hashlib.sha256(template.encode()).hexdigest(),'expected_adds':expected},f,indent=2)
    cfn.get_waiter('change_set_create_complete').wait(ChangeSetName=plan['Id'],WaiterConfig={'Delay':5,'MaxAttempts':24})
    check=cfn.describe_change_set(ChangeSetName=plan['Id'])
    rows=[v['ResourceChange'] for v in check['Changes']]
    if check['Status']!='CREATE_COMPLETE' or check['ExecutionStatus']!='AVAILABLE' or {r['LogicalResourceId']:r['ResourceType'] for r in rows}!=expected or any(r['Action']!='Add' for r in rows):
        raise ValueError('Unexpected additions; not executed')
    print(json.dumps({'marker':'CHECKER_PLAN_READY','side':side,'account':account,'resources':expected,'code_sha256':digest,'executed':False}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('side',choices=ACCOUNTS)
    p.add_argument('--code',type=Path,required=True)
    p.add_argument('--command-state',type=Path,default=Path.home()/'.jdu-web-student/command-state.json')
    p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args()
    try:
        prepare(a.side,a.code,a.command_state,a.receipt)
    except Exception as exc:
        print('CHECKER_PLAN_NOT_CONFIRMED='+type(exc).__name__,flush=True)
        raise SystemExit(2) from None
