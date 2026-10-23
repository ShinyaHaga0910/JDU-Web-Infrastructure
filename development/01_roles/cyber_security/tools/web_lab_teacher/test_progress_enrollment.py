import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from enroll_five_node_progress import encrypt
from progress_enrollment_guest import recipient, decrypt, validate_envelope, write_once


class EnrollmentProtectionTests(unittest.TestCase):
    def bootstrap(self):
        return {'lab_id':'test-lab','release_id':'web-2026-10-r1',
                'deployment_id':'05342512-1a55-4e11-b2d3-cd450487a138','instance_id':'i-'+'a'*17,
                'grading_api_url':'https://unit.execute-api.us-east-1.amazonaws.com','grading_ipv4':'44.216.176.215'}

    def envelope(self):
        c=self.bootstrap()
        config={'schema_version':1,'lab_id':c['lab_id'],'release_id':c['release_id'],
                'api_base_url':c['grading_api_url'],'fixed_ingress_ipv4':c['grading_ipv4'],'lab_token':'F'*43}
        return {k:c[k] for k in ('lab_id','release_id','deployment_id','instance_id')}|{
            'schema_version':1,'purpose':'progress_registration','credentials':config}

    def test_reject_teacher_key_wrong_endpoint_or_different_lab(self):
        e=self.envelope();c=self.bootstrap()
        self.assertEqual(validate_envelope(e,c)['lab_token'],'F'*43)
        for field,value in [('admin_key','fixture-admin'),('api_base_url','https://other.execute-api.us-east-1.amazonaws.com'),
                            ('fixed_ingress_ipv4','1.2.3.4'),('lab_id','other-lab'),('lab_token','short')]:
            bad=copy.deepcopy(e);bad['credentials'][field]=value
            with self.assertRaises(ValueError):validate_envelope(bad,c)

    def test_envelope_purpose_deployment_and_extra_fields_rejected(self):
        for field,value in [('deployment_id','other'),('instance_id','i-other'),('purpose','transport_probe'),
                            ('schema_version',True),('extra','field')]:
            e=self.envelope();e[field]=value
            with self.assertRaises(ValueError):validate_envelope(e,self.bootstrap())

    @unittest.skipUnless(os.geteuid()==0,'root-owned private file protection requires isolated root test')
    def test_existing_credentials_and_symlinks_never_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'configuration';write_once(p,b'fixture-private-value')
            write_once(p,b'fixture-private-value')
            with self.assertRaises(ValueError):write_once(p,b'different-value')
            self.assertEqual(p.read_bytes(),b'fixture-private-value')
            link=Path(t)/'symlink';link.symlink_to(p)
            with self.assertRaises(ValueError):write_once(link,b'fixture-private-value')
            self.assertEqual(p.stat().st_mode&0o777,0o600)

    @unittest.skipUnless(os.geteuid()==0,'root-owned transport key test runs only in isolated WSL root fixture')
    def test_real_cms_roundtrip_ciphertext_tampering_and_cbc_rejection(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            cert=recipient(root,self.bootstrap()['deployment_id'])['certificate_pem'].encode()
            plaintext=json.dumps(self.envelope()).encode()
            cipher=encrypt(cert,plaintext)
            self.assertNotIn(b'F'*43,cipher)
            self.assertEqual(decrypt(root,cipher),self.envelope())
            tampered=cipher[:-1]+bytes([cipher[-1]^1])
            with self.assertRaises(ValueError):decrypt(root,tampered)
            certfile=root/'recipient.crt'
            cbc=subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-cbc','-outform','DER',
                '-recip',str(certfile),'-keyopt','rsa_padding_mode:oaep'],
                input=plaintext,capture_output=True,check=True).stdout
            with self.assertRaises(ValueError):decrypt(root,cbc)
            self.assertEqual((root/'recipient.key').stat().st_mode&0o777,0o600)


if __name__=='__main__':unittest.main()
