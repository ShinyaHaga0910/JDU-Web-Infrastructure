import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

import status


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.account = '123456789012'
        self.stack = 'arn:aws:cloudformation:us-east-1:123456789012:stack/jdu-web-test/a'
        self.binding = dict(account=self.account, lab_id='test-lab', deployment_id='deployment',
                            stack_id=self.stack, nodes={role: {'instance_id': 'i-' + str(i) * 17}
                                                       for i, role in enumerate(status.ROLES, 1)})
        self.sts, self.cfn, self.ec2, self.ssm = [Mock() for _ in range(4)]
        self.sts.get_caller_identity.return_value = {'Account': self.account}
        self.cfn.describe_stacks.return_value = {'Stacks': [{'StackId': self.stack, 'StackStatus': 'UPDATE_COMPLETE',
            'Parameters': [{'ParameterKey': 'LabId', 'ParameterValue': 'test-lab'},
                           {'ParameterKey': 'DeploymentId', 'ParameterValue': 'deployment'}]}]}
        self.resources = [{'LogicalResourceId': label + 'Instance',
                           'PhysicalResourceId': self.binding['nodes'][role]['instance_id']}
                          for role, label in status.ROLES.items()]
        self.cfn.get_paginator.return_value.paginate.return_value = [{'StackResourceSummaries': self.resources}]
        self.ssm.describe_instance_information.return_value = {'InstanceInformationList': [
            {'InstanceId': self.binding['nodes']['bastion']['instance_id'], 'PingStatus': 'Online'}]}
        def describe(InstanceIds):
            instance = {'InstanceId': InstanceIds[0], 'State': {'Name': 'stopped'},
                        'Tags': [{'Key': 'LabId', 'Value': 'test-lab'},
                                 {'Key': 'DeploymentId', 'Value': 'deployment'}]}
            return {'Reservations': [{'Instances': [instance]}]}
        self.ec2.describe_instances.side_effect = describe

    def read(self, binding=None):
        return status.observe(self.sts, self.cfn, self.ec2, self.ssm, binding or self.binding)

    def test_stopped_instances_are_reported_without_starting(self):
        result = self.read()
        self.assertEqual(len(result['instances']), 5)
        self.assertEqual({i['ec2_state'] for i in result['instances']}, {'stopped'})
        self.assertEqual(result['instances'][0]['ssm_state'], 'Online')
        self.assertEqual(result['instances'][1]['ssm_state'], 'unknown')
        self.ec2.start_instances.assert_not_called()
        self.ssm.send_command.assert_not_called()

    def test_addresses_and_last_ssm_ping_are_observations(self):
        ping = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
        instance_id = self.binding['nodes']['bastion']['instance_id']
        self.ssm.describe_instance_information.return_value['InstanceInformationList'][0]['LastPingDateTime'] = ping
        old_describe = self.ec2.describe_instances.side_effect
        def describe(InstanceIds):
            answer = old_describe(InstanceIds)
            if InstanceIds[0] == instance_id:
                answer['Reservations'][0]['Instances'][0].update(PrivateIpAddress='10.20.1.10', PublicIpAddress='192.0.2.10')
            return answer
        self.ec2.describe_instances.side_effect = describe
        bastion = self.read()['instances'][0]
        self.assertEqual(bastion['ssm_last_ping'], ping.isoformat())
        self.assertEqual((bastion['private_ip'], bastion['public_ip']), ('10.20.1.10', '192.0.2.10'))

    def test_wrong_account_or_other_stack_is_rejected(self):
        self.sts.get_caller_identity.return_value = {'Account': '999999999999'}
        with self.assertRaises(status.BindingError):
            self.read()
        self.cfn.describe_stacks.assert_not_called()
        self.sts.get_caller_identity.return_value = {'Account': self.account}
        self.resources[0]['PhysicalResourceId'] = 'i-' + '9' * 17
        with self.assertRaises(status.BindingError):
            self.read()
        self.ec2.describe_instances.assert_not_called()

    def test_unavailable_apis_remain_unknown(self):
        self.ssm.describe_instance_information.side_effect = RuntimeError('unavailable')
        self.ec2.describe_instances.side_effect = RuntimeError('unavailable')
        result = self.read()
        self.assertTrue(all(i['ec2_state'] == i['ssm_state'] == 'unknown' for i in result['instances']))

    def test_wrong_tag_and_duplicate_node_are_rejected(self):
        self.ec2.describe_instances.return_value = {'Reservations': [{'Instances': [
            {'InstanceId': self.binding['nodes']['bastion']['instance_id'], 'Tags': []}]}]}
        self.ec2.describe_instances.side_effect = None
        with self.assertRaises(status.BindingError):
            self.read()
        other = copy.deepcopy(self.binding)
        other['nodes']['web'] = other['nodes']['bastion']
        with self.assertRaises(status.BindingError):
            self.read(other)


if __name__ == '__main__':
    unittest.main()
