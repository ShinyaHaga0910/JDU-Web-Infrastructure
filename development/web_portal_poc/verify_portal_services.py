"""Read-only teacher CloudShell acceptance; never print secret/identity rows.

Checks the actually approved immutable package, not the newest local source.
Unregistered synthetic identities must fail closed. This is not Google/AWS
enrollment acceptance and does not authorize any real student assignment.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from botocore.exceptions import ClientError

from prepare_portal_services import ACCOUNT, ADDITIONS


def verify(created,baseline,clients):
    sts,cfn,lam,secrets,db,ec2=clients
    if sts.get_caller_identity()['Account']!=ACCOUNT or created.get('phase') not in ('private-services-created','private-services-updated'):
        raise ValueError('Wrong acceptance context')
    stack=cfn.describe_stacks(StackName=created['stack_id'])['Stacks'][0]
    resources=cfn.list_stack_resources(StackName=created['stack_id'])
    if (stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE') or resources.get('NextToken')
            or {r['LogicalResourceId']:r['ResourceType'] for r in resources['StackResourceSummaries']}!=ADDITIONS):
        raise ValueError('Unexpected deployed resources')
    outputs={v['OutputKey']:v['OutputValue'] for v in stack['Outputs']}
    if outputs!=created['outputs']:
        raise ValueError('Deployed outputs changed')
    for label in ('EnrollmentArn','GradeReaderArn'):
        arn=outputs[label]
        if not arn.startswith(f'arn:aws:lambda:us-east-1:{ACCOUNT}:function:'):
            raise ValueError('Wrong service account')
        config=lam.get_function_configuration(FunctionName=arn)
        if (config['State']!='Active' or config['Role']!=f'arn:aws:iam::{ACCOUNT}:role/LabRole'
                or base64.b64decode(config['CodeSha256']).hex()!=created['code_sha256']):
            raise ValueError('Unexpected deployed code or role')
        for operation in (lam.get_function_url_config,lam.get_policy):
            try:operation(FunctionName=arn)
            except ClientError as exc:
                if exc.response['Error']['Code']!='ResourceNotFoundException':raise
            else:raise ValueError('Unexpected public URL or resource policy')
    secret=secrets.describe_secret(SecretId=outputs['SubjectKeySecretArn'])
    if (secret['ARN']!=outputs['SubjectKeySecretArn'] or secret['Name']!='jdu/web-portal/class193548-20261029/subject-key'
            or secret.get('DeletedDate') or secret.get('KmsKeyId')):
        raise ValueError('Unexpected key metadata')
    probe=lam.get_function_configuration(FunctionName=baseline['function_arn'])
    env=probe['Environment']['Variables']
    def fingerprint():
        rows=[row for page in db.get_paginator('query').paginate(TableName=env['GRADE_TABLE'],
            KeyConditionExpression='pk=:p',ExpressionAttributeValues={':p':{'S':'LAB#'+env['LAB_ID']}},ConsistentRead=True)
            for row in page.get('Items',[])]
        return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def invoke(arn,event):
        answer=lam.invoke(FunctionName=arn,InvocationType='RequestResponse',Payload=json.dumps(event).encode())
        raw=answer['Payload'].read(65537)
        if answer.get('FunctionError') or answer['StatusCode']!=200 or len(raw)>65536:
            raise ValueError('Acceptance invocation failed')
        return json.loads(raw)
    if fingerprint()!=baseline['partition_sha256']:
        raise ValueError('Original partition changed')
    grade=invoke(baseline['function_arn'],{'operation':'grade'})
    if grade!={'status':'ok','grade':baseline['grade']}:
        raise ValueError('Original grade changed')
    synthetic={'operation':'status','subject':'0','email':'unapproved-smoke-test@jdu.uz','session_id':'0'*64,'token_hash':'0'*64}
    if (invoke(outputs['EnrollmentArn'],synthetic)!={'status':'unauthorized'}
            or invoke(outputs['EnrollmentArn'],{'operation':'approve'})!={'status':'unauthorized'}
            or invoke(outputs['GradeReaderArn'],{'subject':'0'})!={'status':'unauthorized'}):
        raise ValueError('Unregistered request was not denied')
    if fingerprint()!=baseline['partition_sha256']:
        raise ValueError('Original partition changed during verification')
    state=ec2.describe_instances(InstanceIds=['i-019c24636eec3a5d0'])['Reservations'][0]['Instances'][0]['State']['Name']
    if state!='stopped':raise ValueError('Teacher EC2 state changed')
    return {'verified_at':datetime.now(timezone.utc).isoformat(),'stack_status':stack['StackStatus'],
        'code_sha256':created['code_sha256'],'private_functions_verified':2,'new_resources_verified':5,
        'no_function_urls_or_resource_policies':True,'key_metadata_verified_without_reading_value':True,
        'unregistered_synthetic_requests_denied':True,'approve_operation_not_exposed':True,
        'full_grade_projection_unchanged':True,'whole_lab_partition_unchanged':True,'teacher_ec2':'stopped',
        'web_configuration_changed_by_verifier':False,'real_identity_enrollment_tested':False}


if __name__=='__main__':
    import argparse
    import boto3
    parser=argparse.ArgumentParser()
    parser.add_argument('--created',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=verify(json.loads(args.created.read_text()),json.loads(args.baseline.read_text()),
            [boto3.client(n,region_name='us-east-1') for n in ('sts','cloudformation','lambda','secretsmanager','dynamodb','ec2')])
        print(json.dumps(result,sort_keys=True))
    except Exception:
        raise SystemExit('PRIVATE_SERVICES_ACCEPTANCE_NOT_CONFIRMED: no resources or grades changed') from None
