"""Plan/apply a separate private template bucket and one student read grant.

The default prepares an unexecuted change set only. Apply requires a concrete
operator approval for the new cross-account read access; code has no secrets.
Existing artifacts, identity approvals, EC2 and grades are not modified.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from botocore.exceptions import ClientError
from prepare_portal_services import ACCOUNT,private_write

STUDENT='965244652544'
STACK='jdu-web-portal-browser-link-20261029'
CHANGE='assigned-student-template'
ADDITIONS={'BootstrapBucket':'AWS::S3::Bucket','AssignedStudentRead':'AWS::S3::BucketPolicy'}


def inspect(change):
    rows=[v.get('ResourceChange',{}) for v in change.get('Changes',[])]
    if (change.get('Status')!='CREATE_COMPLETE' or change.get('ExecutionStatus')!='AVAILABLE' or len(rows)!=2
            or {v.get('LogicalResourceId'):v.get('ResourceType') for v in rows}!=ADDITIONS
            or any(v.get('Action')!='Add' for v in rows)):
        raise ValueError('Unexpected publication changes')


def prepare(directory,receipt,sts,cfn):
    if sts.get_caller_identity()['Account']!=ACCOUNT or receipt.exists():raise ValueError('Wrong context or existing plan')
    try:cfn.describe_stacks(StackName=STACK)
    except ClientError as error:
        if error.response['Error'].get('Code')!='ValidationError' or error.response['Error'].get('Message')!=f'Stack with id {STACK} does not exist':raise
    else:raise ValueError('Inspect existing publication instead of recreating it')
    code=(directory/'account-link.template.json').read_bytes()
    digest=hashlib.sha256(code).hexdigest()
    definition=(directory/'browser-link-artifacts.template.json').read_text(encoding='utf-8')
    parsed=json.loads(code)
    if (len(parsed['Resources'])!=3 or set(parsed['Parameters'])!={'PairId','ExpectedAccount','LabId'}
            or {v['Type'] for v in parsed['Resources'].values()}!={'AWS::Lambda::Function','AWS::Logs::LogGroup','Custom::JduPortalAccountLink'}):
        raise ValueError('Unexpected student template')
    cfn.validate_template(TemplateBody=code.decode())
    cfn.validate_template(TemplateBody=definition)
    parameters={'StudentAccount':STUDENT,'TemplateDigest':digest,'PublicationId':digest[:12]}
    start={'phase':'preparation-started','account':ACCOUNT,'student_account':STUDENT,'template_sha256':digest,
        'publication_definition_sha256':hashlib.sha256(definition.encode()).hexdigest(),'parameters':parameters}
    private_write(receipt,start)
    request=cfn.create_change_set(StackName=STACK,ChangeSetName=CHANGE,ChangeSetType='CREATE',TemplateBody=definition,
        Parameters=[{'ParameterKey':k,'ParameterValue':v} for k,v in parameters.items()],Tags=[{'Key':'Purpose','Value':'portal-browser-account-link'}])
    cfn.get_waiter('change_set_create_complete').wait(ChangeSetName=request['Id'],StackName=request['StackId'],WaiterConfig={'Delay':5,'MaxAttempts':24})
    inspect(cfn.describe_change_set(ChangeSetName=request['Id'],StackName=request['StackId']))
    private_write(receipt.with_name('browser-link.ready.private.json'),{**start,'phase':'publication-ready-not-executed',
        'change_set_id':request['Id'],'stack_id':request['StackId']})
    print(json.dumps({'marker':'BROWSER_LINK_PUBLICATION_PLAN_READY','executed':False,'new_resources':2,
        'student_account':STUDENT,'public_read_access':False,'template_sha256':digest}),flush=True)


def apply(directory,plan,receipt,sts,cfn,s3):
    if (sts.get_caller_identity()['Account']!=ACCOUNT or plan.get('account')!=ACCOUNT
            or plan.get('student_account')!=STUDENT or plan.get('phase')!='publication-ready-not-executed'):
        raise ValueError('Wrong publication context')
    requested=receipt.with_name('browser-link.apply-requested.private.json')
    if requested.exists():raise ValueError('Inspect previous execution before repeating')
    code=(directory/'account-link.template.json').read_bytes()
    definition=(directory/'browser-link-artifacts.template.json').read_bytes()
    if (hashlib.sha256(code).hexdigest()!=plan['template_sha256']
            or hashlib.sha256(definition).hexdigest()!=plan['publication_definition_sha256']):raise ValueError('Publication source changed')
    change=cfn.describe_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'])
    inspect(change)
    if {v['ParameterKey']:v['ParameterValue'] for v in change['Parameters']}!=plan['parameters']:
        raise ValueError('Student or publication scope changed')
    original=cfn.get_template(StackName=plan['stack_id'],ChangeSetName=plan['change_set_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(original,str):original=json.loads(original)
    if original!=json.loads(definition):raise ValueError('Policy template differs')
    private_write(requested,{'phase':'execute-request-recorded','change_set_id':plan['change_set_id']})
    cfn.execute_change_set(ChangeSetName=plan['change_set_id'],StackName=plan['stack_id'],
        ClientRequestToken='browser-template-'+plan['template_sha256'][:40])
    print('BROWSER_LINK_PUBLICATION_CREATE_REQUESTED',flush=True)
    cfn.get_waiter('stack_create_complete').wait(StackName=plan['stack_id'],WaiterConfig={'Delay':5,'MaxAttempts':60})
    stack=cfn.describe_stacks(StackName=plan['stack_id'])['Stacks'][0]
    bucket={v['OutputKey']:v['OutputValue'] for v in stack['Outputs']}['BucketName']
    expected=f'jdu-web-portal-bootstrap-{ACCOUNT}-{plan["template_sha256"][:12]}'
    if bucket!=expected:raise ValueError('Publication owner differs')
    owner={'Bucket':bucket,'ExpectedBucketOwner':ACCOUNT}
    block=s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration']
    if (not all(block.get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'))
            or s3.get_bucket_versioning(**owner).get('Status')!='Enabled'
            or s3.get_bucket_policy_status(**owner)['PolicyStatus']['IsPublic'] is not False):
        raise ValueError('Publication access protection differs')
    actual=json.loads(s3.get_bucket_policy(**owner)['Policy'])
    expected_statement={'Sid':'AssignedStudentTemplateReadOnly','Effect':'Allow','Principal':{'AWS':f'arn:aws:iam::{STUDENT}:root'},
        'Action':['s3:GetObject','s3:GetObjectVersion'],'Resource':f'arn:aws:s3:::{bucket}/bootstrap/{plan["template_sha256"]}/account-link.template.json',
        'Condition':{'Bool':{'aws:SecureTransport':'true'}}}
    statements=actual.get('Statement',[])
    if len(statements)!=1:raise ValueError('Published grant differs')
    statement=dict(statements[0]);actions=statement.pop('Action',None)
    expected_actions=expected_statement.pop('Action')
    if type(actions) is not list or set(actions)!=set(expected_actions) or statement!=expected_statement:
        raise ValueError('Published grant differs')
    key=f'bootstrap/{plan["template_sha256"]}/account-link.template.json'
    uploaded=s3.put_object(**owner,Key=key,Body=code,IfNoneMatch='*',ServerSideEncryption='AES256',ContentType='application/json',
        ChecksumSHA256=base64.b64encode(hashlib.sha256(code).digest()).decode(),Metadata={'sha256':plan['template_sha256']})
    version=uploaded.get('VersionId')
    if not version or version=='null':raise ValueError('Immutable publication version required')
    read=s3.get_object(**owner,Key=key,VersionId=version)['Body'].read(len(code)+1)
    if hashlib.sha256(read).hexdigest()!=plan['template_sha256']:raise ValueError('Published version differs')
    url=f'https://{bucket}.s3.us-east-1.amazonaws.com/{key}?versionId='+quote(version,safe='')
    private_write(receipt.with_name('browser-link.published.private.json'),{**plan,'phase':'published-for-assigned-student',
        'bucket':bucket,'key':key,'version':version,'template_url':url,'public_read_access':False})
    print(json.dumps({'marker':'BROWSER_LINK_PUBLICATION_COMPLETE','student_account':STUDENT,'public_read_access':False,
                      'template_sha256':plan['template_sha256']}),flush=True)


if __name__=='__main__':
    import boto3
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    try:
        sts,cfn,s3=[boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3')]
        if args.apply:apply(args.directory,json.loads(args.receipt.read_text()),args.receipt,sts,cfn,s3)
        else:prepare(args.directory,args.receipt,sts,cfn)
    except Exception:
        raise SystemExit('BROWSER_LINK_PUBLICATION_NOT_CONFIRMED: inspect receipts; no automatic retry or permission widening') from None
