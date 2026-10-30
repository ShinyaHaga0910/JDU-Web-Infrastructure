"""Real legacy template/selector/parameter builder, Moto journal, fake EC2/CFN.

No signature verification or AWS provisioning is claimed by these fixtures.
"""
from datetime import datetime, timedelta, timezone
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / '01_roles/cyber_security/tools/web_lab_bootstrap'
sys.path[:0] = [str(BOOTSTRAP), str(BOOTSTRAP.parent / 'web_lab_instance_selector')]
# The tested legacy helpers here do not call fcntl. Lambda/CloudShell uses the
# real Linux module; this makes their pure parameter helpers importable on Win.
if sys.platform == 'win32':
    with patch.dict(sys.modules, {'fcntl': SimpleNamespace()}):
        import student_controller as windows_legacy_helpers
from all_nodes_ssm import template as all_ssm
from select_instances import select_plan
from test_select_instances import fixture
from initial_stack import InitialStack
from portal_enrollment import EnrollmentDenied


class InitialStackTest(unittest.TestCase):
    def setUp(self):
        if sys.platform == 'win32':
            compatibility = patch.dict(sys.modules, {'student_controller': windows_legacy_helpers})
            compatibility.start()
            self.addCleanup(compatibility.stop)
        self.mock = mock_aws()
        self.mock.start()
        self.addCleanup(self.mock.stop)
        transport = patch('prepare_teacher_probe.tls_control')
        transport.start()
        self.addCleanup(transport.stop)
        self.db = boto3.client('dynamodb', region_name='us-east-1',
            aws_access_key_id='EXAMPLE', aws_secret_access_key='synthetic-only')
        self.db.create_table(TableName='initial-jobs', BillingMode='PAY_PER_REQUEST',
            AttributeDefinitions=[{'AttributeName': n, 'AttributeType': 'S'} for n in ('pk', 'sk')],
            KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}, {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'five-node.template.json'
        original = ROOT / '03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c3/web-lab-ssm-c3.template.json'
        self.template = all_ssm(json.loads(original.read_bytes()))
        self.path.write_bytes((json.dumps(self.template, separators=(',', ':')) + '\n').encode())
        self.now = datetime.now(timezone.utc)
        self.manifest = {'region': 'us-east-1', 'release_id': 'web-2026-10-r1',
            'expires_at': (self.now + timedelta(days=1)).isoformat(),
            'ami': {'id': 'ami-01234567890123456', 'owner_id': '099720109477', 'image_name': 'synthetic-ubuntu',
                    'root_device_name': '/dev/sda1', 'root_min_gib': 8},
            'grading': {'ipv4': '192.0.2.10', 'fqdn': 'synthetic.execute-api.us-east-1.amazonaws.com'},
            'network': {'s3_prefix_list_id': 'pl-synthetic'},
            'bootstrap': {'bucket': 'synthetic-teacher', 'release_prefix': 'release/r3/'},
            'artifacts': {'repo_bundle': {'path': 'repo-bundle.tar.gz', 'sha256': 'a'*64, 'size_bytes': 123}}}
        self.verified = {'manifest': self.manifest, 'manifest_sha256': 'b'*64, 'files': {'template': self.path}}
        self.grant = {'account': '123456789012', 'lab_id': 'new-student',
            'deployment_id': 'f30a05e6-8356-4a65-8765-e5f4f031525b',
            'release': {'release_id': self.manifest['release_id'], 'manifest_sha256': 'b'*64,
                        'template_sha256': hashlib.sha256(self.path.read_bytes()).hexdigest(),
                        'expires_at': int(self.now.timestamp()) + 86400}}
        self.plan = {'account': self.grant['account'], 'lab_id': self.grant['lab_id'],
            'deployment_id': self.grant['deployment_id'], 'stack_name': 'jdu-web-new-student',
            'region': 'us-east-1', 'release_id': self.manifest['release_id'], 'manifest_sha256': 'b'*64,
            'template_sha256': self.grant['release']['template_sha256'], 'planned_at': self.now.isoformat(),
            'selection': select_plan(fixture()), 'key_name': 'vockey', 'student_public_key': 'ssh-ed25519 synthetic',
            's3_probe_ipv4': '192.0.2.11', 'direct_api_probe_ipv4': '192.0.2.12'}
        self.ec2, self.cfn, self.sts, self.iam, self.s3 = [Mock() for _ in range(5)]
        self.cfn.meta.config.retries = {'total_max_attempts': 1}
        self.sts.get_caller_identity.return_value = {'Account': self.grant['account']}
        self.ec2.get_paginator.return_value.paginate.return_value = []
        self.ec2.describe_key_pairs.return_value = {'KeyPairs': [{'PublicKey': self.plan['student_public_key']}]}
        self.ec2.describe_images.return_value = {'Images': [{'ImageId': self.manifest['ami']['id'],
            'OwnerId': '099720109477', 'Name': 'synthetic-ubuntu', 'Architecture': 'x86_64', 'State': 'available',
            'VirtualizationType': 'hvm', 'RootDeviceType': 'ebs', 'RootDeviceName': '/dev/sda1', 'Public': True,
            'BlockDeviceMappings': [{'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': 8}}]}]}
        self.iam.get_instance_profile.return_value = {'InstanceProfile': {'InstanceProfileName': 'LabInstanceProfile', 'Roles': [{}]}}
        self.s3.head_object.return_value = {'ContentLength': 123, 'Metadata': {'sha256': 'a'*64}}
        self.url = 'https://synthetic-teacher.s3.us-east-1.amazonaws.com/release/r3/repo-bundle.tar.gz?Signature=synthetic-canary'
        self.s3.generate_presigned_url.return_value = self.url
        self.actual = None
        self.stack_id = 'arn:aws:cloudformation:us-east-1:123456789012:stack/jdu-web-new-student/12345678-1234-1234-1234-123456789012'
        def describe(**kwargs):
            if self.actual: return {'Stacks': [self.actual]}
            raise ClientError({'Error': {'Code': 'ValidationError', 'Message': 'Stack with id jdu-web-new-student does not exist'}}, 'DescribeStacks')
        def create(**kwargs):
            self.actual = {'StackId': self.stack_id, 'StackStatus': 'CREATE_IN_PROGRESS',
                           'Tags': kwargs['Tags'], 'Parameters': kwargs['Parameters']}
            return {'StackId': self.stack_id}
        self.cfn.describe_stacks.side_effect = describe
        self.cfn.create_stack.side_effect = create
        self.cfn.get_template.return_value = {'TemplateBody': self.template}
        self.worker = InitialStack(self.verified, self.grant, self.db, 'initial-jobs', self.cfn,
            self.ec2, self.sts, self.iam, self.s3, clock=lambda: self.now.timestamp())
        self.password_hash = '$6$SyntheticSalt$' + 'A'*86

    def test_real_cli_parameters_create_five_ssm_nodes_without_journaling_credentials(self):
        result = self.worker.create(self.plan, self.password_hash)
        self.assertEqual(result['stage'], 'CREATE_REQUESTED')
        call = self.cfn.create_stack.call_args.kwargs
        params = {p['ParameterKey']: p['ParameterValue'] for p in call['Parameters']}
        self.assertEqual(set(params), set(self.template['Parameters']))
        self.assertEqual([params[k] for k in ('BastionInstanceType', 'SmallInstanceType', 'DnsInstanceType')],
                         ['t3a.medium', 't3a.small', 't3a.micro'])
        self.assertEqual(params['DeploymentPhase'], 'bootstrap')
        self.assertEqual(params['RdpPasswordHash'], self.password_hash)
        self.assertEqual(call['ClientRequestToken'], 'portal-' + self.grant['deployment_id'])
        journal = json.dumps(self.db.scan(TableName='initial-jobs')['Items'])
        self.assertNotIn(self.password_hash, journal)
        self.assertNotIn(self.url, journal)
        self.assertEqual(self.worker.saved()['initial_state'], 'foundation_only')
        self.assertFalse(result['lab_ready'])

    def test_double_click_and_status_only_observe_same_stack(self):
        self.worker.create(self.plan, self.password_hash)
        for _ in range(2):
            self.assertEqual(self.worker.create(self.plan, None)['stack_id'], self.stack_id)
            self.assertEqual(self.worker.current()['stack_status'], 'CREATE_IN_PROGRESS')
        self.assertEqual(self.cfn.create_stack.call_count, 1)

    def test_lost_response_never_creates_again_even_if_stack_is_not_visible_yet(self):
        self.cfn.create_stack.side_effect = RuntimeError('private-upstream-canary')
        response = self.worker.create(self.plan, self.password_hash)
        self.assertEqual(response, {'stage': 'CREATE_OBSERVATION_REQUIRED', 'resources_created': None})
        self.assertEqual(self.worker.create(self.plan, None), response)
        self.assertEqual(self.cfn.create_stack.call_count, 1)
        self.assertEqual(len(self.db.scan(TableName='initial-jobs')['Items']), 1)
        self.assertNotIn('private-upstream-canary', json.dumps(response))

    def test_existing_five_nodes_cannot_be_deleted_or_bypassed_to_fit_budget(self):
        self.ec2.get_paginator.return_value.paginate.return_value = [{'Reservations': [{'Instances': [{}]*5}]}]
        with self.assertRaises(EnrollmentDenied): self.worker.create(self.plan, self.password_hash)
        self.cfn.create_stack.assert_not_called()
        self.assertIsNone(self.worker.saved())
        self.ec2.terminate_instances.assert_not_called()

    def test_plan_context_or_release_expiry_rejects_before_journal_and_create(self):
        for changed in ({'account': '999999999999'}, {'deployment_id': '0'*36}, {'template_sha256': 'f'*64}):
            with self.assertRaises(EnrollmentDenied): self.worker.create(dict(self.plan, **changed), self.password_hash)
        self.now += timedelta(days=2)
        with self.assertRaises(EnrollmentDenied): self.worker.create(self.plan, self.password_hash)
        self.cfn.create_stack.assert_not_called()
        self.assertIsNone(self.worker.saved())

    def test_unknown_permission_error_is_not_treated_as_absent_stack(self):
        self.cfn.describe_stacks.side_effect = ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'synthetic'}}, 'DescribeStacks')
        with self.assertRaises(EnrollmentDenied): self.worker.create(self.plan, self.password_hash)
        self.cfn.create_stack.assert_not_called()
        self.assertIsNone(self.worker.saved())

    def test_adoption_of_different_stack_or_modified_template_is_refused(self):
        self.worker.create(self.plan, self.password_hash)
        self.actual['Tags'][0]['Value'] = 'someone-else'
        with self.assertRaises(EnrollmentDenied): self.worker.current()
        self.actual['Tags'][0]['Value'] = self.grant['lab_id']
        changed = copy.deepcopy(self.template)
        changed['Resources']['WebInstance']['Properties']['InstanceType'] = 't3.large'
        self.cfn.get_template.return_value = {'TemplateBody': changed}
        with self.assertRaises(EnrollmentDenied): self.worker.current()
        self.assertEqual(self.cfn.create_stack.call_count, 1)


if __name__ == '__main__': unittest.main()
