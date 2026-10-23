"""Archive and real-signature rejection tests; never provisions resources."""
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import payload_runtime as runtime
import release_validation as validation
import test_web_lab as test_support


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def archive(self, entries):
        path=self.root/"payload.tar.gz"
        with tarfile.open(path,"w:gz") as archive:
            for name,kind,value in entries:
                member=tarfile.TarInfo(name)
                if kind=="file":
                    data=value.encode(); member.size=len(data)
                    archive.addfile(member,io.BytesIO(data))
                else:
                    member.type=kind; member.linkname=value
                    archive.addfile(member)
        return path,hashlib.sha256(path.read_bytes()).hexdigest()

    def test_valid_file_and_hash_before_extraction(self):
        path,sha=self.archive([("release/a.txt","file","ok")])
        with self.assertRaises(validation.ValidationError):
            runtime.safe_extract(path,self.root/"bad","0"*64)
        self.assertFalse((self.root/"bad").exists())
        target=runtime.safe_extract(path,self.root/"stage",sha)
        self.assertEqual((target/"a.txt").read_text(),"ok")

    def test_path_traversal_links_devices_duplicates_and_limit(self):
        cases=[
            [("release/../../outside","file","bad")],
            [("/absolute","file","bad")],
            [("release/link",tarfile.SYMTYPE,"../../outside")],
            [("release/link",tarfile.LNKTYPE,"release/target")],
            [("release/device",tarfile.CHRTYPE,"")],
            [("release/a","file","one"),("release/a","file","two")]]
        for i,entries in enumerate(cases):
            path,sha=self.archive(entries)
            with self.assertRaises(validation.ValidationError):
                runtime.safe_extract(path,self.root/("case"+str(i)),sha)
        path,sha=self.archive([("release/big","file","12345")])
        with self.assertRaises(validation.ValidationError):
            runtime.safe_extract(path,self.root/"limit",sha,maximum_bytes=4)
        self.assertFalse((self.root.parent/"outside").exists())


class PayloadSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_support.SignedReleaseTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        test_support.SignedReleaseTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); (self.root/"manifests").mkdir()
        real_which=validation.shutil.which
        finder=patch.object(validation.shutil,"which",side_effect=lambda name: test_support.GPG if name=="gpg" else real_which(name))
        finder.start(); self.addCleanup(finder.stop)
        self.key=self.root.parent/(self.root.name+"-key.asc")
        self.key.write_bytes(self.public); self.addCleanup(self.key.unlink)
        (self.root/"payload.txt").write_text("payload")

    def sign(self, *, scope="student_payload", expires=None, extra_line=""):
        now=datetime.now(timezone.utc)
        manifest={"schema_version":1,"release_id":"web-2026-10-r1","primary_fingerprint":self.fingerprint,
                  "created_at":(now-timedelta(minutes=1)).isoformat(),"expires_at":(expires or now+timedelta(hours=1)).isoformat(),
                  "scope":scope,"files":[{"path":"payload.txt","sha256":hashlib.sha256(b"payload").hexdigest(),"size_bytes":7}]}
        path=self.root/"manifests/release.json"; path.write_text(json.dumps(manifest))
        sums=(hashlib.sha256(b"payload").hexdigest()+"  payload.txt\n"+
              hashlib.sha256(path.read_bytes()).hexdigest()+"  manifests/release.json\n"+extra_line).encode()
        (self.root/"manifests/SHA256SUMS").write_bytes(sums)
        signature=test_support.gpg(self.home,"--armor","--digest-algo","SHA256","--detach-sign",data=sums)
        (self.root/"manifests/SHA256SUMS.asc").write_bytes(signature)

    def verify(self, candidate=False):
        return runtime.verify_tree(self.root,self.key,self.fingerprint,"web-2026-10-r1",allow_package_candidate=candidate)

    def test_signed_valid_tree(self):
        self.sign(); self.assertEqual(self.verify()["scope"],"student_payload")

    def test_modified_missing_and_unlisted_files(self):
        self.sign(); (self.root/"payload.txt").write_text("changed")
        with self.assertRaises(validation.ValidationError): self.verify()
        (self.root/"payload.txt").write_text("payload"); (self.root/"extra").write_text("unlisted")
        with self.assertRaises(validation.ValidationError): self.verify()
        (self.root/"extra").unlink(); (self.root/"payload.txt").unlink()
        with self.assertRaises(validation.ValidationError): self.verify()

    def test_candidate_requires_explicit_scope(self):
        self.sign(scope="package_only_candidate")
        with self.assertRaises(validation.ValidationError): self.verify()
        self.assertEqual(self.verify(candidate=True)["scope"],"package_only_candidate")

    def test_bad_signature_wrong_key_and_expiry(self):
        self.sign()
        with self.assertRaises(validation.ValidationError):
            runtime.verify_tree(self.root,self.key,"A"*40,"web-2026-10-r1")
        (self.root/"manifests/SHA256SUMS").write_bytes(b"altered")
        with self.assertRaises(validation.ValidationError): self.verify()
        self.sign(expires=datetime.now(timezone.utc)-timedelta(seconds=1))
        with self.assertRaises(validation.ValidationError): self.verify()

    def test_signed_traversal_is_rejected(self):
        self.sign(extra_line="a"*64+"  ../outside\n")
        with self.assertRaises(validation.ValidationError): self.verify()


if __name__=="__main__":
    unittest.main()
