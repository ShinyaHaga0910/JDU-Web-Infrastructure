"""CloudShell-only student status connector preparation and explicit application.

Reads retained private state in CloudShell; never prints/copies its contents.
Default mode makes no AWS changes. --apply creates two isolated stacks: a
private artifact bucket and the read-only Lambda plus approved teacher grant.
Existing student servers, keys, grades, security groups and LabRole are never
changed. No resource is deleted, overwritten or automatically rolled back here.
"""
import argparse
import json
from pathlib import Path
import tempfile

from botocore.exceptions import ClientError

from build_status_package import build
from plan_student_status import plan
from status import ROLES

HERE = Path(__file__).resolve().parent
ARTIFACT_STACK = 'jdu-web-portal-status-artifacts'
PURPOSE = 'web-portal-status-poc'


def artifact_stack(cfn):
    try:
        stacks = cfn.describe_stacks(StackName=ARTIFACT_STACK)['Stacks']
    except ClientError as exc:
        error = exc.response.get('Error', {})
        if error.get('Code') == 'ValidationError' and error.get('Message') == f'Stack with id {ARTIFACT_STACK} does not exist':
            return None
        raise
    if len(stacks) != 1 or {v['Key']: v['Value'] for v in stacks[0].get('Tags', [])}.get('Purpose') != PURPOSE:
        raise ValueError('artifact stack ownership not established')
    if stacks[0].get('StackStatus') != 'CREATE_COMPLETE':
        raise ValueError('inspect existing artifact stack before continuing')
    return stacks[0]


def prepare(state, baseline, expected_account, teacher_account, clients):
    sts, cfn, ec2, ssm, lam, s3 = clients
    result = plan(state, baseline, expected_account, teacher_account, sts, cfn, ec2, ssm, lam)
    retained = artifact_stack(cfn)
    if retained:
        bucket = {v['OutputKey']: v['OutputValue'] for v in retained.get('Outputs', [])}['BucketName']
        owner = {'Bucket': bucket, 'ExpectedBucketOwner': expected_account}
        block = s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration']
        if (any(block.get(k) is not True for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets'))
                or s3.get_bucket_versioning(**owner).get('Status') != 'Enabled'):
            raise ValueError('artifact bucket protection differs')
    with tempfile.TemporaryDirectory() as directory:
        package = Path(directory) / 'status.zip'
        digest = build(package)
        code = package.read_bytes()
    result.update({'artifact_stack': ARTIFACT_STACK, 'artifact_stack_exists': retained is not None,
                   'code_sha256': digest, 'code_bytes': len(code),
                   'new_resources': ['private versioned S3 bucket (unless retained)', 'status Lambda with existing LabRole',
                                     'invoke permission for the specified teacher LabRole'],
                   'public_endpoint': False})
    parameters = {'StudentRoleArn': f'arn:aws:iam::{expected_account}:role/LabRole',
                  'TeacherRoleArn': result['teacher_role'], 'LabId': baseline['lab_id'],
                  'DeploymentId': baseline['deployment_id'], 'StudentStackArn': baseline['stack_id']}
    parameters.update({label + 'Instance': baseline['nodes'][role]['instance_id'] for role, label in ROLES.items()})
    return result, parameters, retained, code


def apply(prepared, clients):
    """Only call after the operator confirms the concrete prepared addition."""
    result, parameters, retained, code = prepared
    _, cfn, _, _, _, s3 = clients
    if retained is None:
        created = cfn.create_stack(StackName=ARTIFACT_STACK,
            TemplateBody=(HERE / 'status-artifacts.template.json').read_text(encoding='utf-8'),
            Tags=[{'Key': 'Purpose', 'Value': PURPOSE}])
        print('ARTIFACT_STACK_CREATE_REQUESTED', flush=True)
        cfn.get_waiter('stack_create_complete').wait(StackName=created['StackId'])
        retained = artifact_stack(cfn)
    bucket = {v['OutputKey']: v['OutputValue'] for v in retained['Outputs']}['BucketName']
    uploaded = s3.put_object(Bucket=bucket, ExpectedBucketOwner=result['account'],
        Key='status/' + result['code_sha256'] + '.zip', Body=code, ServerSideEncryption='AES256',
        Metadata={'sha256': result['code_sha256']})
    version = uploaded.get('VersionId')
    if not isinstance(version, str) or version in ('', 'null'):
        raise ValueError('versioned artifact required; no function created')
    parameters.update({'ArtifactBucket': bucket, 'ArtifactKey': 'status/' + result['code_sha256'] + '.zip',
                       'ArtifactVersion': version})
    created = cfn.create_stack(StackName=result['stack_name'],
        TemplateBody=(HERE / 'student-status.template.json').read_text(encoding='utf-8'),
        Parameters=[{'ParameterKey': k, 'ParameterValue': v} for k, v in parameters.items()],
        Tags=[{'Key': 'Purpose', 'Value': PURPOSE}, {'Key': 'LabId', 'Value': result['lab_id']}])
    print('STUDENT_STATUS_STACK_CREATE_REQUESTED', flush=True)
    cfn.get_waiter('stack_create_complete').wait(StackName=created['StackId'])
    print('STUDENT_STATUS_STACK_CREATE_COMPLETE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--teacher-account', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    import boto3
    try:
        state = json.loads(args.state.read_text(encoding='utf-8'))
        baseline = json.loads(Path(str(args.state) + '.baseline.json').read_text(encoding='utf-8'))
        clients = [boto3.client(n, region_name='us-east-1') for n in ('sts', 'cloudformation', 'ec2', 'ssm', 'lambda', 's3')]
        prepared = prepare(state, baseline, args.expected_account, args.teacher_account, clients)
        print(json.dumps(prepared[0], ensure_ascii=False), flush=True)
        if args.apply:
            apply(prepared, clients)
    except Exception:
        raise SystemExit('Status preparation/application did not complete. Inspect the two new status stacks; existing servers were not changed.') from None
