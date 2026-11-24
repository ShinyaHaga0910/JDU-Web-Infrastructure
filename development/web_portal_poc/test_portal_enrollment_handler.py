import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
sys.path[:0] = [str(ROOT / 'web_lab_assessment'), str(ROOT / 'web_lab_teacher')]
AVAILABLE = importlib.util.find_spec('boto3') is not None
if AVAILABLE:
    from portal_enrollment_handler import serve, handler
    from portal_enrollment import EnrollmentDenied
import build_portal_services_package as package


@unittest.skipUnless(AVAILABLE, 'boto3 required')
class HandlerTest(unittest.TestCase):
    def setUp(self):
        self.event = {'operation': 'begin', 'subject': '12345', 'email': 'synthetic@jdu.uz',
            'session_id': 'a'*64, 'token_hash': 'b'*64, 'request_id': 'c'*64}

    def test_trusted_claims_only_and_no_teacher_approval_route(self):
        service = Mock()
        service.begin.return_value = {'registered': False}
        self.assertEqual(serve(self.event, service)['status'], 'ok')
        self.assertEqual(service.begin.call_args.kwargs['email'], self.event['email'])
        for event in ({**self.event, 'lab_id': 'other'}, {**self.event, 'operation': 'approve'},
                      {**self.event, 'email': 'other@example.org'}, {**self.event, 'session_id': 'invalid'},
                      {'operation': 'complete', 'pair_id': 'd'*64, 'proof_url': 'x'*8193}):
            self.assertEqual(serve(event, service), {'status': 'unauthorized'})
        self.assertEqual(service.begin.call_count, 1)
        service.approve.assert_not_called()

    def test_denials_and_unavailable_never_echo_identity_proof_or_errors(self):
        service = Mock()
        event = {'operation': 'complete', 'pair_id': 'd'*64, 'proof_url': 'sensitive-signed-proof'}
        for error, expected in ((EnrollmentDenied('private detail'), 'unauthorized'), (RuntimeError('private detail'), 'unavailable')):
            service.complete.side_effect = error
            self.assertEqual(serve(event, service), {'status': expected})
        self.assertEqual(handler({'operation': 'approve'}, None), {'status': 'unauthorized'})

    def test_microsoft_test_claim_is_limited_to_one_subject_and_lab(self):
        service, checker = Mock(), Mock()
        lab, subject = 'lab-' + 'a' * 20, '200' + '1' * 39
        now = int(time.time())
        event = {k: v for k, v in self.event.items() if k != 'email'}
        event.update(operation='claim_test_student', subject=subject,
                     code=f'jdu-link1.{lab}.123456789012.{now}.' + 'f' * 64)
        access = f'{lab}:{subject}:{now + 600}'
        for fields, config in (({}, ''), ({}, f'{lab}:{subject}:{now - 1}'),
                               ({'subject': '12345'}, access), ({'code': event['code'].replace(lab, 'lab-' + 'b'*20)}, access)):
            self.assertEqual(serve(event | fields, service, check_student=checker, test_access=config),
                             {'status': 'unauthorized'})
        service.claim.assert_not_called()
        service.claim.return_value = {'registered': True}
        self.assertEqual(serve(event, service, check_student=checker, test_access=access)['status'], 'ok')
        self.assertEqual(service.claim.call_args.kwargs['test_lab'], lab)
        self.assertIsNone(service.claim.call_args.kwargs['email'])

    def test_source_only_package_reproducible_loadable_and_registry_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory)/'a.zip', Path(directory)/'b.zip'
            self.assertEqual(package.build(first), package.build(second))
            with self.assertRaises(FileExistsError): package.build(first)
            with ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), set(package.FILES))
                self.assertEqual(archive.read('assessment-registry.json'), package.FILES['assessment-registry.json'].read_bytes())
                archive.extractall(Path(directory)/'package')
            subprocess.run([sys.executable, '-B', '-c', 'import portal_enrollment_handler,identity_grade_handler'],
                cwd=Path(directory)/'package', check=True, capture_output=True, text=True)


class TemplateTest(unittest.TestCase):
    def test_private_services_reuse_role_and_keep_generated_key_in_secrets_manager(self):
        template = json.loads((package.HERE/'portal-services.template.json').read_text(encoding='utf-8'))
        resources = template['Resources']
        self.assertEqual(sorted(r['Type'] for r in resources.values()),
            sorted(['AWS::Lambda::Function']*2+['AWS::Logs::LogGroup']*2+['AWS::SecretsManager::Secret']))
        secret = resources['SubjectKey']
        self.assertEqual(secret['DeletionPolicy'], 'Retain')
        generator = secret['Properties']['GenerateSecretString']
        alphabet = ''.join(c for c in 'abcdefghijklmnopqrstuvwxyz0123456789' if c not in generator['ExcludeCharacters'])
        self.assertEqual(set(alphabet), set('abcdef0123456789'))
        self.assertEqual(generator['PasswordLength'], 64)
        self.assertNotIn('SecretString', json.dumps(template['Outputs']))
        for name in ('EnrollmentService','GradeReader'):
            self.assertEqual(resources[name]['Properties']['Role'], {'Ref':'LabRoleArn'})
            self.assertNotIn('FunctionName', resources[name]['Properties'])


if __name__ == '__main__': unittest.main()
