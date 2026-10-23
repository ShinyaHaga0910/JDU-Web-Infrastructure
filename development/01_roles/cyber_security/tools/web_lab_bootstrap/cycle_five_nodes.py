"""Stop/start only the five reviewed student nodes; preserve roots and identity."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from setup_internal_ssh import current_nodes


def signature(instance):
    return {k: instance[k] for k in ('InstanceId', 'ImageId', 'InstanceType', 'VpcId',
        'SubnetId', 'PrivateIpAddress', 'KeyName')} | {
        'roots': sorted(v['Ebs']['VolumeId'] for v in instance['BlockDeviceMappings']),
        'groups': sorted(v['GroupId'] for v in instance['SecurityGroups']),
        'profile': instance.get('IamInstanceProfile', {}).get('Arn')}


def validate_nodes(actual, plan, allowed_states):
    if set(actual) != set(plan['nodes']) or len(actual) != 5:
        raise ValueError('Exactly the five original roles are required')
    for role, i in actual.items():
        if (signature(i) != plan['nodes'][role]['signature']
                or i['State']['Name'] not in allowed_states
                or {t['Key']: t['Value'] for t in i.get('Tags', [])}.get('DeploymentId') != plan['deployment_id']):
            raise ValueError('Node identity, root or state differs')


def save_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'stop', 'start', 'status'))
    for name in ('state', 'baseline-plan', 'cycle-state'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    os.umask(0o077)
    state = json.loads(Path(a.state).read_text())
    baseline = json.loads(Path(a.baseline_plan).read_text())
    if (state['account'] != boto3.client('sts').get_caller_identity()['Account']
            or any(state[k] != baseline[k] for k in ('account', 'stack_id', 'deployment_id'))):
        raise ValueError('Wrong account or deployment')
    ec2 = boto3.client('ec2', region_name='us-east-1')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    if a.command == 'prepare':
        if Path(a.cycle_state).exists():
            raise ValueError('Existing cycle retained; inspect status')
        nodes = current_nodes(ec2, cfn, state, baseline)
        plan = {k: state[k] for k in ('account', 'stack_id', 'deployment_id')}
        plan['nodes'] = {}
        for role, n in nodes.items():
            i = ec2.describe_instances(InstanceIds=[n['instance_id']])['Reservations'][0]['Instances'][0]
            plan['nodes'][role] = {'signature': signature(i), 'original_public_ip': i.get('PublicIpAddress')}
        plan['prepared_at'] = datetime.now(timezone.utc).isoformat()
        save_new(a.cycle_state, plan)
        print('FIVE_NODE_CYCLE_PREPARED; teacher/recovery nodes excluded')
        return
    plan = json.loads(Path(a.cycle_state).read_text())
    if any(plan[k] != state[k] for k in ('account', 'stack_id', 'deployment_id')):
        raise ValueError('Wrong cycle identity')
    actual = {role: ec2.describe_instances(InstanceIds=[n['signature']['InstanceId']])['Reservations'][0]['Instances'][0]
              for role, n in plan['nodes'].items()}
    validate_nodes(actual, plan, {'running', 'stopping', 'stopped', 'pending'})
    ids = [v['InstanceId'] for v in actual.values()]
    if a.command == 'stop':
        if Path(str(a.cycle_state) + '.stop-requested').exists():
            raise ValueError('Stop already requested; inspect status')
        validate_nodes(actual, plan, {'running'})
        save_new(str(a.cycle_state) + '.stop-requested', {'at': datetime.now(timezone.utc).isoformat()})
        ec2.stop_instances(InstanceIds=ids)
        print('FIVE_STUDENT_NODES_STOP_REQUESTED; all roots retained')
    elif a.command == 'start':
        if (not Path(str(a.cycle_state) + '.stop-requested').exists()
                or Path(str(a.cycle_state) + '.start-requested').exists()):
            raise ValueError('Start must follow this cycle stop exactly once')
        validate_nodes(actual, plan, {'stopped'})
        save_new(str(a.cycle_state) + '.start-requested', {'at': datetime.now(timezone.utc).isoformat()})
        ec2.start_instances(InstanceIds=ids)
        print('FIVE_STUDENT_NODES_START_REQUESTED; public IPs may change')
    else:
        report = {'scope': 'five_student_node_stop_start_not_class_acceptance',
            'checked_at': datetime.now(timezone.utc).isoformat(), 'deployment_id': state['deployment_id'],
            'same_ids_roots_ami_type_private_ip_groups_profile': True,
            'stop_requested': Path(str(a.cycle_state) + '.stop-requested').exists(),
            'start_requested': Path(str(a.cycle_state) + '.start-requested').exists(),
            'nodes': {role: {'instance_id': v['InstanceId'], 'state': v['State']['Name'],
                'public_ip': v.get('PublicIpAddress'), 'private_ip': v['PrivateIpAddress'],
                'root_volumes': signature(v)['roots']} for role, v in actual.items()}, 'class_ready': False}
        print('FIVE_NODE_CYCLE_STATUS=' + json.dumps(report, separators=(',', ':')))
        stamp = datetime.now(timezone.utc).strftime('%H%M%S')
        save_new(str(a.cycle_state) + '.' + stamp + '.public.json', report)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FIVE_NODE_CYCLE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
