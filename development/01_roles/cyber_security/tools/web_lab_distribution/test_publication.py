import gzip
import io
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest

from publish_release import archive_matches, store


class Missing(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


class PrivateStore:
    exceptions = SimpleNamespace(ClientError=Missing)

    def __init__(self):
        self.values = {}; self.writes = 0

    def get_object(self, **args):
        if args['Key'] not in self.values: raise Missing()
        return dict(Body=io.BytesIO(self.values[args['Key']]), ServerSideEncryption='AES256')

    def put_object(self, **args):
        if args['IfNoneMatch'] != '*' or args['ServerSideEncryption'] != 'AES256':
            raise AssertionError('Only exclusive encrypted publication allowed')
        self.values[args['Key']] = args['Body']; self.writes += 1


class PublicationTests(unittest.TestCase):
    def test_identical_retry_does_not_write_and_different_release_cannot_overwrite(self):
        s3 = PrivateStore()
        store(s3, 'private-fixture', 'one-key', b'one-release', '111122223333')
        store(s3, 'private-fixture', 'one-key', b'one-release', '111122223333')
        self.assertEqual(s3.writes, 1)
        with self.assertRaises(ValueError): store(s3, 'private-fixture', 'one-key', b'another-release', '111122223333')
        self.assertEqual(s3.values['one-key'], b'one-release')

    def test_signed_but_wrong_archive_and_traversal_are_not_published(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'one.txt').write_bytes(b'expected')
            for name, content, accepted in [('jdu-web-distribution/one.txt', b'expected', True),
                    ('jdu-web-distribution/one.txt', b'wrong-version', False),
                    ('jdu-web-distribution/../one.txt', b'expected', False)]:
                out = io.BytesIO()
                with tarfile.open(fileobj=out, mode='w') as archive:
                    info = tarfile.TarInfo(name); info.size = len(content); archive.addfile(info, io.BytesIO(content))
                data = gzip.compress(out.getvalue())
                if accepted: archive_matches(root, data)
                else:
                    with self.assertRaises(ValueError): archive_matches(root, data)


if __name__ == '__main__': unittest.main()
