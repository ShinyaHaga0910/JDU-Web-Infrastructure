import contextlib
from datetime import datetime, timedelta
import errno
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import classroom
import classroom_guest


ROOT = Path(__file__).resolve().parents[5]


class ClassroomTests(unittest.TestCase):
    def test_session_prompt_creates_only_a_missing_default_document(self):
        class MissingDocument(Exception):
            response = {'Error': {'Code': 'InvalidDocument'}}

        ssm = Mock()
        ssm.get_document.side_effect = MissingDocument
        self.assertTrue(classroom.enable_session_prompt(ssm))
        document = json.loads(ssm.create_document.call_args.kwargs['Content'])
        self.assertEqual(document['inputs']['shellProfile']['linux'], classroom.SESSION_PROMPT)
        self.assertIn('/var/lib/jdu-web-classroom/configured.json', classroom.SESSION_PROMPT)
        ssm.reset_mock(side_effect=True)
        ssm.get_document.return_value = {'Content': json.dumps(document)}
        self.assertTrue(classroom.enable_session_prompt(ssm))
        ssm.get_document.return_value = {'Content': '{"inputs":{"shellProfile":{"linux":"pwd"}}}'}
        self.assertFalse(classroom.enable_session_prompt(ssm))
        ssm.create_document.assert_not_called()

    def test_every_stage_and_server_has_a_label_in_all_four_languages(self):
        for language, messages in classroom.TEXT.items():
            with self.subTest(language=language), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(len(messages), len(classroom.LABELS))
                self.assertEqual(len(classroom.SERVER_NAMES[language]), len(classroom.ROLES))
                for role, total in (('teacher', 4), ('student', 11)):
                    screen = classroom.Screen(language, role)
                    self.assertEqual(len(classroom.PACKAGE_TEXT[language]), len(classroom.PACKAGE_LABELS))
                    self.assertEqual(screen.total, total)
                    self.assertIn(classroom.PROGRESS_TEXT[language][0].format(total=total), output.getvalue())
                    for stage in screen.stages:
                        screen.step(stage)
                    self.assertIn(f'01/{total:02d}', output.getvalue())
                    self.assertIn(f'{total:02d}/{total:02d}  {screen.text["done"]}', output.getvalue())
                    if role == 'student':
                        with patch('builtins.input', return_value='invalid') as code_prompt, \
                                patch.dict(sys.modules, install_teacher=Mock()):
                            with self.assertRaisesRegex(ValueError, 'INVITATION_FORMAT'):
                                classroom.student_run(None, screen, None, '012345678901', None)
                            self.assertIn(screen.text['invite'], code_prompt.call_args.args[0])
                        with patch.object(classroom, 'masked_password') as secret_prompt:
                            screen.prompt('password', secret=True)
                            self.assertIn(screen.text['password'], secret_prompt.call_args.args[0])

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

    def test_aws_wait_displays_current_transfer_count(self):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(classroom, 'AWS_PROGRESS_INTERVAL', 0.01):
            screen = classroom.Screen('ja', 'student')
            reported = threading.Event()

            progress = ''

            def record(message):
                if message.startswith('処理中です') and message.endswith(' (取得・検証済みのファイル 56/1135)'):
                    reported.set()

            with patch.object(screen, 'record', side_effect=record), screen.aws_wait(
                    hint='package_hint', progress=lambda: progress):
                progress = screen.text['download_progress'].format(done=56, total=1135)
                self.assertTrue(reported.wait(timeout=2))

    def test_password_is_only_hashed_after_matching_confirmation(self):
        chosen = 'Qx6!'
        with contextlib.redirect_stdout(io.StringIO()) as output:
            screen = classroom.Screen('ja', 'student')
            with patch.object(classroom, 'masked_password', side_effect=['abc', chosen, 'different', chosen, chosen]) as prompt, \
                    patch.object(classroom.subprocess, 'check_output', return_value=b'fixture-hash\n') as openssl:
                self.assertEqual(classroom.rdp_password_hash(screen), 'fixture-hash')
        self.assertEqual(prompt.call_count, 5)
        self.assertIn(screen.text['password_again'], prompt.call_args.args[0])
        self.assertIn(screen.text['password_reminder'], output.getvalue())
        self.assertIn(screen.text['password_masked'], output.getvalue())
        self.assertIn(screen.text['password_invalid'], output.getvalue())
        self.assertIn(screen.text['password_mismatch'], output.getvalue())
        self.assertNotIn(chosen, output.getvalue())
        openssl.assert_called_once_with(['openssl', 'passwd', '-6', '-stdin'], input=(chosen + '\n').encode())

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

    def test_teacher_console_asks_for_language_and_semester_end_and_prints_code_last(self):
        session = Mock()
        session.client.return_value.get_caller_identity.return_value = {'Account': '123456789012'}
        boto3 = Mock()
        boto3.Session.return_value = session
        instructions = ('Share this code with your students.', 'このコードを学生に伝えてください。',
                        'Передайте этот код студентам.', 'Ushbu kodni talabalarga bering.')
        semester_end = (datetime.now(ZoneInfo('Asia/Tashkent')).date() + timedelta(days=30)).isoformat()
        for selection, instruction in zip('1234', instructions):
            output = io.StringIO()
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(output), \
                    patch.dict(sys.modules, boto3=boto3), patch.object(sys, 'path', list(sys.path)), \
                    patch.object(sys, 'argv', ['classroom.py', 'teacher', '--ref', 'a' * 40]), \
                    patch.object(sys.stdin, 'isatty', return_value=True), patch('builtins.input', side_effect=[selection, semester_end, 'teacher@jdu.uz']) as prompt, \
                    patch.object(classroom.Path, 'home', return_value=Path(temp)), patch.object(classroom.os, 'umask'), \
                    patch.object(classroom, 'remote_source', return_value=b'# offline fixture'), \
                    patch.object(classroom, 'teacher_run', return_value='jdu2.offline-fixture'), \
                    patch.object(classroom, 'assignment_portal_url', return_value=None), \
                    patch.object(classroom, 'prepare_assignment_portal') as portal:
                self.assertEqual(classroom.main(), 0)
                self.assertEqual(prompt.call_count, 3)
                portal.assert_called_once()
                self.assertEqual(portal.call_args.args[0].expires_on, semester_end)
                self.assertEqual(portal.call_args.args[0].teacher_email, 'teacher@jdu.uz')
                self.assertIn('[2] Japanese', output.getvalue())
                self.assertEqual(output.getvalue().rstrip().splitlines()[-2:], [instruction, 'jdu2.offline-fixture'])

    def test_student_console_prints_localized_rdp_information_in_final_stage(self):
        boto3 = Mock()
        boto3.Session.return_value.client.return_value.get_caller_identity.return_value = {'Account': '123456789012'}
        for selection, language in zip('1234', ('en', 'ja', 'ru', 'uz')):
            output = io.StringIO()
            with self.subTest(language=language), tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(output), \
                    patch.dict(sys.modules, boto3=boto3), patch.object(sys, 'path', list(sys.path)), \
                    patch.object(sys, 'argv', ['classroom.py', 'student', '--ref', 'a' * 40]), \
                    patch.object(sys.stdin, 'isatty', return_value=True), patch('builtins.input', return_value=selection), \
                    patch.object(classroom.Path, 'home', return_value=Path(temp)), patch.object(classroom.os, 'umask'), \
                    patch.object(classroom, 'remote_source', return_value=b'# offline fixture'), \
                    patch.object(classroom, 'student_run', return_value='192.0.2.10'):
                self.assertEqual(classroom.main(), 0)
                final = output.getvalue().split('┌─ 11/11', 1)[1].rstrip().splitlines()
                instruction, details = classroom.STUDENT_RDP[language]
                self.assertEqual(final[-3:], ['│  ✓  ' + classroom.STUDENT_SUCCESS[language],
                                              '│  ' + instruction, '│  ' + details.format(ip='192.0.2.10')])

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
                        classroom.setup_student(Mock(ref=latest), Mock(), Mock(), '012345678901', {}, work, '123456789012')
                    assets.assert_called_once_with(expected)
                (work / 'deployment.json').touch()

    def test_downloads_eight_in_parallel_then_packs_and_unpacks(self):
        contents = {f'package-{i}.deb': f'fixture-{i}'.encode() for i in range(8)}
        index = {name: (name, hashlib.sha256(raw).hexdigest()) for name, raw in contents.items()}
        inventory = {name: digest for name, (_, digest) in index.items()}
        workers = threading.Barrier(8)

        def open_package(url, *, timeout):
            workers.wait(timeout=5)
            return io.BytesIO(contents[url])

        with tempfile.TemporaryDirectory() as scratch, patch.object(classroom, 'urlopen', side_effect=open_package), \
                patch.object(classroom, 'ARCHIVE_TARGET', 10000):
            directory = Path(scratch)
            progress = []
            cache = directory / 'cache'
            sources = classroom.download_packages(index, cache, directory, progress.append)
            archives = classroom.build_archives(sources, directory)
            self.assertEqual(len(archives), 2)
            self.assertEqual({f.name for f in directory.iterdir()}, set(archives) | {'cache'})
            classroom_guest.unpack_archives(directory, archives, inventory)
            self.assertEqual({name: (directory / name).read_bytes() for name in contents}, contents)
        self.assertEqual(progress, list(range(len(index) + 1)))

    def test_corrupt_download_is_not_counted(self):
        with tempfile.TemporaryDirectory() as scratch, patch.object(classroom, 'urlopen', return_value=io.BytesIO(b'wrong')):
            progress = Mock()
            with self.assertRaisesRegex(ValueError, 'ASSET_VERIFICATION package.deb'):
                classroom.download_packages({'package.deb': ('url', '0' * 64)}, Path(scratch) / 'cache',
                                            Path(scratch), progress)
        progress.assert_called_once_with(0)

    def test_resume_checks_cached_files_before_downloading_missing_or_corrupt_files(self):
        data = b'locked file'
        digest = hashlib.sha256(data).hexdigest()
        names = ('valid.deb', 'corrupt.deb', 'missing.deb')
        index = {name: (name, digest) for name in names}
        with tempfile.TemporaryDirectory() as scratch, patch.object(classroom, 'urlopen') as fetch:
            directory = Path(scratch)
            cache = directory / 'cache'
            cache.mkdir()
            (cache / 'valid.deb').write_bytes(data)
            (cache / 'corrupt.deb').write_bytes(b'corrupt')
            (cache / '.partial-stale').write_bytes(b'interrupted')
            fetch.side_effect = lambda *_args, **_kwargs: io.BytesIO(data)
            progress = []
            sources = classroom.download_packages(index, cache, directory, progress.append)
            self.assertCountEqual([call.args[0] for call in fetch.call_args_list], ['corrupt.deb', 'missing.deb'])
            self.assertEqual(progress, [1, 2, 3])
            classroom.build_archives(sources, directory)
            self.assertEqual({path.name: path.read_bytes() for path in cache.iterdir()}, dict.fromkeys(names, data))

            fetch.reset_mock()
            progress.clear()
            classroom.download_packages(index, cache, directory, progress.append)
            self.assertEqual(progress, [3])
            fetch.assert_not_called()

    def test_full_cache_falls_back_to_temporary_storage(self):
        data = b'locked file'
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as scratch, patch.object(classroom, 'urlopen', return_value=io.BytesIO(data)), \
                patch.object(classroom.shutil, 'copyfileobj', side_effect=OSError(errno.ENOSPC, 'full')):
            directory = Path(scratch)
            cache = directory / 'cache'
            sources = classroom.download_packages({'file.deb': ('url', digest)}, cache, directory, Mock())
            self.assertEqual(sources, {'file.deb': directory / 'file.deb'})
            self.assertEqual(sources['file.deb'].read_bytes(), data)
            self.assertEqual(list(cache.iterdir()), [])

    def test_extract_rejects_wrong_digest_and_members_outside_inventory(self):
        for name, error in (('package.deb', 'file hash differs'), ('../outside', 'Unexpected dependency')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as scratch:
                directory = Path(scratch)
                path = directory / 'jdu-dependencies-0001.tar'
                member = tarfile.TarInfo(name)
                member.size = 4
                with tarfile.open(path, 'w') as archive:
                    archive.addfile(member, io.BytesIO(b'fake'))
                with self.assertRaisesRegex(ValueError, error):
                    classroom_guest.unpack_archives(directory, {path.name: classroom.summary(path)},
                                                    {'package.deb': '0' * 64})
                self.assertEqual(list(directory.iterdir()), [path])

    def test_five_transfers_overlap_and_recipe_follows_verified_archives(self):
        with tempfile.TemporaryDirectory() as scratch, patch.object(classroom_guest, 'ROOT', Path(scratch)):
            directory = Path(scratch) / 'source'
            directory.mkdir()
            assets = Path(scratch) / 'assets'
            assets.mkdir()
            archives = {}
            for number in range(1, 7):
                path = directory / f'jdu-dependencies-{number:04d}.tar'
                path.write_bytes(f'archive {number}'.encode())
                archives[path.name] = classroom.summary(path)
            cached = path.name
            (assets / cached).write_bytes(path.read_bytes())
            recipe = {'archives': archives}
            barrier = threading.Barrier(5)
            progress = []
            exchange = classroom.exchange

            def check_exchange(port, method, name, digest, path=None):
                if method == 'PUT':
                    self.assertNotEqual(name, cached)
                    if name == 'recipe.json':
                        self.assertEqual(progress, list(range(1, 7)))
                    else:
                        barrier.wait(timeout=5)
                return exchange(port, method, name, digest, path)

            with classroom_guest.ThreadingHTTPServer(('127.0.0.1', 0), classroom_guest.Receiver) as server:
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    with patch.object(classroom, 'transfer_session',
                                      side_effect=lambda node: contextlib.nullcontext(server.server_address[1])), \
                            patch.object(classroom, 'command'), patch.object(classroom, 'exchange', side_effect=check_exchange):
                        recipe_hash = classroom.transfer(None, 'repo', directory, recipe, progress.append)
                finally:
                    server.shutdown()
                    thread.join()

            self.assertEqual({name: classroom.summary(assets / name) for name in archives}, archives)
            self.assertEqual(classroom.summary(assets / 'recipe.json'), recipe_hash)

    def test_retry_reuses_only_intact_archives_for_the_same_recipe(self):
        with tempfile.TemporaryDirectory() as scratch, patch.object(classroom_guest, 'ROOT', Path(scratch)):
            assets = Path(scratch) / 'assets'
            assets.mkdir()
            archive = assets / 'jdu-dependencies-0001.tar'
            archive.write_bytes(b'transferred archive')
            pinned = {'assets': {'file.deb': 'a' * 64}, 'requirements': '', 'packages': ['file=1']}
            digest = hashlib.sha256(classroom.encoded(pinned)).hexdigest()
            self.assertIsNone(classroom_guest.reusable_recipe(digest))
            recipe = assets / 'recipe.json'
            recipe.write_bytes(classroom.encoded(dict(pinned, archives={archive.name: classroom.summary(archive)})))
            self.assertEqual(classroom_guest.reusable_recipe(digest), classroom.summary(recipe))
            self.assertIsNone(classroom_guest.reusable_recipe('0' * 64))
            archive.write_bytes(b'damaged archive')
            self.assertIsNone(classroom_guest.reusable_recipe(digest))
            archive.unlink()
            self.assertIsNone(classroom_guest.reusable_recipe(digest))

    def test_web_readiness_accepts_socket_activated_ssh(self):
        def run(args, **kwargs):
            if args[:3] == ['systemctl', 'is-active', '--quiet'] and args[3].startswith('ssh'):
                return Mock(returncode=0 if 'ssh.socket' in args else 3)
            return Mock(returncode=0, stdout=b'')

        with patch.object(classroom_guest.subprocess, 'run', side_effect=run):
            result = classroom_guest.verify({'role': 'web', 'instance_id': 'web-instance'})
        self.assertTrue(result['checks']['ssh'])

    def test_archive_rejection_prevents_sending_recipe(self):
        recipe = {'archives': {'jdu-dependencies-0001.tar': '0' * 64}}
        with tempfile.TemporaryDirectory() as scratch, \
                patch.object(classroom, 'transfer_session', return_value=contextlib.nullcontext(12345)), \
                patch.object(classroom, 'command'), patch.object(classroom, 'exchange', side_effect=[404, 400]) as exchange:
            progress = Mock()
            with self.assertRaisesRegex(ValueError, 'ASSET_VERIFICATION'):
                classroom.transfer(None, 'repo', Path(scratch), recipe, progress)
        self.assertEqual(exchange.call_count, 2)
        progress.assert_not_called()

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

    def test_student_parallelizes_initial_configuration_and_ssh_preparation(self):
        nodes = {role: f'node-{role}' for role in classroom.ROLES}
        outputs = {label + 'InstanceId': nodes[role] for role, label in classroom.ROLES.items()}
        outputs['BastionPublicIp'] = '192.0.2.10'
        session, screen = Mock(), Mock()
        session.client.return_value.describe_stacks.return_value = {'Stacks': [{
            'Outputs': [{'OutputKey': k, 'OutputValue': v} for k, v in outputs.items()],
        }]}
        session.client.return_value.describe_instances.return_value = {
            'Reservations': [{'Instances': [{'PublicIpAddress': '192.0.2.20'}]}],
        }
        screen.aws_wait.side_effect = lambda **kwargs: contextlib.nullcontext()
        screen.text = dict(download_progress='{done}/{total}', archive_progress='{done}/{total}', packing='packing',
                           archive_reused='Reused {count}', wait_for_ssm='waiting', deploy_helpers='deploying')
        screen.servers = dict(zip(nodes, nodes))
        configure_barrier = threading.Barrier(5)
        keys_barrier = threading.Barrier(4)
        authorize_barrier = threading.Barrier(4)
        verified_connections = []
        prepared = set()

        def guest(ssm, node, request, file='classroom_guest.py'):
            operation = request.get('operation') or request['command']
            if operation == 'reuse-archives':
                self.assertEqual(node, nodes['repo'])
                return {'recipe_sha256': 'existing-recipe'}
            if operation == 'repo':
                self.assertEqual(request['recipe_sha256'], 'existing-recipe')
                return {'key': 'repository-key'}
            if operation == 'configure':
                self.assertEqual(request['public_key'], 'repository-key')
                configure_barrier.wait(timeout=5)
                return {'role': request['role'], 'instance_id': node, 'checks': {'service': True}}
            if operation == 'init':
                self.assertEqual(set(request['peers']), set(nodes) - {'bastion'})
                return {'public_key': 'bastion-key'}
            if operation == 'authorize':
                self.assertEqual(request['public_key'], 'bastion-key')
                authorize_barrier.wait(timeout=5)
                prepared.add(request['role'])
                return {'role': request['role'], 'instance_id': node, 'authorized': True}
            self.assertEqual(operation, 'submit')
            self.assertEqual([r['role'] for r in request['report']['checks']], list(nodes))
            self.assertEqual(verified_connections, list(nodes)[1:])
            return {'received_at': 'complete'}

        def command(ssm, node, shell):
            if shell.startswith('cut '):
                keys_barrier.wait(timeout=5)
                return f'key-for-{node}'
            self.assertEqual(node, nodes['bastion'])
            self.assertEqual(prepared, set(nodes) - {'bastion'})
            verified_connections.append(shell.split()[-3])

        dependencies = ({}, {}, {'common': [], 'repo': []},
                        {'firefox_libraries': [], 'desktop_tools': [], 'firefox': {}}, '')
        config = dict(lab_id='lab-1', api_base_url='https://example.com', fixed_ingress_ipv4='192.0.2.1')
        installer = Mock(read_private=lambda path: json.loads(path.read_bytes()))
        with tempfile.TemporaryDirectory() as scratch, patch.dict(sys.modules, install_teacher=installer), \
                patch('classroom_checker.provision') as checker, \
                patch.multiple(classroom, assets=Mock(return_value=dependencies),
                               stack_setup=Mock(return_value=({'deployment_id': 'deployment', 'public_key': 'key'}, 'stack')),
                               wait_online=Mock(), deploy_guest=Mock(), download_packages=Mock(),
                               build_archives=Mock(return_value={}), transfer=Mock(), guest=guest, command=command,
                               stage_lessons=Mock(), register_bastion=Mock(), enable_session_prompt=Mock(return_value=True)):
            ip = classroom.setup_student(Mock(ref='a' * 40), screen, session, '012345678901', config, Path(scratch), '123456789012')
            self.assertEqual(checker.call_args.args[-1], '123456789012')
            classroom.download_packages.assert_not_called()
            classroom.build_archives.assert_not_called()
            classroom.transfer.assert_not_called()
        self.assertEqual(ip, '192.0.2.20')
        session.client.return_value.describe_instances.assert_called_once_with(InstanceIds=[nodes['bastion']])

    def test_lesson_transfer_fits_run_command_and_targets_web_and_db(self):
        ssm = Mock()
        barrier = threading.Barrier(2)

        def send_command(**kwargs):
            barrier.wait(timeout=5)
            return {'Command': {'CommandId': 'command'}}

        ssm.send_command.side_effect = send_command
        ssm.get_command_invocation.side_effect = lambda **args: {
            'Status': 'Success',
            'StandardOutputContent': json.dumps({'public_resources_ready': True, 'role': args['InstanceId']}),
        }
        with patch.object(classroom, 'remote_source', side_effect=lambda _, path: (ROOT / path).read_bytes()):
            classroom.stage_lessons('ref', ssm, {'web': 'web', 'db': 'db'},
                                    {'lab_id': 'lab-1', 'deployment_id': 'deployment'})
        calls = [item.kwargs for item in ssm.send_command.call_args_list]
        self.assertCountEqual([item['InstanceIds'] for item in calls], [['web'], ['db']])
        self.assertTrue(all(len(item['Parameters']['commands'][0]) < 60000 for item in calls))


if __name__ == '__main__':
    unittest.main()
