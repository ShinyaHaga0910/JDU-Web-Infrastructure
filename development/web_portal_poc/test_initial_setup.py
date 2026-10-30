"""Actual closure/node/guest-command adapters; Moto state; fake AWS responses.

No real SSH, SSM, new key, service installation or signature is claimed.
"""
import base64
import copy
from datetime import timedelta
from decimal import Decimal
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

import test_initial_stack as fixtures
from initial_setup import InitialSetup, collect_foundation
from initial_ssm import InitialPending
from initial_worker import InitialWorker
from portal_enrollment import encoded, key


class InitialSetupTest(unittest.TestCase):
    def setUp(self):
        # Public-key parsing and command compilation only; this fake never
        # replaces any Linux account/permission operation in production.
        if sys.platform=='win32':
            compatibility=patch.dict(sys.modules,{'pwd':SimpleNamespace()})
            compatibility.start();self.addCleanup(compatibility.stop)
        self.f=fixtures.InitialStackTest('test_double_click_and_status_only_observe_same_stack')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.initialize_created()

    def initialize_created(self):
        f=self.f
        f.worker.create(f.plan,f.password_hash)
        f.actual['StackStatus']='CREATE_COMPLETE'
        labels={'bastion':'Bastion','web':'Web','dns':'Dns','db':'Db','repo':'Repo'}
        refs={'BootstrapSg':'sg-bootstrap'}
        self.nodes={}
        self.instances={}
        for n,(role,label) in enumerate(labels.items(),1):
            iid=f'i-{n:017x}';vid=f'vol-{n:017x}'
            refs[label+'Instance']=iid;refs[label+'Sg']='sg-'+role
            node={'instance_id':iid,'private_ip':f'10.20.1.{n}','root_volumes':[vid]}
            self.nodes[role]=node
            self.instances[iid]={'InstanceId':iid,'PrivateIpAddress':node['private_ip'],
                'BlockDeviceMappings':[{'Ebs':{'VolumeId':vid}}],'State':{'Name':'running'},
                'Tags':[{'Key':k,'Value':f.grant[k2]} for k,k2 in [('LabId','lab_id'),('DeploymentId','deployment_id')]],
                'SecurityGroups':[{'GroupId':'sg-'+role},{'GroupId':'sg-bootstrap'}],
                'Placement':{'AvailabilityZone':'us-east-1a'}}
        f.cfn.get_paginator.return_value.paginate.return_value=[{'StackResourceSummaries':[
            {'LogicalResourceId':k,'PhysicalResourceId':v} for k,v in refs.items()]}]
        f.ec2.describe_instances.side_effect=lambda **kw:{'Reservations':[{'Instances':[self.instances[kw['InstanceIds'][0]]]}]}
        self.pub='ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+b'x'*32).decode()
        f.ec2.get_console_output.return_value={'Output':'BEGIN SSH HOST KEY KEYS\n'+self.pub+'\nEND SSH HOST KEY KEYS'}
        self.change={'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','ChangeSetId':'synthetic-closure',
            'Changes':[{'ResourceChange':{'LogicalResourceId':name,'ResourceType':kind,'Action':'Modify','Replacement':'False'}}
                for name,kind in [('BootstrapSg','AWS::EC2::SecurityGroup'),('S3Endpoint','AWS::EC2::VPCEndpoint')]]}
        f.cfn.create_change_set.return_value={'Id':'synthetic-closure'}
        f.cfn.describe_change_set.side_effect=lambda **kw:copy.deepcopy(self.change)
        def execute(**kw):
            f.actual['StackStatus']='UPDATE_COMPLETE'
            next(p for p in f.actual['Parameters'] if p['ParameterKey']=='DeploymentPhase')['ParameterValue']='teaching'
        f.cfn.execute_change_set.side_effect=execute
        self.ssm,self.eic=Mock(),Mock()
        self.ssm.exceptions.InvocationDoesNotExist=type('InvocationDoesNotExist',(Exception,),{})
        self.ssm.meta.config.retries={'total_max_attempts':1}
        self.ssm.describe_instance_information.return_value={'InstanceInformationList':[
            {'InstanceId':v['instance_id'],'PingStatus':'Online'} for v in self.nodes.values()]}
        def send(**kw):return {'Command':{'CommandId':f'00000000-0000-0000-0000-{self.ssm.send_command.call_count:012x}'}}
        self.ssm.send_command.side_effect=send
        self.ssm.get_command_invocation.return_value={'Status':'Success','StandardOutputContent':
            json.dumps({'public_key':self.pub,'private_key_exported':False})}
        self.eic.send_ssh_public_key.return_value={'Success':True}
        self.report={'phase':'bootstrap','stack_status':'CREATE_COMPLETE',
            'all_five_role_checks_passed':True,'all_aws_checks_passed':True,'all_five_network_checks_passed':True,
            'nodes':{role:{**node,'network_result':{'phase':'BOOTSTRAP_OBSERVED',
                's3_tcp_reachable':True,'s3_bootstrap_reachable_seen':True}} for role,node in self.nodes.items()}}
        self.collector=Mock(side_effect=lambda *args:copy.deepcopy(self.report))
        self.setup=InitialSetup(f.worker,lambda:{'plan':f.plan},self.ssm,self.eic,collector=self.collector)

    def close(self):
        for _ in range(3):self.setup.advance()
        self.report.update(phase='teaching',stack_status='UPDATE_COMPLETE')
        self.assertEqual(self.setup.advance()['setup_phase'],'ssh_discover')

    def test_all_steps_keep_roots_and_verify_four_peers_after_ephemeral_expiry(self):
        before=copy.deepcopy(self.instances)
        self.assertEqual(self.setup.current()['stage'],'SETUP_REQUIRED')
        self.collector.assert_not_called();self.ssm.send_command.assert_not_called()
        self.close()
        params=self.f.cfn.create_change_set.call_args.kwargs['Parameters']
        self.assertEqual([p for p in params if not p.get('UsePreviousValue')],
                         [{'ParameterKey':'DeploymentPhase','ParameterValue':'teaching'}])
        self.assertNotIn(self.f.password_hash,json.dumps(params))
        for _ in range(9):self.setup.advance()  # host pins, bastion init, four installs
        self.assertEqual(self.setup.current()['setup_phase'],'ssh_verify')
        self.assertEqual(self.eic.send_ssh_public_key.call_count,4)
        self.assertEqual(self.ssm.send_command.call_count,5)
        self.setup.advance()
        self.assertEqual(self.setup.current()['setup_result'],'pending')
        self.assertEqual(self.ssm.send_command.call_count,5)
        self.f.now+=timedelta(seconds=64)
        for _ in range(4):self.setup.advance()
        result=self.setup.current()
        self.assertEqual(result['stage'],'REGISTRATION_PENDING')
        self.assertEqual(result['ssh_completed_roles'],4)
        self.assertTrue(result['foundation_ready']);self.assertFalse(result['lab_ready'])
        self.assertFalse(result['can_advance'])
        self.assertEqual(self.ssm.send_command.call_count,9)
        self.assertEqual(self.eic.send_ssh_public_key.call_count,4)
        self.assertEqual(self.instances,before)
        self.setup.advance();self.setup.current()
        self.assertEqual(self.ssm.send_command.call_count,9)
        self.f.ec2.terminate_instances.assert_not_called()
        journal=json.dumps(self.f.db.scan(TableName='initial-jobs')['Items'])
        for secret in [self.f.password_hash,self.f.url,'PRIVATE KEY']:
            self.assertNotIn(secret,journal)

    def test_unconfirmed_foundation_and_changed_roots_cannot_close_network(self):
        self.report['all_five_role_checks_passed']=False
        self.assertEqual(self.setup.advance()['setup_phase'],'check_foundation')
        self.f.cfn.create_change_set.assert_not_called()
        self.report['all_five_role_checks_passed']=True
        self.setup.advance()
        self.report['nodes']['web']['root_volumes']=['vol-different']
        with self.assertRaisesRegex(Exception,'roots changed'):self.setup.advance()
        self.f.cfn.create_change_set.assert_not_called()
        self.assertFalse(self.setup.get()['busy'])

    def test_closure_rejects_any_replacement_or_extra_resource(self):
        self.setup.advance();self.setup.advance()
        self.change['Changes'][0]['ResourceChange']['Replacement']='True'
        with self.assertRaises(ValueError):self.setup.advance()
        self.f.cfn.execute_change_set.assert_not_called()
        self.assertEqual(self.setup.current()['setup_result'],'unavailable')

    def test_lost_closure_reply_only_observes_original_change_set(self):
        self.setup.advance()
        self.f.cfn.create_change_set.side_effect=RuntimeError('private-upstream-canary')
        self.assertEqual(self.setup.advance()['setup_phase'],'close_plan_sent')
        self.setup.advance()
        self.assertEqual(self.f.cfn.create_change_set.call_count,1)
        self.assertEqual(self.f.cfn.execute_change_set.call_count,1)

    def test_busy_setup_and_stopped_management_cannot_run_again(self):
        self.setup.advance()
        self.f.db.update_item(TableName='initial-jobs',Key=key(self.f.worker.pk,'SETUP'),
            UpdateExpression='SET busy=:yes',ExpressionAttributeValues=encoded({':yes':True}))
        self.assertEqual(self.setup.advance()['stage'],'SETUP_OBSERVATION_REQUIRED')
        self.f.cfn.create_change_set.assert_not_called()

    def test_pending_ssm_poll_resumes_same_key_command_without_another_send(self):
        self.close()
        for _ in range(4):self.setup.advance()
        self.ssm.get_command_invocation.side_effect=InitialPending()
        self.assertEqual(self.setup.advance()['setup_phase'],'ssh_init')
        self.assertEqual(self.ssm.send_command.call_count,1)
        self.ssm.get_command_invocation.side_effect=None
        self.assertEqual(self.setup.advance()['setup_phase'],'ssh_enroll')
        self.assertEqual(self.ssm.send_command.call_count,1)

    def test_changed_actual_root_and_ssm_offline_refuse_ssh_work(self):
        self.close()
        iid=self.nodes['web']['instance_id']
        self.instances[iid]['BlockDeviceMappings'][0]['Ebs']['VolumeId']='vol-replaced'
        with self.assertRaisesRegex(ValueError,'identity changed'):self.setup.advance()
        self.instances[iid]['BlockDeviceMappings'][0]['Ebs']['VolumeId']=self.nodes['web']['root_volumes'][0]
        self.ssm.describe_instance_information.return_value={'InstanceInformationList':[]}
        self.assertEqual(self.setup.advance()['setup_result'],'pending')
        self.ssm.send_command.assert_not_called();self.eic.send_ssh_public_key.assert_not_called()

    def test_worker_observe_never_advances_and_only_explicit_advance_runs(self):
        worker=InitialWorker(self.f.worker,setup=self.setup)
        from portal_enrollment import grant_digest
        event={'grant_digest':grant_digest(self.f.grant)}
        self.assertEqual(worker.serve({**event,'operation':'observe'})['initial']['stage'],'SETUP_REQUIRED')
        self.collector.assert_not_called()
        self.assertEqual(worker.serve({**event,'operation':'advance'})['initial']['setup_phase'],'close_prepare')
        self.assertEqual(worker.serve({**event,'operation':'advance','commands':['anything']})['status'],'unauthorized')

    def test_sdk_collector_receives_native_decimal_state_and_fixed_clients(self):
        def collect(path,template,*,clients):
            self.assertEqual(json.loads(path.read_bytes())['count'],5)
            self.assertEqual(clients['sts'],self.f.sts)
            self.assertEqual(template,self.f.path)
            return {'fixture':True}
        with patch('inspect_teacher_probe.collect',side_effect=collect):
            self.assertEqual(collect_foundation(self.f.worker,{'count':Decimal(5)},self.ssm),{'fixture':True})


if __name__=='__main__':unittest.main()
