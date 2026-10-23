from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web_lab_bootstrap"))
import class_student_delivery as delivery
import refresh_class_delivery as refresh


class ReadOnlySession:
    """Only the exact read/presign surface is available, with no issuance API."""
    def __init__(self, credential):
        self.account = delivery.TEACHER
        self.row = dict(lab_id={"S": refresh.LAB_ID}, release_id={"S": "web-2026-10-r1"},
            active={"BOOL": True}, token_hash={"S": hashlib.sha256(credential["lab_token"].encode()).hexdigest()})
        self.head = dict(ContentLength=delivery.PAYLOAD_SIZE, Metadata={"sha256": delivery.PAYLOAD_SHA})
        self.calls = []

    def client(self, name, **kwargs):
        self.calls.append(name)
        return {
            "sts": SimpleNamespace(get_caller_identity=lambda: {"Account": self.account}),
            "cloudformation": SimpleNamespace(describe_stacks=lambda **kw: {"Stacks": [{
                "StackStatus": "CREATE_COMPLETE", "Outputs": [{"OutputKey": "TableName", "OutputValue": "teacher-progress"}]}]}),
            "dynamodb": SimpleNamespace(get_item=lambda **kw: {"Item": self.row}),
            "s3": SimpleNamespace(head_object=lambda **kw: self.head,
                generate_presigned_url=lambda *a, **kw: "https://" + delivery.BUCKET + ".s3.us-east-1.amazonaws.com/" + delivery.OBJECT + "?signed=fixture"),
        }[name]


class RefreshClassDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jdu-existing-delivery-test-")
        self.root = Path(self.temp.name)
        self.issued = self.root / "old-issued"; self.issued.mkdir(mode=0o700)
        self.credential = dict(schema_version=1, api_base_url="https://7ilp8ph6ki.execute-api.us-east-1.amazonaws.com",
            fixed_ingress_ipv4="50.16.41.7", release_id="web-2026-10-r1", lab_id=refresh.LAB_ID,
            lab_token="nonsecret_fixture_" + "F" * 32)
        delivery.save_json(self.issued / "own-student.credentials.json", self.credential)
        cipher = b"old encrypted transport fixture"
        delivery.save(self.issued / "student-delivery.encrypted.cms", cipher)
        pin = delivery.digest(cipher)
        self.pin = patch.object(refresh, "ORIGINAL_CIPHER_SHA", pin); self.pin.start()
        self.sdk = patch.dict(sys.modules, {"botocore.config": SimpleNamespace(
            Config=lambda **kwargs: SimpleNamespace(**kwargs))})
        self.sdk.start()
        delivery.save_json(self.issued / "issued.public.json", dict(scope="one_student_delivery_issued",
            class_id=delivery.CLASS_ID, teacher_account=delivery.TEACHER, student_account=delivery.STUDENT,
            lab_id=refresh.LAB_ID, teacher_admin_transferred=False, ciphertext_sha256=pin,
            expires_at="2026-10-20T11:45:15+00:00"))
        # An existing Lab token outlives its expired transport URL.
        self.session = ReadOnlySession(self.credential)
        student = SimpleNamespace(client=lambda name: SimpleNamespace(get_caller_identity=lambda: {"Account": delivery.STUDENT}))
        self.receiver = self.root / "fresh-receiver"
        delivery.prepare_receiver(student, self.receiver, refresh.LAB_ID)
        self.request = json.loads((self.receiver / "recipient-request.public.json").read_text())
        self.args = SimpleNamespace(request=self.receiver / "recipient-request.public.json",
            recipient_sha256=self.request["certificate_sha256"], issued_workspace=self.issued,
            output_workspace=self.root / "new-envelope")
        self.tools = dict(manifest_sha256=refresh.MANIFEST_SHA, manifest=dict(release_id="web-2026-10-r1", region="us-east-1",
            bootstrap=dict(bucket=delivery.BUCKET, release_prefix=delivery.OBJECT.rsplit("/", 1)[0] + "/"),
            grading=dict(ipv4="50.16.41.7", fqdn="7ilp8ph6ki.execute-api.us-east-1.amazonaws.com", submit_path="/api/web/submit"),
            artifacts=dict(repo_bundle=dict(path="repo-bundle.tar.gz", sha256=delivery.PAYLOAD_SHA, size_bytes=delivery.PAYLOAD_SIZE))))

    def tearDown(self):
        self.sdk.stop(); self.pin.stop(); self.temp.cleanup()

    def test_real_authenticated_repackaging_preserves_existing_token_and_source(self):
        before = (self.issued / "own-student.credentials.json").read_bytes()
        refresh.refresh(self.session, self.args, self.tools)
        ciphertext = (self.args.output_workspace / "student-delivery.encrypted.cms").read_bytes()
        clear = subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER", "-recip",
            str(self.receiver / "recipient.crt"), "-inkey", str(self.receiver / "recipient.key")],
            input=ciphertext, capture_output=True, check=True).stdout
        envelope = json.loads(clear)
        self.assertEqual(delivery.validate_envelope(envelope, self.request, refresh.MANIFEST_SHA,
            datetime.now(timezone.utc)), self.credential)
        self.assertEqual((self.issued / "own-student.credentials.json").read_bytes(), before)
        receipt = json.loads((self.args.output_workspace / "refresh.public.json").read_text())
        self.assertFalse(receipt["new_credential_issued"])
        self.assertTrue(receipt["existing_credential_preserved"])
        self.assertNotIn(self.credential["lab_token"], json.dumps(receipt))
        self.assertEqual((self.args.output_workspace / "student-delivery.encrypted.cms").stat().st_mode & 0o777, 0o600)
        self.assertIsNone(receipt["bound_deployment_id"])

    def test_wrong_aws_account_stops_before_output(self):
        self.session.account = delivery.STUDENT
        with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, self.tools)
        self.assertFalse(self.args.output_workspace.exists())

    def test_revoked_or_mismatched_server_credential_is_not_reissued(self):
        for key, value in (("active", {"BOOL": False}), ("token_hash", {"S": "0" * 64})):
            with self.subTest(key=key):
                original = self.session.row[key]; self.session.row[key] = value
                with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, self.tools)
                self.session.row[key] = original
        self.assertFalse(self.args.output_workspace.exists())

    def test_changed_original_ciphertext_is_refused(self):
        (self.issued / "student-delivery.encrypted.cms").write_bytes(b"different fixture")
        with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, self.tools)

    def test_expired_or_other_lab_request_is_refused(self):
        now = datetime.now(timezone.utc)
        for change in ({"lab_id": "another-student"}, {"expires_at": (now - timedelta(seconds=1)).isoformat()}):
            self.args.request.write_text(json.dumps(dict(self.request, **change)))
            with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, self.tools)
        self.assertFalse(self.args.output_workspace.exists())

    def test_wrong_manifest_or_changed_payload_stops(self):
        with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, dict(self.tools, manifest_sha256="0" * 64))
        self.session.head["ContentLength"] -= 1
        with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, self.tools)
        self.assertFalse(self.args.output_workspace.exists())

    def test_existing_refresh_output_is_preserved(self):
        self.args.output_workspace.mkdir(mode=0o700)
        marker = self.args.output_workspace / "keep"; marker.write_text("preserved")
        with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, self.tools)
        self.assertEqual(marker.read_text(), "preserved")

    def test_teacher_admin_extra_field_is_refused(self):
        (self.issued / "own-student.credentials.json").write_text(json.dumps(dict(self.credential, admin_key="fixture")))
        with self.assertRaises(ValueError): refresh.refresh(self.session, self.args, self.tools)
        self.assertFalse(self.args.output_workspace.exists())


if __name__ == "__main__": unittest.main()
