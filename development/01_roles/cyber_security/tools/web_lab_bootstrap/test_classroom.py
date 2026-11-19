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
                for role, total in (('teacher', 4), ('student', 11)):
                    screen = classroom.Screen(language, role)
                    self.assertEqual(screen.total, total)
                    self.assertIn(classroom.PROGRESS_TEXT[language][0].format(total=total), output.getvalue())
                    for stage in screen.stages:
                        screen.step(stage)
                    self.assertIn(f'01/{total:02d}', output.getvalue())
                    self.assertIn(f'{total:02d}/{total:02d}  {screen.text["done"]}', output.getvalue())
                    if role == 'student':
                        with patch.object(classroom.getpass, 'getpass') as secret_prompt:
                            for key in ('invite', 'password'):
                                screen.prompt(key, secret=True)
                                self.assertIn(screen.text[key], secret_prompt.call_args.args[0])

    def test_aws_wait_reports_elapsed_time_and_propagates_errors(self):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(classroom, 'AWS_PROGRESS_INTERVAL', 0.01):
            screen = classroom.Screen('ja', 'teacher')
            reported = threading.Event()
            messages = []

            def record(message):
                messages.append(message)
                if message.startswith('AWSで処理中です'):
                    reported.set()

            with patch.object(screen, 'record', side_effect=record):
                with self.assertRaisesRegex(ValueError, 'offline fixture'):
                    with screen.aws_wait():
                        self.assertTrue(reported.wait(timeout=2))
                        raise ValueError('offline fixture')
            self.assertEqual(messages[0], screen.wait_hint)
            self.assertRegex(messages[1], r'経過 \d{2}:\d{2}$')

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
        screen.aws_wait.side_effect = contextlib.nullcontext
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, install_teacher=teacher), \
                patch.object(classroom, 'assessment_api_source', return_value='api source'):
            work = Path(temp)
            issued = classroom.teacher_run(Mock(), screen, Mock(), account, work)
            code = work / 'classroom.invitation.txt'
            invite = classroom.parse_invitation(code.read_text().strip(), '012345678901')
            self.assertEqual(issued, classroom.teacher_run(Mock(), screen, Mock(), account, work))
            self.assertEqual(issued, code.read_text().strip())
            self.assertEqual(code.read_text().strip(), classroom.invitation(invite))
            self.assertEqual(code.stat().st_mode & 0o777, 0o600)
        screen.prompt.assert_not_called()
        self.assertTrue(all(issued not in str(call) for call in screen.record.call_args_list))
        self.assertEqual(teacher.install.call_args.kwargs['enrollment'],
                         ('api source', hashlib.sha256(invite['enrollment_token'].encode()).hexdigest()))

    def test_teacher_console_asks_only_for_language_and_prints_code_last(self):
        session = Mock()
        session.client.return_value.get_caller_identity.return_value = {'Account': '123456789012'}
        boto3 = Mock()
        boto3.Session.return_value = session
        instructions = ('Share this code with your students.', 'このコードを学生に伝えてください。',
                        'Передайте этот код студентам.', 'Ushbu kodni talabalarga bering.')
        for selection, instruction in zip('1234', instructions):
            output = io.StringIO()
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(output), \
                    patch.dict(sys.modules, boto3=boto3), patch.object(sys, 'path', list(sys.path)), \
                    patch.object(sys, 'argv', ['classroom.py', 'teacher', '--ref', 'a' * 40]), \
                    patch.object(sys.stdin, 'isatty', return_value=True), patch('builtins.input', return_value=selection) as prompt, \
                    patch.object(classroom.Path, 'home', return_value=Path(temp)), patch.object(classroom.os, 'umask'), \
                    patch.object(classroom, 'remote_source', return_value=b'# offline fixture'), \
                    patch.object(classroom, 'teacher_run', return_value='jdu2.offline-fixture'):
                self.assertEqual(classroom.main(), 0)
                prompt.assert_called_once()
                self.assertIn('[2] Japanese', output.getvalue())
                self.assertEqual(output.getvalue().rstrip().splitlines()[-2:], [instruction, 'jdu2.offline-fixture'])

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
