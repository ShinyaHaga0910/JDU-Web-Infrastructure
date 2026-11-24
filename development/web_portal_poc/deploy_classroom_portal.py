"""Deploy the assignment portal separately from the existing classroom stacks."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from botocore.exceptions import ClientError

from web.build_web_package import build

HERE = Path(__file__).resolve().parent
REGION = 'us-east-1'
STACK = 'jdu-web-infrastructure-portal'
TEACHER = 'jdu-web-infrastructure-teacher'
FUNCTION = STACK


def read_stack(cfn, name):
    try:
        return cfn.describe_stacks(StackName=name)['Stacks'][0]
    except ClientError as error:
        info = error.response['Error']
        if info['Code'] == 'ValidationError' and info['Message'] == f'Stack with id {name} does not exist':
            return None
        raise


def outputs(stack):
    return {row['OutputKey']: row['OutputValue'] for row in stack.get('Outputs', [])}


def stack_parameters(stack):
    return {row['ParameterKey']: row['ParameterValue'] for row in stack.get('Parameters', [])}


def apply_stack(cfn, name, template, values, *, update=False):
    if name != STACK and not name.startswith(STACK + '-'):
        raise ValueError('Unexpected portal stack')
    current = read_stack(cfn, name)
    if current and current['StackStatus'] in ('CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'):
        waiter = 'stack_create_complete' if current['StackStatus'] == 'CREATE_IN_PROGRESS' else 'stack_update_complete'
        cfn.get_waiter(waiter).wait(StackName=current['StackId'])
        current = read_stack(cfn, name)
    if current and current.get('StackStatus') not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
        raise ValueError(f'{name}: {current["StackStatus"]}')
    if current:
        if not any(tag['Key'] == 'JduComponent' and tag['Value'] == 'ClassroomPortal' for tag in current.get('Tags', [])):
            raise ValueError(f'{name}: stack is not owned by this installer')
        old = cfn.get_template(StackName=name, TemplateStage='Original')['TemplateBody']
        if isinstance(old, str):
            old = json.loads(old)
        if old == template and all(stack_parameters(current).get(key) == value for key, value in values.items()):
            return outputs(current)
        if not update:
            raise ValueError(f'{name}: existing stack configuration differs')

    body = json.dumps(template, separators=(',', ':'))
    cfn.validate_template(TemplateBody=body)
    request = dict(StackName=name, TemplateBody=body, Parameters=[
        {'ParameterKey': key, 'ParameterValue': value} for key, value in values.items()])
    print(f'CloudFormation: {name}', flush=True)
    if current:
        response = cfn.update_stack(**request)
        waiter = 'stack_update_complete'
    else:
        response = cfn.create_stack(**request, Tags=[{'Key': 'JduComponent', 'Value': 'ClassroomPortal'}])
        waiter = 'stack_create_complete'
    cfn.get_waiter(waiter).wait(StackName=response['StackId'])
    return outputs(read_stack(cfn, response['StackId']))


def template(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def publish(s3, account, bucket, prefix, name, contents, content_type):
    digest = hashlib.sha256(contents).hexdigest()
    checksum = base64.b64encode(bytes.fromhex(digest)).decode()
    location = dict(Bucket=bucket, Key=f'{prefix}/{digest}/{name}', ExpectedBucketOwner=account)
    try:
        s3.put_object(**location, Body=contents, ChecksumSHA256=checksum, IfNoneMatch='*',
                      ContentType=content_type, ServerSideEncryption='AES256')
    except ClientError as error:
        if error.response['Error']['Code'] not in ('PreconditionFailed', '412'):
            raise
    receipt = s3.head_object(**location, ChecksumMode='ENABLED')
    version = receipt.get('VersionId')
    if not version or version == 'null' or receipt.get('ChecksumSHA256') != checksum:
        raise ValueError('Could not verify the versioned code package')
    return {'ArtifactBucket': bucket, 'ArtifactKey': location['Key'], 'ArtifactVersion': version}


def get_portal_url(stack):
    origin = outputs(stack).get('PortalUrl', '')
    if not re.fullmatch(r'https://[a-z0-9]{10,64}\.[a-z0-9]{2,16}\.lambda-web\.us-east-1\.on\.aws', origin):
        raise ValueError('PortalUrl is missing or does not match the AWS Web Function endpoint')
    return origin


def prepare(session, account, revision):
    cfn = session.client('cloudformation')
    existing = read_stack(cfn, STACK)
    if existing and existing['StackStatus'] in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
        if not any(tag['Key'] == 'JduComponent' and tag['Value'] == 'ClassroomPortal' for tag in existing.get('Tags', [])):
            raise ValueError('The existing portal belongs to a different installer')
        return get_portal_url(existing)
    if not read_stack(cfn, TEACHER):
        raise ValueError('Teacher foundation stack was not found in this account')
    artifact = apply_stack(cfn, STACK + '-artifacts', template('web/web-artifacts.template.json'),
                           {'WebFunctionName': FUNCTION})
    with TemporaryDirectory() as work:
        archive = Path(work) / 'portal-web.zip'
        build(archive)
        code = publish(session.client('s3'), account, artifact['BucketName'], 'portal', archive.name,
                       archive.read_bytes(), 'application/zip')
    apply_stack(cfn, STACK, template('web/portal-web.template.json'), {
        **code, 'WebFunctionName': FUNCTION, 'ReleaseId': revision,
        'LabRoleArn': f'arn:aws:iam::{account}:role/LabRole',
    })
    return get_portal_url(read_stack(cfn, STACK))


def main():
    import boto3

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('portal-prepare',))
    parser.add_argument('--ref', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.ref):
        raise ValueError('Expected a Git commit')
    session = boto3.Session(region_name=REGION)
    account = session.client('sts').get_caller_identity()['Account']
    if not re.fullmatch(r'[0-9]{12}', account):
        raise ValueError('Unexpected AWS account')
    origin = prepare(session, account, args.ref)
    print(f'PortalUrl: {origin}')
    print(f'Google OAuth redirect URI: {origin}/auth/callback')


if __name__ == '__main__':
    main()

