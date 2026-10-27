"""Read-only five-node observation for the Web portal experiment.

The caller must provide a trusted, server-side binding derived from the
student's retained deployment. Browser-supplied bindings are not trusted.
This module does not authenticate a browser or create such a binding.
"""
from datetime import datetime, timezone
import re

ROLES = {'bastion': 'Bastion', 'web': 'Web', 'dns': 'Dns', 'db': 'Db', 'repo': 'Repo'}
INSTANCE = re.compile(r'i-[0-9a-f]{17}\Z')
ACCOUNT = re.compile(r'[0-9]{12}\Z')
LAB = re.compile(r'[a-z0-9][a-z0-9-]{2,31}\Z')


class BindingError(ValueError):
    """The AWS identity or retained deployment cannot be established."""


def observe(sts, cloudformation, ec2, ssm, binding):
    """Observe exactly the retained five nodes; no instance commands or writes.

    API failures on individual instances/SSM are unknown, not stopped or failed
    grades. A failed account, stack or resource identity check aborts the read.
    """
    account = binding.get('account', '')
    lab = binding.get('lab_id', '')
    deployment = binding.get('deployment_id', '')
    stack_id = binding.get('stack_id', '')
    nodes = binding.get('nodes', {})
    if (not isinstance(account, str) or not ACCOUNT.fullmatch(account)
            or not isinstance(lab, str) or not LAB.fullmatch(lab)
            or not isinstance(deployment, str) or not deployment
            or not isinstance(stack_id, str)
            or not stack_id.startswith('arn:aws:cloudformation:us-east-1:' + account + ':stack/')
            or not isinstance(nodes, dict) or set(nodes) != set(ROLES)):
        raise BindingError('invalid retained binding')
    ids = [nodes[role].get('instance_id', '') if isinstance(nodes[role], dict) else '' for role in ROLES]
    if any(not isinstance(i, str) or not INSTANCE.fullmatch(i) for i in ids) or len(set(ids)) != 5:
        raise BindingError('invalid retained instances')
    if sts.get_caller_identity().get('Account') != account:
        raise BindingError('wrong AWS account')
    stacks = cloudformation.describe_stacks(StackName=stack_id).get('Stacks', [])
    if len(stacks) != 1 or stacks[0].get('StackId') != stack_id:
        raise BindingError('wrong stack')
    params = {p['ParameterKey']: p['ParameterValue'] for p in stacks[0].get('Parameters', [])}
    if params.get('LabId') != lab or params.get('DeploymentId') != deployment:
        raise BindingError('wrong deployment')
    resources = {}
    paginator = cloudformation.get_paginator('list_stack_resources')
    for page in paginator.paginate(StackName=stack_id):
        for item in page.get('StackResourceSummaries', []):
            resources[item['LogicalResourceId']] = item.get('PhysicalResourceId')
    if any(resources.get(label + 'Instance') != nodes[role]['instance_id'] for role, label in ROLES.items()):
        raise BindingError('stack instances differ from retained binding')

    try:
        infos = ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds', 'Values': ids}]).get('InstanceInformationList', [])
        online = {i['InstanceId']: i.get('PingStatus', 'unknown') for i in infos}
    except Exception:
        online = {}
    result = []
    for role, instance_id in zip(ROLES, ids):
        entry = {'role': role, 'instance_id': instance_id, 'ec2_state': 'unknown',
                 'ssm_state': online.get(instance_id, 'unknown'), 'public_ip': None}
        try:
            reservations = ec2.describe_instances(InstanceIds=[instance_id]).get('Reservations', [])
            found = [i for r in reservations for i in r.get('Instances', [])]
            if len(found) != 1 or found[0].get('InstanceId') != instance_id:
                raise BindingError('instance identity mismatch')
            instance = found[0]
            tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
            if tags.get('LabId') != lab or tags.get('DeploymentId') != deployment:
                raise BindingError('instance tags differ from retained binding')
            entry['ec2_state'] = instance.get('State', {}).get('Name', 'unknown')
            entry['public_ip'] = instance.get('PublicIpAddress')
        except BindingError:
            raise
        except Exception:
            pass
        result.append(entry)
    return {'account': account, 'lab_id': lab, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'stack_status': stacks[0].get('StackStatus', 'unknown'), 'instances': result}
