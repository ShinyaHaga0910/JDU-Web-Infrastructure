import contextlib
import hashlib
import io
import json
from pathlib import Path
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
