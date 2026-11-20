"""CloudShell enrollment, with private key generation confined to own bastion.

plan is read-only. apply generates a new authentication key and enrolls exactly
four reviewed peers; the human must execute apply during browser handoff.
verify does not generate keys or publish ephemeral keys.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import time

from internal_ssh_guest import public_key

LABELS = {'bastion': 'Bastion', 'web': 'Web', 'dns': 'Dns', 'db': 'Db', 'repo': 'Repo'}


def console_host_key(output):
    if 'BEGIN SSH HOST KEY KEYS' not in output:
        try:
            output = base64.b64decode(output, validate=True).decode()
        except (ValueError, UnicodeError):
            pass
    output = re.sub(r'\[2026-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z?\]', '', output)
    blocks = re.findall(r'BEGIN SSH HOST KEY KEYS.*?\n(.*?)END SSH HOST KEY KEYS', output, re.S)
    keys = {public_key(m) for block in blocks
            for m in re.findall(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', block)}
    if len(keys) != 1:
        raise ValueError('Exactly one trusted console host key is required')
    return keys.pop()


def save_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def current_nodes(ec2, cfn, state, baseline):
    stack = cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
    params = {x['ParameterKey']: x['ParameterValue'] for x in stack['Parameters']}
    classroom = state.get('foundation') == 'classroom'
    expected_statuses = ('CREATE_COMPLETE', 'UPDATE_COMPLETE') if classroom else ('UPDATE_COMPLETE',)
    if (stack['StackStatus'] not in expected_statuses or (not classroom and params.get('DeploymentPhase') != 'teaching')
            or any(params[x] != state[y] for x, y in [('LabId', 'lab_id'), ('DeploymentId', 'deployment_id')])):
        raise ValueError('Accepted teaching deployment required')
    template=cfn.get_template(StackName=state['stack_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(template,str):template=json.loads(template)
    canonical = (json.dumps(template, sort_keys=classroom, separators=(',', ':'))
                 + ('' if classroom else '\n')).encode()
    if hashlib.sha256(canonical).hexdigest()!=baseline['proposed_sha256']:
        raise ValueError('Live template differs from approved SSM configuration')
    resources = []
    for page in cfn.get_paginator('list_stack_resources').paginate(StackName=state['stack_id']):
        resources.extend(page['StackResourceSummaries'])
    refs = {x['LogicalResourceId']: x.get('PhysicalResourceId') for x in resources}
    nodes = {}
    for role, label in LABELS.items():
        instance_id = refs[label + 'Instance']
        i = ec2.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
        node = {'instance_id': instance_id, 'private_ip': i['PrivateIpAddress'],
                'root_volumes': [v['Ebs']['VolumeId'] for v in i['BlockDeviceMappings']]}
        tags = {x['Key']: x['Value'] for x in i.get('Tags', [])}
        if (node != baseline['nodes'][role] or i['State']['Name'] != 'running'
                or tags.get('DeploymentId') != state['deployment_id'] or tags.get('LabId') != state['lab_id']
                or {x['GroupId'] for x in i['SecurityGroups']} != {refs[label + 'Sg'], refs['BootstrapSg']}):
            raise ValueError('Instance, root or SG identity changed')
        nodes[role] = dict(node, availability_zone=i['Placement']['AvailabilityZone'])
    return nodes


def remote(ssm, instance_id, source, request):
    # Only public source, public host pins and public key enter Run Command history.
    packed = base64.b64encode(source).decode()
    payload = base64.b64encode(json.dumps(request).encode()).decode()
    command = ('python3 -c ' + shlex.quote("import base64,io,sys;sys.stdin=io.StringIO(base64.b64decode('"
               + payload + "').decode());exec(base64.b64decode('" + packed + "'))"))
    command_id = ssm.send_command(InstanceIds=[instance_id], DocumentName='AWS-RunShellScript',
        Parameters={'commands': [command], 'executionTimeout': ['90']},
        TimeoutSeconds=30)['Command']['CommandId']
    for _ in range(45):
        try:
            response = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(1)
            continue
        if response['Status'] == 'Success':
            value = json.loads(response['StandardOutputContent'])
            if not isinstance(value, dict):
                raise ValueError('Unexpected guest response')
            return value
        if response['Status'] in ('Cancelled', 'TimedOut', 'Failed', 'Cancelling'):
            raise ValueError('Guest operation failed; private files retained')
        time.sleep(1)
    raise ValueError('Guest operation pending; inspect command before retry')


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('plan', 'apply', 'verify'))
    for name in ('state', 'baseline-plan', 'plan'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    os.umask(0o077)
    if a.command=='apply' and Path(str(a.plan)+'.enrolled.public.json').exists():
        raise ValueError('Enrollment already completed; use verify')
    state = json.loads(Path(a.state).read_text())
    baseline = json.loads(Path(a.baseline_plan).read_text())
    if (state['account'] != boto3.client('sts').get_caller_identity()['Account']
            or any(state[k] != baseline[k] for k in ('account', 'stack_id', 'deployment_id'))):
        raise ValueError('Wrong account or deployment')
    ec2 = boto3.client('ec2', region_name='us-east-1')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    ssm = boto3.client('ssm', region_name='us-east-1')
    nodes = current_nodes(ec2, cfn, state, baseline)
    info = ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds',
        'Values': [nodes['bastion']['instance_id']]}])['InstanceInformationList']
    if len(info) != 1 or info[0]['PingStatus'] != 'Online':
        raise ValueError('Bastion SSM online is required')
    source = Path(__file__).with_name('internal_ssh_guest.py').read_bytes()
    if a.command == 'plan':
        peers = {}
        for role, node in nodes.items():
            if role == 'bastion':
                continue
            output = ec2.get_console_output(InstanceId=node['instance_id'], Latest=True).get('Output', '')
            try:host_key=console_host_key(output)
            except ValueError:
                from ssm_node_evidence import collect as fresh_evidence
                host_key=public_key(fresh_evidence(ssm,state,role,node['instance_id'],'teaching')['public_host_key'])
            peers[role] = dict(node, host_key=host_key)
        plan = {'account': state['account'], 'stack_id': state['stack_id'],
                'lab_id': state['lab_id'], 'deployment_id': state['deployment_id'],
                'bastion': nodes['bastion'], 'peers': peers,
                'helper_sha256': hashlib.sha256(source).hexdigest(),
                'planned_at': datetime.now(timezone.utc).isoformat()}
        save_new(a.plan, plan)
        print('INTERNAL_SSH_PLAN_READY; 4 host keys pinned from trusted EC2 console; no keys generated or enrolled')
        return
    plan = json.loads(Path(a.plan).read_text())
    if (any(plan[k] != state[k] for k in ('account', 'stack_id', 'lab_id', 'deployment_id'))
            or plan['helper_sha256'] != hashlib.sha256(source).hexdigest()
            or plan['bastion'] != nodes['bastion']):
        raise ValueError('Plan or helper identity differs')
    for role, node in nodes.items():
        if role != 'bastion' and node != {k: v for k, v in plan['peers'][role].items() if k != 'host_key'}:
            raise ValueError('Peer differs from pinned plan')
    common = {k: plan[k] for k in ('lab_id', 'deployment_id')}
    request = dict(common, command='init', instance_id=nodes['bastion']['instance_id'], peers=plan['peers'])
    if a.command == 'verify':
        enrollment = json.loads(Path(str(a.plan) + '.enrolled.public.json').read_text())
        if time.time() - enrollment['last_ephemeral_key_at'] <= 61:
            raise ValueError('Wait for ephemeral key expiry before independent verification')
        pub = public_key(enrollment['public_key'])
    else:
        print('GENERATING_OR_REUSING_DEPLOYMENT_KEY_ON_BASTION_ONLY', flush=True)
        enrollment = remote(ssm, nodes['bastion']['instance_id'], source, request)
        if enrollment.get('private_key_exported') is not False:
            raise ValueError('Invalid key response')
        pub = public_key(enrollment['public_key'])
    eic = boto3.client('ec2-instance-connect', region_name='us-east-1')
    last_push = None
    for role, peer in plan['peers'].items():
        if a.command == 'apply':
            response = eic.send_ssh_public_key(InstanceId=peer['instance_id'], InstanceOSUser='ubuntu',
                SSHPublicKey=pub, AvailabilityZone=peer['availability_zone'])
            if response.get('Success') is not True:
                raise ValueError('Ephemeral public key not accepted')
            last_push = time.time()
        request = dict(common, command='connect', instance_id=nodes['bastion']['instance_id'],
                       peer_role=role, peer_instance_id=peer['instance_id'], public_key=pub,
                       verify_only=a.command == 'verify', helper_b64=base64.b64encode(source).decode())
        remote(ssm, nodes['bastion']['instance_id'], source, request)
        print('INTERNAL_SSH_' + ('ENROLLED' if a.command == 'apply' else 'VERIFIED') + '=' + role, flush=True)
    if a.command == 'apply':
        save_new(str(a.plan) + '.enrolled.public.json', {'public_key': pub,
            'last_ephemeral_key_at': last_push, 'deployment_id': state['deployment_id'],
            'private_key_exported': False, 'persistent_ssh_verified_after_expiry': False})
        print('PUBLIC_ENROLLMENT_COMPLETE; run verify after 62 seconds without another public-key push')
    else:
        save_new(str(a.plan) + '.verified.public.json', {'deployment_id': state['deployment_id'],
            'checked_at': datetime.now(timezone.utc).isoformat(), 'roles': list(plan['peers']),
            'persistent_ssh_verified_after_expiry': True, 'private_key_exported': False,
            'class_ready': False})
        print('PERSISTENT_INTERNAL_SSH_ALL_FOUR_PASS; private key stayed on bastion')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('INTERNAL_SSH_STOPPED=' + type(exc).__name__, flush=True)
        raise SystemExit(2)
