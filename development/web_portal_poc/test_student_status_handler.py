import copy
import unittest
from unittest.mock import Mock

import student_status_handler as handler
from test_status import StatusTest


class StudentHandlerTest(unittest.TestCase):
    def setUp(self):
        fixture = StatusTest('test_stopped_instances_are_reported_without_starting')
        fixture.setUp()
        self.fixture = fixture
        b = fixture.binding
        self.env = {'STUDENT_ACCOUNT': b['account'], 'LAB_ID': b['lab_id'],
                    'DEPLOYMENT_ID': b['deployment_id'], 'STACK_ARN': b['stack_id'],
                    **{'INSTANCE_' + role.upper(): node['instance_id'] for role, node in b['nodes'].items()}}

    def run_handler(self, event, env=None):
        f = self.fixture
        return handler.serve(event, env if env is not None else self.env, f.sts, f.cfn, f.ec2, f.ssm)

    def test_only_preconfigured_five_nodes_are_reported_read_only(self):
        result = self.run_handler({'operation': 'status'})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['observation']['instances']), 5)
        self.assertTrue(all(v['ec2_state'] == 'stopped' for v in result['observation']['instances']))
        self.fixture.ec2.start_instances.assert_not_called()
        self.fixture.ec2.stop_instances.assert_not_called()
        self.fixture.ssm.send_command.assert_not_called()

    def test_caller_cannot_choose_account_or_instance_or_start_action(self):
        for event in ({'operation': 'status', 'account': '999999999999'},
                      {'operation': 'status', 'instances': ['i-'+'9'*17]},
                      {'operation': 'start'}, {}, None):
            with self.subTest(event=event):
                self.assertEqual(self.run_handler(event), {'status': 'unauthorized'})
        self.fixture.sts.get_caller_identity.assert_not_called()

    def test_invalid_configuration_and_mismatched_stack_fail_closed(self):
        env = copy.deepcopy(self.env)
        env['INSTANCE_DB'] = env['INSTANCE_WEB']
        self.assertEqual(self.run_handler({'operation': 'status'}, env), {'status': 'unavailable'})
        self.fixture.ec2.describe_instances.assert_not_called()
        self.fixture.sts.get_caller_identity.return_value = {'Account': '999999999999'}
        self.assertEqual(self.run_handler({'operation': 'status'}), {'status': 'unavailable'})
        self.fixture.cfn.describe_stacks.assert_not_called()

    def test_unreachable_observations_remain_unknown(self):
        self.fixture.ec2.describe_instances.side_effect = RuntimeError('private information')
        self.fixture.ssm.describe_instance_information.side_effect = RuntimeError('private information')
        result = self.run_handler({'operation': 'status'})
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(all(v['ec2_state'] == v['ssm_state'] == 'unknown' for v in result['observation']['instances']))
        self.assertNotIn('private information', repr(result))

    def test_private_diagnostic_contains_only_aws_operation_and_code(self):
        from botocore.exceptions import ClientError
        self.fixture.cfn.describe_stacks.side_effect = ClientError({'Error': {
            'Code': 'AccessDenied', 'Message': 'private details must not leave the function'}}, 'DescribeStacks')
        self.assertEqual(self.run_handler({'operation':'status'}), {'status':'unavailable',
            'diagnostic': {'code':'AccessDenied','operation':'DescribeStacks'}})
        self.fixture.ec2.describe_instances.assert_not_called()
