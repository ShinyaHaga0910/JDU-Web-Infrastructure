"""Real signed kit plus temporary personal CloudShell-like files; no AWS mutations."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

import release_tools as rt
import student
from teacher import store

FINGERPRINT = '65EC6784750CCFA703BA7179519284E45155EC2A'
PROJECT = Path(__file__).resolve().parents[4]
KIT = Path(os.environ.get('JDU_WEB_COURSE_TEST_ROOT', str(PROJECT / '03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2')))


class Session:
    def __init__(self, account='111122223333'):
        self.account = account

    def client(self, service):
        if service != 'sts':
            raise AssertionError('These filesystem tests must never access AWS')
        return types.SimpleNamespace(get_caller_identity=lambda: {'Account': self.account})


class KitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = rt.verify(KIT, FINGERPRINT)

    def test_real_outer_inner_signatures_and_exact_archive_inventory(self):
        raw = rt.read(str(KIT) + '.tar.gz')
        self.assertEqual(rt.checked_archive(raw), rt.tree(KIT))
        self.assertEqual(self.context['release']['raw_maximum'], 62)
        self.assertEqual(self.context['release']['contract_sha256'], '3feeb3d8a9225e6e19e06f68367b07c6cb4a657f05818c146ccb22cfcd654c33')

    def test_no_test_student_identity_or_private_file_in_common_software(self):
        data = rt.tree(KIT)
        self.assertFalse(any('.private.' in n for n in data))
        for raw in data.values():
            for marker in (b'965244652544', b'jdutestuser1@', b'i-0488d26e69614e096'):
                self.assertNotIn(marker, raw)

    def test_changed_or_extra_file_refused_before_import(self):
        for extra in (False, True):
            with tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / 'kit'; shutil.copytree(KIT, target)
                if extra:
                    (target / 'unexpected.py').write_text('raise RuntimeError("must not run")')
                else:
                    (target / 'STUDENT.md').write_text('changed')
                with self.assertRaises(ValueError):
                    rt.verify(target, FINGERPRINT)

    def test_wrong_signer_and_linked_verifier_refused(self):
        with self.assertRaises(ValueError):
            rt.verify(KIT, 'A' * 40)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'kit'; shutil.copytree(KIT, target)
            verifier = target / 'foundation/core/release_validation.py'
            verifier.unlink(); verifier.symlink_to(KIT / 'foundation/core/release_validation.py')
            with self.assertRaises(ValueError):
                rt.verify(target, FINGERPRINT)

    def test_archive_rejects_traversal_links_and_duplicates(self):
        for name, linked, repeat in (('jdu-web-course/../escape', False, False),
                ('jdu-web-course/safe', True, False), ('jdu-web-course/safe', False, True)):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
                entry = tarfile.TarInfo(name)
                if linked:
                    entry.type = tarfile.SYMTYPE; entry.linkname = '/etc/passwd'
                else:
                    entry.size = 1
                archive.addfile(entry, None if linked else io.BytesIO(b'x'))
                if repeat:
                    archive.addfile(entry, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                rt.checked_archive(buffer.getvalue())


class PersonalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_context = rt.verify(KIT, FINGERPRINT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "student's home"; self.home.mkdir(mode=0o700)
        self.context = copy.deepcopy(self.original_context)
        original = self.context['foundation']['controller']
        controller = self.home / '.local/share/jdu-web/controllers' / original.name
        controller.parent.mkdir(mode=0o700, parents=True)
        shutil.copytree(original, controller)
        self.context['foundation']['controller'] = controller
        self.state_path = self.home / 'own-state.private.json'
        self.baseline_path = Path(str(self.state_path) + '.baseline.json')
        self.config_path = self.home / '.jdu-web-student/fixture-student/command-state.json'
        self.config_path.parent.mkdir(mode=0o700, parents=True)
        self.state = dict(account='111122223333', region='us-east-1', lab_id='fixture-student',
            deployment_id='11111111-2222-4333-8444-555555555555', stack_id='fixture-stack', stack_name='jdu-web-fixture-student',
            manifest_sha256=self.context['release']['core_manifest_sha256'], release_id=self.context['foundation']['core']['manifest']['release_id'])
        self.baseline = {k: self.state[k] for k in ('account', 'deployment_id', 'stack_id')}
        self.baseline['nodes'] = {r: {'instance_id': 'i-' + f'{n:017x}'} for n, r in enumerate(sorted(student.ROLES), 1)}
        self.config = dict(scope='signed_student_candidate_commands', state=str(self.state_path),
            baseline_plan=str(self.baseline_path), bootstrap_tools=str(controller),
            ssh_enrollment=str(self.state_path) + '.ssh.json.enrolled.public.json',
            pending_directory=str(self.config_path.parent / 'pending'),
            network_source_sha256=rt.digest(rt.read(controller / 'network_probe.py')))
        for key, name in (('guest_source', 'post_restart_guest.py'), ('submission_source', 'bootstrap_submission_guest.py')):
            self.config[key] = str(controller / name); self.config[key + '_sha256'] = rt.digest(rt.read(controller / name))
        for path, value in ((self.state_path, self.state), (self.baseline_path, self.baseline),
                (self.config_path, self.config), (Path(self.config['ssh_enrollment']), {'deployment_id': self.state['deployment_id']})):
            rt.save(path, rt.encoded(value))
        self.original_bin = self.home / '.local/bin/jdu-web-check'; self.original_bin.parent.mkdir(mode=0o700)
        rt.save(self.original_bin, b'old D08 launcher\n', 0o700)
        self.home_patch = patch.object(Path, 'home', return_value=self.home); self.home_patch.start()

    def tearDown(self):
        self.home_patch.stop(); self.temp.cleanup()

    def rewrite(self, path, value):
        path.write_bytes(rt.encoded(value))

    def test_install_and_identical_retry_preserve_original_files_and_path(self):
        original = {p: p.read_bytes() for p in (self.state_path, self.baseline_path, self.config_path, self.original_bin)}
        target, reused = student.install(self.context, self.config_path, None, Session(), live=lambda *a: None)
        self.assertFalse(reused)
        first = rt.tree(target)
        again, reused = student.install(self.context, self.config_path, None, Session(), live=lambda *a: self.fail('already installed'))
        self.assertTrue(reused); self.assertEqual(target, again); self.assertEqual(first, rt.tree(target))
        self.assertEqual(original, {p: p.read_bytes() for p in original})
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c', 'source "$1"; command -v jdu-web-check',
            'fixture', str(target / 'activate.sh')], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), str(target / 'bin/jdu-web-check'))

    def test_wrong_account_foundation_or_roles_refused_without_install(self):
        for account in ('444455556666', self.context['release']['teacher_account']):
            with self.assertRaises(ValueError):
                student.identity(self.context, self.config_path, account)
        bad = dict(self.state, manifest_sha256='a' * 64); self.rewrite(self.state_path, bad)
        with self.assertRaises(ValueError):
            student.identity(self.context, self.config_path, '111122223333')
        self.rewrite(self.state_path, self.state)
        self.baseline['nodes']['unexpected'] = {}
        self.rewrite(self.baseline_path, self.baseline)
        with self.assertRaises(ValueError):
            student.identity(self.context, self.config_path, '111122223333')

    def test_readable_or_linked_config_refused(self):
        self.config_path.chmod(0o644)
        with self.assertRaises(ValueError):
            student.identity(self.context, self.config_path, '111122223333')
        self.config_path.chmod(0o600)
        raw = self.config_path.read_bytes(); self.config_path.unlink()
        other = self.home / 'linked-source'; rt.save(other, raw); self.config_path.symlink_to(other)
        with self.assertRaises(ValueError):
            student.identity(self.context, self.config_path, '111122223333')

    def test_existing_changed_launcher_retained(self):
        target, _ = student.install(self.context, self.config_path, None, Session(), live=lambda *a: None)
        path = target / 'bin/jdu-web-check'; path.write_bytes(b'changed existing launcher\n')
        with self.assertRaises(ValueError):
            student.install(self.context, self.config_path, None, Session(), live=lambda *a: None)
        self.assertEqual(path.read_bytes(), b'changed existing launcher\n')

    def test_cloudshell_default_writable_home_is_protected_before_install(self):
        self.home.chmod(0o777)
        original = self.config_path.read_bytes()
        target, _ = student.install(self.context, self.config_path, None, Session(), live=lambda *a: None)
        self.assertEqual(self.home.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.config_path.read_bytes(), original)
        self.assertEqual((target / 'binding.private.json').stat().st_mode & 0o777, 0o600)

    def test_linked_output_and_source_overlap_refused(self):
        link = self.home / 'link'; link.symlink_to(self.home / '.local')
        with self.assertRaises(ValueError):
            student.install(self.context, self.config_path, link / 'install', Session(), live=lambda *a: None)
        with self.assertRaises(ValueError):
            student.install(self.context, self.config_path, self.context['root'] / 'install', Session(), live=lambda *a: None)

    def test_bound_command_refuses_configuration_override(self):
        target, _ = student.install(self.context, self.config_path, None, Session(), live=lambda *a: None)
        selected = student.identity(self.context, self.config_path, '111122223333')
        fake = types.SimpleNamespace(client=Session().client)
        with patch.object(student, 'ROOT', target / 'kit'), patch.object(student, 'verify', return_value=self.context), \
                patch.object(student, 'identity', return_value=selected), patch.dict(sys.modules, boto3=fake):
            with self.assertRaises(ValueError):
                student.run(['--binding', str(target / 'binding.private.json'), '--', 'M2', '--command-state=/other'])


class PublicationTests(unittest.TestCase):
    def test_private_immutable_put_and_identical_retry(self):
        class NotFound(Exception):
            response = {'Error': {'Code': 'NoSuchKey'}}
        class S3:
            exceptions = types.SimpleNamespace(ClientError=NotFound)
            def __init__(self): self.data = {}; self.puts = []
            def get_object(self, **kw):
                if kw['Key'] not in self.data: raise NotFound()
                return dict(Body=io.BytesIO(self.data[kw['Key']]), ServerSideEncryption='AES256')
            def put_object(self, **kw):
                self.puts.append(kw); self.data[kw['Key']] = kw['Body']
        s = S3(); store(s, 'private-bucket', 'distributions/release/file', b'public software', '111122223333')
        store(s, 'private-bucket', 'distributions/release/file', b'public software', '111122223333')
        self.assertEqual(len(s.puts), 1)
        self.assertEqual(s.puts[0]['IfNoneMatch'], '*'); self.assertEqual(s.puts[0]['ServerSideEncryption'], 'AES256')
        self.assertNotIn('ACL', s.puts[0])
        with self.assertRaises(ValueError):
            store(s, 'private-bucket', 'distributions/release/file', b'different', '111122223333')
        self.assertEqual(s.data['distributions/release/file'], b'public software')


if __name__ == '__main__':
    unittest.main(verbosity=2)
