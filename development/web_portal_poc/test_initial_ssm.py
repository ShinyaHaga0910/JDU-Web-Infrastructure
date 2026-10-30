"""Moto journal with fake SSM: acceptance recovery, never resending a command."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import test_initial_stack as fixtures
from initial_ssm import JournaledSsm, InitialPending
from portal_enrollment import EnrollmentDenied


class InitialSsmTest(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.InitialStackTest('test_double_click_and_status_only_observe_same_stack')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.client=Mock()
        self.client.meta.config.retries={'total_max_attempts':1}
        self.id='12345678-1234-1234-1234-123456789012'
        self.request={'InstanceIds':['i-01234567890123456'],'DocumentName':'AWS-RunShellScript',
            'Parameters':{'commands':['public-source-only'],'executionTimeout':['90']},'TimeoutSeconds':30}
        self.client.send_command.return_value={'Command':{'CommandId':self.id}}
        self.client.list_commands.return_value={'Commands':[]}
        self.adapter=JournaledSsm(self.f.worker,self.client,'ssh-init')

    def accepted(self):
        return {**copy.deepcopy(self.request),'CommandId':self.id,'Comment':self.adapter.saved()['comment']}

    def lose_reply(self):
        self.client.send_command.side_effect=RuntimeError('synthetic-private-error')
        with self.assertRaises(InitialPending):self.adapter.send_command(**self.request)

    def test_duplicate_uses_original_handle_and_rejects_changed_payload(self):
        first=self.adapter.send_command(**self.request)
        self.assertEqual(self.adapter.send_command(**self.request),first)
        self.assertEqual(self.client.send_command.call_count,1)
        self.client.list_commands.assert_not_called()
        changed=copy.deepcopy(self.request);changed['Parameters']['commands']=['different']
        with self.assertRaises(EnrollmentDenied):self.adapter.send_command(**changed)

    def test_unknown_acceptance_is_recovered_from_aws_including_page_two(self):
        self.lose_reply()
        command=self.accepted()
        self.client.list_commands.side_effect=[{'Commands':[],'NextToken':'second'}, {'Commands':[command]}]
        result=self.adapter.send_command(**self.request)
        self.assertEqual(result['Command']['CommandId'],self.id)
        self.assertEqual(self.client.send_command.call_count,1)
        self.assertEqual(self.client.list_commands.call_args.kwargs['NextToken'],'second')
        self.assertEqual(self.adapter.saved()['command_id'],self.id)

    def test_unknown_absent_mismatch_or_multiple_never_resends(self):
        self.lose_reply()
        with self.assertRaises(InitialPending):self.adapter.send_command(**self.request)
        command=self.accepted();command['Parameters']={'commands':['changed']}
        self.client.list_commands.return_value={'Commands':[command]}
        with self.assertRaises(EnrollmentDenied):self.adapter.send_command(**self.request)
        command=self.accepted()
        self.client.list_commands.return_value={'Commands':[command,{**command,'CommandId':'a'*36}]}
        with self.assertRaises(EnrollmentDenied):self.adapter.send_command(**self.request)
        self.assertEqual(self.client.send_command.call_count,1)

    def test_deadline_invalid_target_and_sdk_retries_cannot_send(self):
        adapter=JournaledSsm(self.f.worker,self.client,'ssh-init',remaining=lambda:7999)
        with self.assertRaises(InitialPending):adapter.send_command(**self.request)
        with self.assertRaises(EnrollmentDenied):self.adapter.send_command(**{**self.request,'InstanceIds':['one','two']})
        self.client.meta.config.retries={'total_max_attempts':2}
        with self.assertRaises(EnrollmentDenied):JournaledSsm(self.f.worker,self.client,'ssh-init')
        self.client.send_command.assert_not_called()
        self.assertIsNone(adapter.saved())


if __name__=='__main__':unittest.main()
