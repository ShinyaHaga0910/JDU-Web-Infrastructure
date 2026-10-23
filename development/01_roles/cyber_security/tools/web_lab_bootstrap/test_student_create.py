"""Exercise actual selector -> signed template -> create SDK boundary; no AWS."""
from contextlib import ExitStack,redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import student_controller as controller

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'web_lab_instance_selector'))
import select_instances
from test_select_instances import fixture


class MissingStack(Exception):
    response=dict(Error=dict(Code='ValidationError',Message='Stack with id jdu-web-fixture does not exist'))


class ActualSelectorCreateBoundary(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        template=ROOT.parents[3]/'03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c3/web-lab-ssm-c3.template.json'
        self.manifest=dict(region='us-east-1',release_id='web-2026-10-r1',ami=dict(id='ami-fixture'),
            grading=dict(ipv4='44.216.176.215',fqdn='fixture.execute-api.us-east-1.amazonaws.com'),
            artifacts=dict(repo_bundle=dict(path='repo-bundle.tar.gz',sha256='a'*64,size_bytes=123)),
            network=dict(s3_prefix_list_id='pl-fixture'),bootstrap=dict(bucket='fixture-bucket',release_prefix='c4/'))
        self.verified=dict(manifest=self.manifest,manifest_sha256='b'*64,files=dict(template=template))
        self.plan=dict(account='111111111111',region='us-east-1',manifest_sha256='b'*64,stack_name='jdu-web-fixture',
            lab_id='fixture',release_id=self.manifest['release_id'],deployment_id='f30a05e6-8356-4a65-8765-e5f4f031525b',
            template_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),key_name='vockey',student_public_key='ssh-ed25519 fixture',
            planned_at=controller.datetime.now(controller.timezone.utc).isoformat(),s3_probe_ipv4='1.2.3.4',direct_api_probe_ipv4='1.2.3.5',
            selection=select_instances.select_plan(fixture()))
        self.args=SimpleNamespace(plan=str(self.root/'plan.json'),state=str(self.root/'state.json'),confirmed_access=True,bootstrap_url_file=None)
        controller.save_new(self.args.plan,self.plan)
        self.ec2=Mock();self.ec2.get_paginator.return_value.paginate.return_value=[]
        self.ec2.describe_key_pairs.return_value=dict(KeyPairs=[dict(PublicKey=self.plan['student_public_key'])])
        self.cfn=Mock();self.cfn.exceptions=SimpleNamespace(ClientError=MissingStack);self.cfn.describe_stacks.side_effect=MissingStack()
        self.cfn.create_stack.return_value=dict(StackId='fixture-stack-id')
        iam=Mock();iam.get_instance_profile.return_value=dict(InstanceProfile=dict(InstanceProfileName='LabInstanceProfile',Roles=[{}]))
        s3=Mock();s3.head_object.return_value=dict(ContentLength=123,Metadata=dict(sha256='a'*64))
        s3.generate_presigned_url.return_value='https://fixture-bucket.s3.amazonaws.com/c4/repo-bundle.tar.gz?Signature=fake'
        self.clients={'ec2':self.ec2,'cloudformation':self.cfn,'iam':iam,'s3':s3,
            'sts':SimpleNamespace(get_caller_identity=lambda:dict(Account=self.plan['account']))}
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict('sys.modules',boto3=SimpleNamespace(client=lambda name,**kw:self.clients[name]),
            web_lab=SimpleNamespace(check_ami=Mock()),prepare_teacher_probe=SimpleNamespace(tls_control=Mock())))
        self.stack.enter_context(patch.object(controller.sys.stdin,'isatty',return_value=True))
        self.password=self.stack.enter_context(patch.object(controller.getpass,'getpass',return_value='DisposableFixtureOnly23'))
        self.output=io.StringIO();self.stack.enter_context(redirect_stdout(self.output))

    def test_real_selector_output_reaches_sdk_and_saves_no_secrets(self):
        self.assertEqual(controller.create(self.verified,self.args)['stage'],'CREATE_IN_PROGRESS')
        call=self.cfn.create_stack.call_args.kwargs
        values={x['ParameterKey']:x['ParameterValue'] for x in call['Parameters']}
        self.assertEqual(values['BastionInstanceType'],'t3a.medium')
        self.assertEqual(values['SmallInstanceType'],'t3a.small');self.assertEqual(values['DnsInstanceType'],'t3a.micro')
        self.assertEqual(set(values),set(json.loads(call['TemplateBody'])['Parameters']))
        self.assertTrue(values['RdpPasswordHash'].startswith('$6$'))
        saved=Path(self.args.state).read_text();self.assertNotIn('DisposableFixtureOnly23',saved)
        self.assertNotIn(values['RdpPasswordHash'],saved);self.assertNotIn(values['BundleUrl'],saved)
        self.assertNotIn(values['RdpPasswordHash'],self.output.getvalue())
        self.assertEqual(json.loads(saved)['phase'],'CREATE_IN_PROGRESS')

    def test_mismatched_role_size_stops_before_password(self):
        self.plan['selection']['roles']['Package']['instance_type']='t3a.micro';controller.update(self.args.plan,self.plan)
        with self.assertRaisesRegex(ValueError,'role sizes'):controller.create(self.verified,self.args)
        self.password.assert_not_called();self.cfn.create_stack.assert_not_called()

    def test_all_nodes_ssm_template_reaches_sdk_with_same_parameter_contract(self):
        from all_nodes_ssm import template
        new=template(json.loads(self.verified['files']['template'].read_text()))
        path=self.root/'all-ssm-template.json'; path.write_text(json.dumps(new,separators=(',',':'))+'\n')
        self.verified['files']['template']=path
        self.plan['template_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();controller.update(self.args.plan,self.plan)
        self.assertEqual(controller.create(self.verified,self.args)['stage'],'CREATE_IN_PROGRESS')
        call=self.cfn.create_stack.call_args.kwargs
        self.assertLessEqual(len(call['TemplateBody'].encode()),51200)
        self.assertEqual(len(call['Parameters']),21)
        for label in ('Bastion','Web','Dns','Db','Repo'):
            self.assertEqual(json.loads(call['TemplateBody'])['Resources'][label+'Instance']['Properties']['IamInstanceProfile'],'LabInstanceProfile')

    def test_lowercase_or_missing_roles_stop_before_password(self):
        self.plan['selection']['roles']={k.lower():v for k,v in self.plan['selection']['roles'].items()};controller.update(self.args.plan,self.plan)
        with self.assertRaisesRegex(ValueError,'selection differs'):controller.create(self.verified,self.args)
        self.password.assert_not_called()

    def test_template_contract_mismatch_stops_before_password(self):
        t=json.loads(self.verified['files']['template'].read_text());t['Parameters']['NewRequiredParameter']={'Type':'String'}
        p=self.root/'changed-template.json';p.write_text(json.dumps(t));self.verified['files']['template']=p
        self.plan['template_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();controller.update(self.args.plan,self.plan)
        with self.assertRaisesRegex(ValueError,'parameter contract'):controller.create(self.verified,self.args)
        self.password.assert_not_called();self.cfn.create_stack.assert_not_called()

    def test_unknown_sdk_result_retains_pending_state_and_refuses_duplicate(self):
        self.cfn.create_stack.side_effect=RuntimeError('Simulated request timeout')
        with self.assertRaises(RuntimeError):controller.create(self.verified,self.args)
        saved=json.loads(Path(self.args.state).read_text())
        self.assertEqual(saved['phase'],'CREATE_REQUEST_PENDING');self.assertIsNone(saved['resources_created'])
        self.password.reset_mock()
        with self.assertRaisesRegex(ValueError,'Existing state retained'):controller.create(self.verified,self.args)
        self.password.assert_not_called();self.assertEqual(self.cfn.create_stack.call_count,1)

    def test_capacity_change_during_input_prevents_create(self):
        self.ec2.get_paginator.return_value.paginate.side_effect=[[],[dict(Reservations=[dict(Instances=[{}]*5)])]]
        with self.assertRaisesRegex(ValueError,'ceiling changed'):controller.create(self.verified,self.args)
        self.cfn.create_stack.assert_not_called();self.assertFalse(Path(self.args.state).exists())


if __name__=='__main__':unittest.main()
