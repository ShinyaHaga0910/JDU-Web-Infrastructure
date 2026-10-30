"""Actual issuance/binding transactions in Moto; guest/STS are fake."""
import base64
import hashlib
import copy
import unittest
from unittest.mock import Mock,patch

import test_portal_preparation as fixtures
from initial_registration import InitialRegistration
from portal_preparation import checked_assignment
from portal_enrollment import EnrollmentDenied,grant_digest,email_key


class InitialRegistrationTest(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PreparationTest('test_initial_assignment_requires_no_existing_nodes_or_grade_meta')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f
        # This test fixture's assignment is made before AWS confirmation. It
        # uses the inner deployment release, as the verified manifest does.
        row=f.row();row['grant']=checked_assignment(row['grant']);row['grant']['release']['release_id']='web-2026-10-r1';row['grant_digest']=grant_digest(row['grant'])
        f.put('bindings',row)
        for pk in ('ACCOUNT#'+f.account,'LAB#'+f.lab):
            reservation=f.prep.get(pk,'PREPARATION');reservation['grant_digest']=row['grant_digest'];f.put('bindings',reservation)
        f.confirmed();f.prep.confirm(**f.claims())
        self.instances={r:f'i-{n:017x}' for n,r in enumerate(('bastion','web','dns','db','repo'),1)}
        cert='-----BEGIN CERTIFICATE-----\n'+'synthetic-public-recipient-'*8+'\n-----END CERTIFICATE-----\n'
        self.recipient={**{k:f.row()['grant'][k] for k in ('account','lab_id','deployment_id')},
            'release_id':'web-2026-10-r1','instance_id':self.instances['bastion'],'instances':self.instances,
            'certificate_pem':cert,'certificate_sha256':hashlib.sha256(cert.encode()).hexdigest()}
        self.delivery={'schema_version':1,'certificate_sha256':self.recipient['certificate_sha256'],
                       'ciphertext_b64':base64.b64encode(b'x'*384).decode(),'token_hash':'f'*64}
        self.receipt={**{k:self.recipient[k] for k in ('lab_id','release_id','deployment_id')},
            'registered':True,'instance_count':5,'private_credential_exported':False,
            'transport_private_key_retired':True,'token_hash':self.delivery['token_hash']}
        def gateway(grant,operation,**fields):
            if operation=='recipient':return copy.deepcopy(self.recipient)
            if operation=='register':return copy.deepcopy(self.receipt)
            if operation=='observe':return {'stage':'REGISTRATION_PENDING'}
            raise AssertionError('Unexpected operation')
        f.prep.initial=Mock(side_effect=gateway)
        self.service=InitialRegistration(f.prep)

    def test_issued_hash_cipher_and_meta_commit_together_then_existing_reader_binding_works(self):
        f=self.f
        self.assertFalse(self.service.context(**f.claims())['issued'])
        result=self.service.register(self.delivery,**f.claims())
        self.assertTrue(result['registered'])
        saved=f.row()['registration']
        self.assertEqual(saved['delivery'],self.delivery)
        self.assertTrue(f.auth.registered(f.row()['bound_subject'],saved['grant'],f.row()['pk']))
        self.assertTrue(f.auth.status(**f.claims())['registered'])
        self.assertTrue(f.prep.status(**f.claims())['registration_complete'])
        self.assertEqual(f.auth.get('grades',f.existing['pk'],'META'),f.existing)
        meta=f.auth.get('grades','LAB#'+f.lab,'META')
        self.assertEqual(meta['instances'],self.instances)
        self.assertEqual(meta['token_hash'],'f'*64)
        self.assertNotIn('selected_score',meta)  # No invented zero/full score.
        self.assertNotIn('lab_token',str(f.snapshot()))

    def test_guest_unavailable_keeps_same_delivery_and_retry_does_not_issue_another_token(self):
        f=self.f;calls=[]
        original=f.prep.initial.side_effect
        def lost(grant,op,**fields):
            if op=='register':calls.append(fields);raise RuntimeError('synthetic-private-upstream')
            return original(grant,op,**fields)
        f.prep.initial.side_effect=lost
        with self.assertRaises(RuntimeError):self.service.register(self.delivery,**f.claims())
        saved=copy.deepcopy(f.row()['registration'])
        self.assertTrue(self.service.context(**f.claims())['issued'])
        f.prep.initial.side_effect=original
        different={**self.delivery,'token_hash':'e'*64}
        self.service.register(different,**f.claims())
        self.assertEqual(f.row()['registration'],saved)
        self.assertEqual(f.prep.initial.call_args.kwargs['delivery'],self.delivery)
        count=len(f.snapshot()['bindings'])
        self.service.register(None,**f.claims())
        self.assertEqual(len(f.snapshot()['bindings']),count)

    def test_session_revoked_at_issuance_rolls_back_meta_and_saved_cipher(self):
        f=self.f;original=f.db.transact_write_items
        def revoke(**kw):
            f.put('bindings',{'pk':f.session,'sk':'PORTAL','active':False,'expires_at':int(f.now)+3600,'token_hash':f.token})
            return original(**kw)
        with patch.object(f.db,'transact_write_items',side_effect=revoke):
            with self.assertRaises(EnrollmentDenied):self.service.register(self.delivery,**f.claims())
        self.assertIsNone(f.auth.get('grades','LAB#'+f.lab,'META'))
        self.assertNotIn('registration',f.row())
        self.assertFalse(any(c.args[1]=='register' for c in f.prep.initial.call_args_list))

    def test_other_identity_existing_meta_or_different_recipient_cannot_issue(self):
        f=self.f;before=f.snapshot()
        with self.assertRaises(EnrollmentDenied):self.service.register(self.delivery,**{**f.claims(),'subject':'999999999'})
        self.assertEqual(f.snapshot(),before)
        with self.assertRaises(EnrollmentDenied):self.service.register({**self.delivery,'certificate_sha256':'e'*64},**f.claims())
        f.put('grades',{'pk':'LAB#'+f.lab,'sk':'META','active':True,'original':True})
        with self.assertRaises(EnrollmentDenied):self.service.register(self.delivery,**f.claims())
        self.assertTrue(f.auth.get('grades','LAB#'+f.lab,'META')['original'])

    def test_wrong_guest_ack_never_authorizes_reader_and_changed_meta_blocks_recovery(self):
        f=self.f;self.receipt['token_hash']='0'*64
        with self.assertRaises(EnrollmentDenied):self.service.register(self.delivery,**f.claims())
        self.assertIsNone(f.prep.get('ACCOUNT#'+f.account,'BINDING'))
        self.assertNotIn('registration_complete',f.row())
        meta=f.auth.get('grades','LAB#'+f.lab,'META');meta['instances']['web']='i-'+'f'*17;f.put('grades',meta)
        with self.assertRaises(EnrollmentDenied):self.service.context(**f.claims())

    def test_binding_conflict_rolls_back_all_new_reader_records(self):
        f=self.f;self.service.issue(f.claims(),self.delivery)
        f.put('bindings',{'pk':'LAB#'+f.lab,'sk':'SUBJECT','subject_pk':'SUBJECT#'+'0'*64})
        with self.assertRaises(EnrollmentDenied):self.service.register(None,**f.claims())
        self.assertIsNone(f.prep.get('ACCOUNT#'+f.account,'BINDING'))
        self.assertIsNone(f.prep.get(f.row()['pk'],'LAB'))
        self.assertNotIn('registration_complete',f.row())

    def test_meta_changed_during_final_binding_rolls_back_every_reader_record(self):
        f=self.f;self.service.issue(f.claims(),self.delivery)
        original=f.db.transact_write_items
        def interleave(**kw):
            meta=f.auth.get('grades','LAB#'+f.lab,'META');meta['release_id']='web-2026-11-r1';f.put('grades',meta)
            return original(**kw)
        with patch.object(f.db,'transact_write_items',side_effect=interleave):
            with self.assertRaises(EnrollmentDenied):self.service.register(None,**f.claims())
        self.assertIsNone(f.prep.get('ACCOUNT#'+f.account,'BINDING'))
        self.assertIsNone(f.prep.get(f.row()['pk'],'LAB'))
        self.assertNotIn('registration_complete',f.row())

    def test_private_handler_accepts_cipher_only_and_has_no_finish_or_issue_route(self):
        from portal_enrollment_handler import serve
        f=self.f
        event={'operation':'prepare_register','delivery':self.delivery,**f.claims()}
        for changed in ({'operation':'prepare_finish'},{'operation':'prepare_issue'},{'lab_token':'never-accept-plaintext'},
                        {'delivery':{**self.delivery,'lab_token':'never-accept-plaintext'}}):
            self.assertEqual(serve({**event,**changed},f.auth,f.prep),{'status':'unauthorized'})
        self.assertEqual(serve(event,f.auth,f.prep)['status'],'ok')
        self.assertTrue(serve({'operation':'prepare_registration_context',**f.claims()},f.auth,f.prep)['preparation']['registered'])


if __name__=='__main__':unittest.main()
