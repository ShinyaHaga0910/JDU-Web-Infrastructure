import json
from pathlib import Path
import tempfile
import unittest

from bind_checker_commands import bind
from build_checker_bundle import bundle
from install_checker_bundle import checked_archive


class BindingGuards(unittest.TestCase):
    def fixture(self,root):
        files,_=checked_archive(bundle(Path(__file__).resolve().parent)[0])
        installed=root/'installed';installed.mkdir()
        for name,raw in files.items():
            p=installed/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        config=root/'old.json';config.write_text(json.dumps(dict(state='/private/existing-state.json',
            ssh_enrollment='/private/existing-public-enrollment.json',private_token_file='/private/never-read.json')));config.chmod(0o600)
        launcher=root/'jdu-web-check';launcher.write_text('#!/bin/sh\nexit 42\n');launcher.chmod(0o700)
        return installed,config,root/'new.json',launcher
    def test_binding_preserves_originals_without_reading_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            r,c,t,l=self.fixture(Path(d));old=c.read_bytes();body=l.read_bytes()
            result=bind(r,c,t,l)
            self.assertEqual(c.read_bytes(),old)
            self.assertEqual(Path(str(l)+'.before-signed-web02').read_bytes(),body)
            self.assertEqual(json.loads(t.read_text())['private_token_file'],'/private/never-read.json')
            self.assertFalse(result['credentials_read'])
            self.assertIn('check_dispatch.py',l.read_text())
    def test_changed_installed_file_rejected_before_any_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            r,c,t,l=self.fixture(Path(d));old=l.read_bytes();(r/'http_task.py').write_text('tampered')
            with self.assertRaises(ValueError):bind(r,c,t,l)
            self.assertEqual(l.read_bytes(),old);self.assertFalse(t.exists())
    def test_second_binding_refused_and_keeps_previous_launcher(self):
        with tempfile.TemporaryDirectory() as d:
            r,c,t,l=self.fixture(Path(d));bind(r,c,t,l);current=l.read_bytes()
            with self.assertRaises(ValueError):bind(r,c,t,l)
            self.assertEqual(l.read_bytes(),current)


if __name__=='__main__':unittest.main()
