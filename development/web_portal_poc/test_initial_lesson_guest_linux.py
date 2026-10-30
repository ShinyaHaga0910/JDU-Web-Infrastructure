"""Real root-owned file staging in isolated Linux temporary directories only.

Run separately with Linux Python as root; no AWS, packages or service changes.
"""
import base64
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from initial_lesson_guest import stage


class LessonGuestLinuxTest(unittest.TestCase):
    def setUp(self):
        if os.name!='posix' or os.geteuid()!=0:
            raise RuntimeError('Run this separate filesystem test in isolated Linux as root')
        self.temporary=tempfile.TemporaryDirectory(prefix='jdu-public-lessons-test-',dir='/root')
        self.addCleanup(self.temporary.cleanup)
        self.parent=Path(self.temporary.name)
        if self.parent.resolve().parent!=Path('/root'):raise RuntimeError('Unexpected test path')
        self.root=self.parent/'lesson-resources-r1'
        self.bootstrap=self.parent/'bootstrap.json'
        self.identity={'lab_id':'synthetic-student','deployment_id':'05342512-1a55-4e11-b2d3-cd450487a138',
                       'instance_id':'i-'+'a'*17,'role':'web'}
        self.bootstrap.write_text(json.dumps(self.identity))
        self.files={n:('public synthetic '+n).encode() for n in
            ('catalog-app.tar.gz','registry.py','assessment-registry.json','database_secret.py','offline_assets.py')}
        self.request={**self.identity,'files':{n:base64.b64encode(v).decode() for n,v in self.files.items()}}

    def run_stage(self,request=None):return stage(request or self.request,root=self.root,bootstrap=self.bootstrap)

    def test_first_and_repeat_keep_exact_five_public_files_and_linux_modes(self):
        expected={'public_resources_ready':True,'role':'web','file_count':5,'services_changed':False}
        self.assertEqual(self.run_stage(),expected);self.assertEqual(self.run_stage(),expected)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode),0o755)
        for n,raw in self.files.items():
            p=self.root/n;self.assertEqual(p.read_bytes(),raw)
            self.assertEqual(p.stat().st_uid,0);self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o644)

    def test_partial_stage_can_fill_missing_files_but_different_existing_content_is_retained(self):
        self.root.mkdir(mode=0o755)
        first=self.root/'registry.py';first.write_bytes(self.files['registry.py']);first.chmod(0o644)
        self.assertTrue(self.run_stage()['public_resources_ready'])
        first.write_bytes(b'different existing public content')
        with self.assertRaises(ValueError):self.run_stage()
        self.assertEqual(first.read_bytes(),b'different existing public content')

    def test_symlink_and_unrelated_files_never_get_followed_or_overwritten(self):
        self.root.mkdir(mode=0o755)
        target=self.parent/'outside';target.write_bytes(b'preserve')
        link=self.root/'registry.py';link.symlink_to(target)
        with self.assertRaises(ValueError):self.run_stage()
        self.assertEqual(target.read_bytes(),b'preserve')
        link.unlink();extra=self.root/'student-file.txt';extra.write_bytes(b'preserve extra')
        with self.assertRaises(ValueError):self.run_stage()
        self.assertEqual(extra.read_bytes(),b'preserve extra')
        self.assertEqual(set(p.name for p in self.root.iterdir()),{'student-file.txt'})

    def test_wrong_instance_role_or_extra_field_cannot_place_files(self):
        for changed in ({'instance_id':'i-'+'b'*17},{'role':'db'},{'root':'/another-target'}):
            with self.assertRaises(ValueError):self.run_stage({**self.request,**changed})
            self.assertFalse(self.root.exists())


if __name__=='__main__':unittest.main()
