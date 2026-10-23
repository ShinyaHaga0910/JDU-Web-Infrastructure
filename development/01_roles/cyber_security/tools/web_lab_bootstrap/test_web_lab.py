"""Local fixtures and mocked AWS only; never creates cloud resources or production keys."""

import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout

import release_validation as validation
import web_lab


HERE = Path(__file__).parent
GPG = shutil.which("gpg") or shutil.which("C:/Program Files/Git/usr/bin/gpg.exe")


def gpg(home, *args, data=None):
    result = subprocess.run([GPG, "--no-options", "--batch", "--no-tty", "--homedir", validation.gpg_path(GPG, home),
                             *args], input=data, capture_output=True, timeout=45)
    if result.returncode:
        raise AssertionError("Disposable test-key GPG command failed: " + result.stderr.decode(errors="replace"))
    return result.stdout


def wire_key(octet=1):
    def field(value):
        return struct.pack(">I", len(value)) + value
    wire = field(b"ssh-ed25519") + field(bytes([octet]) * 32)
    return b"ssh-ed25519 " + base64.b64encode(wire) + b" disposable-test-fixture\n"


class SignedReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing GPG must fail the suite, not silently skip all cryptographic coverage.
        if not GPG:
            raise AssertionError("GPG is required to run the signature tests")
        cls.key_temp = tempfile.TemporaryDirectory(prefix="jdu-web-test-key-")
        cls.home = Path(cls.key_temp.name)
        cls.home.chmod(0o700)
        gpg(cls.home, "--pinentry-mode", "loopback", "--passphrase", "",
            "--quick-generate-key", "Disposable Web Lab Test <test@invalid.example>", "rsa3072", "sign", "2d")
        listing = gpg(cls.home, "--with-colons", "--list-keys").decode()
        cls.fingerprint = next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:"))
        cls.public = gpg(cls.home, "--armor", "--export", cls.fingerprint)

    @classmethod
    def tearDownClass(cls):
        # The agent process may hold test files open on Windows.
        conf = Path(GPG).with_name("gpgconf.exe" if os.name == "nt" else "gpgconf")
        if conf.exists():
            subprocess.run([str(conf), "--homedir", validation.gpg_path(str(conf), cls.home), "--kill", "gpg-agent"],
                           capture_output=True, timeout=15)
        cls.key_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jdu-web-test-release-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        sources = {"wrapper": HERE / "web_lab.py", "validation": HERE / "release_validation.py",
                   "schema": HERE / "deployment-manifest.schema.json",
                   "selector": HERE.parent / "web_lab_instance_selector" / "select_instances.py"}
        files = {role: source.name for role, source in sources.items()}
        for role, source in sources.items():
            shutil.copyfile(source, self.root / files[role])
        files.update(repo_bundle="test-payload.tar.gz", template="test-template.json", public_key="test-release-key.asc")
        (self.root / files["repo_bundle"]).write_bytes(b"TEST DATA ONLY - not a package archive")
        (self.root / files["template"]).write_text(json.dumps({"Resources": {"Fixture": {
            "Type": "AWS::CloudFormation::WaitConditionHandle"}}}), encoding="utf-8")
        (self.root / files["public_key"]).write_bytes(self.public)
        artifacts = {role: {"path": name, "sha256": validation.file_digest(self.root / name)[0],
                            "size_bytes": (self.root / name).stat().st_size} for role, name in files.items()}
        now = datetime.now(timezone.utc)
        self.manifest = {"schema_version": 1, "release_id": "web-2026-10-r1",
            "created_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(hours=6)).isoformat(), "region": "us-east-1",
            "ami": {"id": "ami-0123456789abcdef0", "owner_id": "099720109477",
                    "image_name": "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20261001",
                    "architecture": "x86_64", "ubuntu": "24.04", "root_device_name": "/dev/sda1", "root_min_gib": 8},
            "network": {"vpc_cidr": "10.20.0.0/16", "public_subnet_cidr": "10.20.1.0/24",
                        "private_subnet_cidr": "10.20.2.0/24", "s3_prefix_list_id": "pl-01234567",
                        "rdp_ipv4_cidrs": [f"45.1.1.{index}/32" for index in range(1, 51)]},
            "grading": {"ipv4": "8.8.8.8", "fqdn": "grader.fixture-university.uz", "submit_path": "/api/web/submit"},
            "bootstrap": {"bucket": "jdu-disposable-fixture", "release_prefix": "releases/web-2026-10-r1/"},
            "signing": {"primary_fingerprint": self.fingerprint}, "artifacts": artifacts}
        self.path, self.signature = self.root / "deployment-manifest.json", self.root / "deployment-manifest.sig"
        self.key = self.root / files["public_key"]
        self.ssh_key = self.root / "student-test.pub"
        self.ssh_key.write_bytes(wire_key())
        self.output = self.root / "new.plan.json"
        self.sign()

    def sign(self, raw=None, digest="SHA256", signer=None):
        self.path.write_bytes(raw if raw is not None else json.dumps(self.manifest).encode())
        gpg(self.home, "--yes", "--pinentry-mode", "loopback", "--passphrase", "",
            "--local-user", (signer or self.fingerprint) + "!", "--digest-algo", digest,
            "--output", validation.gpg_path(GPG, self.signature), "--detach-sign", validation.gpg_path(GPG, self.path))

    def verify(self, **overrides):
        arguments = {"manifest_path": self.path, "signature_path": self.signature, "key_path": self.key,
                     "trusted_fingerprint": self.fingerprint, "artifact_root": self.root, "gpg": GPG}
        arguments.update(overrides)
        return validation.verify_release(**arguments)

    def test_valid_real_signature_and_all_seven_hashes(self):
        result = self.verify()
        self.assertEqual(result["manifest"]["release_id"], "web-2026-10-r1")
        self.assertEqual(len(result["files"]), 7)
        self.assertEqual(result["manifest_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_modified_manifest_is_rejected_before_json_parse(self):
        self.path.write_bytes(self.path.read_bytes() + b" ")
        with patch.object(validation, "json_bytes", side_effect=AssertionError("Unverified JSON must not be parsed")):
            with self.assertRaisesRegex(validation.ValidationError, "signature"):
                self.verify()

    def test_wrong_trust_pin_and_missing_verifier_fail_closed(self):
        for overrides in ({"trusted_fingerprint": "A" * 40}, {"gpg": "jdu-nonexistent-gpg"}):
            with self.subTest(overrides=overrides), self.assertRaises(validation.ValidationError):
                self.verify(**overrides)

    def test_payload_tampering_is_rejected(self):
        (self.root / self.manifest["artifacts"]["repo_bundle"]["path"]).write_bytes(b"MODIFIED")
        with self.assertRaisesRegex(validation.ValidationError, "hash or size"):
            self.verify()

    def test_cloudshell_can_verify_small_tools_without_local_bundle_but_records_deferral(self):
        (self.root / self.manifest["artifacts"]["repo_bundle"]["path"]).unlink()
        result = self.verify(include_bundle=False)
        self.assertFalse(result["bundle_verified_locally"])
        with self.assertRaises(validation.ValidationError):
            self.verify()

    def test_wrong_declared_size_is_rejected(self):
        self.manifest["artifacts"]["repo_bundle"]["size_bytes"] += 1
        self.sign()
        with self.assertRaisesRegex(validation.ValidationError, "hash or size"):
            self.verify()

    def test_signed_but_expired_future_or_outliving_manifest_is_rejected(self):
        original = copy.deepcopy(self.manifest)
        now = datetime.now(timezone.utc)
        for changes in ({"expires_at": (now - timedelta(seconds=1)).isoformat()},
                        {"created_at": (now + timedelta(hours=1)).isoformat()},
                        {"expires_at": (now + timedelta(days=3)).isoformat()}):
            with self.subTest(changes=changes):
                self.manifest = dict(original, **changes)
                self.sign()
                with self.assertRaisesRegex(validation.ValidationError, "future dated, expired or outlives"):
                    self.verify()

    def test_signing_subkey_is_bound_to_primary_and_limits_manifest_expiry(self):
        gpg(self.home, "--pinentry-mode", "loopback", "--passphrase", "", "--quick-add-key",
            self.fingerprint, "rsa3072", "sign", "1d")
        listing = gpg(self.home, "--with-colons", "--with-subkey-fingerprint", "--list-keys").decode()
        signer = [line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:")][-1]
        self.key.write_bytes(gpg(self.home, "--armor", "--export", self.fingerprint))
        artifact = self.manifest["artifacts"]["public_key"]
        artifact["sha256"], artifact["size_bytes"] = validation.file_digest(self.key)
        self.manifest["expires_at"] = (datetime.now(timezone.utc) + timedelta(hours=36)).isoformat()
        self.sign(signer=signer)
        with self.assertRaisesRegex(validation.ValidationError, "outlives its signing key"):
            self.verify()
        self.manifest["expires_at"] = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        self.sign(signer=signer)
        self.assertEqual(self.verify()["trusted_fingerprint"], self.fingerprint)

    def test_unknown_fields_missing_fields_bool_and_duplicate_json_keys_rejected(self):
        original = copy.deepcopy(self.manifest)
        variants = [dict(original, token="DISPOSABLE-SECRET-MUST-NOT-BE-LOGGED"), dict(original, schema_version=True)]
        missing = copy.deepcopy(original)
        del missing["ami"]
        variants.append(missing)
        for value in variants:
            with self.subTest(variant=list(value)):
                self.manifest = value
                self.sign()
                with self.assertRaises(validation.ValidationError):
                    self.verify()
        self.sign(raw=self.path.read_bytes()[:-1] + b', "schema_version": 1}')
        with self.assertRaisesRegex(validation.ValidationError, "Duplicate JSON"):
            self.verify()

    def test_signed_placeholders_overbroad_and_overlapping_networks_rejected(self):
        original = copy.deepcopy(self.manifest)
        cases = [("grading", "ipv4", "203.0.113.1"), ("grading", "ipv4", "10.1.1.1"),
                 ("grading", "fqdn", "grader.example.com"), ("grading", "fqdn", "grader.lab.test"),
                 ("ami", "id", "ami-00000000000000000"),
                 ("network", "rdp_ipv4_cidrs", ["0.0.0.0/0"] + original["network"]["rdp_ipv4_cidrs"][1:]),
                 ("network", "rdp_ipv4_cidrs", ["45.1.1.0/24"] + original["network"]["rdp_ipv4_cidrs"][1:])]
        for section, key, value in cases:
            with self.subTest(section=section, key=key, value=value):
                self.manifest = copy.deepcopy(original)
                self.manifest[section][key] = value
                self.sign()
                with self.assertRaises(validation.ValidationError):
                    self.verify()

    def test_missing_traversing_and_duplicate_artifact_paths_rejected(self):
        original = copy.deepcopy(self.manifest)
        for name in ("../outside.tar.gz", "missing.tar.gz", original["artifacts"]["template"]["path"]):
            with self.subTest(name=name):
                self.manifest = copy.deepcopy(original)
                self.manifest["artifacts"]["repo_bundle"]["path"] = name
                self.sign()
                with self.assertRaises(validation.ValidationError):
                    self.verify()

    def test_running_validator_must_match_signed_tool(self):
        target = self.root / "release_validation.py"
        target.write_bytes(target.read_bytes() + b"\n# signed different implementation\n")
        self.manifest["artifacts"]["validation"]["sha256"], self.manifest["artifacts"]["validation"]["size_bytes"] = validation.file_digest(target)
        self.sign()
        with self.assertRaisesRegex(validation.ValidationError, "Running validation tool"):
            self.verify()

    def test_sha1_signature_is_rejected(self):
        self.sign(digest="SHA1")
        with self.assertRaises(validation.ValidationError):
            self.verify()

    def test_expired_primary_key_is_rejected_even_with_historically_valid_signature(self):
        with tempfile.TemporaryDirectory(prefix="jdu-web-test-expired-key-") as directory:
            home = Path(directory)
            home.chmod(0o700)
            old = str(int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp()))
            try:
                gpg(home, "--faked-system-time", old, "--pinentry-mode", "loopback", "--passphrase", "",
                    "--quick-generate-key", "Disposable Expired Test <old@invalid.example>", "rsa3072", "sign", "1d")
                listing = gpg(home, "--with-colons", "--list-keys").decode()
                fingerprint = next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:"))
                public = gpg(home, "--armor", "--export", fingerprint)
                signature = gpg(home, "--faked-system-time", str(int(old) + 60),
                    "--pinentry-mode", "loopback", "--passphrase", "", "--local-user", fingerprint,
                    "--digest-algo", "SHA256", "--detach-sign", data=b"historically signed test bytes")
                with self.assertRaisesRegex(validation.ValidationError, "Primary signing key is expired"):
                    validation.verify_signature(b"historically signed test bytes", signature, public, fingerprint, GPG)
            finally:
                conf = Path(GPG).with_name("gpgconf.exe" if os.name == "nt" else "gpgconf")
                if conf.exists():
                    subprocess.run([str(conf), "--homedir", validation.gpg_path(str(conf), home), "--kill", "gpg-agent"],
                                   capture_output=True, timeout=15)

    def aws_fixture(self, service, operation, region, *arguments):
        self.assertIn((service, operation), web_lab.READ_OPERATIONS)
        self.assertEqual(region, "us-east-1")
        self.calls.append((service, operation))
        if operation == "get-caller-identity":
            return {"Account": "123456789012"}
        if operation == "describe-stacks":
            raise web_lab.StackMissing("Fixture stack absent")
        if operation == "describe-images":
            ami = self.manifest["ami"]
            return {"Images": [{"ImageId": ami["id"], "OwnerId": ami["owner_id"], "Name": ami["image_name"],
                "Architecture": "x86_64", "State": "available", "VirtualizationType": "hvm", "Public": True,
                "RootDeviceType": "ebs", "RootDeviceName": "/dev/sda1", "BlockDeviceMappings": [
                    {"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 8}}]}]}
        if operation == "describe-key-pairs":
            return {"KeyPairs": [{"KeyName": "student-key", "PublicKey": wire_key().decode()}]}
        if operation == "describe-managed-prefix-lists":
            return {"PrefixLists": [{"PrefixListId": "pl-01234567", "OwnerId": "AWS", "AddressFamily": "IPv4",
                                     "PrefixListName": "com.amazonaws.us-east-1.s3"}]}
        if operation == "validate-template":
            return {"Parameters": []}
        if operation == "describe-availability-zones":
            return {"AvailabilityZones": [{"ZoneName": "us-east-1b", "ZoneId": "use1-az2", "State": "available"}]}
        if operation == "describe-instance-types":
            return {"InstanceTypes": [{"InstanceType": family + "." + size, "MemoryInfo": {"SizeInMiB": memory},
                "VCpuInfo": {"DefaultVCpus": cpus}, "ProcessorInfo": {"SupportedArchitectures": ["x86_64"]},
                "SupportedVirtualizationTypes": ["hvm"], "SupportedRootDeviceTypes": ["ebs"]}
                for family in ("t3", "t3a") for size, memory, cpus in (("micro", 1024, 1), ("small", 2048, 1), ("medium", 4096, 2))]}
        if operation == "describe-instance-type-offerings":
            return {"InstanceTypeOfferings": [{"InstanceType": family + "." + size, "Location": "us-east-1b"}
                for family in ("t3", "t3a") for size in ("micro", "small", "medium")]}
        if operation == "get-products":
            attributes = {item["Field"]: item["Value"] for item in json.loads(arguments[arguments.index("--filters") + 1])}
            family, size = attributes["instanceType"].split(".")
            rate = {"micro": ".01", "small": ".02", "medium": ".04"}[size] if family == "t3a" else ".08"
            return {"PriceList": [{"product": {"productFamily": "Compute Instance", "attributes": attributes},
                "terms": {"OnDemand": {"fixture": {"effectiveDate": "2020-01-01T00:00:00Z", "priceDimensions": {
                    "rate": {"unit": "Hrs", "beginRange": "0", "endRange": "Inf", "pricePerUnit": {"USD": rate}}}}}}}]}
        raise AssertionError("Unmocked operation")

    def plan(self, **kwargs):
        return web_lab.make_plan(self.verify(), "student-001", "student-key", self.ssh_key, self.output, **kwargs)

    def test_plan_integrates_live_discovery_shape_and_cheapest_selector_without_mutations(self):
        self.calls = []
        with patch.object(web_lab, "aws_json", side_effect=self.aws_fixture):
            plan = self.plan()
        self.assertEqual(plan["stage"], "PLAN_READY")
        self.assertFalse(plan["resources_created"])
        self.assertEqual(plan["selection"]["family"], "t3a")
        self.assertEqual(plan["selection"]["compute_hourly_usd"], "0.11")
        self.assertEqual(json.loads(self.output.read_text()), plan)
        self.assertTrue(set(self.calls) <= web_lab.READ_OPERATIONS)
        if os.name != "nt":
            self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_existing_stack_or_aws_access_failure_never_becomes_new_plan(self):
        self.calls = []
        for failure in (False, True):
            def aws(service, operation, region, *arguments):
                if operation == "describe-stacks":
                    if failure:
                        raise web_lab.AwsReadError("Access denied")
                    return {"Stacks": [{"StackStatus": "ROLLBACK_COMPLETE"}]}
                return self.aws_fixture(service, operation, region, *arguments)
            with self.subTest(access_failure=failure), patch.object(web_lab, "aws_json", side_effect=aws):
                with self.assertRaises((validation.ValidationError, web_lab.AwsReadError)):
                    self.plan()
            self.assertFalse(self.output.exists())

    def test_ami_key_and_region_mismatch_prevent_selection_and_plan(self):
        self.calls = []
        for operation in ("describe-images", "describe-key-pairs", "describe-managed-prefix-lists"):
            def aws(service, name, region, *arguments):
                result = self.aws_fixture(service, name, region, *arguments)
                if name == operation:
                    if name == "describe-images":
                        result["Images"][0]["OwnerId"] = "123456789012"
                    elif name == "describe-key-pairs":
                        result["KeyPairs"][0]["PublicKey"] = wire_key(2).decode()
                    else:
                        result["PrefixLists"][0]["PrefixListName"] = "com.amazonaws.eu-west-1.s3"
                return result
            with self.subTest(operation=operation), patch.object(web_lab, "aws_json", side_effect=aws):
                with self.assertRaises(validation.ValidationError):
                    self.plan()
            self.assertFalse(self.output.exists())

    def test_output_reuse_and_private_ssh_key_stop_before_aws(self):
        verified = self.verify()
        self.output.write_text("preserve me")
        with patch.object(web_lab, "aws_json", side_effect=AssertionError("No AWS on bad local inputs")):
            with self.assertRaises(validation.ValidationError):
                web_lab.make_plan(verified, "student-001", "student-key", self.ssh_key, self.output)
            self.assertEqual(self.output.read_text(), "preserve me")
            self.ssh_key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nDISPOSABLE-NOT-A-REAL-KEY")
            with self.assertRaises(validation.ValidationError):
                web_lab.make_plan(verified, "student-001", "student-key", self.ssh_key, self.root / "second.plan.json")

    def test_price_api_failure_does_not_create_plan_or_guess_prices(self):
        self.calls = []
        def aws(service, operation, region, *arguments):
            if operation == "get-products":
                raise web_lab.AwsReadError("Fixture pricing denied")
            return self.aws_fixture(service, operation, region, *arguments)
        with patch.object(web_lab, "aws_json", side_effect=aws), self.assertRaises(web_lab.AwsReadError):
            self.plan()
        self.assertFalse(self.output.exists())

    def test_plan_cli_uses_small_archive_and_reports_plan_without_printing_account(self):
        (self.root / self.manifest["artifacts"]["repo_bundle"]["path"]).unlink()
        args = ["plan", "--deployment-manifest", str(self.path), "--signature", str(self.signature),
                "--public-key", str(self.key), "--trusted-fingerprint", self.fingerprint,
                "--artifact-root", str(self.root), "--gpg", GPG, "--lab-id", "student-001",
                "--key-name", "student-key", "--public-key-file", str(self.ssh_key), "--output", str(self.output)]
        output, self.calls = io.StringIO(), []
        with redirect_stdout(output), patch.object(web_lab, "aws_json", side_effect=self.aws_fixture):
            self.assertEqual(web_lab.main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["stage"], "PLAN_READY")
        self.assertNotIn("123456789012", output.getvalue())
        self.assertFalse(json.loads(self.output.read_text())["bundle_verified_locally"])

    def test_cli_validation_failure_does_not_query_aws_or_print_input_secret(self):
        self.manifest["secret"] = "DISPOSABLE-SECRET-MUST-NOT-BE-LOGGED"
        self.sign()
        args = ["verify", "--deployment-manifest", str(self.path), "--signature", str(self.signature),
                "--public-key", str(self.key), "--trusted-fingerprint", self.fingerprint,
                "--artifact-root", str(self.root), "--gpg", GPG]
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output), patch.object(web_lab, "aws_json", side_effect=AssertionError()):
            self.assertEqual(web_lab.main(args), 2)
        self.assertNotIn(self.manifest["secret"], output.getvalue())


class ReadOnlyBoundaryTests(unittest.TestCase):
    def test_write_operation_is_rejected_before_cli(self):
        with patch.object(web_lab.subprocess, "run", side_effect=AssertionError("No CLI")):
            with self.assertRaises(validation.ValidationError):
                web_lab.aws_json("ec2", "run-instances", "us-east-1")

    def test_absence_is_only_exact_validation_error_not_accessdenied(self):
        missing = "An error occurred (ValidationError) when calling the DescribeStacks operation: Stack with id jdu-web-test does not exist\n"
        for stderr, exception in ((missing, web_lab.StackMissing),
                ("An error occurred (AccessDenied) when calling the DescribeStacks operation", web_lab.AwsReadError),
                ("Stack with id jdu-web-test does not exist plus unexpected error", web_lab.AwsReadError)):
            response = subprocess.CompletedProcess([], 1, "", stderr)
            with self.subTest(stderr=stderr), patch.object(web_lab.subprocess, "run", return_value=response):
                with self.assertRaises(exception) as caught:
                    web_lab.aws_json("cloudformation", "describe-stacks", "us-east-1", "--stack-name", "jdu-web-test")
                if exception is web_lab.AwsReadError:
                    self.assertNotIsInstance(caught.exception, web_lab.StackMissing)

    def test_traversal_and_symlink_artifact_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("../escape", "a/../b", "a//b", "/etc/passwd", "C:/secret", "a\\b"):
                with self.subTest(name=name), self.assertRaises(validation.ValidationError):
                    validation.relative_file(root, name)
            target, link = root / "file", root / "link"
            target.write_text("fixture")
            try:
                link.symlink_to(target)
            except OSError:
                # Windows without Developer Mode: inject only the OS link observation.
                with patch.object(Path, "is_symlink", return_value=True):
                    with self.assertRaises(validation.ValidationError):
                        validation.relative_file(root, "link")
            else:
                with self.assertRaises(validation.ValidationError):
                    validation.relative_file(root, "link")


if __name__ == "__main__":
    unittest.main()
