"""Read-only verification against the retained teaching CloudFormation template."""
import json

try:
    from bootstrap_inspection import expected_permissions, permissions, resolve, ssm_endpoint_matches, profile_matches
except ImportError:
    from inspect_teacher_probe import expected_permissions, permissions, resolve, ssm_endpoint_matches, profile_matches

LABELS = {'bastion': 'Bastion', 'web': 'Web', 'dns': 'Dns', 'db': 'Db', 'repo': 'Repo'}


def verify(ec2, cfn, ssm, state, template, nodes):
    stack = cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
    parameters = {p['ParameterKey']: p['ParameterValue'] for p in stack['Parameters']}
    if parameters.get('DeploymentPhase') != 'teaching':
        return False
    refs = dict(parameters)
    for page in cfn.get_paginator('list_stack_resources').paginate(StackName=state['stack_id']):
        refs.update({r['LogicalResourceId']: r.get('PhysicalResourceId') for r in page['StackResourceSummaries']})
    expected = expected_permissions(template, refs, 'teaching')
    actual = {g['GroupId']: g for g in ec2.describe_security_groups(GroupIds=[refs[k] for k in expected])['SecurityGroups']}
    checks = []
    for name, rules in expected.items():
        group = actual[refs[name]]
        checks.append(permissions(group['IpPermissions']) == rules['ingress'] and permissions(group['IpPermissionsEgress']) == rules['egress'])
    for role, label in LABELS.items():
        instance = ec2.describe_instances(InstanceIds=[nodes[role]['instance_id']])['Reservations'][0]['Instances'][0]
        checks.append(profile_matches(instance, template['Resources'][label + 'Instance']['Properties']))
        checks.append(all({g['GroupId'] for g in eni['Groups']} == {refs[label + 'Sg'], refs['BootstrapSg']}
                          for eni in instance['NetworkInterfaces']))
        if role in ('dns', 'db', 'repo'):
            checks.append(not instance.get('PublicIpAddress'))
    for name in ('SsmEndpoint', 'SsmMessagesEndpoint'):
        endpoint = ec2.describe_vpc_endpoints(VpcEndpointIds=[refs[name]])['VpcEndpoints'][0]
        checks.append(ssm_endpoint_matches(endpoint, resolve(template['Resources'][name]['Properties'], refs, 'teaching')))
    infos = ssm.describe_instance_information(Filters=[dict(Key='InstanceIds', Values=[n['instance_id'] for n in nodes.values()])])['InstanceInformationList']
    checks.append(len(infos) == 5 and all(i['PingStatus'] == 'Online' for i in infos))
    tables = {t['RouteTableId']: t for t in ec2.describe_route_tables(RouteTableIds=[refs['PublicRoutes'], refs['PrivateRoutes']])['RouteTables']}
    for side in ('Public', 'Private'):
        routes = tables[refs[side + 'Routes']]['Routes']
        def allowed(route):
            if route.get('GatewayId') == 'local':
                return route.get('DestinationCidrBlock') == '10.20.0.0/16'
            if route.get('DestinationPrefixListId') == parameters['S3PrefixListId']:
                return route.get('GatewayId') == refs['S3Endpoint']
            return side == 'Public' and route.get('DestinationCidrBlock') == '0.0.0.0/0' and route.get('GatewayId') == refs['InternetGateway']
        checks.append(len(routes) == (3 if side == 'Public' else 2) and all(allowed(r) for r in routes))
    checks.append(not ec2.describe_nat_gateways(Filter=[dict(Name='vpc-id', Values=[refs['Vpc']]),
        dict(Name='state', Values=['pending', 'available', 'deleting'])])['NatGateways'])
    return all(checks)
