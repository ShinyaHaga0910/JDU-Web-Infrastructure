"""Optional real Nginx acceptance in a temporary loopback-only server."""
import grp
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest

from http_guest_v2 import current_file, custom_root_config
from http_task_current import contract, http_probe


@unittest.skipUnless(getattr(os, 'geteuid', lambda: -1)() == 0 and shutil.which('nginx'), 'root and an existing Nginx binary required')
class RealNginxTest(unittest.TestCase):
    def test_both_roots_permissions_and_unchanged_urls(self):
        with tempfile.TemporaryDirectory(prefix='jdu-http-rubric-') as name:
            root = Path(name)
            root.chmod(0o755)
            specs = []
            for task, folder in [('P1', 'jdu-practice'), ('M1', 'jdu-mission')]:
                spec = contract(task)
                directory = root / folder
                directory.mkdir(mode=0o755)
                path = directory / Path(spec['file']).name
                path.write_text(spec['body'])
                os.chown(path, 0, grp.getgrnam('www-data').gr_gid)
                path.chmod(0o640)
                specs.append(dict(spec, file=str(path)))
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            config = root / 'nginx.conf'
            mappings = ''.join('location = ' + s['path'] + ' { root ' + str(Path(s['file']).parent) + '; }' for s in specs)
            config.write_text('user www-data; pid ' + str(root / 'nginx.pid') + '; error_log ' + str(root / 'error.log')
                + '; events {} http { access_log off; server { listen 127.0.0.1:' + str(port) + '; ' + mappings + '} }')
            command = ['nginx', '-p', name, '-c', str(config)]
            compiled = subprocess.run(command + ['-T'], capture_output=True, text=True, check=True)
            self.assertTrue(custom_root_config(compiled.stdout, specs))
            process = subprocess.Popen(command + ['-g', 'daemon off;'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for _ in range(60):
                    with socket.socket() as check:
                        if check.connect_ex(('127.0.0.1', port)) == 0:
                            break
                    if process.poll() is not None:
                        self.fail(process.communicate()[1].decode())
                    time.sleep(.05)
                for spec in specs:
                    self.assertTrue(current_file(spec))
                    self.assertTrue(http_probe('127.0.0.1', spec['path'], spec['body'], 'a' * 32, port))
                practice = Path(specs[0]['file'])
                practice.chmod(0o644)
                self.assertFalse(current_file(specs[0]))
                practice.chmod(0o640)
                os.chown(practice, 0, 0)
                self.assertFalse(current_file(specs[0]))
                self.assertFalse(http_probe('127.0.0.1', specs[0]['path'], specs[0]['body'], 'a' * 32, port))
            finally:
                process.terminate()
                process.communicate(timeout=10)


if __name__ == '__main__':
    unittest.main()
