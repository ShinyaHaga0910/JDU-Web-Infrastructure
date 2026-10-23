import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

import all_nodes_ssm
import inspect_teacher_probe as inspector
import node_evidence_guest as guest
import ssm_node_evidence as evidence
import adopt_all_nodes_ssm as migration


class AllNodesSsmTests(unittest.TestCase):
    def original(self):
        return json.loads((Path(__file__).resolve().parents[4] /
            '03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c3/web-lab-ssm-c3.template.json').read_text())

    def test_only_four_profiles_and_existing_two_ssm_references_change(self):
        original = self.original(); new = all_nodes_ssm.template(original)
        self.assertLessEqual(len((json.dumps(new, separators=(',', ':')) + '\n').encode()), 51200)
        self.assertEqual(set(new['Resources']), set(original['Resources']))
        for label in ('Web', 'Dns', 'Db', 'Repo'):
            self.assertEqual(new['Resources'][label + 'Instance']['Properties'].pop('IamInstanceProfile'), 'LabInstanceProfile')
        self.assertEqual(new['Resources']['SsmSg']['Properties']['SecurityGroupIngress'][0]['SourceSecurityGroupId'], {'Ref': 'BootstrapSg'})
        self.assertEqual(new['Resources']['BastionSsmOut']['Properties']['GroupId'], {'Ref': 'BootstrapSg'})
        new['Resources']['SsmSg'] = original['Resources']['SsmSg']
        new['Resources']['BastionSsmOut'] = original['Resources']['BastionSsmOut']
        self.assertEqual(new, original)

    def test_ssm_stays_after_s3_closure_and_no_public_tcp443_is_added(self):
        new = all_nodes_ssm.template(self.original()); refs = {k: 'resource-' + k for k in new['Resources']}
        refs.update(GradingIpv4='44.216.176.215', S3PrefixListId='pl-fixture')
        boot = inspector.expected_permissions(new, refs, 'bootstrap')
        closed = inspector.expected_permissions(new, refs, 'teaching')
        endpoint = ('tcp', 443, 443, 'UserIdGroupPairs', refs['SsmSg'])
        s3 = ('tcp', 443, 443, 'PrefixListIds', 'pl-fixture')
        self.assertIn(endpoint, boot['BootstrapSg']['egress'])
        self.assertIn(endpoint, closed['BootstrapSg']['egress'])
        self.assertIn(s3, boot['BootstrapSg']['egress'])
        self.assertNotIn(s3, closed['BootstrapSg']['egress'])
        self.assertEqual(closed['SsmSg']['ingress'], {('tcp',443,443,'UserIdGroupPairs',refs['BootstrapSg'])})

    def test_unknown_original_ssm_rules_or_profiles_refused(self):
        for mutate in ('profile','source','egress'):
            t = self.original()
            if mutate == 'profile': t['Resources']['WebInstance']['Properties']['IamInstanceProfile'] = 'other'
            if mutate == 'source': t['Resources']['SsmSg']['Properties']['SecurityGroupIngress'][0]['CidrIp'] = '0.0.0.0/0'
            if mutate == 'egress': t['Resources']['BastionSsmOut']['Properties']['ToPort'] = 65535
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): all_nodes_ssm.template(t)

    def request(self):
        return dict(lab_id='own-lab', deployment_id='own-deployment', role='dns', instance_id='i-'+'a'*17,
            release_id='web-2026-10-r1', expected_scope='student_payload', nonce='b'*32)

    def test_fresh_ssm_rejects_wrong_nonce_identity_stale_and_fabricated_pass(self):
        request = self.request()
        good = dict(request, all_fresh_checks_passed=True, private_data_exported=False, class_ready=False,
            fresh_checks=dict(service=True), fresh_checked_at=datetime.now(timezone.utc).isoformat())
        self.assertEqual(evidence.validate(good, request), good)
        for field, value in [('nonce','c'*32),('instance_id','i-'+'c'*17),('deployment_id','old'),
                ('all_fresh_checks_passed',1),('fresh_checks',dict(service=1)),
                ('fresh_checked_at',(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat())]:
            bad = dict(good); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): evidence.validate(bad, request)

    def test_guest_initial_timestamp_and_public_only_filter_survive_recovery(self):
        request = self.request(); config = {k:v for k,v in request.items() if k != 'nonce'}
        initial = dict(config, stage='ROLE_PREPARED', student_release_ready=False, checked_at='2026-10-16T00:00:00+00:00',
            checks={k:True for k in inspector.role_checks('dns')}, private_fixture='never export')
        safe = guest.public_role(config, initial, request)
        self.assertEqual(safe['checked_at'], initial['checked_at']); self.assertNotIn('private_fixture', safe)
        wrong = dict(request, deployment_id='other')
        with self.assertRaises(ValueError): guest.public_role(config, initial, wrong)

    def migration_changes(self):
        changes=[dict(ResourceChange=dict(LogicalResourceId='SsmSg',ResourceType='AWS::EC2::SecurityGroup',
            Action='Modify',Replacement='False',Details=[dict(Target=dict(Name='SecurityGroupIngress'))])),
            dict(ResourceChange=dict(LogicalResourceId='BastionSsmOut',ResourceType='AWS::EC2::SecurityGroupEgress',
            Action='Modify',Replacement='True',Details=[dict(Target=dict(Name='GroupId'))]))]
        changes += [dict(ResourceChange=dict(LogicalResourceId='Recovery'+n+'SsmOut',
            ResourceType='AWS::EC2::SecurityGroupEgress',Action='Remove')) for n in ('Web','Dns','Db','Repo')]
        return dict(Status='CREATE_COMPLETE',ExecutionStatus='AVAILABLE',Changes=changes)

    def test_migration_only_replaces_the_existing_egress_rule_and_removes_temporary_rules(self):
        self.assertEqual(len(migration.validate_changes(self.migration_changes())),6)
        for field,value in [('LogicalResourceId','WebInstance'),('ResourceType','AWS::EC2::Instance'),
                ('Action','Remove'),('Replacement','Conditional')]:
            bad=self.migration_changes();bad['Changes'][0]['ResourceChange'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):migration.validate_changes(bad)


if __name__ == '__main__': unittest.main()
