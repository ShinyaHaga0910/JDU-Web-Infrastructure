"""New-Lab assets -> real status/checker adapters; Moto and fake AWS/SSM.

The kit fixture uses accepted assessment bytes with a synthetic unsigned course
envelope. It is not a GPG claim or an actual EC2 file/service installation.
"""
import base64
import copy
from datetime import timedelta
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from zipfile import ZipFile
import uuid

import test_initial_package as packages
import test_initial_setup as setup_fixtures
from initial_teaching import InitialTeaching
from initial_ssm import InitialPending
from portal_enrollment import encoded,grant_digest,EnrollmentDenied
from initial_status_handler import serve as status
from initial_checker_handler import serve as checker


class InitialTeachingTest(unittest.TestCase):
    def setUp(self):
        if sys.platform=='win32':
            compat=patch.dict(sys.modules,{'pwd':SimpleNamespace()});compat.start();self.addCleanup(compat.stop)
        self.package=packages.InitialPackageTest('test_package_is_reproducible_uses_signed_controller_and_imports_on_linux_layout')
        self.package.setUp();self.addCleanup(self.package.doCleanups)
        f=self.package.f
        from portal_preparation import checked_assignment
        f.worker.grant=checked_assignment(f.grant)
        f.plan['manifest_sha256']=f.grant['release']['manifest_sha256']
        self.fixture=setup_fixtures.InitialSetupTest('test_all_steps_keep_roots_and_verify_four_peers_after_ephemeral_expiry')
        self.fixture.f=f;self.fixture.initialize_created();self.fixture.close()
        for _ in range(9):self.fixture.setup.advance()
        f.now+=timedelta(seconds=64)
        for _ in range(4):self.fixture.setup.advance()
        receipt={**{k:f.grant[k] for k in ('lab_id','deployment_id')},'release_id':f.manifest['release_id'],
            'registered':True,'instance_count':5,'private_credential_exported':False,'transport_private_key_retired':True}
        f.db.put_item(TableName=f.worker.table,Item=encoded({'pk':f.worker.pk,'sk':'ENROLLED',
            'grant_digest':grant_digest(f.grant),'receipt':receipt}))
        archive=f.path.parent/'worker.zip';self.package.build(archive)
        self.root=f.path.parent/'package'
        with ZipFile(archive) as z:z.extractall(self.root)
        self.env={'STUDENT_ACCOUNT':f.grant['account'],'LAB_ID':f.grant['lab_id'],'INITIAL_DEPLOYMENT_ID':f.grant['deployment_id'],
            'INITIAL_PROGRESS_TABLE':f.worker.table,'INITIAL_CHECK_TABLE':'jdu-web-check-'+f.grant['lab_id']+'-results'}
        # The actual runtime contract uses a fixed table name.
        expected='jdu-web-initial-'+f.grant['lab_id']+'-progress'
        f.db.create_table(TableName=expected,BillingMode='PAY_PER_REQUEST',
            AttributeDefinitions=[{'AttributeName':n,'AttributeType':'S'} for n in ('pk','sk')],
            KeySchema=[{'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}])
        for row in f.db.scan(TableName=f.worker.table)['Items']:f.db.put_item(TableName=expected,Item=row)
        f.worker.table=expected;self.env['INITIAL_PROGRESS_TABLE']=expected
        self.lam=Mock()
        code=base64.b64encode(b'x'*32).decode()
        handlers={'initial':'initial_worker.handler','status':'initial_status_handler.handler','check':'initial_checker_handler.handler'}
        def function(**kw):
            name=kw['FunctionName'];kind=next(k for k in handlers if name=='jdu-web-'+k+'-'+f.grant['lab_id'])
            return {'FunctionArn':'arn:aws:lambda:us-east-1:'+f.grant['account']+':function:'+name,
                'Handler':handlers[kind],'Runtime':'python3.11','Role':'arn:aws:iam::'+f.grant['account']+':role/LabRole',
                'CodeSha256':code,'Environment':{'Variables':dict(self.env)}}
        self.lam.get_function_configuration.side_effect=function
        def invoke(**kw):
            event=json.loads(kw['Payload'])
            args=(event,self.root,self.env,f.db,f.sts,f.cfn,f.ec2,self.fixture.ssm)
            result=status(*args) if kw['FunctionName'].endswith('jdu-web-status-'+f.grant['lab_id']) else checker(*args)
            return {'StatusCode':200,'Payload':io.BytesIO(json.dumps(result).encode())}
        self.lam.invoke.side_effect=invoke
        def stage_reply(**kw):
            role=next(r for r,n in self.fixture.nodes.items() if n['instance_id']==kw['InstanceId'])
            return {'Status':'Success','StandardOutputContent':json.dumps({'public_resources_ready':True,
                'role':role,'file_count':5,'services_changed':False})}
        self.fixture.ssm.get_command_invocation.side_effect=stage_reply
        self.teaching=InitialTeaching(self.fixture.setup,self.root,self.env,self.lam)

    def test_two_public_stages_and_actual_adapter_probes_required_before_ready(self):
        self.assertFalse(self.teaching.current()['lab_ready'])
        self.assertEqual(self.teaching.advance()['teaching_completed_roles'],1)
        self.assertEqual(self.teaching.advance()['teaching_completed_roles'],2)
        self.assertIsNone(self.teaching.get('READY'))
        result=self.teaching.advance()
        self.assertEqual(result['stage'],'INITIAL_READY');self.assertTrue(result['lab_ready'])
        self.assertEqual(self.fixture.ssm.send_command.call_count,11)
        self.assertEqual(self.lam.invoke.call_count,2)
        self.teaching.current();self.teaching.advance()
        self.assertEqual(self.fixture.ssm.send_command.call_count,11)
        self.assertEqual(self.lam.invoke.call_count,2)
        from initial_worker import InitialWorker
        worker=InitialWorker(self.fixture.f.worker,setup=self.fixture.setup,teaching=self.teaching)
        event={'grant_digest':grant_digest(self.fixture.f.grant)}
        self.assertEqual(worker.serve({**event,'operation':'observe'})['initial']['stage'],'INITIAL_READY')
        self.assertEqual(worker.serve({**event,'operation':'advance'})['initial']['stage'],'INITIAL_READY')
        self.fixture.f.ec2.start_instances.assert_not_called()
        self.fixture.f.ec2.terminate_instances.assert_not_called()

    def test_pending_command_continues_original_ssm_handle_without_resend(self):
        original=self.fixture.ssm.get_command_invocation.side_effect
        self.fixture.ssm.get_command_invocation.side_effect=None
        self.fixture.ssm.get_command_invocation.return_value={'Status':'InProgress'}
        with self.assertRaises(InitialPending):self.teaching.advance()
        self.assertEqual(self.fixture.ssm.send_command.call_count,10)
        self.fixture.ssm.get_command_invocation.side_effect=original
        self.assertEqual(self.teaching.advance()['teaching_completed_roles'],1)
        self.assertEqual(self.fixture.ssm.send_command.call_count,10)

    def test_bad_lesson_ack_or_changed_file_cannot_claim_ready(self):
        self.fixture.ssm.get_command_invocation.side_effect=None
        self.fixture.ssm.get_command_invocation.return_value={'Status':'Success','StandardOutputContent':
            json.dumps({'public_resources_ready':True,'role':'web','file_count':5,'services_changed':True})}
        with self.assertRaises(EnrollmentDenied):self.teaching.advance()
        self.assertIsNone(self.teaching.get('TEACHING#web'));self.assertIsNone(self.teaching.get('READY'))
        (self.root/'catalog-app.tar.gz').write_bytes(b'changed')
        with self.assertRaises(EnrollmentDenied):self.teaching.current()

    def test_different_connector_code_or_unavailable_status_cannot_set_ready(self):
        self.teaching.advance();self.teaching.advance()
        original=self.lam.get_function_configuration.side_effect
        def changed(**kw):
            result=original(**kw)
            if kw['FunctionName'].startswith('jdu-web-check-'):result['CodeSha256']=base64.b64encode(b'y'*32).decode()
            return result
        self.lam.get_function_configuration.side_effect=changed
        with self.assertRaises(EnrollmentDenied):self.teaching.advance()
        self.assertIsNone(self.teaching.get('READY'))
        self.lam.get_function_configuration.side_effect=original
        self.lam.invoke.side_effect=lambda **kw:{'StatusCode':200,'Payload':io.BytesIO(b'{"status":"unavailable"}')}
        with self.assertRaises(InitialPending):self.teaching.advance()
        self.assertIsNone(self.teaching.get('READY'))

    def test_status_after_stop_reads_same_five_without_commands_or_invented_scores(self):
        for _ in range(3):self.teaching.advance()
        for instance in self.fixture.instances.values():instance['State']['Name']='stopped'
        self.fixture.ssm.describe_instance_information.return_value={'InstanceInformationList':[]}
        f=self.fixture.f
        answer=status({'operation':'status'},self.root,self.env,f.db,f.sts,f.cfn,f.ec2,self.fixture.ssm)
        self.assertEqual(answer['status'],'ok')
        self.assertEqual({n['ec2_state'] for n in answer['observation']['instances']},{'stopped'})
        self.assertEqual(self.fixture.ssm.send_command.call_count,11)
        self.assertTrue(self.teaching.current()['lab_ready'])  # initial readiness, not running state
        self.assertNotIn('score',answer)

    def test_checker_before_ready_and_wrong_target_never_create_a_job(self):
        f=self.fixture.f
        self.assertEqual(checker({'operation':'start','spec':{}},self.root,self.env,f.db,f.sts,f.cfn,f.ec2,self.fixture.ssm),{'status':'unavailable'})
        self.assertEqual(self.fixture.ssm.send_command.call_count,9)
        from initial_context import context
        with self.assertRaises(EnrollmentDenied):context(self.root,{**self.env,'STUDENT_ACCOUNT':'999999999999'},f.db)
        self.assertEqual(status({'operation':'status','target':'other'},self.root,self.env,f.db,f.sts,f.cfn,f.ec2,self.fixture.ssm),{'status':'unauthorized'})


if __name__=='__main__':unittest.main()
