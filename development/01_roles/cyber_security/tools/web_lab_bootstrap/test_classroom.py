import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import classroom
import classroom_guest


ROOT = Path(__file__).resolve().parents[5]


class ClassroomTests(unittest.TestCase):
    def test_every_stage_and_server_has_a_label_in_all_four_languages(self):
        for language, messages in classroom.TEXT.items():
            with self.subTest(language=language), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(len(messages), len(classroom.LABELS))
                self.assertEqual(len(classroom.SERVER_NAMES[language]), len(classroom.ROLES))
                screen = classroom.Screen(language, 'student')
                screen.step('lessons')
                screen.step('grading')
                self.assertIn('01', output.getvalue())
                self.assertIn(screen.text['grading'], output.getvalue())

    def test_invitation_is_rejected_in_another_aws_account(self):
        invited = dict(student_account='012345678901', teacher_account='123456789012',
                       api_base_url='https://abc.execute-api.us-east-1.amazonaws.com',
                       fixed_ingress_ipv4='8.8.8.8', lab_id='lab-1', lab_token='a' * 43,
                       release_id=classroom.RELEASE, schema_version=1)
        code = classroom.invitation(invited)
        self.assertEqual(classroom.parse_invitation(code, invited['student_account']), invited)
        with self.assertRaisesRegex(ValueError, 'INVITATION_ACCOUNT_OR_SCOPE'):
            classroom.parse_invitation(code, invited['teacher_account'])

    def test_shared_code_accepts_multiple_accounts_and_reuses_a_private_identity(self):
        invite = dict(teacher_account='123456789012', api_base_url='https://abc.execute-api.us-east-1.amazonaws.com',
                      fixed_ingress_ipv4='8.8.8.8', enrollment_token='a' * 43, release_id=classroom.RELEASE,
                      schema_version=1)
        code = classroom.invitation(invite)
        for account in ('012345678901', '987654321012'):
            self.assertEqual(classroom.parse_invitation(code, account), invite)
        with self.assertRaisesRegex(ValueError, 'INVITATION_ACCOUNT_OR_SCOPE'):
            classroom.parse_invitation(code, invite['teacher_account'])

        teacher, progress = Mock(), Mock()
        teacher.read_private.side_effect = lambda path: json.loads(path.read_bytes())
        progress.request.side_effect = lambda _, path, body, token: {
            'ok': path == '/api/web/enroll' and token == invite['enrollment_token'],
            'lab_id': body['lab_id'], 'release_id': body['release_id'],
        }
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, install_teacher=teacher, web_progress=progress):
            first, second = (Path(temp, name) for name in ('first', 'second'))
            first.mkdir()
            second.mkdir()
            initial = classroom.student_credentials(invite, first)
            self.assertEqual(initial, classroom.student_credentials(invite, first))
            other = classroom.student_credentials(invite, second)
            self.assertNotEqual(initial['lab_id'], other['lab_id'])
            self.assertNotEqual(initial['lab_token'], other['lab_token'])
            self.assertNotIn('enrollment_token', initial)
            for call in progress.request.call_args_list:
                self.assertEqual(set(call.args[2]), {'lab_id', 'lab_token', 'release_id'})

    def test_teacher_emits_one_reusable_code_without_asking_for_accounts(self):
        account = '123456789012'
        teacher = Mock()
        teacher.read_private.side_effect = lambda path: json.loads(path.read_bytes())
        teacher.install.return_value = dict(schema_version=1, release_id=classroom.RELEASE,
                                            api_base_url='https://abc.execute-api.us-east-1.amazonaws.com',
                                            fixed_ingress_ipv4='8.8.8.8')
        screen = Mock(text={'waiting': 'Waiting'})
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, install_teacher=teacher), \
                patch.object(classroom, 'remote_source', return_value=b'api source'):
            work = Path(temp)
            classroom.teacher_run(Mock(), screen, Mock(), account, work)
            code = work / 'classroom.invitation.txt'
            invite = classroom.parse_invitation(code.read_text().strip(), '012345678901')
            classroom.teacher_run(Mock(), screen, Mock(), account, work)
            self.assertEqual(code.read_text().strip(), classroom.invitation(invite))
            self.assertEqual(code.stat().st_mode & 0o777, 0o600)
        screen.prompt.assert_not_called()
        self.assertEqual(teacher.install.call_args.kwargs['enrollment'],
                         ('api source', hashlib.sha256(invite['enrollment_token'].encode()).hexdigest()))

    def test_template_keeps_private_topology_and_all_nodes_use_ssm(self):
        source = ROOT / 'development/templates/web-lab-student.template.json'
        template = classroom.classroom_template(json.loads(source.read_bytes()))
        resources = template['Resources']
        self.assertNotIn('S3Endpoint', json.dumps(template))
        self.assertNotIn('WaitCondition', json.dumps(template))
        for role, name in classroom.ROLES.items():
            instance = resources[name + 'Instance']
            self.assertIn('SsmMessagesEndpoint', instance['DependsOn'])
            self.assertEqual(instance['Properties']['IamInstanceProfile'], 'LabInstanceProfile')
            self.assertEqual(instance['Properties']['PrivateIpAddress'], classroom.IPS[role])
            self.assertIn({'Ref': 'BootstrapSg'}, instance['Properties']['SecurityGroupIds'])
            self.assertEqual('UserData' in instance['Properties'], role == 'bastion')
        self.assertTrue(template['Parameters']['RdpPasswordHash']['NoEcho'])

    def test_student_uses_latest_source_for_new_install_and_saved_source_on_resume(self):
        latest, saved = 'a' * 40, 'b' * 40
        teacher = Mock()
        teacher.read_private.return_value = {'ref': saved}
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, install_teacher=teacher):
            work = Path(temp)
            for expected in (latest, saved):
                with patch.object(classroom, 'assets', side_effect=ValueError('STOP_BEFORE_DEPLOY')) as assets:
                    with self.assertRaisesRegex(ValueError, 'STOP_BEFORE_DEPLOY'):
                        classroom.setup_student(Mock(ref=latest), Mock(), Mock(), '012345678901', {}, work)
                    assets.assert_called_once_with(expected)
                (work / 'deployment.json').touch()

    def test_receiver_rejects_wrong_hash_and_reuses_verified_asset(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(classroom_guest, 'ROOT', Path(temp)):
            assets = Path(temp, 'assets')
            assets.mkdir()
            data = Path(temp, 'sample')
            data.write_bytes(b'locked dependency')
            digest = hashlib.sha256(data.read_bytes()).hexdigest()
            with classroom_guest.ThreadingHTTPServer(('127.0.0.1', 0), classroom_guest.Receiver) as server:
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    port = server.server_address[1]
                    self.assertEqual(classroom.exchange(port, 'PUT', 'sample.deb', '0' * 64, data), 400)
                    self.assertEqual(classroom.exchange(port, 'HEAD', 'sample.deb', digest), 404)
                    self.assertEqual(classroom.exchange(port, 'PUT', 'sample.deb', digest, data), 201)
                    self.assertEqual(classroom.exchange(port, 'HEAD', 'sample.deb', digest), 200)
                finally:
                    server.shutdown()
                    thread.join()
            self.assertEqual((assets / 'sample.deb').read_bytes(), data.read_bytes())

    def test_lesson_transfer_fits_run_command_and_targets_web_and_db(self):
        ssm = Mock()
        ssm.send_command.return_value = {'Command': {'CommandId': 'command'}}
        ssm.get_command_invocation.side_effect = lambda **args: {
            'Status': 'Success',
            'StandardOutputContent': json.dumps({'public_resources_ready': True, 'role': args['InstanceId']}),
        }
        with patch.object(classroom, 'remote_source', side_effect=lambda _, path: (ROOT / path).read_bytes()):
            classroom.stage_lessons('ref', ssm, {'web': 'web', 'db': 'db'},
                                    {'lab_id': 'lab-1', 'deployment_id': 'deployment'})
        calls = [item.kwargs for item in ssm.send_command.call_args_list]
        self.assertEqual([item['InstanceIds'] for item in calls], [['web'], ['db']])
        self.assertTrue(all(len(item['Parameters']['commands'][0]) < 60000 for item in calls))


if __name__ == '__main__':
    unittest.main()
