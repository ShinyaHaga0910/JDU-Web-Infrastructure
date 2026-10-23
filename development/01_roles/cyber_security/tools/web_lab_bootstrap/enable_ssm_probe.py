"""Prepare a narrowly bounded SSM change for the existing five-node probe.

Preparation creates a reviewable CloudFormation change set, never applies it.
No keys, passwords, public SSH rules, UserData changes or replacements are used.
"""
import argparse
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from inspect_teacher_probe import collect

ADDITIONS = {'SsmSg': 'AWS::EC2::SecurityGroup',
             'BastionSsmOut': 'AWS::EC2::SecurityGroupEgress',
             'SsmEndpoint': 'AWS::EC2::VPCEndpoint',
             'SsmMessagesEndpoint': 'AWS::EC2::VPCEndpoint'}


def encode(value):
    return (json.dumps(value, separators=(',', ':')) + '\n').encode()


def make_template(original):
    t = copy.deepcopy(original)
    r = t['Resources']
    if any(n in r for n in ADDITIONS) or 'IamInstanceProfile' in r['BastionInstance']['Properties']:
        raise ValueError('Existing SSM configuration must be reviewed separately')
    ref = lambda n: {'Ref': n}
    r['BastionInstance']['Properties']['IamInstanceProfile'] = 'LabInstanceProfile'
    r['SsmSg'] = {'Type': ADDITIONS['SsmSg'], 'Properties': {
        'VpcId': ref('Vpc'), 'GroupDescription': 'Bastion SSM only',
        'SecurityGroupIngress': [{'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
                                  'SourceSecurityGroupId': ref('BastionSg')}],
        'SecurityGroupEgress': [{'IpProtocol': '-1', 'CidrIp': '127.0.0.1/32'}]}}
    r['BastionSsmOut'] = {'Type': ADDITIONS['BastionSsmOut'], 'Properties': {
        'GroupId': ref('BastionSg'), 'IpProtocol': 'tcp', 'FromPort': 443,
        'ToPort': 443, 'DestinationSecurityGroupId': ref('SsmSg')}}
    for name, service in [('SsmEndpoint', 'ssm'), ('SsmMessagesEndpoint', 'ssmmessages')]:
        r[name] = {'Type': ADDITIONS[name], 'Properties': {
            'VpcId': ref('Vpc'), 'VpcEndpointType': 'Interface',
            'ServiceName': 'com.amazonaws.us-east-1.' + service,
            'SubnetIds': [ref('PrivateSubnet')], 'SecurityGroupIds': [ref('SsmSg')],
            'PrivateDnsEnabled': True}}
    if len(encode(t)) > 51200:
        raise ValueError('Direct CloudFormation template limit exceeded')
    return t


def validate_template(original, proposed):
    if proposed != make_template(original):
        raise ValueError('Only the reviewed SSM resources/profile may change')


def validate_change_set(change):
    if change['Status'] != 'CREATE_COMPLETE' or change['ExecutionStatus'] != 'AVAILABLE':
        raise ValueError('SSM change set is not available')
    seen = set()
    for item in change.get('Changes', []):
        r = item.get('ResourceChange', {})
        n = r.get('LogicalResourceId')
        if n in seen:
            raise ValueError('Duplicate change')
        seen.add(n)
        if n in ADDITIONS:
            if r.get('Action') != 'Add' or r.get('ResourceType') != ADDITIONS[n]:
                raise ValueError('Expected new SSM resources only')
        elif n == 'BastionInstance':
            details = r.get('Details', [])
            if (r.get('Action') != 'Modify' or r.get('ResourceType') != 'AWS::EC2::Instance'
                    or r.get('Replacement') != 'False' or r.get('Scope') != ['Properties']
                    or not details or any(d.get('Target', {}).get('Name') != 'IamInstanceProfile'
                                          or d.get('Target', {}).get('RequiresRecreation') != 'Never'
                                          for d in details)):
                raise ValueError('Bastion may only gain its profile without replacement')
        else:
            raise ValueError('Unrelated resource change rejected')
    if seen != set(ADDITIONS) | {'BastionInstance'}:
        raise ValueError('Expected exactly four additions and one profile update')
    return [{'logical_id': n, 'action': 'Modify' if n == 'BastionInstance' else 'Add'}
            for n in sorted(seen)]


def require_baseline(report):
    if (report['stack_status'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE')
            or report['phase'] != 'teaching' or len(report['nodes']) != 5
            or not all(report[k] is True for k in ('all_five_role_checks_passed',
                'all_aws_checks_passed', 'all_five_network_checks_passed'))):
        raise ValueError('Five accepted live nodes and closed S3 are required')
    for n in report['nodes'].values():
        network = n['network_result']
        if (n['state'] != 'running' or network['phase'] != 'LOCK_TRANSITION_OBSERVED'
                or network['s3_tcp_reachable'] is not False):
            raise ValueError('Live teaching baseline required')
    return {role: {k: node[k] for k in ('instance_id', 'root_volumes', 'private_ip')}
            for role, node in report['nodes'].items()}


def save(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'review', 'execute'))
    for name in ('state', 'template', 'change-state'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    os.umask(0o077)
    if a.command == 'execute' and Path(str(a.change_state) + '.executed.json').exists():
        raise ValueError('Execution was already requested; inspect live state')
    state = json.loads(Path(a.state).read_text())
    if state['account'] != boto3.client('sts').get_caller_identity()['Account']:
        raise ValueError('Wrong account')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    old = json.loads(Path(a.template).read_text())
    live = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
    if isinstance(live, str):
        live = json.loads(live)
    if live != old:
        raise ValueError('Live template differs from accepted baseline')
    new = make_template(old)
    if a.command == 'prepare':
        if Path(a.change_state).exists():
            raise ValueError('Existing plan retained; use review')
        nodes = require_baseline(collect(a.state, a.template))
        iam = boto3.client('iam')
        profile = iam.get_instance_profile(InstanceProfileName='LabInstanceProfile')['InstanceProfile']
        if [r['RoleName'] for r in profile['Roles']] != ['LabRole']:
            raise ValueError('Unexpected Lab profile role')
        policies = iam.list_attached_role_policies(RoleName='LabRole')['AttachedPolicies']
        if 'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore' not in {x['PolicyArn'] for x in policies}:
            raise ValueError('Existing SSM core policy is required')
        stack = cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
        name = 'ssm-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        response = cfn.create_change_set(StackName=state['stack_id'], ChangeSetName=name,
            ChangeSetType='UPDATE', TemplateBody=encode(new).decode(),
            Parameters=[{'ParameterKey': x['ParameterKey'], 'UsePreviousValue': True}
                        for x in stack['Parameters']])
        plan = {'account': state['account'], 'stack_id': state['stack_id'],
                'deployment_id': state['deployment_id'], 'change_set_id': response['Id'],
                'baseline_sha256': hashlib.sha256(Path(a.template).read_bytes()).hexdigest(),
                'proposed_sha256': hashlib.sha256(encode(new)).hexdigest(),
                'nodes': nodes, 'phase': 'prepared'}
        save(a.change_state, plan)
        save(str(a.change_state) + '.template.json', new)
        print('SSM_CHANGE_SET_PREPARED=' + name)
        return
    plan = json.loads(Path(a.change_state).read_text())
    if (plan['phase'] != 'prepared' or any(plan[k] != state[k] for k in ('account', 'stack_id', 'deployment_id'))
            or plan['baseline_sha256'] != hashlib.sha256(Path(a.template).read_bytes()).hexdigest()
            or plan['proposed_sha256'] != hashlib.sha256(encode(new)).hexdigest()):
        raise ValueError('Plan identity or phase differs')
    change = cfn.describe_change_set(StackName=state['stack_id'], ChangeSetName=plan['change_set_id'],
                                     IncludePropertyValues=True)
    review = validate_change_set(change)
    pending = cfn.get_template(StackName=state['stack_id'], ChangeSetName=plan['change_set_id'],
                               TemplateStage='Original')['TemplateBody']
    if isinstance(pending, str):
        pending = json.loads(pending)
    validate_template(old, pending)
    nodes = require_baseline(collect(a.state, a.template))
    if nodes != plan['nodes']:
        raise ValueError('Instance/root identity changed')
    public = {'scope': 'ssm_change_review_not_applied', 'changes': review,
              'all_five_ids_and_roots_preserved': True, 'parameters_preserved': True,
              'public_ssh_opened': False, 's3_reopened': False,
              'bastion_profile': 'LabInstanceProfile', 'role': 'LabRole',
              'role_has_additional_existing_lab_permissions': True,
              'interface_endpoints': ['ssm', 'ssmmessages'], 'endpoint_az_count': 1,
              'ssm_agent_presence_and_version': 'unverified', 'ssm_live_accepted': False,
              'template_bytes': len(encode(new)), 'template_sha256': plan['proposed_sha256']}
    print('SSM_CHANGE_SET_REVIEW=' + json.dumps(public, separators=(',', ':')))
    if a.command == 'execute':
        cfn.execute_change_set(StackName=state['stack_id'], ChangeSetName=plan['change_set_id'])
        plan['phase'] = 'executed'
        # Keep the original plan as evidence; this separate marker prevents repeat execution.
        save(str(a.change_state) + '.executed.json', plan)
        print('SSM_EXECUTION_REQUESTED; SSM online/session acceptance still required')
    else:
        output = Path(str(a.change_state) + '.review.public.json')
        if not output.exists():
            save(output, public)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('SSM_CHANGE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
