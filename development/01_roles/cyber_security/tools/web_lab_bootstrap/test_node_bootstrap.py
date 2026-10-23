"""Linux fixtures for validation before host changes and bounded network retries."""
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch,MagicMock
import urllib.error

import node_bootstrap as node
from release_validation import ValidationError


class NodeValidationTests(unittest.TestCase):
    def config(self):
        return {'schema_version':1,'lab_id':'teacher-probe','deployment_id':'20a8c4ad-dc96-4e3a-bc90-249a498229fd',
            'release_id':'web-2026-10-r1','role':'dns','fingerprint':'A'*40,'expected_scope':'package_only_candidate',
            'script_pins':{},'signal_url':'https://signal.invalid/','student_public_key':'ssh-ed25519 AAAATEST',
            'grading_api_url':'https://example.execute-api.us-east-1.amazonaws.com','grading_ipv4':'44.216.176.215',
            's3_probe_ipv4':'52.216.0.1','direct_api_probe_ipv4':'44.200.0.1'}

    def identity(self,config):
        with patch.object(node.os,'geteuid',return_value=0),patch.object(node.platform,'machine',return_value='x86_64'),\
             patch.object(node.sys,'version_info',(3,12,3)),patch.object(Path,'read_text',return_value='ID=ubuntu\nVERSION_ID="24.04"\n'),\
             patch.object(node,'get',side_effect=[b'imds-token',b'i-0123456789abcdef0',b'10.20.2.10']) as get:
            result=node.identity(config)
            self.assertEqual(get.call_args_list[0].args[3],'PUT')
            self.assertEqual(get.call_args_list[1].args[2],{'X-aws-ec2-metadata-token':'imds-token'})
            return result

    def test_imdsv2_role_identity(self):
        self.assertEqual(self.identity(self.config()),'i-0123456789abcdef0')

    def test_mismatched_private_ip_rejected(self):
        config=self.config();config['role']='db'
        with self.assertRaises(ValidationError): self.identity(config)

    def test_undeclared_config_rejected(self):
        config=self.config();config['admin_token']='fixture'
        with self.assertRaises(ValidationError): node.identity(config)

    def test_private_network_control_rejected(self):
        config=self.config();config['s3_probe_ipv4']='10.20.2.30'
        with self.assertRaises(ValidationError): node.identity(config)

    def test_wrong_student_key_rejected_before_commands(self):
        with patch.object(Path,'read_text',return_value='ssh-ed25519 OTHER\n'),patch.object(node.subprocess,'run') as run:
            with self.assertRaises(ValidationError): node.validate_access(self.config())
            run.assert_not_called()

    def test_existing_rdp_user_preserved(self):
        config=self.config();config.update(role='bastion',rdp_hash='$6$fixture$'+'a'*86)
        with patch.object(Path,'read_text',return_value='ssh-ed25519 AAAATEST\n'),\
             patch.object(node.pwd,'getpwnam',return_value=object()),patch.object(node.subprocess,'run') as run:
            with self.assertRaises(ValidationError): node.validate_access(config)
            run.assert_not_called()

    def test_invalid_rdp_hash_rejected_without_commands(self):
        config=self.config();config.update(role='bastion',rdp_hash='plaintext-invalid')
        with patch.object(Path,'read_text',return_value='ssh-ed25519 AAAATEST\n'),patch.object(node.subprocess,'run') as run:
            with self.assertRaises(ValidationError): node.validate_access(config)
            run.assert_not_called()

    def test_signal_retries_three_with_same_real_id(self):
        opener=MagicMock();opener.open.side_effect=urllib.error.URLError('fixture offline')
        with patch.object(node,'OPENER',opener),patch.object(node.time,'sleep'):
            with self.assertRaises(urllib.error.URLError): node.signal(self.config(),'SUCCESS','fixture','i-0123456789abcdef0','fixture')
        self.assertEqual(opener.open.call_count,3)
        self.assertTrue(all(json.loads(c.args[0].data)['UniqueId']=='i-0123456789abcdef0' for c in opener.open.call_args_list))

    def test_oversized_metadata_not_retried(self):
        response=MagicMock();response.status=200;response.read.return_value=b'12345'
        opener=MagicMock();opener.open.return_value.__enter__.return_value=response
        with patch.object(node,'OPENER',opener):
            with self.assertRaises(ValidationError): node.get('http://10.20.2.30/fixture',4)
        self.assertEqual(opener.open.call_count,1)


if __name__=='__main__': unittest.main()
