"""Provision the browser checker for one existing classroom foundation."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

PORTAL = Path('development/web_portal_poc')


def checker_archive(source):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        portal = root / PORTAL
        portal.mkdir(parents=True)
        for name in ('build_checker_package.py', 'build_portal_services_package.py', 'build_grade_package.py'):
            path = PORTAL / name
            (root / path).write_bytes(source(path.as_posix()))
        inventory = subprocess.check_output([sys.executable, '-B', '-c',
            'import json; from pathlib import Path; from build_checker_package import FILES; '
            'print(json.dumps(sorted({p.relative_to(Path.cwd().parents[1]).as_posix() for p in FILES.values()})))'],
            cwd=portal, text=True)

        def fetch(path):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source(path))

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(fetch, json.loads(inventory)))
        archive = root / 'checker.zip'
        subprocess.run([sys.executable, '-B', str(portal / 'build_checker_package.py'),
                        '--output', str(archive)], check=True, stdout=subprocess.DEVNULL)
        return archive.read_bytes()


def provision(session, find_stack, source, state, instances, public_key, teacher_account):
    cfn, ec2, functions = (session.client(name) for name in ('cloudformation', 'ec2', 'lambda'))
    template = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
    if isinstance(template, str):
        template = json.loads(template)
    digest = hashlib.sha256(json.dumps(template, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    nodes = {}
    for role, instance_id in instances.items():
        node = ec2.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
        nodes[role] = {'instance_id': instance_id, 'private_ip': node['PrivateIpAddress'],
                       'root_volumes': [volume['Ebs']['VolumeId'] for volume in node['BlockDeviceMappings']]}
    config = json.dumps({'state': state, 'baseline': {'nodes': nodes, 'proposed_sha256': digest},
                         'public_key': public_key}, separators=(',', ':'), sort_keys=True)

    body = json.loads(source((PORTAL / 'student-checker.template.json').as_posix()))
    for field in ('ArtifactBucket', 'ArtifactKey', 'ArtifactVersion'):
        del body['Parameters'][field]
    checker = body['Resources']['Checker']['Properties']
    checker.update(Handler='index.handler', Code={'ZipFile': 'def handler(event, context):\n    return {"status": "unavailable"}\n'})
    values = {'LabId': state['lab_id'], 'CheckConfig': config,
              'TeacherRoleArn': f'arn:aws:iam::{teacher_account}:role/LabRole'}
    name = 'jdu-web-portal-check-' + state['lab_id']
    archive = checker_archive(source)
    stack = find_stack(cfn, name)
    if not stack:
        encoded_body = json.dumps(body, separators=(',', ':'))
        cfn.validate_template(TemplateBody=encoded_body)
        stack_id = cfn.create_stack(StackName=name, TemplateBody=encoded_body, Parameters=[
            {'ParameterKey': key, 'ParameterValue': value} for key, value in values.items()])['StackId']
        stack = cfn.describe_stacks(StackName=stack_id)['Stacks'][0]
    if {p['ParameterKey']: p['ParameterValue'] for p in stack['Parameters']} != values:
        raise ValueError('CHECKER_STACK_IDENTITY')
    stack_id = stack['StackId']
    live = cfn.get_template(StackName=stack_id, TemplateStage='Original')['TemplateBody']
    if (json.loads(live) if isinstance(live, str) else live) != body:
        raise ValueError('CHECKER_STACK_TEMPLATE')
    if stack['StackStatus'] == 'CREATE_IN_PROGRESS':
        cfn.get_waiter('stack_create_complete').wait(StackName=stack_id)
    elif stack['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
        raise ValueError('CHECKER_STACK_STATUS')
    name = 'jdu-web-check-' + state['lab_id']
    resource = cfn.describe_stack_resource(StackName=stack_id, LogicalResourceId='Checker')['StackResourceDetail']
    if resource['ResourceType'] != 'AWS::Lambda::Function' or resource['PhysicalResourceId'] != name:
        raise ValueError('CHECKER_STACK_IDENTITY')
    digest = base64.b64encode(hashlib.sha256(archive).digest()).decode()
    functions.get_waiter('function_updated_v2').wait(FunctionName=name)
    info = functions.get_function_configuration(FunctionName=name)
    if info['CodeSha256'] != digest:
        functions.update_function_code(FunctionName=name, ZipFile=archive, RevisionId=info['RevisionId'])
        functions.get_waiter('function_updated_v2').wait(FunctionName=name)
        info = functions.get_function_configuration(FunctionName=name)
    if info['CodeSha256'] != digest or info['Handler'] != 'index.handler':
        raise ValueError('CHECKER_CODE_VERIFICATION')
    result = functions.invoke(FunctionName=name, InvocationType='RequestResponse',
                              Payload=b'{"operation":"installation-check"}')
    if result.get('FunctionError') or json.load(result['Payload']) != {'status': 'ready'}:
        raise ValueError('CHECKER_READINESS')
