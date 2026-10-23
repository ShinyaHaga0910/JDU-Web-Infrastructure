import io
from pathlib import Path
import sys
import tempfile
import unittest

from build_package_repository import validate_application_bundles

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'web_lab_teacher'))
from build_checker_bundle import bundle


class ApplicationPayloadGuards(unittest.TestCase):
    def test_valid_real_catalog_and_checker_inventories(self):
        root=Path(__file__).resolve().parent.parent
        sys.path.insert(0,str(root/'web_lab_catalog'))
        from build_bundle import bundle as app_bundle
        with tempfile.TemporaryDirectory() as work:
            a=Path(work)/'app.tar.gz';c=Path(work)/'checker.tar.gz'
            a.write_bytes(app_bundle(root/'web_lab_catalog')[0]);c.write_bytes(bundle(root/'web_lab_teacher')[0])
            result=validate_application_bundles(a,c)
            self.assertEqual(result['app_file_count'],33)
            self.assertEqual(result['supported_tasks'],['bootstrap','P1','M1'])
            self.assertEqual(result['scope'],'web02_only_no_course_points')
    def test_arbitrary_archive_cannot_grant_payload_scope(self):
        root=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as work:
            a=Path(work)/'app.tar.gz';c=Path(work)/'checker.tar.gz'
            a.write_bytes(b'not an application archive');c.write_bytes(bundle(root/'web_lab_teacher')[0])
            with self.assertRaises(Exception):validate_application_bundles(a,c)


if __name__=='__main__':unittest.main()
