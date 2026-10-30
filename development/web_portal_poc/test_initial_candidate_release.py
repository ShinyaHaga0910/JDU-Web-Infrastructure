"""Candidate trust/expiry separation, Moto fixtures; GPG is explicitly stubbed."""
import copy
from datetime import datetime,timedelta,timezone
import hashlib
import json
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import initial_candidate_release as candidate
import build_initial_worker as worker
from initial_assets_package import from_course
import test_initial_package as packages


class CandidateReleaseTest(unittest.TestCase):
    def setUp(self):
        self.f=packages.InitialPackageTest('test_template_has_fixed_three_functions_and_one_teacher_role_no_public_url')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.core=self.f.f.verified
        self.root=self.f.f.path.parent/'verification-candidate';self.root.mkdir()
        key=self.f.f.path.parent/'fixture-public.asc';key.write_bytes(b'fixture-key-not-a-real-signing-key')
        self.core['files']['public_key']=key
        source=self.f.course['root']
        for name in ('assessment.tar.gz',): (self.root/name).write_bytes((source/name).read_bytes())
        (self.root/'assessment.tar.gz.asc').write_bytes(b'fixture-signature')
        (self.root/'package-signing-public.asc').write_bytes(key.read_bytes())
        (self.root/'course-release.json.asc').write_bytes(b'fixture-signature')
        self.release={**self.f.course['release'],'schema_version':1,'scope':candidate.SCOPE,
            'class_id':193548,'teacher_account':'111111111111',
            'created_at':(datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat(),
            'distribution_ready':False,'foundation_acceptance_pending':True}
        self.save()
        signature_patch=patch.object(candidate,'verify_signature',return_value=int((datetime.now(timezone.utc)+timedelta(days=2)).timestamp()))
        self.sig=signature_patch.start();self.addCleanup(signature_patch.stop)

    def save(self):
        (self.root/'course-release.json').write_text(json.dumps(self.release),encoding='utf-8')

    def verified(self):return candidate.verify(self.root,self.core,candidate.FINGERPRINT)

    def test_candidate_packages_without_claiming_formal_distribution_acceptance(self):
        course=self.verified()
        target=self.root.parent/'initial-candidate-worker.zip'
        worker.build_verified(target,self.f.manifest,self.core,self.f.f.grant,course)
        with ZipFile(target) as z:
            self.assertIn('initial_checker_handler.py',z.namelist())
            metadata=json.loads(z.read('initial-teaching.json'))
            self.assertEqual(metadata['course_distribution_sha256'],course['sha256'])
        self.assertFalse(course['release']['distribution_ready'])
        self.assertTrue(course['release']['foundation_acceptance_pending'])

    def test_expiry_mixed_core_and_false_acceptance_are_rejected(self):
        original=copy.deepcopy(self.release)
        for changes in ({'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()},
                        {'expires_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()},
                        {'core_manifest_sha256':'0'*64},{'distribution_ready':True},
                        {'foundation_acceptance_pending':False},{'scope':'web_course_distribution'}):
            self.release={**original,**changes};self.save()
            with self.assertRaises(ValueError):self.verified()

    def test_candidate_flag_cannot_turn_an_unaccepted_formal_course_into_ready(self):
        course=self.verified();course.pop('verification_candidate')
        with self.assertRaises(ValueError):from_course(course,self.core,self.f.f.grant)
        course['verification_candidate']=True
        self.assertIn('initial-teaching.json',from_course(course,self.core,self.f.f.grant))
        self.release['scope']='web_course_distribution';self.save()
        course.update(release=self.release,sha256=hashlib.sha256((self.root/'course-release.json').read_bytes()).hexdigest())
        with self.assertRaises(ValueError):from_course(course,self.core,self.f.f.grant)

    def test_unexpected_files_key_or_assessment_changes_are_rejected(self):
        extra=self.root/'unreviewed.py';extra.write_text('fixture')
        with self.assertRaises(ValueError):self.verified()
        extra.unlink()
        key=self.root/'package-signing-public.asc';old=key.read_bytes();key.write_bytes(b'other-key')
        with self.assertRaises(ValueError):self.verified()
        key.write_bytes(old)
        archive=self.root/'assessment.tar.gz';archive.write_bytes(archive.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.verified()

    def test_both_signatures_and_independent_core_pin_are_required(self):
        self.verified();self.assertEqual(self.sig.call_count,2)
        for index in (0,1):
            self.sig.side_effect=[ValueError('bad signature')] if index==0 else [int((datetime.now(timezone.utc)+timedelta(days=2)).timestamp()),ValueError('bad signature')]
            with self.assertRaises(ValueError):self.verified()
        self.sig.side_effect=None
        wrong={**self.core,'trusted_fingerprint':'0'*40}
        with self.assertRaises(ValueError):candidate.verify(self.root,wrong,candidate.FINGERPRINT)


if __name__=='__main__':unittest.main()
