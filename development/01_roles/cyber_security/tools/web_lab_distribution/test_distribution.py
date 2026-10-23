"""Cross-student isolation and real encrypted reuse without an issuance surface."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'web_lab_bootstrap'), str(HERE.parent / 'web_lab_teacher')]
import distribution as d


class ReadOnlyTeacher:
    def __init__(self, context, credential):
        self.context = context
        self.row = dict(lab_id={'S': credential['lab_id']}, release_id={'S': credential['release_id']},
            active={'BOOL': True}, token_hash={'S': d.digest(credential['lab_token'].encode())},
            deployment_id={'S': 'unchanged-deployment-fixture'})
        self.original = copy.deepcopy(self.row)
        self.names = []

    def client(self, name, **kwargs):
        self.names.append(name)
        m = self.context['core']['manifest']
        return {
            'sts': SimpleNamespace(get_caller_identity=lambda: {'Account': self.context['release']['teacher_account']}),
            'cloudformation': SimpleNamespace(describe_stacks=lambda **kw: {'Stacks': [{
                'StackStatus': 'CREATE_COMPLETE', 'Outputs': [
                    {'OutputKey': 'TableName', 'OutputValue': 'teacher-progress-fixture'},
                    {'OutputKey': 'ApiBaseUrl', 'OutputValue': 'https://' + m['grading']['fqdn']},
                    {'OutputKey': 'FixedIngressIpv4', 'OutputValue': m['grading']['ipv4']}]}]}),
            'dynamodb': SimpleNamespace(get_item=lambda **kw: {'Item': self.row}),
            's3': SimpleNamespace(head_object=lambda **kw: {'ContentLength': 100,
                'Metadata': {'sha256': 'b' * 64}}, generate_presigned_url=lambda *a, **kw:
                    'https://fixture-bucket.s3.us-east-1.amazonaws.com/release/repo-bundle.tar.gz?fixture=nonsecret'),
        }[name]


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.context = dict(release_sha256='a' * 64, release=dict(class_id=123456, teacher_account='111122223333',
            teacher_stack='teacher-fixture', region='us-east-1', expires_at=(self.now + timedelta(days=2)).isoformat()),
            core=dict(manifest=dict(release_id='web-fixture-r1', region='us-east-1',
                grading=dict(fqdn='fixture123.execute-api.us-east-1.amazonaws.com', ipv4='50.16.41.7'),
                bootstrap=dict(bucket='fixture-bucket', release_prefix='release/'),
                artifacts=dict(repo_bundle=dict(sha256='b' * 64, size_bytes=100)))))
        self.temp = tempfile.TemporaryDirectory(prefix='jdu-general-delivery-test-')
        self.root = Path(self.temp.name)
        self.student = '444455556666'
        self.student_session = SimpleNamespace(client=lambda name: SimpleNamespace(
            get_caller_identity=lambda: {'Account': self.student}))
        self.credential = dict(schema_version=1, api_base_url='https://fixture123.execute-api.us-east-1.amazonaws.com',
            fixed_ingress_ipv4='50.16.41.7', release_id='web-fixture-r1', lab_id='student-fixture-001',
            lab_token='nonsecret_fixture_token_' + 'F' * 32)
        self.sdk = patch.dict(sys.modules, {'botocore.config': SimpleNamespace(Config=lambda **kw: None)})
        self.sdk.start()

    def tearDown(self):
        self.sdk.stop()
        self.temp.cleanup()

    def new_recipient(self, suffix='one'):
        workspace = self.root / ('receiver-' + suffix)
        d.recipient(self.context, self.student_session, SimpleNamespace(lab_id=self.credential['lab_id'], workspace=workspace))
        return workspace, json.loads((workspace / 'recipient-request.public.json').read_text())

    def test_real_crypto_roundtrip_retains_original_token_and_rejects_replay(self):
        workspace, request = self.new_recipient()
        old = self.root / 'original.credentials.json'; d.save_json(old, self.credential)
        before = old.read_bytes()
        config = self.root / 'teacher.private.json'
        d.save_json(config, dict(self.credential, admin_key='nonsecret_teacher_fixture'))
        session = ReadOnlyTeacher(self.context, self.credential)
        args = SimpleNamespace(request=workspace / 'recipient-request.public.json', student_account=self.student,
            recipient_sha256=request['certificate_sha256'], mode='reuse', existing_credential=old,
            plan=self.root / 'review.private.json', teacher_config=config, workspace=self.root / 'refreshed', confirmed_access=True)
        d.plan(self.context, session, args)
        with patch.object(d.sys, 'stdin', SimpleNamespace(isatty=lambda: True)):
            d.send(self.context, session, args)
            cipher = args.workspace / 'student-delivery.encrypted.cms'
            received = SimpleNamespace(workspace=workspace, confirmed_access=True,
                recipient_sha256=request['certificate_sha256'], ciphertext=cipher, ciphertext_sha256=d.digest(cipher.read_bytes()))
            d.receive(self.context, self.student_session, received)
            saved = workspace / 'received/own-student.credentials.json'
            self.assertEqual(json.loads(saved.read_text()), self.credential)
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                d.receive(self.context, self.student_session, received)
        self.assertEqual(old.read_bytes(), before)
        self.assertEqual(session.row, session.original)
        self.assertEqual(set(session.names), {'sts', 'cloudformation', 'dynamodb', 's3'})

    def test_independent_student_account_class_release_and_recipient_required(self):
        _, request = self.new_recipient()
        for field, value in (('student_account', '777788889999'), ('class_id', 193548),
                ('teacher_account', '777788889999'), ('distribution_sha256', 'c' * 64),
                ('certificate_pem', 'substituted'), ('lab_token', 'extra-secret-fixture')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                d.request_value(self.context, dict(request, **{field: value}), self.student,
                    request['certificate_sha256'], self.now + timedelta(seconds=10))

    def test_second_unrelated_class_and_student_do_not_use_test193548_constants(self):
        self.context['release'].update(class_id=987654, teacher_account='999900001111')
        self.student = '222233334444'
        _, request = self.new_recipient('different-class')
        self.assertEqual(d.request_value(self.context, request, self.student, request['certificate_sha256'],
            datetime.now(timezone.utc))['class_id'], 987654)

    def test_expired_recipient_and_admin_in_student_credential_rejected(self):
        _, request = self.new_recipient()
        with self.assertRaises(ValueError):
            d.request_value(self.context, request, self.student, request['certificate_sha256'], self.now + timedelta(days=1, seconds=10))
        with self.assertRaises(ValueError):
            d.credential_value(self.context, dict(self.credential, admin_key='fixture'), self.credential['lab_id'])

    def test_inactive_or_rotated_credential_never_reissued(self):
        path = self.root / 'old.private.json'; d.save_json(path, self.credential)
        session = ReadOnlyTeacher(self.context, self.credential)
        for field, value in (('active', {'BOOL': False}), ('token_hash', {'S': 'c' * 64}), ('lab_id', {'S': 'other-lab'})):
            session.row = dict(session.original, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                d.existing(self.context, session, path, self.credential['lab_id'])

    def test_existing_lab_refuses_new_issuance_before_creating_plan(self):
        workspace, request = self.new_recipient()
        args = SimpleNamespace(request=workspace / 'recipient-request.public.json', student_account=self.student,
            recipient_sha256=request['certificate_sha256'], mode='new', plan=self.root / 'must-not-exist.json')
        with self.assertRaises(ValueError):
            d.plan(self.context, ReadOnlyTeacher(self.context, self.credential), args)
        self.assertFalse(args.plan.exists())

    def test_send_or_receive_without_human_tty_stops_before_new_state(self):
        session = ReadOnlyTeacher(self.context, self.credential)
        with patch.object(d.sys, 'stdin', SimpleNamespace(isatty=lambda: False)):
            with self.assertRaises(ValueError):
                d.send(self.context, session, SimpleNamespace(confirmed_access=True))
            with self.assertRaises(ValueError):
                d.receive(self.context, self.student_session, SimpleNamespace(confirmed_access=True))

    def test_link_or_public_privatefile_is_refused(self):
        path = self.root / 'private.json'; d.save_json(path, self.credential)
        path.chmod(0o644)
        with self.assertRaises(ValueError): d.read(path, private=True)
        path.chmod(0o600)
        link = self.root / 'linked.json'; link.symlink_to(path)
        with self.assertRaises(ValueError): d.read(link, private=True)


if __name__ == '__main__':
    unittest.main()
