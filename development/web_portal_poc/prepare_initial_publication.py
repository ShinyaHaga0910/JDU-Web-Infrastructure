"""Reuse the private template bucket for one immutable initial-worker object.

Default: upload source and prepare one policy change, without executing it.
Apply only after operator approval of that concrete cross-account read grant.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile
from botocore.exceptions import ClientError

from prepare_portal_services import ACCOUNT,private_write
from prepare_browser_link_publication import STACK,STUDENT

HERE=Path(__file__).resolve().parent


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def statement(bucket,worker=None,template=None):
    return {'Sid':'AssignedStudentInitialWorkerReadOnly' if worker else 'AssignedStudentTemplateReadOnly',
        'Effect':'Allow','Principal':{'AWS':'arn:aws:iam::'+STUDENT+':root'},
        'Action':['s3:GetObject','s3:GetObjectVersion'],
        'Resource':'arn:aws:s3:::'+bucket+('/worker/'+worker+'/initial-worker.zip' if worker else '/bootstrap/'+template+'/account-link.template.json'),
        'Condition':{'Bool':{'aws:SecureTransport':'true'}}}


def proposal(original,parameters,digest):
    expected=json.loads((HERE/'browser-link-artifacts.template.json').read_bytes())
    if (original!=expected or set(parameters)!={'StudentAccount','TemplateDigest','PublicationId'}
            or parameters['StudentAccount']!=STUDENT
            or not re.fullmatch(r'[a-f0-9]{64}',parameters['TemplateDigest'])
            or parameters['PublicationId']!=parameters['TemplateDigest'][:12]
            or not re.fullmatch(r'[a-f0-9]{64}',digest)):
        raise ValueError('Original narrow publication required')
    value=copy.deepcopy(original)
    value['Parameters']['WorkerDigest']={'Type':'String','AllowedPattern':'[a-f0-9]{64}'}
    added=statement('BUCKET',worker='DIGEST')
    added['Principal']={'AWS':{'Fn::Sub':'arn:aws:iam::${StudentAccount}:root'}}
    added['Resource']={'Fn::Sub':'${BootstrapBucket.Arn}/worker/${WorkerDigest}/initial-worker.zip'}
    value['Resources']['AssignedStudentRead']['Properties']['PolicyDocument']['Statement'].append(added)
    return value


def inspect(value):
    rows=[x.get('ResourceChange',{}) for x in value.get('Changes',[])]
    if (value.get('Status')!='CREATE_COMPLETE' or value.get('ExecutionStatus')!='AVAILABLE' or len(rows)!=1
            or rows[0].get('LogicalResourceId')!='AssignedStudentRead' or rows[0].get('ResourceType')!='AWS::S3::BucketPolicy'
            or rows[0].get('Action')!='Modify' or rows[0].get('Replacement') not in ('False',False)
            or not rows[0].get('Details')
            or any(x.get('Target',{}).get('Name')!='PolicyDocument' for x in rows[0]['Details'])):
        raise ValueError('Only the existing policy document may change')


def original(clients):
    sts,cfn,s3=clients
    if sts.get_caller_identity()['Account']!=ACCOUNT:raise ValueError('Wrong teacher account')
    stack=cfn.describe_stacks(StackName=STACK)['Stacks'][0]
    if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):raise ValueError('Publication unavailable')
    parameters={x['ParameterKey']:x['ParameterValue'] for x in stack['Parameters']}
    bucket={x['OutputKey']:x['OutputValue'] for x in stack['Outputs']}['BucketName']
    if bucket!='jdu-web-portal-bootstrap-'+ACCOUNT+'-'+parameters.get('PublicationId',''):
        raise ValueError('Original publication owner changed')
    owner={'Bucket':bucket,'ExpectedBucketOwner':ACCOUNT}
    protection=s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration']
    if (not all(protection.get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'))
            or s3.get_bucket_versioning(**owner).get('Status')!='Enabled'
            or s3.get_bucket_policy_status(**owner)['PolicyStatus']['IsPublic'] is not False):
        raise ValueError('Original publication protection changed')
    policy=json.loads(s3.get_bucket_policy(**owner)['Policy'])
    if policy!={'Version':'2012-10-17','Statement':[statement(bucket,template=parameters['TemplateDigest'])]}:
        raise ValueError('Inspect existing publication grant instead of overwriting it')
    template=cfn.get_template(StackName=STACK,TemplateStage='Original')['TemplateBody']
    if isinstance(template,str):template=json.loads(template)
    return stack,parameters,bucket,policy,template


def prepare(worker,digest,receipt,clients):
    if receipt.exists():raise ValueError('Inspect existing preparation receipt')
    raw=worker.read_bytes()
    if sha(raw)!=digest:raise ValueError('Reviewed worker differs')
    with ZipFile(worker) as archive:
        if len(archive.namelist())>100 or any(Path(n).name!=n for n in archive.namelist()):raise ValueError('Flat reviewed worker required')
        config=json.loads(archive.read('initial-assignment.json'))
        if config['assignment']['account']!=STUDENT or config['initial_state']!='foundation_only':
            raise ValueError('Assigned student foundation worker required')
    stack,params,bucket,policy,template=original(clients)
    proposed=proposal(template,params,digest)
    sts,cfn,s3=clients;owner={'Bucket':bucket,'ExpectedBucketOwner':ACCOUNT};key='worker/'+digest+'/initial-worker.zip'
    start={'phase':'initial-worker-publication-started','account':ACCOUNT,'student':STUDENT,'stack_id':stack['StackId'],
        'worker_sha256':digest,'previous_template_sha256':sha(canonical(template)),'previous_parameters':params,
        'previous_policy':policy,'proposed_template':proposed,'bucket':bucket,'key':key}
    private_write(receipt,start)
    try:
        stored=s3.put_object(**owner,Key=key,Body=raw,IfNoneMatch='*',ServerSideEncryption='AES256',
            ChecksumSHA256=base64.b64encode(hashlib.sha256(raw).digest()).decode(),Metadata={'sha256':digest})
    except ClientError as error:
        if error.response['Error'].get('Code') not in ('PreconditionFailed','412'):raise
        stored=s3.head_object(**owner,Key=key)
    version=stored.get('VersionId')
    if not version or version=='null':raise ValueError('Immutable object version required')
    body=s3.get_object(**owner,Key=key,VersionId=version)['Body']
    try:fetched=body.read(len(raw)+1)
    finally:body.close()
    if sha(fetched)!=digest:raise ValueError('Uploaded worker differs')
    cfn.validate_template(TemplateBody=canonical(proposed).decode())
    change=cfn.create_change_set(StackName=stack['StackId'],ChangeSetName='initial-worker-read-'+digest[:12],ChangeSetType='UPDATE',
        TemplateBody=canonical(proposed).decode(),
        Parameters=[{'ParameterKey':k,'UsePreviousValue':True} for k in params]+[{'ParameterKey':'WorkerDigest','ParameterValue':digest}])
    cfn.get_waiter('change_set_create_complete').wait(StackName=stack['StackId'],ChangeSetName=change['Id'],WaiterConfig={'Delay':5,'MaxAttempts':24})
    inspect(cfn.describe_change_set(StackName=stack['StackId'],ChangeSetName=change['Id']))
    plan={**start,'phase':'initial-worker-publication-ready','version':version,'change_set_id':change['Id']}
    private_write(receipt.with_name(receipt.stem+'.ready.json'),plan)
    print(json.dumps({'marker':'INITIAL_WORKER_PUBLICATION_PLAN_READY','executed':False,'new_resources':0,
        'policy_modifications':1,'student':STUDENT,'worker_sha256':digest,'public_read_access':False}))


def apply(plan,receipt,clients):
    if plan.get('phase')!='initial-worker-publication-ready' or plan.get('account')!=ACCOUNT or plan.get('student')!=STUDENT:
        raise ValueError('Reviewed publication plan required')
    requested=receipt.with_name(receipt.stem+'.apply-requested.json')
    if requested.exists():raise ValueError('Inspect prior execution instead of repeating it')
    stack,params,bucket,policy,template=original(clients)
    if (stack['StackId']!=plan['stack_id'] or params!=plan['previous_parameters'] or bucket!=plan['bucket']
            or policy!=plan['previous_policy'] or sha(canonical(template))!=plan['previous_template_sha256']
            or proposal(template,params,plan['worker_sha256'])!=plan['proposed_template']):
        raise ValueError('Publication plan changed')
    sts,cfn,s3=clients
    change=cfn.describe_change_set(StackName=stack['StackId'],ChangeSetName=plan['change_set_id']);inspect(change)
    if {x['ParameterKey']:x['ParameterValue'] for x in change['Parameters']}!={**params,'WorkerDigest':plan['worker_sha256']}:
        raise ValueError('Publication parameters changed')
    proposed=cfn.get_template(StackName=stack['StackId'],ChangeSetName=plan['change_set_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(proposed,str):proposed=json.loads(proposed)
    if proposed!=plan['proposed_template']:raise ValueError('Prepared policy changed')
    body=s3.get_object(Bucket=bucket,Key=plan['key'],VersionId=plan['version'],ExpectedBucketOwner=ACCOUNT)['Body']
    try:raw=body.read(4*1024*1024+1)
    finally:body.close()
    if sha(raw)!=plan['worker_sha256']:raise ValueError('Immutable worker changed')
    private_write(requested,{'change_set_id':plan['change_set_id'],'phase':'execute-request-recorded'})
    cfn.execute_change_set(StackName=stack['StackId'],ChangeSetName=plan['change_set_id'],ClientRequestToken='initial-worker-'+plan['worker_sha256'][:40])
    cfn.get_waiter('stack_update_complete').wait(StackName=stack['StackId'],WaiterConfig={'Delay':5,'MaxAttempts':60})
    actual=json.loads(s3.get_bucket_policy(Bucket=bucket,ExpectedBucketOwner=ACCOUNT)['Policy'])
    if actual!={'Version':'2012-10-17','Statement':policy['Statement']+[statement(bucket,worker=plan['worker_sha256'])]}:
        raise ValueError('Inspect applied policy')
    private_write(receipt.with_name(receipt.stem+'.applied.json'),{**plan,'phase':'initial-worker-publication-applied'})
    print(json.dumps({'marker':'INITIAL_WORKER_PUBLICATION_APPLIED','policy_modifications':1,'new_resources':0}))


if __name__=='__main__':
    import boto3
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker',type=Path);p.add_argument('--sha256');p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    clients=[boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','s3')]
    if a.apply:apply(json.loads(a.receipt.read_bytes()),a.receipt,clients)
    elif a.worker and a.sha256:prepare(a.worker,a.sha256,a.receipt,clients)
    else:p.error('Worker and reviewed SHA256 required for preparation')
