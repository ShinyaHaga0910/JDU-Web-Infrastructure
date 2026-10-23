import copy
import unittest

from build_template import build
from update_progress_tracking import validate_changes, validate_templates


class UpdateGuards(unittest.TestCase):
    def baseline(self):
        new = build(); old = copy.deepcopy(new)
        old['Resources'].pop('Route7')
        old['Resources']['ProgressFunction']['Properties']['Code']['ZipFile'] = 'prior-public-source'
        return old, new

    def test_code_and_authenticated_route_only(self):
        old, new = self.baseline()
        validate_templates(old, new)
        for resource, property_name, value in [('TeacherInstance', 'InstanceType', 't3a.large'),
                ('ProgressFunction', 'Role', 'different-role'), ('ProgressTable', 'BillingMode', 'PROVISIONED')]:
            changed = copy.deepcopy(new)
            changed['Resources'][resource]['Properties'][property_name] = value
            with self.assertRaises(ValueError): validate_templates(old, changed)

    def test_replacement_permissions_or_other_resources_rejected(self):
        changes = dict(Status='CREATE_COMPLETE', ExecutionStatus='AVAILABLE', Changes=[
            {'ResourceChange': dict(LogicalResourceId='ProgressFunction', Action='Modify',
                ResourceType='AWS::Lambda::Function', Replacement='False', Scope=['Properties'],
                Details=[{'Target': {'Name': 'Code'}}])},
            {'ResourceChange': dict(LogicalResourceId='Route7', Action='Add', ResourceType='AWS::ApiGatewayV2::Route')},
        ])
        validate_changes(changes)
        changed = copy.deepcopy(changes)
        changed['Changes'][0]['ResourceChange']['Replacement'] = 'True'
        with self.assertRaises(ValueError): validate_changes(changed)
        changed = copy.deepcopy(changes)
        changed['Changes'][0]['ResourceChange']['Details'][0]['Target']['Name'] = 'Environment'
        with self.assertRaises(ValueError): validate_changes(changed)
        changed = copy.deepcopy(changes)
        changed['Changes'][1]['ResourceChange']['LogicalResourceId'] = 'InvokePermission'
        with self.assertRaises(ValueError): validate_changes(changed)


if __name__ == '__main__': unittest.main()
