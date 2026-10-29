import copy
import unittest
from unittest.mock import Mock
from botocore.exceptions import ClientError

from test_status import StatusTest
from plan_student_status import plan


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.f = StatusTest('test_stopped_instances_are_reported_without_starting')
        self.f.setUp()
        self.baseline = copy.deepcopy(self.f.binding)
        self.state = {key: self.baseline[key] for key in ('account', 'lab_id', 'deployment_id', 'stack_id')}
        self.lambda_client = Mock()
        self.lambda_client.get_function.side_effect = ClientError({'Error': {'Code': 'ResourceNotFoundException'}}, 'GetFunction')
        actual = self.f.cfn.describe_stacks.return_value
        def stacks(StackName):
            if StackName == 'jdu-web-portal-status-test-lab':
                raise ClientError({'Error': {'Code': 'ValidationError', 'Message': 'Stack with id jdu-web-portal-status-test-lab does not exist'}}, 'DescribeStacks')
            return actual
        self.f.cfn.describe_stacks.side_effect = stacks

    def run_plan(self, state=None, baseline=None, account='123456789012'):
        f = self.f
        return plan(state or self.state, baseline or self.baseline, account, '999999999999',
                    f.sts, f.cfn, f.ec2, f.ssm, self.lambda_client)

    def test_plan_checks_five_nodes_and_never_changes_resources(self):
        before = copy.deepcopy(self.state), copy.deepcopy(self.baseline)
        answer = self.run_plan()
        self.assertEqual(len(answer['nodes']), 5)
        self.assertTrue(all(v['ec2_state'] == 'stopped' for v in answer['nodes']))
        self.assertTrue(answer['function_arn'].endswith(':function:jdu-web-status-test-lab'))
        self.assertNotIn('private_ip', repr(answer))
        self.assertEqual((self.state, self.baseline), before)
        self.f.ec2.start_instances.assert_not_called()
        self.f.ec2.stop_instances.assert_not_called()
        self.f.ssm.send_command.assert_not_called()
        self.lambda_client.create_function.assert_not_called()
        self.f.cfn.create_stack.assert_not_called()

    def test_wrong_account_or_changed_baseline_stops_before_mutation(self):
        with self.assertRaises(ValueError): self.run_plan(account='888888888888')
        changed = dict(self.baseline, deployment_id='different')
        with self.assertRaises(ValueError): self.run_plan(baseline=changed)
        self.lambda_client.create_function.assert_not_called()

    def test_existing_function_or_stack_is_not_overwritten(self):
        self.lambda_client.get_function.side_effect = None
        self.lambda_client.get_function.return_value = {'Configuration': {}}
        with self.assertRaises(ValueError): self.run_plan()
        self.lambda_client.get_function.side_effect = ClientError({'Error': {'Code': 'ResourceNotFoundException'}}, 'GetFunction')
        actual = self.f.cfn.describe_stacks.return_value
        self.f.cfn.describe_stacks.side_effect = lambda StackName: {'Stacks': [{}]} if StackName == 'jdu-web-portal-status-test-lab' else actual
        with self.assertRaisesRegex(ValueError, 'status stack already exists'): self.run_plan()
        self.lambda_client.create_function.assert_not_called()
