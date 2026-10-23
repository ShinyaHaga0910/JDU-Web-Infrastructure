import copy
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import boot_evidence_guest as guest
import temporary_ssm_recovery as recovery


class TemporaryRecoveryTests(unittest.TestCase):
    def original(self):
        return json.loads((Path(__file__).resolve().parents[4] /
            '03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c3/web-lab-ssm-c3.template.json').read_text())

    def test_only_four_profiles_endpoint_ingress_and_four_egress_rules_change(self):
        original = self.original(); modified = recovery.make_template(original)
        for label in recovery.PEERS:
            self.assertEqual(modified['Resources'][label + 'Instance']['Properties'].pop('IamInstanceProfile'), 'LabInstanceProfile')
            rule = modified['Resources'].pop('Recovery' + label + 'SsmOut')
            self.assertEqual(rule['Type'], 'AWS::EC2::SecurityGroupEgress')
            out = rule['Properties']
            incoming = modified['Resources']['SsmSg']['Properties']['SecurityGroupIngress'].pop(1)
            self.assertEqual(out, dict(GroupId={'Ref': label + 'Sg'}, IpProtocol='tcp', FromPort=443, ToPort=443, DestinationSecurityGroupId={'Ref': 'SsmSg'}))
            self.assertEqual(incoming, dict(IpProtocol='tcp', FromPort=443, ToPort=443, SourceSecurityGroupId={'Ref': label + 'Sg'}))
        self.assertEqual(modified, original)

    def test_existing_peer_profile_is_never_adopted(self):
        original = self.original(); original['Resources']['WebInstance']['Properties']['IamInstanceProfile'] = 'other'
        with self.assertRaises(ValueError): recovery.make_template(original)

    def changes(self):
        resources = [('SsmSg', 'AWS::EC2::SecurityGroup', 'SecurityGroupIngress')]
        resources += [(n + 'Instance', 'AWS::EC2::Instance', 'IamInstanceProfile') for n in recovery.PEERS]
        change = dict(Status='CREATE_COMPLETE', ExecutionStatus='AVAILABLE', Changes=[dict(ResourceChange=dict(
            LogicalResourceId=n, ResourceType=t, Action='Modify', Replacement='False',
            Details=[dict(Target=dict(Name=p, RequiresRecreation='Never'))])) for n, t, p in resources])
        change['Changes'] += [dict(ResourceChange=dict(LogicalResourceId='Recovery' + n + 'SsmOut',
            ResourceType='AWS::EC2::SecurityGroupEgress', Action='Add')) for n in recovery.PEERS]
        return change

    def test_exact_nonreplacement_change_set(self):
        self.assertEqual(len(recovery.validate_changes(self.changes())), 9)

    def test_replacement_other_properties_extra_and_missing_rejected(self):
        for change in ('replace', 'userdata', 'rdp', 'extra', 'missing', 'duplicate'):
            value = self.changes()
            if change == 'replace': value['Changes'][1]['ResourceChange']['Replacement'] = 'True'
            if change == 'userdata': value['Changes'][1]['ResourceChange']['Details'][0]['Target']['Name'] = 'UserData'
            if change == 'rdp': value['Changes'][0]['ResourceChange']['LogicalResourceId'] = 'BastionSg'
            if change == 'extra': value['Changes'].append(dict(ResourceChange=dict(LogicalResourceId='Other')))
            if change == 'missing': value['Changes'].pop()
            if change == 'duplicate': value['Changes'].append(value['Changes'][0])
            with self.subTest(change=change), self.assertRaises(ValueError): recovery.validate_changes(value)

    def test_restore_removes_only_the_four_added_rules(self):
        change = self.changes()
        for c in change['Changes']:
            if c['ResourceChange']['Action'] == 'Add': c['ResourceChange']['Action'] = 'Remove'
        self.assertEqual(len(recovery.validate_changes(change, restoring=True)), 9)
        with self.assertRaises(ValueError): recovery.validate_changes(change)

    def test_wait_ignores_stale_completed_state_until_expected_template_is_live(self):
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = [dict(Stacks=[dict(StackStatus=s)]) for s in (
            'CREATE_COMPLETE', 'UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE', 'UPDATE_COMPLETE')]
        cfn.get_template.side_effect = [dict(TemplateBody={'old': True}), dict(TemplateBody={'new': True})]
        with patch.object(recovery.time, 'sleep'):
            recovery.wait_stack(cfn, 'stack', {'new': True})
        self.assertEqual(cfn.describe_stacks.call_count, 4)

    def test_wait_does_not_accept_a_failed_update(self):
        cfn = MagicMock(); cfn.describe_stacks.return_value = dict(Stacks=[dict(StackStatus='UPDATE_ROLLBACK_COMPLETE')])
        with self.assertRaises(ValueError): recovery.wait_stack(cfn, 'stack', {'new': True})

    def role(self):
        c = dict(lab_id='teacher-c4-probe', deployment_id=recovery.DEPLOYMENT, role='dns',
            instance_id=recovery.NODES['Dns'][0], release_id='web-2026-10-r1', expected_scope='student_payload')
        import inspect_teacher_probe
        r = dict(c, stage='ROLE_PREPARED', checks={k: True for k in inspect_teacher_probe.role_checks('dns')},
            checked_at='2026-10-16T13:00:00+00:00', student_release_ready=False, secret='must-never-export')
        return c, r

    def test_retained_initial_timestamp_preserved_and_extra_data_removed(self):
        c, r = self.role(); safe = guest.public_role(c, r)
        self.assertEqual(safe['checked_at'], r['checked_at'])
        self.assertNotIn('secret', safe)
        self.assertNotIn('must-never-export', json.dumps(safe))

    def test_wrong_identity_and_incomplete_or_nonboolean_checks_rejected(self):
        for field, value in [('instance_id', recovery.NODES['Db'][0]), ('deployment_id', 'old'),
                ('checks', {}), ('checks', {'ssh_active': 1})]:
            c, r = self.role(); r[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): guest.public_role(c, r)


if __name__ == '__main__': unittest.main()
