"""Real Linux root filesystem and OpenSSL OAEP; application calls are synthetic."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import uuid

if os.name!='posix' or os.geteuid()!=0:raise RuntimeError('Run this native filesystem test as Linux root')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'01_roles/cyber_security/tools/web_lab_assessment'))
import browser_check_guest as guest


class NativeGuestTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='jdu-browser-functional-test-',dir='/root')
        self.addCleanup(temporary.cleanup);self.base=Path(temporary.name)/'functional';self.calls=[]
        self.request={'lab_id':'synthetic-lab','release_id':'web-2026-10-r1','deployment_id':str(uuid.uuid4()),
            'role':'bastion','instance_id':'i-'+'1'*17,'run_id':str(uuid.uuid4()),'task_id':'M5',
            'instances':{r:'i-'+str(i)*17 for i,r in enumerate(('bastion','web','dns','db','repo'),1)}}
        def collect(request,*,password):self.calls.append(password);return {'report':{'synthetic_application_reply':True}}
        mock=patch.dict(sys.modules,{'remote_guest':types.SimpleNamespace(identity=lambda request:self.request,collect=collect)})
        mock.start();self.addCleanup(mock.stop)
        original=guest.job;replacement=patch.object(guest,'job',side_effect=lambda request:original(request,self.base))
        replacement.start();self.addCleanup(replacement.stop)
        self.recipient=guest.prepare(self.request)['functional_recipient']
        self.root=self.base/self.request['run_id']

    def seal(self,password,job_id=None):
        public=self.root/'public.pem';public.write_text(self.recipient['public_key'])
        plain=json.dumps([job_id or self.request['run_id'],password],ensure_ascii=False).encode()
        answer=subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(public),'-pkeyopt','rsa_padding_mode:oaep',
            '-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],input=plain,capture_output=True,check=True)
        return base64.b64encode(answer.stdout).decode()

    def test_real_oaep_unicode_and_private_key_retirement(self):
        password='あ'*128
        result=guest.execute(self.request,self.seal(password))
        self.assertTrue(result['report']['synthetic_application_reply']);self.assertEqual(self.calls,[password])
        self.assertFalse((self.root/'recipient.pem').exists())
        self.assertNotIn(password,(self.root/'context.json').read_text())
        self.assertEqual(self.root.stat().st_mode&0o777,0o700)

    def test_other_job_ciphertext_cannot_run_the_application(self):
        with self.assertRaises(ValueError):guest.execute(self.request,self.seal('SyntheticOnly',str(uuid.uuid4())))
        self.assertEqual(self.calls,[])

    def test_changed_ciphertext_and_unsafe_private_key_are_rejected(self):
        value=bytearray(base64.b64decode(self.seal('SyntheticOnly')));value[10]^=1
        with self.assertRaises(subprocess.CalledProcessError):guest.execute(self.request,base64.b64encode(value).decode())
        (self.root/'recipient.pem').chmod(0o666)
        with self.assertRaises(ValueError):guest.execute(self.request,self.seal('SyntheticOnly'))
        self.assertEqual(self.calls,[])

    def test_expired_recipient_is_not_used(self):
        path=self.root/'context.json';data=json.loads(path.read_bytes());data['created_at']=int(time.time())-901
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):guest.execute(self.request,self.seal('SyntheticOnly'))
        self.assertEqual(self.calls,[])


if __name__=='__main__':unittest.main()
