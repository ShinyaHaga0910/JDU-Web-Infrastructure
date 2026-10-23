from datetime import datetime, timedelta, timezone
import unittest
from types import SimpleNamespace

from transfer_class_payload import (CLASS_ID, SHA256, SIZE, SOURCE_ACCOUNT, SOURCE_BUCKET, SOURCE_KEY,
                                    TARGET_ACCOUNT, account, validate_envelope, validate_url)


class PayloadTransferTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
        self.url = "https://" + SOURCE_BUCKET + ".s3.us-east-1.amazonaws.com/" + SOURCE_KEY + "?signed=fixture"
        self.value = dict(scope="single_software_payload_url_transfer", source_account=SOURCE_ACCOUNT,
            target_account=TARGET_ACCOUNT, class_id=CLASS_ID, certificate_sha256="a" * 64,
            issued_at=self.now.isoformat(), expires_at=(self.now + timedelta(hours=1)).isoformat(),
            source_bucket=SOURCE_BUCKET, source_key=SOURCE_KEY, sha256=SHA256, size_bytes=SIZE, url=self.url)

    def test_exact_source_and_recipient(self):
        self.assertEqual(validate_envelope(self.value, "a" * 64, self.now), self.url)

    def test_other_recipient_or_modified_payload_rejected(self):
        for key, value in [("target_account", SOURCE_ACCOUNT), ("class_id", 188571),
                           ("certificate_sha256", "b" * 64), ("sha256", "c" * 64), ("size_bytes", 1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_envelope(dict(self.value, **{key: value}), "a" * 64, self.now)

    def test_expired_or_extended_envelope_rejected(self):
        for issued, expiry in [(self.now - timedelta(hours=2), self.now - timedelta(hours=1)),
                               (self.now, self.now + timedelta(hours=2))]:
            with self.subTest(expiry=expiry), self.assertRaises(ValueError):
                validate_envelope(dict(self.value, issued_at=issued.isoformat(), expires_at=expiry.isoformat()),
                                  "a" * 64, self.now)

    def test_other_urls_rejected(self):
        for url in [self.url.replace("https://", "http://"), self.url.replace(SOURCE_BUCKET, "other-bucket"),
                    self.url.replace("/c4/", "/c5/"), self.url + "#fragment",
                    self.url.replace("https://", "https://user@"), self.url.replace(".com/", ".com:443/")]:
            with self.subTest(url=url), self.assertRaises(ValueError): validate_url(url)

    def test_wrong_cloudshell_identity_stops(self):
        session = SimpleNamespace(client=lambda name: SimpleNamespace(
            get_caller_identity=lambda: {"Account": SOURCE_ACCOUNT}))
        with self.assertRaises(ValueError): account(session, TARGET_ACCOUNT)


if __name__ == "__main__": unittest.main()
