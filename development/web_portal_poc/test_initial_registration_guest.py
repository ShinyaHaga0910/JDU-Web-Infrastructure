"""Real guest command compiler/journal, Moto; registration response is fake."""
import base64
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sys
import unittest

import test_initial_setup as fixtures
from initial_registration_guest import InitialRegistrationGuest
from portal_enrollment import EnrollmentDenied

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'01_roles/cyber_security/tools/web_lab_teacher'))


class InitialRegistrationGuestTest(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.InitialSetupTest('test_all_steps_keep_roots_and_verify_four_peers_after_ephemeral_expiry')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;f.close()
        for _ in range(9):f.setup.advance()
        f.f.now+=timedelta(seconds=64)
        for _ in range(4):f.setup.advance()
        self.guest=InitialRegistrationGuest(f.setup)
        self.cert='-----BEGIN CERTIFICATE-----\n'+'public-synthetic-fixture-'*8+'\n-----END CERTIFICATE-----\n'
        self.delivery={'schema_version':1,'certificate_sha256':hashlib.sha256(self.cert.encode()).hexdigest(),
            'ciphertext_b64':base64.b64encode(b'x'*384).decode(),'token_hash':'f'*64}

    def response(self,value):
        self.f.ssm.get_command_invocation.return_value={'Status':'Success','StandardOutputContent':json.dumps(value)}

    def recipient(self):
        self.response({'certificate_pem':self.cert,'certificate_sha256':self.delivery['certificate_sha256']})
        return self.guest.recipient()

    def ack(self):
        grant=self.f.f.grant
        return {'lab_id':grant['lab_id'],'deployment_id':grant['deployment_id'],
            'release_id':grant['release']['release_id'],'registered':True,'instance_count':5,
            'private_credential_exported':False,'transport_private_key_retired':True,'token_hash':'f'*64}

    def test_same_recipient_and_same_registration_handles_survive_retry_and_stopped_lab(self):
        first=self.recipient()
        self.assertEqual(first['instances'],{r:n['instance_id'] for r,n in self.f.nodes.items()})
        self.assertEqual(self.guest.recipient(),first)
        self.assertEqual(self.f.ssm.send_command.call_count,10)
        self.response(self.ack())
        answer=self.guest.register(self.delivery)
        self.assertTrue(answer['registered'])
        self.assertEqual(self.f.ssm.send_command.call_count,11)
        self.f.ssm.describe_instance_information.return_value={'InstanceInformationList':[]}
        self.assertEqual(self.guest.register(self.delivery),answer)
        json.dumps(self.guest.register(self.delivery))  # real DDB Decimal -> wire ints
        self.assertEqual(self.f.ssm.send_command.call_count,11)
        state=self.f.setup.current()
        self.assertEqual(state['stage'],'TEACHING_ASSETS_PENDING');self.assertFalse(state['lab_ready'])
        with self.assertRaises(EnrollmentDenied):self.guest.register({**self.delivery,'token_hash':'e'*64})

    def test_wrong_pin_or_unconfirmed_retirement_never_claims_registered(self):
        self.recipient()
        with self.assertRaises(EnrollmentDenied):self.guest.register({**self.delivery,'certificate_sha256':'e'*64})
        self.assertEqual(self.f.ssm.send_command.call_count,10)
        self.response({**self.ack(),'transport_private_key_retired':False})
        with self.assertRaises(EnrollmentDenied):self.guest.register(self.delivery)
        self.assertIsNone(self.guest.saved('ENROLLED'))
        self.assertEqual(self.f.setup.current()['stage'],'REGISTRATION_PENDING')


if __name__=='__main__':unittest.main()
