from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web_lab_bootstrap"))
from class_student_delivery import (BUCKET, CLASS_ID, OBJECT, PAYLOAD_SHA, PAYLOAD_SIZE,
    STUDENT, TEACHER, digest, identity, validate_envelope, validate_manifest, validate_request)
import class_student_delivery as delivery


class ClassStudentDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
        self.cert = "PUBLIC CERTIFICATE FIXTURE"
        self.cert_sha = digest(self.cert.encode())
        self.request = dict(scope="one_student_private_delivery_request", class_id=CLASS_ID,
            teacher_account=TEACHER, student_account=STUDENT, lab_id="class193548-test1",
            release_id="web-2026-10-r1", created_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(days=1)).isoformat(), certificate_pem=self.cert,
            certificate_sha256=self.cert_sha)
        self.manifest = dict(release_id="web-2026-10-r1", region="us-east-1",
            bootstrap=dict(bucket=BUCKET, release_prefix=OBJECT.rsplit("/", 1)[0] + "/"),
            grading=dict(ipv4="50.16.41.7", fqdn="7ilp8ph6ki.execute-api.us-east-1.amazonaws.com",
                         submit_path="/api/web/submit"),
            artifacts=dict(repo_bundle=dict(path="repo-bundle.tar.gz", sha256=PAYLOAD_SHA, size_bytes=PAYLOAD_SIZE)))
        self.envelope = dict(scope="one_student_credentials_and_payload_url",
            request_sha256=digest(json.dumps(self.request, sort_keys=True).encode()), manifest_sha256="a" * 64,
            class_id=CLASS_ID, student_account=STUDENT, teacher_account=TEACHER,
            created_at=self.now.isoformat(), expires_at=(self.now + timedelta(hours=1)).isoformat(),
            credentials=dict(schema_version=1, api_base_url="https://7ilp8ph6ki.execute-api.us-east-1.amazonaws.com",
                fixed_ingress_ipv4="50.16.41.7", release_id="web-2026-10-r1",
                lab_id=self.request["lab_id"], lab_token="fixture_not_real_" * 3),
            bootstrap_url="https://" + BUCKET + ".s3.us-east-1.amazonaws.com/" + OBJECT + "?signed=fixture")

    def test_public_request_and_manifest_accept_exact_scope(self):
        self.assertEqual(validate_request(self.request, self.cert_sha, self.now), self.request)
        validate_manifest(self.manifest)

    def test_request_rejects_other_student_class_recipient_and_extra_secret(self):
        for key, value in (("student_account", TEACHER), ("class_id", 188571),
                           ("certificate_pem", "different"), ("admin_key", "fixture")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_request(dict(self.request, **{key: value}), self.cert_sha, self.now)

    def test_request_expiry_is_bounded(self):
        for now in (self.now - timedelta(seconds=1), self.now + timedelta(days=1)):
            with self.subTest(now=now), self.assertRaises(ValueError):
                validate_request(self.request, self.cert_sha, now)

    def test_other_class_teacher_or_replaced_payload_rejected(self):
        for field, value in (("grading", dict(self.manifest["grading"], ipv4="44.216.176.215")),
                              ("bootstrap", dict(self.manifest["bootstrap"], bucket="old-test2")),
                              ("artifacts", dict(repo_bundle=dict(self.manifest["artifacts"]["repo_bundle"], sha256="b" * 64)))):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_manifest(dict(self.manifest, **{field: value}))

    def test_student_receives_only_own_token_and_signed_destination_url(self):
        result = validate_envelope(self.envelope, self.request, "a" * 64, self.now)
        self.assertEqual(result["lab_id"], self.request["lab_id"])

    def test_admin_extra_field_or_other_lab_is_rejected(self):
        for key, value in (("admin_key", "fixture"), ("lab_id", "other-student"),
                           ("api_base_url", "https://7eg7nm5oe2.execute-api.us-east-1.amazonaws.com")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_envelope(dict(self.envelope, credentials=dict(self.envelope["credentials"], **{key: value})),
                                  self.request, "a" * 64, self.now)

    def test_substituted_manifest_request_or_url_is_rejected(self):
        for key, value in (("manifest_sha256", "b" * 64), ("request_sha256", "c" * 64),
                           ("bootstrap_url", self.envelope["bootstrap_url"].replace("/c7/", "/c4/"))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_envelope(dict(self.envelope, **{key: value}), self.request, "a" * 64, self.now)

    def test_expired_envelope_and_other_aws_account_stop(self):
        with self.assertRaises(ValueError):
            validate_envelope(self.envelope, self.request, "a" * 64, self.now + timedelta(hours=1))
        session = SimpleNamespace(client=lambda name: SimpleNamespace(get_caller_identity=lambda: {"Account": TEACHER}))
        with self.assertRaises(ValueError): identity(session, STUDENT)

    def test_real_authenticated_crypto_receive_and_replay_retention(self):
        """Exercise the actual CMS path with a non-secret token fixture in Linux /tmp."""
        session = SimpleNamespace(client=lambda name: SimpleNamespace(get_caller_identity=lambda: {"Account": STUDENT}))
        from enroll_five_node_progress import encrypt
        with tempfile.TemporaryDirectory(prefix="jdu-delivery-crypto-test-") as temp:
            workspace = Path(temp) / "receiver"
            delivery.prepare_receiver(session, workspace, "class193548-test1")
            request = json.loads((workspace / "recipient-request.public.json").read_text())
            now = datetime.now(timezone.utc)
            value = dict(self.envelope, request_sha256=digest(json.dumps(request, sort_keys=True).encode()),
                         created_at=now.isoformat(), expires_at=(now + timedelta(minutes=5)).isoformat())
            cipher = Path(temp) / "fixture.encrypted.cms"
            cipher.write_bytes(encrypt(request["certificate_pem"].encode(), json.dumps(value).encode()))
            args = SimpleNamespace(confirmed_access=True, workspace=workspace,
                recipient_sha256=request["certificate_sha256"], ciphertext=cipher)
            delivery.receive(session, args, {"manifest_sha256": "a" * 64})
            own = workspace / "received/own-student.credentials.json"
            self.assertEqual(json.loads(own.read_text()), value["credentials"])
            self.assertEqual(own.stat().st_mode & 0o777, 0o600)
            original = own.read_bytes()
            with self.assertRaises(FileExistsError):
                delivery.receive(session, args, {"manifest_sha256": "a" * 64})
            self.assertEqual(own.read_bytes(), original)


if __name__ == "__main__": unittest.main()
