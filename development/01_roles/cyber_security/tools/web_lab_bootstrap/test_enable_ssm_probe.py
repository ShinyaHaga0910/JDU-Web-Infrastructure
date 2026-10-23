import copy
import json
from pathlib import Path
import unittest

from enable_ssm_probe import ADDITIONS, encode, make_template, validate_template, validate_change_set, require_baseline


class SsmProtectionTests(unittest.TestCase):
    def original(self):
        path = Path(__file__).resolve().parents[4] / '03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c3/web-lab-repair-c3.template.json'
        return json.loads(path.read_text())

    def change(self):
        changes = [{'ResourceChange': {'LogicalResourceId': n, 'ResourceType': t, 'Action': 'Add'}}
                   for n, t in ADDITIONS.items()]
        changes.append({'ResourceChange': {'LogicalResourceId': 'BastionInstance',
            'ResourceType': 'AWS::EC2::Instance', 'Action': 'Modify', 'Replacement': 'False',
            'Scope': ['Properties'], 'Details': [{'Target': {
                'Name': 'IamInstanceProfile', 'RequiresRecreation': 'Never'}}]}})
        return {'Status': 'CREATE_COMPLETE', 'ExecutionStatus': 'AVAILABLE', 'Changes': changes}

    def test_preserves_all_existing_resources_except_bastion_profile(self):
        old = self.original()
        new = make_template(old)
        self.assertLessEqual(len(encode(new)), 51200)
        self.assertEqual(len(validate_change_set(self.change())), 5)
        for n, v in old['Resources'].items():
            actual = copy.deepcopy(new['Resources'][n])
            if n == 'BastionInstance':
                self.assertEqual(actual['Properties'].pop('IamInstanceProfile'), 'LabInstanceProfile')
            self.assertEqual(actual, v)
        validate_template(old, new)

    def test_s3_userdata_key_and_rdp_mutations_rejected(self):
        old = self.original()
        for resource, field, value in [('BastionInstance', 'UserData', 'changed'),
                ('WebInstance', 'KeyName', 'changed'), ('S3Endpoint', 'PolicyDocument', {}),
                ('BastionSg', 'SecurityGroupIngress', [])]:
            new = make_template(old)
            new['Resources'][resource]['Properties'][field] = value
            with self.assertRaises(ValueError):
                validate_template(old, new)

    def test_public_or_all_nodes_endpoint_access_rejected(self):
        old = self.original()
        for source in ({'CidrIp': '0.0.0.0/0'}, {'SourceSecurityGroupId': {'Ref': 'BootstrapSg'}}):
            new = make_template(old)
            rule = new['Resources']['SsmSg']['Properties']['SecurityGroupIngress'][0]
            rule.pop('SourceSecurityGroupId')
            rule.update(source)
            with self.assertRaises(ValueError):
                validate_template(old, new)

    def test_replacements_userdata_changes_and_other_nodes_rejected(self):
        for field, value in [('Replacement', 'True'), ('Replacement', 'Conditional'),
                ('Action', 'Remove'), ('LogicalResourceId', 'RepoInstance'), ('Details', []),
                ('Details', [{'Target': {'Name': 'UserData', 'RequiresRecreation': 'Never'}}])]:
            change = self.change()
            change['Changes'][-1]['ResourceChange'][field] = value
            with self.assertRaises(ValueError):
                validate_change_set(change)

    def test_missing_duplicate_extra_and_wrong_type_rejected(self):
        for operation in ('missing', 'duplicate', 'extra', 'wrong_type'):
            change = self.change()
            if operation == 'missing':
                change['Changes'].pop(0)
            elif operation == 'duplicate':
                change['Changes'].append(change['Changes'][0])
            elif operation == 'extra':
                change['Changes'].append({'ResourceChange': {'LogicalResourceId': 'WebSg', 'Action': 'Modify'}})
            else:
                change['Changes'][0]['ResourceChange']['ResourceType'] = 'AWS::IAM::Role'
            with self.assertRaises(ValueError):
                validate_change_set(change)

    def baseline(self):
        return {'stack_status': 'UPDATE_COMPLETE', 'phase': 'teaching',
            'all_five_role_checks_passed': True, 'all_aws_checks_passed': True,
            'all_five_network_checks_passed': True,
            'nodes': {r: {'instance_id': 'i-' + r, 'root_volumes': ['vol-' + r],
                'private_ip': r, 'state': 'running', 'network_result': {
                    'phase': 'LOCK_TRANSITION_OBSERVED', 's3_tcp_reachable': False}}
                for r in ('bastion', 'web', 'dns', 'db', 'repo')}}

    def test_closed_live_five_node_baseline_required(self):
        self.assertEqual(len(require_baseline(self.baseline())), 5)
        for field, value in [('state', 'stopped'), ('network_result', {
                'phase': 'LOCK_TRANSITION_OBSERVED', 's3_tcp_reachable': True})]:
            b = self.baseline()
            b['nodes']['bastion'][field] = value
            with self.assertRaises(ValueError):
                require_baseline(b)
        b = self.baseline()
        b['all_aws_checks_passed'] = False
        with self.assertRaises(ValueError):
            require_baseline(b)


if __name__ == '__main__':
    unittest.main()
