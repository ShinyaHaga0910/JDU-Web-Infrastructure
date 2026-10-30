"""Real Node RSA-OAEP -> OpenSSL interoperability; temporary fixture keys only.

Windows checks cryptography, not Linux root-owned permission semantics. The
unchanged CMS route is also exercised against authenticated GCM and rejects CBC.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
TEACHER=HERE.parent/'01_roles/cyber_security/tools/web_lab_teacher'
sys.path.insert(0,str(TEACHER))
import progress_enrollment_guest as guest
from enroll_five_node_progress import encrypt


class InitialDeliveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        openssl=shutil.which('openssl')
        if not openssl and Path('C:/Program Files/Git/usr/bin/openssl.exe').is_file():
            openssl='C:/Program Files/Git/usr/bin/openssl.exe'
        if not openssl:raise RuntimeError('OpenSSL required for real delivery interoperability checks')
        cls.path_patch=patch.dict(os.environ,{'PATH':str(Path(openssl).parent)+os.pathsep+os.environ.get('PATH','')})
        cls.path_patch.start();cls.addClassCleanup(cls.path_patch.stop)
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);cls.root=Path(cls.tmp.name)
        cls.c={'lab_id':'synthetic-student','release_id':'web-2026-10-r1','deployment_id':'05342512-1a55-4e11-b2d3-cd450487a138',
            'instance_id':'i-'+'a'*17,'grading_api_url':'https://synthetic.execute-api.us-east-1.amazonaws.com','grading_ipv4':'192.0.2.10'}
        subprocess.run(['openssl','req','-x509','-newkey','rsa:3072','-noenc','-batch','-days','1',
            '-subj','/CN=jdu-web-envelope-'+cls.c['deployment_id'],'-keyout',str(cls.root/'recipient.key'),
            '-out',str(cls.root/'recipient.crt')],capture_output=True,check=True)
        cert=(cls.root/'recipient.crt').read_bytes().decode()
        cls.context={**{k:cls.c[k] for k in ('lab_id','release_id','deployment_id','instance_id')},'account':'123456789012',
                     'certificate_pem':cert,'certificate_sha256':hashlib.sha256(cert.encode()).hexdigest()}

    def node(self,context=None):
        script="import {createInitialDelivery} from './initial-delivery.mjs'; let s='';for await(const b of process.stdin)s+=b; console.log(JSON.stringify(createInitialDelivery(JSON.parse(s))))"
        return subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(context or self.context),
            cwd=HERE/'web',capture_output=True,text=True)

    def decrypt(self,cipher,context=None):
        with patch.object(guest,'safe'):
            return guest.decrypt_oaep(self.root,cipher,context or self.c)

    def test_real_node_to_guest_roundtrip_only_cipher_and_hash_leave_node(self):
        result=self.node();self.assertEqual(result.returncode,0,result.stderr)
        packet=json.loads(result.stdout);cipher=base64.b64decode(packet['ciphertext_b64'],validate=True)
        self.assertEqual(len(cipher),384)
        value=self.decrypt(cipher)
        config=guest.validate_envelope(value,self.c)
        self.assertEqual(len(config['lab_token']),43)
        self.assertEqual(hashlib.sha256(config['lab_token'].encode()).hexdigest(),packet['token_hash'])
        self.assertNotIn(config['lab_token'],result.stdout)
        self.assertEqual(set(packet),{'schema_version','certificate_sha256','ciphertext_b64','token_hash'})

    def test_tampering_different_context_and_wrong_certificate_pin_fail(self):
        packet=json.loads(self.node().stdout);cipher=base64.b64decode(packet['ciphertext_b64'])
        with self.assertRaises(ValueError):self.decrypt(cipher[:-1]+bytes([cipher[-1]^1]))
        for k,v in [('lab_id','other-student'),('deployment_id','different'),('instance_id','i-'+'b'*17)]:
            with self.assertRaises(ValueError):self.decrypt(cipher,{**self.c,k:v})
        self.assertNotEqual(self.node({**self.context,'certificate_sha256':'0'*64}).returncode,0)
        with self.assertRaises(ValueError):self.decrypt(cipher[:128])

    def test_existing_authenticated_cms_route_still_works_and_cbc_is_rejected(self):
        config={'schema_version':1,'api_base_url':self.c['grading_api_url'],'fixed_ingress_ipv4':self.c['grading_ipv4'],
            'lab_id':self.c['lab_id'],'release_id':self.c['release_id'],'lab_token':'F'*43}
        value={**{k:self.c[k] for k in ('lab_id','release_id','deployment_id','instance_id')},
               'schema_version':1,'purpose':'progress_registration','credentials':config}
        certificate=(self.root/'recipient.crt').read_bytes()
        cipher=encrypt(certificate,json.dumps(value).encode())
        with patch.object(guest,'safe'):
            self.assertEqual(guest.decrypt(self.root,cipher),value)
            cbc=subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-cbc','-outform','DER',
                '-recip',str(self.root/'recipient.crt'),'-keyopt','rsa_padding_mode:oaep'],
                input=json.dumps(value).encode(),capture_output=True,check=True).stdout
            with self.assertRaises(ValueError):guest.decrypt(self.root,cbc)


if __name__=='__main__':unittest.main()
