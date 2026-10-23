import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import decode, encode, private_create, private_read


class EnvironmentSafety(unittest.TestCase):
    def config(self):
        return dict(DJANGO_SECRET_KEY='fictional-fixture-' + 'x' * 50,
            DJANGO_ALLOWED_HOSTS='web.lab.test,admin.lab.test,10.20.1.20',
            DB_HOST='db.lab.test', DB_PORT='5432', DB_NAME='jdu_catalog', DB_USER='catalog_app',
            DB_PASSWORD='fictional-' + r'"\$` % $(no-execution)' + '-only',
            DJANGO_STATIC_ROOT='/var/lib/jdu-catalog/static', CATALOG_SITE_NAME='JDU 備品カタログ')

    def test_roundtrip_and_fail_closed_fields(self):
        c = self.config()
        self.assertEqual(decode(encode(c, 'runtime'), 'runtime'), c)
        for field, value in [('DB_HOST', 'external.example'), ('DB_USER', 'postgres'),
                             ('DJANGO_ALLOWED_HOSTS', '*'), ('DB_PASSWORD', 'short'),
                             ('CATALOG_SITE_NAME', 'line\nbreak')]:
            altered = dict(c, **{field: value})
            with self.assertRaises(ValueError): encode(altered, 'runtime')
        with self.assertRaises(ValueError): decode(encode(c, 'runtime') + b'DB_USER="catalog_app"\n', 'runtime')
        with self.assertRaises(ValueError): decode(b'export DB_PASSWORD=anything\n', 'runtime')

    @unittest.skipUnless(os.geteuid() == 0, 'isolated root fixture only')
    def test_private_creation_preserves_existing_and_rejects_links_or_permissions(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'app.env'
            private_create(p, self.config(), 'runtime')
            self.assertEqual(private_read(p, 'runtime'), self.config())
            before = p.read_bytes()
            with self.assertRaises(FileExistsError): private_create(p, self.config(), 'runtime')
            link = Path(t) / 'link.env'
            link.symlink_to(p)
            with self.assertRaises(OSError): private_read(link, 'runtime')
            p.chmod(0o644)
            with self.assertRaises(ValueError): private_read(p, 'runtime')
            self.assertEqual(p.read_bytes(), before)

    @unittest.skipUnless(os.geteuid() == 0 and Path('/run/systemd/system').exists(), 'real systemd root fixture only')
    def test_actual_systemd_environmentfile_preserves_literals_without_execution(self):
        with tempfile.TemporaryDirectory() as t:
            marker = Path(t) / 'should-not-exist'
            c = self.config()
            c['CATALOG_SITE_NAME'] = 'JDU $(touch ' + str(marker) + ') `touch ' + str(marker) + '` $HOME %n'
            p = Path(t) / 'fixture.env'
            private_create(p, c, 'runtime')
            child = 'import hashlib,json,os;print(hashlib.sha256(json.dumps({k:os.environ[k] for k in '+repr(sorted(c))+'},sort_keys=True,ensure_ascii=False).encode()).hexdigest())'
            result = subprocess.run(['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                '-p', 'EnvironmentFile=' + str(p), '/usr/bin/python3', '-c', child],
                capture_output=True, text=True, timeout=20, check=True)
            expected = hashlib.sha256(json.dumps(c, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(result.stdout.strip(), expected)
            self.assertFalse(marker.exists())


if __name__ == '__main__': unittest.main()
