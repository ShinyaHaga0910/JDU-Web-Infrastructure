"""Deploy the assignment portal separately from the existing classroom stacks."""
import argparse
import base64
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from botocore.exceptions import ClientError

from web.build_web_package import build
from build_checker_package import build as build_checker
from build_portal_services_package import build as build_services

HERE = Path(__file__).resolve().parent
REGION = 'us-east-1'
STACK = 'jdu-web-infrastructure-portal'
TEACHER = 'jdu-web-infrastructure-teacher'
FUNCTION = STACK
GOOGLE_SECRET_NAME = 'jdu/web-portal/infrastructure-classroom/google-oauth'


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


def prepare(session, account, revision, expires=None):
    cfn = session.client('cloudformation')
    existing = read_stack(cfn, STACK)
    if existing and existing['StackStatus'] in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
        if not any(tag['Key'] == 'JduComponent' and tag['Value'] == 'ClassroomPortal' for tag in existing.get('Tags', [])):
            raise ValueError('The existing portal belongs to a different installer')
        if not expires or stack_parameters(existing).get('PortalMode') == 'enabled':
            return get_portal_url(existing)
    teacher = read_stack(cfn, TEACHER)
    if not teacher or teacher['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
        raise ValueError('Teacher foundation stack is not ready in this account')
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
        **({'PortalExpiresAt': expires} if expires else {}),
    }, update=bool(existing and expires))
    return get_portal_url(read_stack(cfn, STACK))


def backend(session, account):
    cfn = session.client('cloudformation')
    teacher = read_stack(cfn, TEACHER)
    if not teacher or teacher['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
        raise ValueError('Teacher foundation must be ready')
    grades = outputs(teacher)['TableName']
    role = f'arn:aws:iam::{account}:role/LabRole'
    bindings = apply_stack(cfn, STACK + '-bindings', template('binding-table.template.json'), {})['TableName']
    bucket = outputs(read_stack(cfn, STACK + '-artifacts'))['BucketName']
    s3 = session.client('s3')
    with TemporaryDirectory() as work:
        services_code = Path(work) / 'portal-services.zip'
        checker_code = Path(work) / 'checker.zip'
        build_services(services_code)
        build_checker(checker_code)
        services = apply_stack(cfn, STACK + '-services', template('portal-services.template.json'), {
            **publish(s3, account, bucket, 'services', services_code.name, services_code.read_bytes(), 'application/zip'),
            'LabRoleArn': role, 'GradeTableName': grades, 'BindingTableName': bindings,
            'SecretScope': 'infrastructure-classroom',
        }, update=True)
        checker_template = template('teacher-checker.template.json')
        checker_template['Resources']['Checker']['Properties']['FunctionName'] = STACK + '-checker'
        checker = apply_stack(cfn, STACK + '-checker', checker_template, {
            **publish(s3, account, bucket, 'services', checker_code.name, checker_code.read_bytes(), 'application/zip'),
            'SubjectKeyArn': services['SubjectKeySecretArn'], 'BindingTable': bindings, 'GradeTable': grades,
        }, update=True)
    return {'GradeTable': grades, 'BindingTableName': bindings, **services, **checker}


def publish_link(session, account, origin, students, expires):
    from build_browser_link_template import template as account_link

    if any(not re.fullmatch(r'[0-9]{12}', student) or student == account for student in students):
        raise ValueError('Separate student AWS accounts are required')
    code = (json.dumps(account_link(origin), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(code).hexdigest()
    definition = template('browser-link-artifacts.template.json')
    rule = definition['Resources']['AssignedStudentRead']['Properties']['PolicyDocument']['Statement'][0]
    rule['Principal']['AWS'] = [f'arn:aws:iam::{student}:root' for student in sorted(set(students))]
    deadline = datetime.fromtimestamp(int(expires), timezone.utc).isoformat().replace('+00:00', 'Z')
    rule['Condition']['DateLessThan'] = {'aws:CurrentTime': deadline}
    del definition['Parameters']['StudentAccount']
    cfn, s3 = session.client('cloudformation'), session.client('s3')
    bucket = apply_stack(cfn, STACK + '-link-' + digest[:12], definition,
                        {'TemplateDigest': digest, 'PublicationId': digest[:12]}, update=True)['BucketName']
    location = dict(Bucket=bucket, Key=f'bootstrap/{digest}/account-link.template.json', ExpectedBucketOwner=account)
    try:
        s3.put_object(**location, Body=code, IfNoneMatch='*', ServerSideEncryption='AES256',
                            ContentType='application/json', ChecksumSHA256=base64.b64encode(bytes.fromhex(digest)).decode())
    except ClientError as error:
        if error.response['Error']['Code'] not in ('PreconditionFailed', '412'):
            raise
    receipt = s3.head_object(**location, ChecksumMode='ENABLED')
    if not receipt.get('VersionId') or receipt.get('VersionId') == 'null' or receipt.get('ChecksumSHA256') != base64.b64encode(bytes.fromhex(digest)).decode():
        raise ValueError('Account-link template verification failed')
    return digest


def expiry_timestamp(value):
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value or ''):
        raise ValueError('Use YYYY-MM-DD for the last day of the semester')
    midnight = datetime.combine(date.fromisoformat(value) + timedelta(days=1), time(), ZoneInfo('Asia/Tashkent'))
    if midnight.timestamp() <= datetime.now().timestamp():
        raise ValueError('Semester end must not be in the past')
    return str(int(midnight.timestamp()))


def activate(session, account, revision, origin, google_source, students, expires):
    cfn = session.client('cloudformation')
    live = read_stack(cfn, STACK)
    if not live or get_portal_url(live) != origin:
        raise ValueError('Prepare the teacher portal first')
    # Reuse the OAuth client without changing its existing AWS secret. The
    # teacher must register this precise callback in Google before activation.
    sm = session.client('secretsmanager')
    source = sm.describe_secret(SecretId=google_source)['ARN']
    scope = f'arn:aws:secretsmanager:{REGION}:{account}:secret:jdu/web-portal/'
    if not re.fullmatch(re.escape(scope)+r'[a-z0-9-]+/google-oauth-[A-Za-z0-9]{6}', source):
        raise ValueError('Use a same-account portal Google OAuth secret')
    raw = json.loads(sm.get_secret_value(SecretId=source, VersionStage='AWSCURRENT')['SecretString'])
    if (raw.get('schema_version') != 1
            or not re.fullmatch(r'[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', raw.get('client_id', ''))
            or not re.fullmatch(r'GOCSPX-[A-Za-z0-9_-]{16,256}', raw.get('client_secret', ''))):
        raise ValueError('Invalid Google OAuth credential format')
    oauth = dict(schema_version=1, client_id=raw['client_id'], client_secret=raw['client_secret'],
                 redirect_uri=origin + '/auth/callback')
    name = GOOGLE_SECRET_NAME
    try:
        target = sm.describe_secret(SecretId=name)['ARN']
    except sm.exceptions.ResourceNotFoundException:
        target = sm.create_secret(Name=name, SecretString=json.dumps(oauth),
                                  Description='Google OAuth for the classroom grading portal')['ARN']
    else:
        existing = json.loads(sm.get_secret_value(SecretId=target, VersionStage='AWSCURRENT')['SecretString'])
        if existing != oauth:
            raise ValueError('Existing OAuth configuration differs; inspect before updating')
    refs = backend(session, account)
    digest = publish_link(session, account, origin, students, expires)
    bucket = outputs(read_stack(cfn, STACK + '-artifacts'))['BucketName']
    with TemporaryDirectory() as work:
        archive = Path(work) / 'portal-web.zip'
        build(archive)
        code = publish(session.client('s3'), account, bucket, 'portal', archive.name, archive.read_bytes(), 'application/zip')
    apply_stack(cfn, STACK, template('web/portal-web.template.json'), {
        **code, 'WebFunctionName': FUNCTION, 'ReleaseId': revision, 'LabRoleArn': f'arn:aws:iam::{account}:role/LabRole',
        'PortalMode': 'enabled', 'PortalExpiresAt': expires, 'PublicOrigin': origin, 'GoogleOAuthSecretArn': target,
        'BindingTableName': refs['BindingTableName'], 'GradeReaderFunctionArn': refs['GradeReaderArn'],
        'CheckerFunctionArn': refs['CheckerArn'], 'CheckerEnabled': 'true', 'EnrollmentEnabled': 'true',
        'EnrollmentFunctionArn': refs['EnrollmentArn'], 'BootstrapTemplateDigest': digest,
    }, update=True)
    if get_portal_url(read_stack(cfn, STACK)) != origin:
        raise ValueError('Unexpected portal endpoint after update')


def configure_google_secret(session, account, origin, client_id):
    import getpass
    import sys
    from uuid import uuid4

    from store_google_oauth import preflight, store

    if not sys.stdin.isatty():
        raise ValueError('Interactive input is required')
    sm = session.client('secretsmanager')
    preflight(session.client('sts'), sm, account, client_id, origin, GOOGLE_SECRET_NAME)
    secret = getpass.getpass('Google OAuth client secret (hidden): ')
    store(sm, account, client_id, origin, GOOGLE_SECRET_NAME, secret, uuid4().hex)
    print('Google OAuth credentials saved in AWS Secrets Manager.')

def approve_student(session, student, lab):
    import getpass
    import sys
    from approve_portal_student import original_grant
    from portal_enrollment import PortalEnrollment

    if not re.fullmatch(r'[0-9]{12}', student) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', lab):
        raise ValueError('Invalid student AWS account or Lab ID')
    cfn = session.client('cloudformation')
    refs = outputs(read_stack(cfn, STACK + '-services'))
    table = outputs(read_stack(cfn, TEACHER))['TableName']
    bindings = outputs(read_stack(cfn, STACK + '-bindings'))['TableName']
    db = session.client('dynamodb')
    grant = original_grant(db, table, lab, student)
    if not sys.stdin.isatty():
        raise ValueError('Interactive input is required')
    email = getpass.getpass('Approved school Google email: ')
    subject_key = session.client('secretsmanager').get_secret_value(
        SecretId=refs['SubjectKeySecretArn'], VersionStage='AWSCURRENT')['SecretString']
    print(PortalEnrollment(db, bindings, table, bytes.fromhex(subject_key)).approve(email, grant))

def approve_teacher(session, class_id, labs):
    import getpass
    import sys
    from datetime import datetime, timezone
    from uuid import uuid4

    from portal_enrollment import encoded
    from prepare_teacher_access import condition, get
    from teacher_progress import checked_assignment, teacher_key

    if (not re.fullmatch(r'[0-9]{1,12}', class_id or '') or not 1 <= len(labs) <= 50
            or len(set(labs)) != len(labs) or any(not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', lab) for lab in labs)):
        raise ValueError('Specify a class and the exact Lab IDs to show this teacher')
    if not sys.stdin.isatty():
        raise ValueError('Interactive input is required')
    cfn, db = session.client('cloudformation'), session.client('dynamodb')
    bindings = outputs(read_stack(cfn, STACK + '-bindings'))['TableName']
    services = outputs(read_stack(cfn, STACK + '-services'))
    grades = outputs(read_stack(cfn, TEACHER))['TableName']
    assigned, guards = [], []
    for lab in sorted(labs):
        meta = get(db, grades, 'LAB#' + lab, 'META')
        if not meta or meta.get('active') is not True or meta.get('lab_id') != lab:
            raise ValueError('The assigned Lab must already be registered')
        assigned.append({'lab_id': lab, 'deployment_id': meta['deployment_id'],
                         'context': meta.get('assessment_context', 'course')})
        guards.append(condition(grades, 'LAB#' + lab, 'META',
                                {key: meta[key] for key in ('active', 'lab_id', 'deployment_id')}))
    email = getpass.getpass('Approved teacher Google email: ')
    pepper = session.client('secretsmanager').get_secret_value(
        SecretId=services['SubjectKeySecretArn'], VersionStage='AWSCURRENT')['SecretString']
    pk = teacher_key(email, bytes.fromhex(pepper))
    existing = get(db, bindings, pk, 'ACCESS')
    if existing and existing.get('active') is True and existing.get('class_id') == class_id and existing.get('labs') == assigned:
        print('Teacher access already configured.')
        return
    if existing:
        raise ValueError('Teacher already has an assignment. Review its scope before replacing it.')
    revision = str(uuid4())
    row = {'pk': pk, 'sk': 'ACCESS', 'active': True, 'class_id': class_id,
           'labs': assigned, 'revision': revision, 'updated_at': datetime.now(timezone.utc).isoformat()}
    checked_assignment(row)
    db.transact_write_items(TransactItems=[{'Put': {'TableName': bindings, 'Item': encoded(row),
                                                   'ConditionExpression': 'attribute_not_exists(pk)'}}, *guards],
                            ClientRequestToken=revision)
    print(f'Teacher access granted for {len(labs)} Lab(s).')

def main():
    import boto3

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('portal-prepare', 'portal-init', 'portal-connect', 'portal-enable', 'portal-approve', 'portal-teacher', 'portal-secret'))
    parser.add_argument('--google-secret', default=GOOGLE_SECRET_NAME)
    parser.add_argument('--google-client-id')
    parser.add_argument('--lang', choices=('en', 'ja', 'ru', 'uz'), default='ja')
    parser.add_argument('--expires-on', help='Last day of the semester in Asia/Tashkent (YYYY-MM-DD)')
    parser.add_argument('--student-account', action='append', default=[])
    parser.add_argument('--lab-id', action='append', default=[])
    parser.add_argument('--class-id')
    parser.add_argument('--ref', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.ref):
        raise ValueError('Expected a Git commit')
    session = boto3.Session(region_name=REGION)
    account = session.client('sts').get_caller_identity()['Account']
    if not re.fullmatch(r'[0-9]{12}', account):
        raise ValueError('Unexpected AWS account')
    if args.phase in ('portal-prepare', 'portal-init'):
        expires = expiry_timestamp(args.expires_on) if args.phase == 'portal-init' else None
        origin = prepare(session, account, args.ref, expires)
        if expires:
            backend(session, account)
            messages = {
                'en': 'Add the redirect URI in Google Cloud, then run portal-enable.',
                'ja': 'Google CloudにリダイレクトURIを追加した後、portal-enable を実行してください。',
                'ru': 'Добавьте URI перенаправления в Google Cloud и запустите portal-enable.',
                'uz': 'Google Cloud da qayta yo‘naltirish URI manzilini qo‘shing, so‘ng portal-enable ni bajaring.',
            }
            print(messages[args.lang])
        print(f'PortalUrl: {origin}')
        print(f'Google OAuth redirect URI: {origin}/auth/callback')
    elif args.phase == 'portal-connect':
        backend(session, account)
        print('Portal backend connected to the existing grade table.')
    elif args.phase == 'portal-enable':
        if not args.student_account:
            parser.error('--student-account is required')
        portal = read_stack(session.client('cloudformation'), STACK)
        origin = get_portal_url(portal)
        expires = expiry_timestamp(args.expires_on) if args.expires_on else stack_parameters(portal).get('PortalExpiresAt', '')
        if not re.fullmatch(r'[0-9]{10}', expires) or int(expires) <= datetime.now().timestamp():
            parser.error('Configure a future semester end using --expires-on YYYY-MM-DD')
        activate(session, account, args.ref, origin, args.google_secret, args.student_account, expires)
        print(f'PortalUrl: {origin}')
    elif args.phase == 'portal-secret':
        if not args.google_client_id:
            parser.error('--google-client-id is required')
        origin = get_portal_url(read_stack(session.client('cloudformation'), STACK))
        configure_google_secret(session, account, origin, args.google_client_id)
    elif args.phase == 'portal-approve':
        if len(args.student_account) != 1 or len(args.lab_id) != 1:
            parser.error('One --student-account and --lab-id are required')
        approve_student(session, args.student_account[0], args.lab_id[0])
    else:
        approve_teacher(session, args.class_id, args.lab_id)


if __name__ == '__main__':
    main()

