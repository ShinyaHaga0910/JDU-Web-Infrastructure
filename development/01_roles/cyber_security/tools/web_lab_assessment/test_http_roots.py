"""Custom-root rubric regressions; no changes to a running lesson server."""
import base64
import hashlib
from pathlib import Path
import stat
import sys
import types
import unittest
from unittest.mock import Mock, patch

import http_guest_v2 as guest
from http_task_current import contract


class RootTests(unittest.TestCase):
    def test_current_contract_bytes_and_custom_roots(self):
        data = Path(__file__).with_name('http_task_current.py').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), guest.CONTRACT_SHA256)
        self.assertEqual(contract('P1')['file'], '/var/www/jdu-practice/practice.txt')
        self.assertEqual(contract('M1')['file'], '/var/www/jdu-mission/mission.txt')

    def test_default_configuration_cannot_pass_the_mapping_check(self):
        specs = [contract('P1'), contract('M1')]
        text = 'server { listen 80; root /var/www/html; location / { try_files $uri =404; } }'
        self.assertFalse(guest.custom_root_config(text, specs))
        practice = 'location = /practice.txt { root /var/www/jdu-practice; }'
        mission = 'location = /mission.txt { root /var/www/jdu-mission; }'
        self.assertTrue(guest.custom_root_config('server {' + practice + '}', specs[:1]))
        self.assertFalse(guest.custom_root_config('server {' + practice + '}', specs))
        self.assertTrue(guest.custom_root_config('server {' + practice + mission + '}', specs))
        self.assertFalse(guest.custom_root_config('# ' + practice + '\nserver {' + mission + '}', specs))
        self.assertFalse(guest.custom_root_config('server {' + practice.replace('jdu-practice', 'html') + mission + '}', specs))
        self.assertTrue(guest.custom_root_config('server {' + practice.replace('root /var', 'root "/var').replace('practice;', 'practice";') + '}', specs[:1]))

    def test_owner_group_mode_and_links_are_all_enforced(self):
        spec = contract('P1')
        target = Mock()
        target.parents = []
        target.read_bytes.return_value = spec['body'].encode()
        info = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_gid=33, st_size=40)
        target.lstat.return_value = info
        group = types.SimpleNamespace(getgrnam=lambda name: types.SimpleNamespace(gr_gid=33))
        with patch.object(guest, 'Path', return_value=target), patch.dict(sys.modules, {'grp': group}):
            self.assertTrue(guest.current_file(spec))
            info.st_mode = stat.S_IFREG | 0o644
            self.assertFalse(guest.current_file(spec))
            info.st_mode = stat.S_IFREG | 0o640
            info.st_gid = 0
            self.assertFalse(guest.current_file(spec))
            info.st_gid, info.st_uid = 33, 1000
            self.assertFalse(guest.current_file(spec))
            info.st_uid = 0
            target.parents = [Mock(is_symlink=lambda: True)]
            self.assertFalse(guest.current_file(spec))


if __name__ == '__main__':
    unittest.main()
