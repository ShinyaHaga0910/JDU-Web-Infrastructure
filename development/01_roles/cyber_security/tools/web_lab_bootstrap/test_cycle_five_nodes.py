import copy
import unittest
from cycle_five_nodes import signature, validate_nodes


class CycleProtectionTests(unittest.TestCase):
    def fixture(self):
        actual = {}
        for role in ('bastion', 'web', 'dns', 'db', 'repo'):
            actual[role] = {'InstanceId': 'i-' + role, 'ImageId': 'ami-fixture',
                'InstanceType': 't3a.small', 'VpcId': 'vpc-fixture', 'SubnetId': 'subnet-fixture',
                'PrivateIpAddress': role, 'KeyName': 'vockey',
                'BlockDeviceMappings': [{'Ebs': {'VolumeId': 'vol-' + role}}],
                'SecurityGroups': [{'GroupId': 'sg-' + role}], 'State': {'Name': 'running'},
                'Tags': [{'Key': 'DeploymentId', 'Value': 'fixture-deployment'}]}
        plan = {'deployment_id': 'fixture-deployment',
                'nodes': {role: {'signature': signature(v)} for role, v in actual.items()}}
        return actual, plan

    def test_only_original_five_nodes_allowed(self):
        actual, plan = self.fixture()
        validate_nodes(actual, plan, {'running'})
        for change in ('missing', 'extra', 'role'):
            bad = copy.deepcopy(actual)
            if change == 'missing':bad.pop('repo')
            elif change == 'extra':bad['teacher'] = bad['repo']
            else:bad['teacher'] = bad.pop('repo')
            with self.assertRaises(ValueError):validate_nodes(bad, plan, {'running'})

    def test_root_profile_id_and_groups_change_rejected(self):
        actual, plan = self.fixture()
        for field, value in [('InstanceId', 'i-other'), ('IamInstanceProfile', {'Arn': 'other'}),
                ('BlockDeviceMappings', [{'Ebs': {'VolumeId': 'vol-other'}}]),
                ('SecurityGroups', [{'GroupId': 'sg-other'}])]:
            bad = copy.deepcopy(actual);bad['bastion'][field] = value
            with self.assertRaises(ValueError):validate_nodes(bad, plan, {'running'})

    def test_start_requires_stopped_and_same_deployment(self):
        actual, plan = self.fixture()
        with self.assertRaises(ValueError):validate_nodes(actual, plan, {'stopped'})
        for v in actual.values():v['State']['Name'] = 'stopped'
        validate_nodes(actual, plan, {'stopped'})
        actual['db']['Tags'][0]['Value'] = 'other'
        with self.assertRaises(ValueError):validate_nodes(actual, plan, {'stopped'})


if __name__ == '__main__':unittest.main()
