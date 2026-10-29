import copy
import json
import unittest
from unittest.mock import Mock, patch

from test_plan_student_status import PlanTest
import deploy_student_status as deploy


class DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.p = PlanTest('test_plan_checks_five_nodes_and_never_changes_resources')
        self.p.setUp()
        f = self.p.f
        self.s3 = Mock()
        self.clients = [f.sts, f.cfn, f.ec2, f.ssm, self.p.lambda_client, self.s3]
        actual_stacks = f.cfn.describe_stacks.side_effect

        def stacks(StackName):
            if StackName == deploy.ARTIFACT_STACK:
                from botocore.exceptions import ClientError
                raise ClientError({'Error': {'Code': 'ValidationError', 'Message': f'Stack with id {StackName} does not exist'}}, 'DescribeStacks')
            return actual_stacks(StackName=StackName)
        f.cfn.describe_stacks.side_effect = stacks

    def prepare(self):
        return deploy.prepare(self.p.state, self.p.baseline, '123456789012', '999999999999', self.clients)

    def test_preparation_preserves_state_and_never_creates_or_uploads(self):
        before = copy.deepcopy(self.p.state), copy.deepcopy(self.p.baseline)
        prepared = self.prepare()
        self.assertEqual(prepared[0]['code_bytes'], len(prepared[3]))
        self.assertFalse(prepared[0]['public_endpoint'])
        self.assertFalse(prepared[0]['artifact_stack_exists'])
        self.assertEqual((self.p.state, self.p.baseline), before)
        self.clients[1].create_stack.assert_not_called()
        self.s3.put_object.assert_not_called()

    def test_unrelated_or_incomplete_artifact_stack_is_never_adopted(self):
        for stack in ({'StackStatus': 'CREATE_COMPLETE'}, {'Tags': [{'Key': 'Purpose', 'Value': deploy.PURPOSE}], 'StackStatus': 'CREATE_IN_PROGRESS'}):
            with self.subTest(stack=stack):
                self.clients[1].describe_stacks.return_value = {'Stacks': [stack]}
                self.clients[1].describe_stacks.side_effect = None
                with self.assertRaises(ValueError): deploy.artifact_stack(self.clients[1])
                self.clients[1].create_stack.assert_not_called()

    def test_artifact_template_has_only_private_retained_versioned_storage(self):
        template = json.loads((deploy.HERE / 'status-artifacts.template.json').read_text())
        self.assertEqual(set(template['Resources']), {'ArtifactBucket'})
        resource = template['Resources']['ArtifactBucket']
        self.assertEqual(resource['Type'], 'AWS::S3::Bucket')
        self.assertEqual(resource['DeletionPolicy'], 'Retain')
        self.assertEqual(resource['Properties']['VersioningConfiguration']['Status'], 'Enabled')
        self.assertTrue(all(resource['Properties']['PublicAccessBlockConfiguration'].values()))

    def test_apply_requires_versioned_artifact_before_function_stack(self):
        prepared = list(self.prepare())
        retained = {'Outputs': [{'OutputKey': 'BucketName', 'OutputValue': 'synthetic-private-bucket'}]}
        prepared[2] = retained
        self.s3.put_object.return_value = {'VersionId': 'null'}
        with self.assertRaises(ValueError): deploy.apply(tuple(prepared), self.clients)
        self.clients[1].create_stack.assert_not_called()

    def test_apply_uses_fixed_two_resource_template_and_retained_five_ids(self):
        prepared = list(self.prepare())
        prepared[2] = {'Outputs': [{'OutputKey': 'BucketName', 'OutputValue': 'synthetic-private-bucket'}]}
        self.s3.put_object.return_value = {'VersionId': 'synthetic-version'}
        self.clients[1].create_stack.return_value = {'StackId': 'synthetic-new-status-stack'}
        with patch('builtins.print'):
            deploy.apply(tuple(prepared), self.clients)
        request = self.clients[1].create_stack.call_args.kwargs
        self.assertEqual(request['StackName'], prepared[0]['stack_name'])
        params = {p['ParameterKey']: p['ParameterValue'] for p in request['Parameters']}
        self.assertEqual(params['ArtifactVersion'], 'synthetic-version')
        self.assertEqual(params['BastionInstance'], self.p.baseline['nodes']['bastion']['instance_id'])
        self.clients[2].start_instances.assert_not_called()
        self.clients[2].stop_instances.assert_not_called()
        self.clients[3].send_command.assert_not_called()
