"""Read-only SDK discovery for the signed five-node controller (R1).

Lambda has no AWS CLI. Keep the existing selector and signed price catalogue;
use boto3 only for discovery instead of invoking the CloudShell CLI wrapper.
"""
from datetime import datetime, timezone
import ipaddress
import socket

from portal_enrollment import EnrollmentDenied


class InitialBudgetExceeded(EnrollmentDenied):
    def __init__(self, budget):
        super().__init__('Existing servers retained; resource budget exceeded')
        self.budget = budget


def make_plan(stack, *, resolve=socket.getaddrinfo):
    from student_controller import existing_nodes, budget_check
    from web_lab import check_ami, ssh_public_key
    from select_instances import load_catalog, select_plan
    grant, manifest = stack.grant, stack.verified['manifest']
    template = stack.checked_files()
    if stack.sts.get_caller_identity()['Account'] != grant['account'] or stack.saved():
        raise EnrollmentDenied('Wrong student account or an existing create request')
    if stack.stack() is not None:
        raise EnrollmentDenied('Existing stack retained')
    budget = budget_check(existing_nodes(stack.ec2))
    if not budget['within_pilot_budget']:
        raise InitialBudgetExceeded(budget)
    check_ami(manifest, stack.ec2.describe_images(ImageIds=[manifest['ami']['id']]))
    pairs = stack.ec2.describe_key_pairs(KeyNames=['vockey'], IncludePublicKey=True)['KeyPairs']
    if len(pairs) != 1:
        raise EnrollmentDenied('One existing Academy public key required')
    public = ' '.join(pairs[0]['PublicKey'].split()[:2])
    ssh_public_key(public.encode('ascii'))
    filters = [{'Name': 'instance-type', 'Values': ['t*.micro', 't*.small', 't*.medium']},
               {'Name': 'processor-info.supported-architecture', 'Values': ['x86_64']}]
    types = [v for p in stack.ec2.get_paginator('describe_instance_types').paginate(Filters=filters)
             for v in p['InstanceTypes']]
    offerings = [v for p in stack.ec2.get_paginator('describe_instance_type_offerings').paginate(
        LocationType='availability-zone', Filters=filters[:1]) for v in p['InstanceTypeOfferings']]
    zones = stack.ec2.describe_availability_zones(Filters=[{'Name': 'state', 'Values': ['available']}])['AvailabilityZones']
    catalog = load_catalog(stack.verified['files']['price_catalog'], manifest['region'])
    selection = select_plan({'region': manifest['region'], 'instance_types': types, 'zones': zones,
        'offerings': offerings, 'prices': catalog['prices'], 'price_source': {
            'kind': 'teacher AWS Price List catalog', 'collected_at': catalog['collected_at']}})
    prefix = manifest['network']['s3_prefix_list_id']
    lists = stack.ec2.describe_managed_prefix_lists(PrefixListIds=[prefix])['PrefixLists']
    if (len(lists) != 1 or lists[0]['OwnerId'] != 'AWS'
            or lists[0]['PrefixListName'] != 'com.amazonaws.us-east-1.s3'):
        raise EnrollmentDenied('Wrong S3 prefix list')
    ranges = [ipaddress.ip_network(v['Cidr']) for p in stack.ec2.get_paginator(
        'get_managed_prefix_list_entries').paginate(PrefixListId=prefix) for v in p['Entries']]
    def addresses(host):
        return sorted({v[4][0] for v in resolve(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)})
    s3 = [v for v in addresses('s3.us-east-1.amazonaws.com') if any(ipaddress.ip_address(v) in n for n in ranges)]
    direct = [v for v in addresses(manifest['grading']['fqdn']) if v != manifest['grading']['ipv4']
              and not any(ipaddress.ip_address(v) in n for n in ranges)]
    if not s3 or not direct:
        raise EnrollmentDenied('Live network controls unavailable')
    stack.cfn.validate_template(TemplateBody=template.decode('utf-8'))
    return {'schema_version': 1, 'scope': 'student_payload_candidate', 'expected_scope': 'student_payload',
        'account': grant['account'], 'region': manifest['region'], 'stack_name': stack.name,
        'lab_id': grant['lab_id'], 'deployment_id': grant['deployment_id'], 'release_id': manifest['release_id'],
        'manifest_sha256': grant['release']['manifest_sha256'],
        'template_sha256': grant['release']['template_sha256'], 'key_name': pairs[0]['KeyName'],
        'student_public_key': public, 'selection': selection, 'resource_budget': budget,
        's3_probe_ipv4': s3[0], 'direct_api_probe_ipv4': direct[0],
        'planned_at': datetime.fromtimestamp(stack.clock(), timezone.utc).isoformat(),
        'resources_created': False, 'initial_state': 'foundation_only'}
