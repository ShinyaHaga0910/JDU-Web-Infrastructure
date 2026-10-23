"""Fetch Class193548's exact signed v7 software across separate Lab accounts.

Only public software GET URLs travel in the encrypted envelope. This command
does not issue or receive grading credentials, create servers, or change access.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import unquote, urlsplit
import urllib.request

from class_student_delivery import (BUCKET, CLASS_ID, FINGERPRINT, STUDENT, TEACHER,
    digest, identity, read, save, save_json, validate_request, verified_tools)

PREFIX = "student-tools/class193548-v7/"
ARCHIVE_SHA = "082ffed4773ea42d9c35368cedca0a8e5f8ea213979971f25e7e953707a35365"
ARCHIVE_SIZE = 82074
MANIFEST_SHA = "a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2"
NAMES = ("student-tools.tar.gz", "student-tools.tar.gz.asc", "package-signing-public.asc")


def validate_url(url, name):
    p = urlsplit(url)
    hosts = {"s3.amazonaws.com", "s3.us-east-1.amazonaws.com"}
    expected = "/" + PREFIX + name if p.hostname in {BUCKET + "." + h for h in hosts} else "/" + BUCKET + "/" + PREFIX + name
    if (not isinstance(url, str) or len(url) > 16384 or p.scheme != "https" or p.port
            or p.hostname not in hosts | {BUCKET + "." + h for h in hosts}
            or unquote(p.path) != expected or not p.query or p.username or p.password or p.fragment
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url)):
        raise ValueError("Only the exact signed software object may be fetched")


def envelope(value, request, now):
    if (set(value) != {"scope", "request_sha256", "created_at", "expires_at", "files"}
            or value["scope"] != "class193548_v7_public_software_urls"
            or value["request_sha256"] != digest(json.dumps(request, sort_keys=True).encode())
            or not isinstance(value["files"], list) or [f.get("name") for f in value["files"]] != list(NAMES)):
        raise ValueError("Software recipient or file inventory differs")
    created, expiry = (datetime.fromisoformat(value[k]) for k in ("created_at", "expires_at"))
    if (created.tzinfo is None or expiry.tzinfo is None or not created <= now < expiry
            or not timedelta(0) < expiry - created <= timedelta(hours=1)):
        raise ValueError("Software envelope expired or future dated")
    for item in value["files"]:
        if (set(item) != {"name", "sha256", "size_bytes", "url"}
                or not isinstance(item["sha256"], str) or len(item["sha256"]) != 64
                or not isinstance(item["size_bytes"], int) or not 0 < item["size_bytes"] <= 1024 * 1024):
            raise ValueError("Software object facts differ")
        validate_url(item["url"], item["name"])
    if (value["files"][0]["sha256"], value["files"][0]["size_bytes"]) != (ARCHIVE_SHA, ARCHIVE_SIZE):
        raise ValueError("Independently pinned software archive differs")
    return value


def export(session, args):
    identity(session, TEACHER)
    now = datetime.now(timezone.utc)
    request = validate_request(json.loads(read(args.request)), args.recipient_sha256, now)
    from botocore.config import Config
    s3 = session.client("s3", region_name="us-east-1", config=Config(signature_version="s3v4"))
    files = []
    for name in NAMES:
        result = s3.get_object(Bucket=BUCKET, Key=PREFIX + name, ExpectedBucketOwner=TEACHER)
        try:
            if not 0 < result["ContentLength"] <= 1024 * 1024:
                raise ValueError("Software object exceeds its limit")
            data = result["Body"].read(1024 * 1024 + 1)
        finally: result["Body"].close()
        if len(data) != result["ContentLength"] or digest(data) != result["Metadata"].get("sha256"):
            raise ValueError("Software object no longer matches its recorded bytes")
        files.append(dict(name=name, sha256=digest(data), size_bytes=len(data),
            url=s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": PREFIX + name}, ExpiresIn=3600)))
    value = dict(scope="class193548_v7_public_software_urls", request_sha256=digest(json.dumps(request, sort_keys=True).encode()),
        created_at=now.isoformat(), expires_at=(now + timedelta(hours=1)).isoformat(), files=files)
    envelope(value, request, now)
    with tempfile.TemporaryDirectory(prefix="jdu-public-student-recipient-") as temp:
        cert = Path(temp) / "recipient.public.crt"; cert.write_text(request["certificate_pem"])
        ciphertext = subprocess.run(["openssl", "cms", "-encrypt", "-binary", "-aes-256-gcm", "-outform", "DER",
            "-recip", str(cert), "-keyopt", "rsa_padding_mode:oaep", "-keyopt", "rsa_oaep_md:sha256",
            "-keyopt", "rsa_mgf1_md:sha256"], input=json.dumps(value).encode(), capture_output=True, check=True).stdout
    save(args.ciphertext, ciphertext)
    print("SIGNED_SOFTWARE_URLS_ENCRYPTED; public software only; no grading credential issued")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("Software redirects refused")


def extract(data, destination):
    import io
    destination.mkdir(mode=0o700, exist_ok=False)
    seen = set(); total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar:
            p = PurePosixPath(member.name)
            if (not member.isfile() or len(p.parts) != 2 or p.parts[0] != "student-tools"
                    or p.name in ("", ".", "..") or "\\" in member.name or ":" in member.name
                    or member.name in seen or len(seen) >= 30 or not 0 <= member.size <= 1024 * 1024):
                raise ValueError("Unsafe signed tools archive")
            seen.add(member.name); total += member.size
            if total > 4 * 1024 * 1024: raise ValueError("Signed tools expansion exceeds limit")
            save(destination / p.name, tar.extractfile(member).read())


def fetch(session, args):
    identity(session, STUDENT)
    if args.expected_archive_sha256 != ARCHIVE_SHA or args.expected_manifest_sha256 != MANIFEST_SHA:
        raise ValueError("Independent software and manifest pins are required")
    request = json.loads(read(args.workspace / "recipient-request.public.json", private=True))
    validate_request(request, args.recipient_sha256, datetime.now(timezone.utc))
    read(args.workspace / "recipient.key", private=True)
    cipher = read(args.ciphertext, limit=65536)
    description = subprocess.run(["openssl", "cms", "-cmsout", "-inform", "DER", "-print"],
        input=cipher, capture_output=True, check=True).stdout
    if any(part not in description for part in (b"id-smime-ct-authEnvelopedData", b"aes-256-gcm", b"rsaesOaep")):
        raise ValueError("Authenticated software transport required")
    clear = subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
        "-recip", str(args.workspace / "recipient.crt"), "-inkey", str(args.workspace / "recipient.key")],
        input=cipher, capture_output=True, check=True).stdout
    value = envelope(json.loads(clear), request, datetime.now(timezone.utc))
    args.output.mkdir(mode=0o700, exist_ok=False)
    opener = urllib.request.build_opener(NoRedirect())
    for item in value["files"]:
        with opener.open(item["url"], timeout=30) as response:
            data = response.read(item["size_bytes"] + 1)
            if response.status != 200 or len(data) != item["size_bytes"] or digest(data) != item["sha256"]:
                raise ValueError("Downloaded signed software differs")
        save(args.output / item["name"], data)
    from release_validation import verify_signature
    archive = read(args.output / NAMES[0]); key = read(args.output / NAMES[2])
    verify_signature(archive, read(args.output / NAMES[1]), key, FINGERPRINT)
    tools = args.output / "student-tools"; extract(archive, tools)
    verified = verified_tools(tools)
    if verified["manifest_sha256"] != MANIFEST_SHA:
        raise ValueError("Downloaded signed manifest differs from the independent pin")
    (tools / "jdu-web-lab").chmod(0o700)
    save_json(args.output / "software-fetch.public.json", dict(scope="separate_student_signed_software_s3_fetch",
        class_id=CLASS_ID, teacher_account=TEACHER, student_account=STUDENT, checked_at=datetime.now(timezone.utc).isoformat(),
        archive_sha256=ARCHIVE_SHA, manifest_sha256=MANIFEST_SHA, raw_signature_verified_before_extract=True,
        outer_signature_and_files_verified=True, s3_get_from_other_account=True, grading_credentials_received=False,
        resources_created=False, class_ready=False))
    print("SEPARATE_STUDENT_SIGNED_SOFTWARE_FETCH_PASSED; no grading credentials or resources created")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("export", "fetch"))
    for name in ("workspace", "request", "ciphertext", "output"):
        parser.add_argument("--" + name, type=Path)
    for name in ("recipient-sha256", "expected-archive-sha256", "expected-manifest-sha256"):
        parser.add_argument("--" + name)
    args = parser.parse_args(); os.umask(0o077)
    import boto3
    session = boto3.Session(region_name="us-east-1")
    (export if args.command == "export" else fetch)(session, args)


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print("CLASS_SIGNED_SOFTWARE_STOPPED=" + type(exc).__name__, flush=True)
        raise SystemExit(2)
