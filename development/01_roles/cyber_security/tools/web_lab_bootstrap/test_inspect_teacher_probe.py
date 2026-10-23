import base64
import copy
import json
import unittest
import inspect_teacher_probe as inspector
import make_five_node_template as builder


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.state={'lab_id':'teacher-fixture','deployment_id':'20a8c4ad-dc96-4e3a-bc90-249a498229fd'}
        self.instance='i-0123456789abcdef0'
        self.value=dict(self.state,release_id='web-2026-10-r1',role='dns',instance_id=self.instance,
            expected_scope='package_only_candidate',stage='ROLE_PREPARED',checked_at='2026-10-15T12:00:00+00:00',
            checks={k:True for k in inspector.role_checks('dns')},student_release_ready=False)

    def parse(self,value,encoding=False):
        text='JDU_NODE_ROLE_RESULT='+json.dumps(value)
        if encoding:text=base64.b64encode(text.encode()).decode()
        return inspector.parse_console(text,'dns',self.instance,self.state)

    def test_plain_and_encoded_console(self):
        self.assertIsNotNone(self.parse(self.value)['role_result'])
        self.assertIsNotNone(self.parse(self.value,True)['role_result'])

    def test_inserted_serial_timestamps_preserve_report_timestamp(self):
        value=copy.deepcopy(self.value);value['checked_at']='2026-10-16T04:38:24Z'
        text='JDU_NODE_ROLE_RESULT='+json.dumps(value)
        for stamp in ('[2026-10-16T04:38:24.729330]','[2026-10-16T04:38:24.729330Z]'):
            interrupted=text[:80]+stamp+text[80:]
            result=inspector.parse_console(interrupted,'dns',self.instance,self.state)
            self.assertEqual(result['role_result']['checked_at'],value['checked_at'])

    def test_other_deployment_or_instance_is_not_accepted(self):
        for field,new in [('instance_id','i-11111111111111111'),('deployment_id','other'),('role','db')]:
            value=copy.deepcopy(self.value);value[field]=new
            self.assertIsNone(self.parse(value)['role_result'])

    def test_missing_checks_and_nonboolean_results_are_rejected(self):
        value=copy.deepcopy(self.value);value['checks']={}
        self.assertIsNone(self.parse(value)['role_result'])
        value=copy.deepcopy(self.value);value['checks']['ssh_active']=1
        self.assertIsNone(self.parse(value)['role_result'])

    def test_arbitrary_console_fields_are_never_exported(self):
        value=copy.deepcopy(self.value);value['secret']='private-fixture'
        self.assertNotIn('private-fixture',json.dumps(self.parse(value)))

    def test_sg_source_identity_and_ipv6_cannot_be_ignored(self):
        a=[{'IpProtocol':'tcp','FromPort':22,'ToPort':22,'UserIdGroupPairs':[{'GroupId':'sg-aaa'}]}]
        b=copy.deepcopy(a);b[0]['UserIdGroupPairs'][0]['GroupId']='sg-bbb'
        self.assertNotEqual(inspector.permissions(a),inspector.permissions(b))
        b=copy.deepcopy(a);b[0]['Ipv6Ranges']=[{'CidrIpv6':'::/0'}]
        self.assertNotEqual(inspector.permissions(a),inspector.permissions(b))

    def test_phase_removes_s3_only_preserving_role_rules(self):
        template=builder.make_template();refs={k:'resource-'+k for k in template['Resources']}
        refs.update(GradingIpv4='44.216.176.215',S3PrefixListId='pl-fixture')
        bootstrap=inspector.expected_permissions(template,refs,'bootstrap');teaching=inspector.expected_permissions(template,refs,'teaching')
        for group in bootstrap:
            if group!='BootstrapSg':self.assertEqual(bootstrap[group],teaching[group])
        self.assertEqual(len(bootstrap['BootstrapSg']['egress']),2)
        self.assertEqual(len(teaching['BootstrapSg']['egress']),1)


if __name__=='__main__':unittest.main()
