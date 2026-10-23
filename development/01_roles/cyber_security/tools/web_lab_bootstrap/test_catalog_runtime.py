import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_catalog_runtime_guest import extract_app


class AppExtractionGuards(unittest.TestCase):
    def archive(self, name, link=False):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w:gz') as t:
            m = tarfile.TarInfo(name)
            if link:
                m.type = tarfile.SYMTYPE
                m.linkname = '/etc/passwd'
                t.addfile(m)
            else:
                m.size = 1
                t.addfile(m, io.BytesIO(b'x'))
        return out.getvalue()

    def test_traversal_absolute_or_links_rejected_before_target_creation(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t) / 'app'
            for name, link in [('/jdu-catalog/file', False), ('jdu-catalog/../file', False),
                               ('other/file', False), ('jdu-catalog/file', True)]:
                with self.assertRaises(ValueError): extract_app(self.archive(name, link), target)
                self.assertFalse(target.exists())


if __name__ == '__main__': unittest.main()
