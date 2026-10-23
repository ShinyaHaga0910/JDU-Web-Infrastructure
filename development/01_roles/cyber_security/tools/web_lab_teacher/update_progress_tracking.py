"""Update only Web progress Lambda code and its authenticated own-email route.

All existing keys, table, API, EC2, EIP and parameters are retained. No Linux
resources or credential issuance are part of this update.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from build_template import build

STACK = 'jdu-web-progress-2026'


def validate_templates(old, new):
    original = json.loads(json.dumps(old))
    proposed = json.loads(json.dumps(new))
    old_code = original['Resources']['ProgressFunction']['Properties']['Code']
    new_code = proposed['Resources']['ProgressFunction']['Properties']['Code']
    if set(old_code) != {'ZipFile'} or set(new_code) != {'ZipFile'} or old_code == new_code:
        raise ValueError('Expected an inline function code update')
    route = proposed['Resources'].pop('Route7')
    if route != dict(Type='AWS::ApiGatewayV2::Route', Properties=dict(ApiId={'Ref': 'ProgressApi'},
        RouteKey='POST /api/web/link-email', Target={'Fn::Join': ['/', ['integrations', {'Ref': 'Integration'}]]})):
        raise ValueError('Only the authenticated own-email route may be added')
    proposed['Resources']['ProgressFunction']['Properties']['Code'] = old_code
    if proposed != original:
        raise ValueError('Unexpected infrastructure, parameters, permissions or credential changes')


def validate_changes(change):
    if change['Status'] != 'CREATE_COMPLETE' or change['ExecutionStatus'] != 'AVAILABLE':
        raise ValueError('Reviewed change set must be available')
    expected = {'ProgressFunction': ('Modify', 'AWS::Lambda::Function'), 'Route7': ('Add', 'AWS::ApiGatewayV2::Route')}
    observed = {}
    for item in change.get('Changes', []):
        r = item['ResourceChange']; name = r['LogicalResourceId']
        if (name in observed or name not in expected or (r['Action'], r['ResourceType']) != expected[name]
                or r.get('Replacement', 'False') != 'False'):
            raise ValueError('Update must preserve all existing resources and access')
        if name == 'ProgressFunction':
            if r.get('Scope') != ['Properties'] or any(d.get('Target', {}).get('Name') != 'Code' for d in r.get('Details', [])):
                raise ValueError('Function change must be Code only')
        observed[name] = expected[name]
    if set(observed) != set(expected):
        raise ValueError('Expected exactly code update and one route')


def save(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(value, f, indent=2); f.write('\n')


def digest_template(template):
    return hashlib.sha256((json.dumps(template, separators=(',', ':')) + '\n').encode()).hexdigest()


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'review', 'execute', 'status'))
    p.add_argument('--plan', required=True)
    a = p.parse_args(); os.umask(0o077)
    identity = json.loads((Path.home() / '.jdu-web-teacher/identity.json').read_text())
    if identity != dict(account=boto3.client('sts').get_caller_identity()['Account'], region='us-east-1', stack_name=STACK):
        raise ValueError('Wrong teacher account')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    stack = cfn.describe_stacks(StackName=STACK)['Stacks'][0]
    old = cfn.get_template(StackName=stack['StackId'], TemplateStage='Original')['TemplateBody']
    if isinstance(old, str): old = json.loads(old)
    new = build()
    if a.command == 'prepare':
        if Path(a.plan).exists() or stack['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
            raise ValueError('Existing plan or unfinished stack retained')
        validate_templates(old, new)
        body = json.dumps(new, separators=(',', ':')) + '\n'
        if len(body.encode()) > 51200: raise ValueError('Template exceeds inline limit')
        cfn.validate_template(TemplateBody=body)
        name = 'progress-tracking-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        response = cfn.create_change_set(StackName=stack['StackId'], ChangeSetName=name, ChangeSetType='UPDATE',
            TemplateBody=body, Parameters=[dict(ParameterKey=x['ParameterKey'], UsePreviousValue=True) for x in stack['Parameters']])
        save(a.plan, dict(account=identity['account'], stack_id=stack['StackId'], change_set_id=response['Id'],
            old_sha256=digest_template(old), new_sha256=digest_template(new),
            outputs=stack['Outputs'], parameter_names=sorted(x['ParameterKey'] for x in stack['Parameters'])))
        print('WEB_PROGRESS_UPDATE_PREPARING; code + authenticated own-email route; no key or resource replacement')
        return
    plan = json.loads(Path(a.plan).read_text())
    if plan['account'] != identity['account'] or plan['stack_id'] != stack['StackId'] or plan['new_sha256'] != digest_template(new):
        raise ValueError('Update plan identity differs')
    if a.command == 'status':
        print('WEB_PROGRESS_STACK_STATUS=' + stack['StackStatus'])
        if stack['StackStatus'] == 'UPDATE_COMPLETE':
            if digest_template(old) != plan['new_sha256'] or stack['Outputs'] != plan['outputs']:
                raise ValueError('Updated template or retained outputs differ')
            print('WEB_PROGRESS_RETAINED_API_TABLE_EC2_EIP=True')
        return
    if digest_template(old) != plan['old_sha256'] or stack['Outputs'] != plan['outputs']:
        raise ValueError('Live baseline changed before update')
    # Resolve references before reviewing: a Lambda code update otherwise lists
    # its unchanged IntegrationUri as a speculative dependent modification.
    change = cfn.describe_change_set(StackName=stack['StackId'], ChangeSetName=plan['change_set_id'], IncludePropertyValues=True)
    validate_changes(change)
    parameters = change.get('Parameters', [])
    # DescribeChangeSet omits UsePreviousValue. Compare returned values to the
    # current stack, and require Code-only details (no Environment/Role changes).
    if ({x['ParameterKey']: x.get('ParameterValue') for x in parameters}
            != {x['ParameterKey']: x.get('ParameterValue') for x in stack['Parameters']}):
        raise ValueError('Original parameter values differ')
    proposed = cfn.get_template(StackName=stack['StackId'], ChangeSetName=plan['change_set_id'], TemplateStage='Original')['TemplateBody']
    if isinstance(proposed, str): proposed = json.loads(proposed)
    if digest_template(proposed) != plan['new_sha256']:
        raise ValueError('Change-set template differs from reviewed code')
    print('WEB_PROGRESS_REVIEW=ProgressFunction.Code Modify; Route7 Add; existing keys/table/API/EC2/EIP retained')
    if a.command == 'execute':
        if Path(a.plan + '.executed').exists(): raise ValueError('Execution already requested')
        cfn.execute_change_set(StackName=stack['StackId'], ChangeSetName=plan['change_set_id'])
        save(a.plan + '.executed', dict(requested_at=datetime.now(timezone.utc).isoformat()))
        print('WEB_PROGRESS_UPDATE_EXECUTION_REQUESTED')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('WEB_PROGRESS_UPDATE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
