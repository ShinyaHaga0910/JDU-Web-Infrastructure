import copy
import hashlib
import io
import json
import unittest
from unittest.mock import Mock

from test_identity_grade import IdentityGradeTest
from status_gateway import student_status


class GatewayTest(unittest.TestCase):
    def setUp(self):
        f = IdentityGradeTest('test_verified_subject_reads_only_own_existing_grade')
        f.setUp()
        self.f = f
        self.instances = {r: 'i-' + str(i) * 17 for i, r in enumerate(('bastion', 'web', 'dns', 'db', 'repo'), 1)}
        f.meta['instances'] = dict(self.instances)
        self.arn = 'arn:aws:lambda:us-east-1:123456789012:function:jdu-web-status-test-lab'
        self.digest = hashlib.sha256(self.arn.encode()).hexdigest()
        for key in [(f.pk, 'BINDING'), ('LAB#test-lab', 'BINDING'), ('ACCOUNT#123456789012', 'BINDING')]:
            f.bindings.rows[key]['connector'] = self.digest
        self.connector = {'arn': self.arn, 'account': '123456789012', 'lab_id': 'test-lab',
                          'deployment_id': 'same', 'active': True}
        f.bindings.rows[('CONNECTOR#' + self.digest, 'META')] = copy.deepcopy(self.connector)
        self.observation = {'lab_id': 'test-lab', 'account': '123456789012',
            'observed_at': '2026-10-27T12:00:00+00:00', 'stack_status': 'CREATE_COMPLETE',
            'instances': [{'role': role, 'instance_id': instance, 'ec2_state': 'stopped',
                'ssm_state': 'unknown', 'ssm_last_ping': None, 'public_ip': None,
                'private_ip': '10.20.1.1'} for role, instance in self.instances.items()]}
        self.client = Mock()
        self.response()

    def response(self, observation=None):
        payload = json.dumps({'status': 'ok', 'observation': observation or self.observation}).encode()
        self.client.invoke.return_value = {'StatusCode': 200, 'Payload': io.BytesIO(payload)}

    def run_gateway(self, subject=None):
        f = self.f
        return student_status(subject or f.subject, f.pepper, f.bindings, f.store, self.client)

    def test_registered_identity_invokes_only_fixed_function_and_reads_five(self):
        result = self.run_gateway()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['observation']['instances']), 5)
        self.assertTrue(all(row['ec2_state'] == 'stopped' for row in result['observation']['instances']))
        self.client.invoke.assert_called_once_with(FunctionName=self.arn, InvocationType='RequestResponse',
                                                   Payload=b'{"operation":"status"}')
        self.client.start_instances.assert_not_called()

    def test_unregistered_identity_and_unapproved_connector_never_invoke(self):
        self.assertEqual(self.run_gateway('9999999999'), {'status': 'unauthorized'})
        self.f.bindings.rows[('CONNECTOR#' + self.digest, 'META')]['arn'] = 'https://attacker.invalid/'
        self.assertEqual(self.run_gateway(), {'status': 'unavailable'})
        self.client.invoke.assert_not_called()

    def test_other_instances_and_bad_addresses_fail_closed(self):
        for patch in ('instance', 'address', 'state', 'account'):
            with self.subTest(patch=patch):
                other = copy.deepcopy(self.observation)
                if patch == 'instance': other['instances'][0]['instance_id'] = 'i-' + '9'*17
                if patch == 'address': other['instances'][0]['public_ip'] = '<script>'
                if patch == 'state': other['instances'][0]['ec2_state'] = 'running<script>'
                if patch == 'account': other['account'] = '999999999999'
                self.response(other)
                self.assertEqual(self.run_gateway(), {'status': 'unavailable'})

    def test_binding_revoked_while_remote_runs_discards_observation(self):
        f = self.f
        def invoke(**kwargs):
            f.bindings.rows[(f.pk, 'BINDING')]['active'] = False
            return {'StatusCode': 200, 'Payload': io.BytesIO(json.dumps({'status':'ok', 'observation':self.observation}).encode())}
        self.client.invoke.side_effect = invoke
        self.assertEqual(self.run_gateway(), {'status': 'unauthorized'})

    def test_failed_or_large_response_does_not_become_a_stop_or_zero(self):
        private = {'status': 'unavailable', 'diagnostic': {'code': 'AccessDenied', 'operation': 'DescribeStacks'}}
        self.client.invoke.return_value = {'StatusCode': 200, 'Payload': io.BytesIO(json.dumps(private).encode())}
        self.assertEqual(self.run_gateway(), {'status': 'unavailable'})
        self.client.invoke.return_value = {'StatusCode': 200, 'Payload': io.BytesIO(b'x' * 65537)}
        self.assertEqual(self.run_gateway(), {'status': 'unavailable'})
        self.client.invoke.side_effect = RuntimeError('sensitive internal text')
        self.assertEqual(self.run_gateway(), {'status': 'unavailable'})
