"""Teacher-only, reviewed temporary SSM access to recover lost boot evidence.

prepare/review do not grant access. apply needs action-time human approval.
Only the current c4-v4 four peers gain the existing LabInstanceProfile and
TCP443 to the existing SSM endpoints. Always restore the signed template.
No password, private key, new instance, disk or internet rule is created.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

DEPLOYMENT = 'fc335855-7034-427c-8494-6d7a0491ddf1'
MANIFEST = '54450c362f6b834285780c210db162c2bb80a0d45b50a8adb642c2298415b2f7'
NODES = {
    'Bastion': ('i-049b9086584a4e6df', 'vol-049a034a1cf207d09'),
    'Web': ('i-08012a39f3101c7db', 'vol-0e5036e079ff31201'),
    'Dns': ('i-06eb7eea745fa53d3', 'vol-05cce5e0e1c6dbc6c'),
    'Db': ('i-01ef765664432f107', 'vol-064682fc1cdd0a66b'),
    'Repo': ('i-004fb2b85da079a6a', 'vol-075858fb44913965f'),
}
PEERS = tuple(n for n in NODES if n != 'Bastion')


def encode(value):
    return (json.dumps(value, separators=(',', ':')) + '\n').encode()


def make_template(original):
    t = copy.deepcopy(original)
    r = t['Resources']
    if r['BastionInstance']['Properties']['IamInstanceProfile'] != 'LabInstanceProfile':
        raise ValueError('Existing bastion profile required')
    for label in PEERS:
        instance = r[label + 'Instance']['Properties']
        if 'IamInstanceProfile' in instance:
            raise ValueError('Peer already has an instance profile')
        instance['IamInstanceProfile'] = 'LabInstanceProfile'
        r['Recovery' + label + 'SsmOut'] = {'Type': 'AWS::EC2::SecurityGroupEgress', 'Properties': {
            'GroupId': {'Ref': label + 'Sg'}, 'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
            'DestinationSecurityGroupId': {'Ref': 'SsmSg'}}}
        r['SsmSg']['Properties']['SecurityGroupIngress'].append({
            'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443,
            'SourceSecurityGroupId': {'Ref': label + 'Sg'}})
    return t


def validate_changes(change, restoring=False):
    if change['Status'] != 'CREATE_COMPLETE' or change['ExecutionStatus'] != 'AVAILABLE':
        raise ValueError('Change set not available')
    wanted = {'SsmSg': 'AWS::EC2::SecurityGroup'}
    wanted.update({n + 'Instance': 'AWS::EC2::Instance' for n in PEERS})
    additions = {'Recovery' + n + 'SsmOut': 'AWS::EC2::SecurityGroupEgress' for n in PEERS}
    wanted.update(additions)
    seen = set()
    for item in change.get('Changes', []):
        c = item['ResourceChange']; n = c['LogicalResourceId']
        if n in seen or n not in wanted or c['ResourceType'] != wanted[n]:
            raise ValueError('Only nine temporary SSM changes allowed')
        if n in additions:
            if c['Action'] != ('Remove' if restoring else 'Add'):
                raise ValueError('Only four temporary endpoint egress rules may be added or removed')
            seen.add(n); continue
        if c['Action'] != 'Modify' or c['Replacement'] != 'False':
            raise ValueError('Existing resources must stay in place')
        allowed = {'IamInstanceProfile'} if n.endswith('Instance') else {
            'SecurityGroupIngress' if n == 'SsmSg' else 'SecurityGroupEgress'}
        if not c.get('Details') or any(d.get('Target', {}).get('Name') not in allowed
                or d.get('Target', {}).get('RequiresRecreation') != 'Never' for d in c['Details']):
            raise ValueError('Unexpected property change')
        seen.add(n)
    if seen != set(wanted):
        raise ValueError('Expected four profiles, endpoint ingress and four egress rules')
    return sorted(seen)


def save(path, value):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(value, f, indent=2); f.write('\n')


def check_context(ec2, cfn, state):
    if (state['deployment_id'] != DEPLOYMENT or state['stack_name'] != 'jdu-web-teacher-c4-probe'
            or state['manifest_sha256'] != MANIFEST):
        raise ValueError('Only the reviewed v4 pilot allowed')
    stack = cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
    values = {x['ParameterKey']: x['ParameterValue'] for x in stack['Parameters']}
    if (values['DeploymentId'] != DEPLOYMENT or values['LabId'] != state['lab_id']
            or values['DeploymentPhase'] != 'bootstrap'):
        raise ValueError('Same bootstrap deployment required')
    refs = {x['LogicalResourceId']: x.get('PhysicalResourceId')
        for page in cfn.get_paginator('list_stack_resources').paginate(StackName=state['stack_id'])
        for x in page['StackResourceSummaries']}
    for label, (iid, root) in NODES.items():
        if refs[label + 'Instance'] != iid:
            raise ValueError('Instance changed')
        i = ec2.describe_instances(InstanceIds=[iid])['Reservations'][0]['Instances'][0]
        tags = {x['Key']: x['Value'] for x in i.get('Tags', [])}
        if (i['State']['Name'] != 'running' or tags.get('DeploymentId') != DEPLOYMENT
                or [b['Ebs']['VolumeId'] for b in i['BlockDeviceMappings']] != [root]):
            raise ValueError('Node/root identity changed')
    return stack


def wait_stack(cfn, stack_id, expected_template=None):
    for _ in range(90):
        value = cfn.describe_stacks(StackName=stack_id)['Stacks'][0]['StackStatus']
        if value == 'UPDATE_COMPLETE':
            if expected_template is None: return
            actual = cfn.get_template(StackName=stack_id, TemplateStage='Original')['TemplateBody']
            if isinstance(actual, str): actual = json.loads(actual)
            if actual == expected_template: return
        if value not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'):
            raise ValueError('Unexpected stack state: ' + value)
        time.sleep(5)
    raise ValueError('Stack pending; keep recovery plan')


def describe(cfn, state, cid):
    return cfn.describe_change_set(StackName=state['stack_id'], ChangeSetName=cid, IncludePropertyValues=True)


def create_change(cfn, state, url, suffix):
    stack = cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
    return cfn.create_change_set(StackName=state['stack_id'], ChangeSetName='evidence-' + suffix + '-' + uuid.uuid4().hex,
        ChangeSetType='UPDATE', TemplateURL=url,
        Parameters=[dict(ParameterKey=p['ParameterKey'], UsePreviousValue=True) for p in stack['Parameters']])['Id']


def restore(cfn, ec2, state, plan, path):
    current = cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]['StackStatus']
    if current in ('UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'):
        wait_stack(cfn, state['stack_id'])
    check_context(ec2, cfn, state)
    template = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
    if isinstance(template, str): template = json.loads(template)
    original = json.loads(Path(plan['original_path']).read_text())
    if template == original:
        return
    if template != make_template(original):
        raise ValueError('Unknown template retained; no blind restoration')
    marker = Path(str(path) + '.restore-change.json')
    if marker.exists(): cid = json.loads(marker.read_text())['change_set_id']
    else:
        cid = create_change(cfn, state, plan['original_url'], 'restore'); save(marker, dict(change_set_id=cid))
    for _ in range(60):
        change = describe(cfn, state, cid)
        if change['Status'] != 'CREATE_IN_PROGRESS': break
        time.sleep(2)
    validate_changes(change, restoring=True)
    cfn.execute_change_set(StackName=state['stack_id'], ChangeSetName=cid)
    wait_stack(cfn, state['stack_id'], original)
    actual = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
    if isinstance(actual, str): actual = json.loads(actual)
    if actual != original: raise ValueError('Original template restoration failed')


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=('prepare', 'review', 'apply', 'cleanup'))
    for name in ('state', 'plan'): p.add_argument('--' + name, required=True)
    p.add_argument('--template'); p.add_argument('--guest')
    p.add_argument('--confirmed-temporary-ssm', action='store_true'); a = p.parse_args()
    os.umask(0o077); state = json.loads(Path(a.state).read_text()); path = Path(a.plan)
    if boto3.client('sts').get_caller_identity()['Account'] != state['account']:
        raise ValueError('Wrong account')
    cfn = boto3.client('cloudformation', region_name='us-east-1'); ec2 = boto3.client('ec2', region_name='us-east-1')
    stack = check_context(ec2, cfn, state)
    if a.operation == 'prepare':
        if path.exists(): raise ValueError('Existing plan retained')
        raw = Path(a.template).read_bytes(); original = json.loads(raw)
        if hashlib.sha256(raw).hexdigest() != state['template_sha256']:
            raise ValueError('Original signed template hash differs')
        live = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
        if isinstance(live, str): live = json.loads(live)
        if live != original or stack['StackStatus'] != 'CREATE_COMPLETE':
            raise ValueError('Unchanged original stack required')
        for label in PEERS:
            i = ec2.describe_instances(InstanceIds=[NODES[label][0]])['Reservations'][0]['Instances'][0]
            if i.get('IamInstanceProfile'): raise ValueError('Original peers must have no profile')
        temporary = make_template(original); s3 = boto3.client('s3', region_name='us-east-1')
        bucket = 'jdu-web-capture-20261015-bf04d16eb603'; prefix = 'teacher-recovery/' + DEPLOYMENT + '/'
        urls = {}
        for label, data in (('original', raw), ('temporary', encode(temporary))):
            key = prefix + label + '-' + hashlib.sha256(data).hexdigest() + '.json'
            s3.put_object(Bucket=bucket, Key=key, Body=data, ServerSideEncryption='AES256', ContentType='application/json')
            urls[label] = 'https://' + bucket + '.s3.us-east-1.amazonaws.com/' + key
        cid = create_change(cfn, state, urls['temporary'], 'temporary')
        save(path, dict(account=state['account'], deployment_id=DEPLOYMENT, stack_id=state['stack_id'],
            original_path=str(Path(a.template).resolve()), original_url=urls['original'], temporary_url=urls['temporary'],
            change_set_id=cid, guest_sha256=hashlib.sha256(Path(a.guest).read_bytes()).hexdigest()))
        print('TEMPORARY_SSM_PREPARED; not executed'); return
    plan = json.loads(path.read_text())
    if any(plan[k] != state[k] for k in ('account', 'deployment_id', 'stack_id')):
        raise ValueError('Wrong recovery plan')
    if a.operation == 'cleanup': restore(cfn, ec2, state, plan, path); print('ORIGINAL_TEMPLATE_RESTORED'); return
    change = describe(cfn, state, plan['change_set_id']); names = validate_changes(change)
    print('TEMPORARY_SSM_REVIEW=' + json.dumps(dict(resources=names, peer_ids=[NODES[n][0] for n in PEERS],
        temporary_profile='LabInstanceProfile (LabRole including existing non-SSM lab permissions)',
        endpoint_access='existing private endpoints TCP443 only', parameters='all previous values',
        new_instances=0, new_disks=0, password_changes=0, restore_signed_template_after=True)), flush=True)
    if a.operation == 'review': return
    if not a.confirmed_temporary_ssm: raise ValueError('Action-time human approval required')
    source = Path(a.guest).read_bytes()
    if hashlib.sha256(source).hexdigest() != plan['guest_sha256']: raise ValueError('Reviewed guest changed')
    save(str(path) + '.execution-requested.json', dict(execution_requested=True))
    ssm = boto3.client('ssm', region_name='us-east-1')
    try:
        cfn.execute_change_set(StackName=state['stack_id'], ChangeSetName=plan['change_set_id'])
        wait_stack(cfn, state['stack_id'], make_template(json.loads(Path(plan['original_path']).read_text())))
        ids = [x[0] for x in NODES.values()]
        for _ in range(60):
            online = ssm.describe_instance_information(Filters=[dict(Key='InstanceIds', Values=ids)])['InstanceInformationList']
            if {v['InstanceId'] for v in online if v['PingStatus'] == 'Online'} == set(ids): break
            time.sleep(5)
        else: raise ValueError('SSM agents not online; restore permissions')
        import base64, shlex
        code = "import base64;exec(base64.b64decode('" + base64.b64encode(source).decode() + "'))"
        result = ssm.send_command(InstanceIds=ids, DocumentName='AWS-RunShellScript',
            Parameters=dict(commands=['python3 -c ' + shlex.quote(code)], executionTimeout=['90']))
        job = dict(command_id=result['Command']['CommandId'], instance_ids=ids)
        save(str(path) + '.job.json', job)
        reports = {}
        for _ in range(60):
            for iid in ids:
                if iid in reports: continue
                try: v = ssm.get_command_invocation(CommandId=job['command_id'], InstanceId=iid)
                except ssm.exceptions.InvocationDoesNotExist: continue
                if v['Status'] == 'Success': reports[iid] = json.loads(v['StandardOutputContent'])
                elif v['Status'] in ('Failed', 'TimedOut', 'Cancelled'): raise ValueError('Guest check failed; restore permissions')
            if len(reports) == 5: break
            time.sleep(2)
        else: raise ValueError('Guest checks pending; preserve command and restore permissions')
        save(str(path) + '.evidence.public.json', dict(checked_at=datetime.now(timezone.utc).isoformat(),
            deployment_id=DEPLOYMENT, nodes=reports, class_ready=False))
    finally:
        restore(cfn, ec2, state, plan, path)
    print('BOOT_EVIDENCE_RECOVERED_AND_ORIGINAL_TEMPLATE_RESTORED', flush=True)


if __name__ == '__main__': main()
