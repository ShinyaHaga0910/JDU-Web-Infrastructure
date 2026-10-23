from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from class_student_delivery import digest
from class_signed_tools import (ARCHIVE_SHA, ARCHIVE_SIZE, BUCKET, NAMES, PREFIX, envelope, extract, validate_url)


class ClassSignedToolsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
        self.request = {"public": "recipient-fixture"}
        self.value = dict(scope="class193548_v7_public_software_urls",
            request_sha256=digest(json.dumps(self.request, sort_keys=True).encode()),
            created_at=self.now.isoformat(), expires_at=(self.now + timedelta(hours=1)).isoformat(),
            files=[dict(name=n, sha256=ARCHIVE_SHA if i == 0 else "a" * 64,
                size_bytes=ARCHIVE_SIZE if i == 0 else 100,
                url="https://" + BUCKET + ".s3.us-east-1.amazonaws.com/" + PREFIX + n + "?signed=fixture")
                for i, n in enumerate(NAMES)])

    def test_exact_software_envelope(self):
        self.assertEqual(envelope(self.value, self.request, self.now), self.value)

    def test_expiry_recipient_replacement_and_extra_credential_refused(self):
        for changes in ({"request_sha256": "b" * 64}, {"lab_token": "fixture"},
                        {"expires_at": (self.now + timedelta(hours=2)).isoformat()}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                envelope(dict(self.value, **changes), self.request, self.now)
        with self.assertRaises(ValueError):
            envelope(self.value, self.request, self.now + timedelta(hours=1))

    def test_replaced_archive_or_file_inventory_refused(self):
        for files in (self.value["files"][::-1], self.value["files"][:2],
                      [dict(self.value["files"][0], sha256="c" * 64)] + self.value["files"][1:]):
            with self.subTest(files=files), self.assertRaises(ValueError):
                envelope(dict(self.value, files=files), self.request, self.now)

    def test_other_software_destinations_refused(self):
        url = self.value["files"][0]["url"]
        for changed in (url.replace("https://", "http://"), url.replace(BUCKET, "other-bucket"),
                        url.replace("v7/", "v6/"), url + "#fragment", url.replace(".com/", ".com:443/")):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_url(changed, NAMES[0])

    def archive(self, name, *, symlink=False):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w:gz") as tar:
            member = tarfile.TarInfo(name); member.size = 2
            if symlink: member.type = tarfile.SYMTYPE; member.linkname = "/tmp/elsewhere"
            tar.addfile(member, None if symlink else io.BytesIO(b"ok"))
        return out.getvalue()

    def test_flat_signed_archive_extraction_and_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "tools"
            extract(self.archive("student-tools/README.txt"), out)
            self.assertEqual((out / "README.txt").read_bytes(), b"ok")
            with self.assertRaises(FileExistsError): extract(self.archive("student-tools/README.txt"), out)

    def test_traversal_nested_and_link_members_refused(self):
        for name, linked in (("student-tools/../outside", False), ("other/file", False),
                             ("student-tools/nested/file", False), ("student-tools/link", True)):
            with tempfile.TemporaryDirectory() as temp, self.subTest(name=name), self.assertRaises(ValueError):
                extract(self.archive(name, symlink=linked), Path(temp) / "tools")


if __name__ == "__main__": unittest.main()
