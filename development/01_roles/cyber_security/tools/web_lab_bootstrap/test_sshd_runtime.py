"""Regression: standalone sshd validation must have a safe runtime directory."""
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import node_bootstrap as node
from release_validation import ValidationError


class SshRuntimeTests(unittest.TestCase):
    def test_missing_directory_and_existing_safe_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'sshd'
            # Fixture files use the test user; production requires root ownership.
            original=Path.lstat
            def root_stat(p):
                value=original(p)
                return SimpleNamespace(st_mode=value.st_mode,st_uid=0,st_gid=0)
            with patch.object(Path,'lstat',root_stat):
                node.prepare_sshd_runtime(path)
                self.assertTrue(path.is_dir())
                self.assertEqual(stat.S_IMODE(original(path).st_mode),0o755)
                node.prepare_sshd_runtime(path)

    def test_symlink_file_and_unsafe_ownership_or_mode_are_rejected(self):
        for mode,uid,gid in ((stat.S_IFLNK|0o755,0,0),(stat.S_IFREG|0o755,0,0),
                             (stat.S_IFDIR|0o777,0,0),(stat.S_IFDIR|0o755,1000,0),
                             (stat.S_IFDIR|0o755,0,1000)):
            with self.subTest(mode=mode,uid=uid,gid=gid),\
                 patch.object(Path,'mkdir',side_effect=FileExistsError),\
                 patch.object(Path,'lstat',return_value=SimpleNamespace(st_mode=mode,st_uid=uid,st_gid=gid)):
                with self.assertRaises(ValidationError):node.prepare_sshd_runtime()


if __name__=='__main__':unittest.main()
