"""Review/apply only Web Lambda code and two existing-admin authenticated operations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from build_teacher import admin_route, inline_source, ROUTES, validate_upgrade


def sha(template):
    return hashlib.sha256(json.dumps(template, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(value, f, indent=2); f.write('\n')


def propose(old):
    new = json.loads(json.dumps(old))
    new['Resources']['ProgressFunction']['Properties']['Code'] = dict(ZipFile=inline_source())
    for index, route in enumerate(ROUTES, 8):
        name = 'Route' + str(index)
        if name in new['Resources']:
            if new['Resources'][name] != admin_route(route):
                raise ValueError('Existing D11 admin route differs')
        else:
            new['Resources'][name] = admin_route(route)
    validate_upgrade(old, new)
    return new


def review(change, old):
    if change['Status'] != 'CREATE_COMPLETE' or change['ExecutionStatus'] != 'AVAILABLE':
        raise ValueError('Reviewed change set must be available')
    expected = {'ProgressFunction': ('Modify', 'AWS::Lambda::Function')}
    for index in (8, 9):
        name = 'Route' + str(index)
        if name not in old['Resources']:
            expected[name] = ('Add', 'AWS::ApiGatewayV2::Route')
    seen = set()
    for item in change.get('Changes', []):
        r = item['ResourceChange']; name = r['LogicalResourceId']
        if (name in seen or name not in expected or (r['Action'], r['ResourceType']) != expected[name]
                or r.get('Replacement', 'False') != 'False'):
            raise ValueError('Only code and two authenticated admin routes may change')
        if name == 'ProgressFunction' and any(d.get('Target', {}).get('Name') != 'Code' for d in r.get('Details', [])):
            raise ValueError('No IAM, environment, networking or runtime changes are allowed')
        seen.add(name)
    if seen != set(expected):
        raise ValueError('Incomplete expected changes')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'review', 'execute', 'status'))
    p.add_argument('--plan', required=True)
    a = p.parse_args(); os.umask(0o077)
    import boto3
    identity = json.loads((Path.home() / '.jdu-web-teacher/identity.json').read_text())
    if identity['account'] != boto3.client('sts').get_caller_identity()['Account'] or identity['stack_name'] != 'jdu-web-progress-2026':
        raise ValueError('Wrong teacher account')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    stack = cfn.describe_stacks(StackName=identity['stack_name'])['Stacks'][0]
    old = cfn.get_template(StackName=stack['StackId'], TemplateStage='Original')['TemplateBody']
    if isinstance(old, str):
        old = json.loads(old)
    if a.command == 'prepare':
        new = propose(old)
        body = json.dumps(new, separators=(',', ':')) + '\n'
        if len(body.encode()) > 51200:
            raise ValueError('Direct template limit exceeded')
        cfn.validate_template(TemplateBody=body)
        change = cfn.create_change_set(StackName=stack['StackId'], ChangeSetType='UPDATE',
            ChangeSetName='d11-code-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
            TemplateBody=body, Parameters=[dict(ParameterKey=p['ParameterKey'], UsePreviousValue=True) for p in stack['Parameters']])
        save(a.plan, dict(account=identity['account'], stack_id=stack['StackId'], change_set_id=change['Id'],
                          old_sha256=sha(old), new_sha256=sha(new), outputs=stack['Outputs']))
        save(a.plan + '.before-template.json', old)
        print('D11_TEACHER_UPGRADE_PREPARED; code + two authenticated routes; all keys/resources retained')
        return
    plan = json.loads(Path(a.plan).read_text())
    if plan['account'] != identity['account'] or plan['stack_id'] != stack['StackId'] or plan['outputs'] != stack['Outputs']:
        raise ValueError('Retained account, stack or outputs changed')
    if a.command == 'status':
        if stack['StackStatus'] == 'UPDATE_COMPLETE' and sha(old) != plan['new_sha256']:
            raise ValueError('Live code differs from the prepared upgrade')
        print('D11_TEACHER_STATUS=' + stack['StackStatus'])
        return
    if sha(old) != plan['old_sha256']:
        raise ValueError('Baseline changed before applying the reviewed upgrade')
    changed = cfn.describe_change_set(StackName=stack['StackId'], ChangeSetName=plan['change_set_id'], IncludePropertyValues=True)
    review(changed, old)
    proposed = cfn.get_template(StackName=stack['StackId'], ChangeSetName=plan['change_set_id'], TemplateStage='Original')['TemplateBody']
    if isinstance(proposed, str):
        proposed = json.loads(proposed)
    if sha(proposed) != plan['new_sha256']:
        raise ValueError('Reviewed template differs')
    validate_upgrade(old, proposed)
    print('D11_TEACHER_REVIEW_PASSED; keys/table/API/EC2/EIP/IAM/network unchanged')
    if a.command == 'execute':
        if Path(a.plan + '.executed').exists():
            raise ValueError('Upgrade already requested')
        cfn.execute_change_set(StackName=stack['StackId'], ChangeSetName=plan['change_set_id'])
        save(a.plan + '.executed', dict(at=datetime.now(timezone.utc).isoformat()))
        print('D11_TEACHER_UPGRADE_REQUESTED')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('D11_TEACHER_UPGRADE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
