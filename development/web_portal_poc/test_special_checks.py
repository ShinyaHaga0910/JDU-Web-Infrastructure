"""Moto workflow integration with the real command compiler; guest replies are fake."""
import base64
import copy
from datetime import datetime,timezone
import json
from unittest.mock import Mock
import unittest
import uuid

import test_assessment_observation as fixtures
from assessment_command_jobs import sha,checked_spec
from student_checker_handler import StudentChecker
from special_checks import SpecialChecks
from registry import build_report,canonical_checks


class SpecialChecksTest(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ObservationTest();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.spec=copy.deepcopy(self.f.spec);self.spec['run_id']=self.spec['job_id']
        self.snapshot=copy.deepcopy(self.f.snapshot)
        self.ec2=Mock();self.ec2_state='running';self.bad_volume=False;self.snapshot_error=False
        self.web={'InstanceId':self.spec['instances']['web'],'State':{'Name':'running'},
            'Tags':[{'Key':'LabId','Value':self.spec['lab_id']},{'Key':'DeploymentId','Value':self.spec['deployment_id']}],
            'BlockDeviceMappings':[{'Ebs':{'VolumeId':self.snapshot['root_volumes']['web'][0]}}]}
        def describe(**kw):
            self.assertEqual(kw['InstanceIds'],[self.spec['instances']['web']])
            value=copy.deepcopy(self.web);value['State']['Name']=self.ec2_state
            if self.bad_volume:value['BlockDeviceMappings'][0]['Ebs']['VolumeId']='vol-'+'f'*17
            return {'Reservations':[{'Instances':[value]}]}
        self.ec2.describe_instances.side_effect=describe
        config={'state':{k:self.spec[k] for k in ('account','lab_id','deployment_id','release_id')},
                'baseline':{'nodes':{r:{'instance_id':i} for r,i in self.spec['instances'].items()}}}
        self.owner=StudentChecker(config,self.f.fixture.db,'jobs',None,None,self.ec2,self.f.fixture.ssm)
        def snapshot(spec):
            if self.snapshot_error:raise PermissionError('Unavailable')
            return {**copy.deepcopy(self.snapshot),'spec_sha256':sha(spec)}
        self.owner.snapshot=snapshot
        send=self.f.fixture.ssm.send_command
        def fresh(**kw):
            self.f.fixture.ssm.command_id=str(uuid.uuid4());return send(**kw)
        self.f.fixture.ssm.send_command=fresh

    def select(self,task,mode):self.spec.update(task_id=task,check_mode=mode)
    def call(self,operation='start',**fields):return self.owner.serve({'operation':operation,'spec':self.spec,**fields})
    def report(self,*,functional=False,retention=None):
        values={c:True for c in canonical_checks(self.spec['task_id'])}
        if 'WEB04_STOP_START_RETENTION' in values:values['WEB04_STOP_START_RETENTION']=retention
        if not functional:
            for c in ('WEB06_PASSWORD_LOGIN','WEB06_CREATE_REFLECT','WEB06_EDIT_REFLECT','WEB06_LOGOUT','WEB07_ANONYMOUS_DENIED','WEB07_BAD_PASSWORD_DENIED'):
                if c in values:values[c]=None
        return build_report(self.spec['task_id'],self.spec,values,self.spec['run_id'],
            mode='functional' if functional else 'read_only',checked_at=datetime.now(timezone.utc).isoformat())

    def prepared_storage(self):
        self.select('M3','storage')
        self.f.fixture.ssm.output=json.dumps({'report':self.report(),'storage_evidence':{
            'root_volume':self.snapshot['root_volumes']['web'][0],'marker_sha256':'a'*64,'boot_id':str(uuid.uuid4())}})
        self.assertEqual(self.call()['job']['phase'],'observing')
        self.assertEqual(self.call('advance')['job']['phase'],'awaiting_stop')

    def prepared_functional(self):
        self.select('M5','functional')
        self.f.fixture.ssm.output=json.dumps({'report':self.report(),'functional_recipient':{
            'job_id':self.spec['run_id'],'public_key':'-----BEGIN PUBLIC KEY-----\nsynthetic-public-key\n-----END PUBLIC KEY-----'}})
        self.assertEqual(self.call()['job']['phase'],'observing')
        self.assertEqual(self.call('advance')['job']['phase'],'awaiting_password')

    def test_retired_stop_start_tasks_never_send_commands_or_operate_ec2(self):
        for task in ('P3', 'M3'):
            for mode in ('read_only', 'storage', 'storage_prepare'):
                self.select(task, mode)
                self.assertEqual(self.call()['status'], 'unavailable')
        self.assertEqual(len(self.f.fixture.ssm.sends), 0)
        self.ec2.describe_instances.assert_not_called()
        self.ec2.stop_instances.assert_not_called()
        self.ec2.start_instances.assert_not_called()

    def test_functional_recipient_ciphertext_and_exact_result_are_retained(self):
        self.prepared_functional()
        context=self.call('functional_context');self.assertEqual(context['functional_recipient']['job_id'],self.spec['run_id'])
        self.assertEqual(self.call('result')['job']['phase'],'awaiting_password')
        sealed=base64.b64encode(b'x'*512).decode()
        self.assertEqual(self.call('functional_start',sealed_password=sealed)['job']['phase'],'observing')
        self.f.fixture.ssm.output=json.dumps({'report':self.report(functional=True),'storage_evidence':{}})
        result=self.call('advance');self.assertEqual(result['result']['score']['raw_earned'],13)
        self.assertEqual(self.call('report')['report']['mode'],'functional')
        altered=base64.b64encode(b'y'*512).decode()
        self.assertEqual(self.call('functional_start',sealed_password=altered)['result'],result['result'])
        self.assertEqual(SpecialChecks(self.owner,self.spec).get()['sealed_password'],sealed)
        self.assertEqual(len(self.f.fixture.ssm.sends),2)
        self.assertNotIn('password',SpecialChecks(self.owner,self.spec).get())

    def test_owner_mode_task_and_plain_password_injection_are_denied(self):
        self.prepared_functional();original=copy.deepcopy(self.spec)
        self.spec['owner_hash']='f'*64
        self.assertEqual(self.call('result')['status'],'unavailable')
        self.spec=original
        self.assertEqual(self.call('functional_start',password='synthetic-plaintext')['status'],'unauthorized')
        self.assertEqual(self.call('functional_start',sealed_password='invalid')['status'],'unavailable')
        self.assertEqual(self.call('storage_observe')['status'],'unauthorized')
        with self.assertRaises(ValueError):checked_spec({**self.spec,'task_id':'M1'})
        self.assertEqual(len(self.f.fixture.ssm.sends),1)

    def test_get_before_start_never_prepares_a_key_or_sends_commands(self):
        self.select('M6','functional')
        self.assertEqual(self.call('result')['status'],'unavailable')
        self.assertEqual(self.f.fixture.ssm.sends,[])

    def test_old_storage_resume_is_rejected_without_sending_a_command(self):
        self.select('M3', 'storage')
        self.assertEqual(self.call('storage_resume')['status'], 'unavailable')
        self.assertEqual(len(self.f.fixture.ssm.sends), 0)


if __name__=='__main__':unittest.main()
