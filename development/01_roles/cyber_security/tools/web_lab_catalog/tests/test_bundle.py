import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_bundle import FILES, bundle


class BundleSafety(unittest.TestCase):
    def test_deterministic_exact_public_files_and_integrity(self):
        data, manifest = bundle(ROOT)
        self.assertEqual(data, bundle(ROOT)[0])
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
            self.assertEqual(set(tar.getnames()), {'jdu-catalog/' + p for p in FILES} | {'jdu-catalog/APP-MANIFEST.json'})
            self.assertEqual(json.load(tar.extractfile('jdu-catalog/APP-MANIFEST.json')), manifest)
            for f in manifest['files']:
                raw = tar.extractfile('jdu-catalog/' + f['path']).read()
                self.assertEqual((hashlib.sha256(raw).hexdigest(), len(raw)), (f['sha256'], f['size_bytes']))
            self.assertTrue(all(m.isfile() and m.mode == 0o644 and m.mtime == 0 for m in tar))
        self.assertNotIn(b'fictional-local-runtime-only', data)

    def test_private_and_fixture_files_excluded_and_source_link_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name in FILES:
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            (root / 'app.env').write_text('fictional-secret-should-not-be-packed')
            (root / 'setup.credentials.json').write_text('fictional-private-fixture')
            data, _ = bundle(root)
            self.assertEqual(data, bundle(ROOT)[0])
            (root / 'manage.py').unlink()
            (root / 'manage.py').symlink_to(ROOT / 'manage.py')
            with self.assertRaises(ValueError): bundle(root)


if __name__ == '__main__': unittest.main()
