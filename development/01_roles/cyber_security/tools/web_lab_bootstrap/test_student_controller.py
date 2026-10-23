import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch

from build_controller_bundle import bundle
from controller_runtime import controller_files,install_controller
import student_controller as controller


class BootstrapDestinationGuards(unittest.TestCase):
    def setUp(self):
        self.manifest=dict(region='us-east-1',bootstrap=dict(bucket='signed-fixture',release_prefix='c4/'),
            artifacts=dict(repo_bundle=dict(path='repo-bundle.tar.gz',size_bytes=123,sha256='a'*64)))
        self.key='c4/repo-bundle.tar.gz'

    def test_regional_global_and_path_style_presigned_destinations(self):
        for host,path in [('signed-fixture.s3.us-east-1.amazonaws.com','/'+self.key),
                ('signed-fixture.s3.amazonaws.com','/'+self.key),
                ('s3.us-east-1.amazonaws.com','/signed-fixture/'+self.key),
                ('s3.amazonaws.com','/signed-fixture/'+self.key)]:
            url='https://'+host+path+'?AWSAccessKeyId=fixture&Signature=fixture&Expires=9999999999'
            with self.subTest(host=host):self.assertEqual(controller.validate_bootstrap_url(url,self.manifest,self.key),url)
        other=dict(self.manifest,region='us-west-2')
        with self.assertRaises(ValueError):controller.validate_bootstrap_url(url,other,self.key)

    def test_wrong_destination_and_ambiguous_url_rejected_without_disclosure(self):
        good='https://signed-fixture.s3.us-east-1.amazonaws.com/'+self.key
        for url in [good,good+'?secret=fixture#fragment',good.replace('https:','http:')+'?secret=fixture',
                good.replace('signed-fixture.','other.')+'?secret=fixture',
                good.replace('amazonaws.com','amazonaws.com.evil.example')+'?secret=fixture',
                good.replace('https://','https://someone@')+'?secret=fixture',
                good.replace('.com/','.com:444/')+'?secret=fixture',
                good.replace(self.key,'c4/other.tar.gz')+'?secret=fixture',
                good+'?secret=fixture\n',good+'?secret=fixture value']:
            with self.subTest(url=url),self.assertRaises(ValueError) as failure:
                controller.validate_bootstrap_url(url,self.manifest,self.key)
            self.assertNotIn('secret=fixture',str(failure.exception))

    def test_stored_bundle_rejected_before_presigning(self):
        s3=Mock();s3.head_object.return_value=dict(ContentLength=124,Metadata=dict(sha256='a'*64))
        with self.assertRaisesRegex(ValueError,'Stored bundle differs'):
            controller.bootstrap_url(dict(manifest=self.manifest),SimpleNamespace(bootstrap_url_file=None),s3)
        s3.generate_presigned_url.assert_not_called()

    def test_private_url_file_requires_private_regular_single_link(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'url';file.write_text('https://signed-fixture.s3.amazonaws.com/'+self.key+'?Signature=fixture');file.chmod(0o600)
            args=SimpleNamespace(bootstrap_url_file=str(file));s3=Mock()
            self.assertIn('s3.amazonaws.com',controller.bootstrap_url(dict(manifest=self.manifest),args,s3))
            s3.head_object.assert_not_called()
            file.chmod(0o644)
            with self.assertRaises(ValueError):controller.bootstrap_url(dict(manifest=self.manifest),args,s3)
            file.chmod(0o600);(Path(d)/'link').hardlink_to(file)
            with self.assertRaises(ValueError):controller.bootstrap_url(dict(manifest=self.manifest),args,s3)


class CredentialEndpointGuards(unittest.TestCase):
    def test_student_config_must_match_signed_teacher_for_install_and_register(self):
        m=dict(release_id='release-fixture',grading=dict(fqdn='fixture.execute-api.us-east-1.amazonaws.com',ipv4='44.216.176.215'))
        state=dict(lab_id='lab-fixture')
        good=dict(schema_version=1,lab_id=state['lab_id'],release_id=m['release_id'],api_base_url='https://'+m['grading']['fqdn'],
            fixed_ingress_ipv4=m['grading']['ipv4'],lab_token='fake-fixture-token')
        fake=SimpleNamespace(private_json=lambda path:good)
        with patch.dict('sys.modules',web_progress=fake):
            self.assertEqual(controller.student_credential(dict(manifest=m),state,'ignored'),good)
            for field,value in [('api_base_url','https://other.execute-api.us-east-1.amazonaws.com'),
                    ('fixed_ingress_ipv4','1.1.1.1'),('release_id','other'),('lab_id','other'),('lab_token',''),('schema_version',2)]:
                changed=dict(good);changed[field]=value;fake.private_json=lambda path:changed
                with self.subTest(field=field),self.assertRaises(ValueError):controller.student_credential(dict(manifest=m),state,'ignored')


class ControllerArchiveGuards(unittest.TestCase):
    def test_deterministic_public_bundle_and_cache_tamper_rejection(self):
        data,m=bundle(Path(__file__).resolve().parent)
        self.assertEqual(data,bundle(Path(__file__).resolve().parent)[0]);self.assertFalse(m['credentials_included'])
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'controller';install_controller(data,target);install_controller(data,target)
            (target/'student_controller.py').write_text('changed')
            with self.assertRaises(ValueError):install_controller(data,target)
    def test_links_traversal_and_duplicates_rejected(self):
        import tarfile
        for name,kind in [('controller/../escape',tarfile.REGTYPE),('/absolute',tarfile.REGTYPE),('controller/link',tarfile.SYMTYPE)]:
            out=io.BytesIO()
            with tarfile.open(fileobj=out,mode='w') as tar:
                i=tarfile.TarInfo(name);i.type=kind;i.linkname='/tmp/escape';i.size=1;tar.addfile(i,io.BytesIO(b'x'))
            with self.subTest(name=name),self.assertRaises(ValueError):controller_files(gzip.compress(out.getvalue()))


class StudentOperationGuards(unittest.TestCase):
    def fixture(self,d):
        m=dict(region='us-east-1',release_id='web-2026-10-r1')
        verified=dict(manifest=m,manifest_sha256='a'*64)
        p=dict(account='111111111111',region='us-east-1',manifest_sha256='a'*64,stack_name='jdu-web-fixture',
               lab_id='fixture',release_id='web-2026-10-r1')
        path=Path(d)/'plan.json';controller.save_new(path,p)
        a=SimpleNamespace(plan=str(path),state=str(Path(d)/'new-state.json'),confirmed_access=True)
        return verified,p,a
    def test_pilot_budget_counts_stopped_nodes_too(self):
        self.assertTrue(controller.budget_check([{}]*4)['within_pilot_budget'])
        self.assertFalse(controller.budget_check([{}]*5)['within_pilot_budget'])
        self.assertEqual(controller.budget_check([{}]*9)['projected'],14)
    def test_resource_guard_prevents_password_prompt_or_create(self):
        with tempfile.TemporaryDirectory() as d:
            verified,p,a=self.fixture(d);ec2=Mock();ec2.get_paginator.return_value.paginate.return_value=[dict(Reservations=[dict(Instances=[{}]*9)])]
            def client(name,**kwargs):
                if name=='sts':return SimpleNamespace(get_caller_identity=lambda:dict(Account=p['account']))
                if name=='ec2':return ec2
                raise AssertionError('No mutation client may be used')
            with patch.dict('sys.modules',boto3=SimpleNamespace(client=client)),patch.object(controller.sys.stdin,'isatty',return_value=True),patch.object(controller.getpass,'getpass') as password:
                with self.assertRaisesRegex(ValueError,'resource ceiling'):controller.create(verified,a)
                password.assert_not_called();self.assertFalse(Path(a.state).exists())
    def test_wrong_account_rejected_before_ec2_or_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            verified,p,a=self.fixture(d)
            def client(name,**kwargs):
                if name=='sts':return SimpleNamespace(get_caller_identity=lambda:dict(Account='222222222222'))
                raise AssertionError('Must reject before further AWS calls')
            with patch.dict('sys.modules',boto3=SimpleNamespace(client=client)),patch.object(controller.sys.stdin,'isatty',return_value=True),patch.object(controller.getpass,'getpass') as password:
                with self.assertRaises(ValueError):controller.create(verified,a)
                password.assert_not_called()
    def test_bundle_checks_fail_before_human_password_or_stack_request(self):
        class MissingStack(Exception):
            response=dict(Error=dict(Code='ValidationError',Message='Stack with id jdu-web-fixture does not exist'))
        with tempfile.TemporaryDirectory() as d:
            verified,p,a=self.fixture(d)
            template=Path(d)/'template.json';template.write_text('{}')
            import hashlib
            p.update(template_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),key_name='vockey',
                student_public_key='ssh-ed25519 fixture',planned_at=controller.datetime.now(controller.timezone.utc).isoformat(),
                s3_probe_ipv4='1.2.3.4',direct_api_probe_ipv4='1.2.3.5')
            controller.update(a.plan,p)
            verified['files']=dict(template=template)
            verified['manifest'].update(ami=dict(id='ami-fixture'),grading=dict(ipv4='44.216.176.215',fqdn='fixture.execute-api.us-east-1.amazonaws.com'),
                artifacts=dict(repo_bundle=dict(size_bytes=123,sha256='a'*64)))
            ec2=Mock();ec2.get_paginator.return_value.paginate.return_value=[]
            ec2.describe_key_pairs.return_value=dict(KeyPairs=[dict(PublicKey='ssh-ed25519 fixture')])
            cfn=Mock();cfn.exceptions=SimpleNamespace(ClientError=MissingStack);cfn.describe_stacks.side_effect=MissingStack()
            iam=Mock();iam.get_instance_profile.return_value=dict(InstanceProfile=dict(InstanceProfileName='LabInstanceProfile',Roles=[{}]))
            def client(name,**kwargs):
                return {'sts':SimpleNamespace(get_caller_identity=lambda:dict(Account=p['account'])),
                        'ec2':ec2,'cloudformation':cfn,'iam':iam,'s3':Mock()}[name]
            fake_web=SimpleNamespace(check_ami=Mock());fake_prepare=SimpleNamespace(tls_control=Mock())
            with patch.dict('sys.modules',boto3=SimpleNamespace(client=client),web_lab=fake_web,prepare_teacher_probe=fake_prepare),\
                    patch.object(controller.sys.stdin,'isatty',return_value=True),\
                    patch.object(controller,'bootstrap_url',side_effect=ValueError('Stored bundle differs')),\
                    patch.object(controller.getpass,'getpass') as password:
                with self.assertRaisesRegex(ValueError,'Stored bundle differs'):controller.create(verified,a)
                password.assert_not_called();cfn.create_stack.assert_not_called();self.assertFalse(Path(a.state).exists())
    def test_private_file_links_and_public_mode_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'private.json';controller.save_new(file,dict(nonsecret_fixture=True))
            file.chmod(0o644)
            with self.assertRaises(ValueError):controller.private(file)
            file.chmod(0o600);link=Path(d)/'link';link.symlink_to(file)
            with self.assertRaises(ValueError):controller.private(link)
    def test_parallel_state_operations_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json'
            with controller.locked(path):
                with self.assertRaises(BlockingIOError):
                    with controller.locked(path):pass


if __name__=='__main__':unittest.main()
