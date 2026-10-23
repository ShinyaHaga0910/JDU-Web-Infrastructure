"""The template loader must not run downloaded code before its pinned hash."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import offline_repo_loader as loader
import make_offline_repo_template as template


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def bundle(self,duplicate=False,link=False):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w:gz') as archive:
            for name in ('payload_runtime.py','release_validation.py'):
                member=tarfile.TarInfo('release/artifacts/bootstrap/'+name)
                data=b'# disposable public test fixture\n'
                if link and name=='payload_runtime.py':
                    member.type=tarfile.SYMTYPE; member.linkname='/outside'
                    archive.addfile(member)
                else:
                    member.size=len(data); archive.addfile(member,io.BytesIO(data))
                    if duplicate and name=='payload_runtime.py':
                        archive.addfile(member,io.BytesIO(data))
        return stream.getvalue()

    def execute(self,data,expected):
        (self.root/'private.json').write_text(json.dumps({'bundle_url':'https://fixture.invalid/public-bundle','bundle_sha256':expected}))
        with patch.object(loader.urllib.request,'urlopen',return_value=io.BytesIO(data)),patch.object(loader.runpy,'run_path') as run:
            self.last_run=run
            loader.main(self.root)
            self.assertEqual(run.call_count,1)

    def test_pinned_hash_precedes_verifier_loading(self):
        data=self.bundle()
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            self.execute(data,'0'*64)
        self.assertFalse((self.root/'payload_runtime.py').exists())
        self.assertFalse((self.root/'release_validation.py').exists())
        self.last_run.assert_not_called()

    def test_only_exact_regular_verifiers_load(self):
        data=self.bundle(); self.execute(data,hashlib.sha256(data).hexdigest())
        self.assertEqual((self.root/'payload_runtime.py').read_bytes(),b'# disposable public test fixture\n')

    def test_duplicate_and_linked_verifiers_rejected(self):
        for case in ('duplicate','link'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as directory:
                self.root=Path(directory)
                data=self.bundle(**{case:True})
                with self.assertRaisesRegex(ValueError,'ambiguous'):
                    self.execute(data,hashlib.sha256(data).hexdigest())
                self.last_run.assert_not_called()


class PrivateTopologyTests(unittest.TestCase):
    def test_private_probe_cannot_introduce_internet_or_incoming_access(self):
        data=template.make_template(); resources=data['Resources']
        forbidden={'AWS::EC2::InternetGateway','AWS::EC2::NatGateway','AWS::EC2::EIP','AWS::EC2::Route','AWS::IAM::Role'}
        self.assertFalse({r['Type'] for r in resources.values()}&forbidden)
        instance=resources['ProbeInstance']['Properties']
        self.assertNotIn('KeyName',instance); self.assertNotIn('IamInstanceProfile',instance)
        self.assertFalse(instance['NetworkInterfaces'][0]['AssociatePublicIpAddress'])
        self.assertEqual(instance['NetworkInterfaces'][0]['PrivateIpAddress'],'10.20.2.30')
        sg=resources['ProbeSecurityGroup']['Properties']
        self.assertEqual(sg['SecurityGroupIngress'],[])
        self.assertEqual(sg['SecurityGroupEgress'],[{'IpProtocol':'tcp','FromPort':443,'ToPort':443,'DestinationPrefixListId':{'Ref':'S3PrefixListId'}}])
        userdata=instance['UserData']['Fn::Base64']['Fn::Sub']
        self.assertLess(len(userdata.encode()),16384)
        self.assertTrue(data['Parameters']['BundleUrl']['NoEcho'])


if __name__=='__main__':
    unittest.main()
