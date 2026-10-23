"""Move the exact accepted software payload through an encrypted short-lived URL.

AWS and administrator credentials never leave their own CloudShell. The receiver
key encrypts transport data only; it is not an authentication credential.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import urllib.request

SOURCE_ACCOUNT = "144753397193"
TARGET_ACCOUNT = "170126527713"
CLASS_ID = 193548
SOURCE_BUCKET = "jdu-web-capture-20261015-bf04d16eb603"
SOURCE_KEY = "teacher-candidates/web-2026-10-r1/c4/repo-bundle.tar.gz"
TARGET_BUCKET = "jdu-web-class193548-170126527713"
TARGET_KEY = "teacher-candidates/web-2026-10-r1/c7/repo-bundle.tar.gz"
SHA256 = "60fbd303712672e34848c02f2d7d697ce21318eb7af91bf67665c88688f4deeb"
SIZE = 741180532
FINGERPRINT = "65EC6784750CCFA703BA7179519284E45155EC2A"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(value)


def save_json(path, value):
    save_new(path, (json.dumps(value, indent=2) + "\n").encode())


def account(session, expected):
    if session.client("sts").get_caller_identity()["Account"] != expected:
        raise ValueError("Wrong CloudShell account")


def validate_url(url):
    value = urlsplit(url)
    virtual = {SOURCE_BUCKET + ".s3.amazonaws.com", SOURCE_BUCKET + ".s3.us-east-1.amazonaws.com"}
    path_style = {"s3.amazonaws.com", "s3.us-east-1.amazonaws.com"}
    if (value.scheme != "https" or value.port or value.username or value.password or value.fragment
            or not value.query or any(ord(c) <= 32 or ord(c) == 127 for c in url)):
        raise ValueError("Invalid software source URL")
    expected = "/" + SOURCE_KEY if value.hostname in virtual else "/" + SOURCE_BUCKET + "/" + SOURCE_KEY
    if value.hostname not in virtual | path_style or unquote(value.path) != expected:
        raise ValueError("Unexpected software source object")
    return url


def validate_envelope(value, certificate_sha256, now):
    required = {"scope", "source_account", "target_account", "class_id", "certificate_sha256",
                "issued_at", "expires_at", "source_bucket", "source_key", "sha256", "size_bytes", "url"}
    if (set(value) != required or value["scope"] != "single_software_payload_url_transfer"
            or value["source_account"] != SOURCE_ACCOUNT or value["target_account"] != TARGET_ACCOUNT
            or value["class_id"] != CLASS_ID or value["certificate_sha256"] != certificate_sha256
            or value["source_bucket"] != SOURCE_BUCKET or value["source_key"] != SOURCE_KEY
            or value["sha256"] != SHA256 or value["size_bytes"] != SIZE):
        raise ValueError("Payload transfer identity differs")
    issued, expiry = (datetime.fromisoformat(value[key]) for key in ("issued_at", "expires_at"))
    if (issued.tzinfo is None or expiry.tzinfo is None or not issued <= now < expiry
            or not timedelta(0) < expiry - issued <= timedelta(hours=1)):
        raise ValueError("Payload URL transfer expired or future dated")
    return validate_url(value["url"])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("Software source redirects are refused")


def receive_prepare(session, workspace):
    account(session, TARGET_ACCOUNT)
    workspace.mkdir(mode=0o700, parents=False, exist_ok=False)
    subprocess.run(["openssl", "req", "-new", "-x509", "-newkey", "rsa:3072", "-sha256", "-days", "1",
                    "-nodes", "-keyout", str(workspace / "recipient.key"), "-out", str(workspace / "recipient.crt"),
                    "-subj", "/CN=Class193548SoftwareTransport"], capture_output=True, check=True)
    print("PUBLIC_RECIPIENT_CERT=" + base64.b64encode((workspace / "recipient.crt").read_bytes()).decode())
    print("PUBLIC_RECIPIENT_CERT_SHA256=" + sha(workspace / "recipient.crt"))


def sender_export(session, workspace, certificate, certificate_sha256):
    account(session, SOURCE_ACCOUNT)
    if sha(certificate) != certificate_sha256:
        raise ValueError("Public recipient certificate differs")
    workspace.mkdir(mode=0o700, parents=False, exist_ok=False)
    from botocore.config import Config
    s3 = session.client("s3", region_name="us-east-1", config=Config(signature_version="s3v4"))
    head = s3.head_object(Bucket=SOURCE_BUCKET, Key=SOURCE_KEY, ExpectedBucketOwner=SOURCE_ACCOUNT)
    if head["ContentLength"] != SIZE or head["Metadata"].get("sha256") != SHA256:
        raise ValueError("Accepted source payload differs")
    now = datetime.now(timezone.utc)
    url = s3.generate_presigned_url("get_object", Params={"Bucket": SOURCE_BUCKET, "Key": SOURCE_KEY}, ExpiresIn=3600)
    validate_url(url)
    value = dict(scope="single_software_payload_url_transfer", source_account=SOURCE_ACCOUNT,
        target_account=TARGET_ACCOUNT, class_id=CLASS_ID, certificate_sha256=certificate_sha256,
        issued_at=now.isoformat(), expires_at=(now + timedelta(hours=1)).isoformat(),
        source_bucket=SOURCE_BUCKET, source_key=SOURCE_KEY, sha256=SHA256, size_bytes=SIZE, url=url)
    encrypted = subprocess.run(["openssl", "cms", "-encrypt", "-binary", "-aes-256-gcm", "-outform", "DER",
        "-recip", str(certificate), "-keyopt", "rsa_padding_mode:oaep", "-keyopt", "rsa_oaep_md:sha256",
        "-keyopt", "rsa_mgf1_md:sha256"], input=json.dumps(value).encode(), capture_output=True, check=True).stdout
    save_new(workspace / "payload-url.cms", encrypted)
    print("ENCRYPTED_SOFTWARE_URL=" + base64.b64encode(encrypted).decode())
    print("ENCRYPTED_SOFTWARE_URL_SHA256=" + hashlib.sha256(encrypted).hexdigest())


def receive_copy(session, workspace, ciphertext):
    account(session, TARGET_ACCOUNT)
    if (workspace / "payload-copy.public.json").exists():
        raise ValueError("Completed payload copy retained")
    description = subprocess.run(["openssl", "cms", "-cmsout", "-inform", "DER", "-print"],
        input=ciphertext, capture_output=True, check=True).stdout
    if any(value not in description for value in (b"id-smime-ct-authEnvelopedData", b"aes-256-gcm", b"rsaesOaep")):
        raise ValueError("Authenticated software transport required")
    clear = subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
        "-recip", str(workspace / "recipient.crt"), "-inkey", str(workspace / "recipient.key")],
        input=ciphertext, capture_output=True, check=True).stdout
    url = validate_envelope(json.loads(clear), sha(workspace / "recipient.crt"), datetime.now(timezone.utc))
    del clear
    s3 = session.client("s3", region_name="us-east-1")
    block = s3.get_public_access_block(Bucket=TARGET_BUCKET, ExpectedBucketOwner=TARGET_ACCOUNT)["PublicAccessBlockConfiguration"]
    if len(block) != 4 or not all(block.values()):
        raise ValueError("Private destination public access controls differ")
    try:
        s3.head_object(Bucket=TARGET_BUCKET, Key=TARGET_KEY, ExpectedBucketOwner=TARGET_ACCOUNT)
    except s3.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchKey"):
            raise
    else:
        raise ValueError("Immutable destination object already exists")
    download = Path("/tmp/jdu-class193548-payload-v1")
    download.mkdir(mode=0o700, exist_ok=False)
    if shutil.disk_usage(download).free < 3 * SIZE:
        raise ValueError("Insufficient temporary space; no payload download attempted")
    archive = download / "repo-bundle.tar.gz"
    opener = urllib.request.build_opener(NoRedirect())
    print("PAYLOAD_SOURCE_DOWNLOAD_STARTED", flush=True)
    with opener.open(url, timeout=60) as response, archive.open("xb") as stream:
        if response.status != 200 or int(response.headers.get("Content-Length", "0")) != SIZE:
            raise ValueError("Source object size differs")
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > SIZE:
                raise ValueError("Source object exceeds accepted size")
            stream.write(chunk)
    del url
    if total != SIZE or sha(archive) != SHA256:
        raise ValueError("Source object hash differs; partial data retained")
    sys.dont_write_bytecode = True
    from payload_runtime import safe_extract, verify_tree
    release = safe_extract(archive, download / "payload", SHA256)
    manifest = verify_tree(release, Path(__file__).with_name("archive-key.asc"), FINGERPRINT, "web-2026-10-r1")
    print("PAYLOAD_COMPLETE_SIGNED_TREE_VERIFIED", len(manifest["files"]), flush=True)
    s3.upload_file(str(archive), TARGET_BUCKET, TARGET_KEY, ExtraArgs={
        "Metadata": {"sha256": SHA256}, "ContentType": "application/gzip", "ServerSideEncryption": "AES256"})
    response = s3.get_object(Bucket=TARGET_BUCKET, Key=TARGET_KEY, ExpectedBucketOwner=TARGET_ACCOUNT)
    uploaded = hashlib.sha256(); size = 0
    try:
        for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
            uploaded.update(chunk); size += len(chunk)
    finally:
        response["Body"].close()
    if size != SIZE or uploaded.hexdigest() != SHA256:
        raise ValueError("Uploaded payload verification failed; do not overwrite")
    checked = datetime.now(timezone.utc).isoformat()
    facts = dict(scope="teacher_payload_public_facts", account=TARGET_ACCOUNT, class_id=CLASS_ID,
        region="us-east-1", checked_at=checked, private_bucket=TARGET_BUCKET, object_key=TARGET_KEY,
        bundle_sha256=SHA256, bundle_size_bytes=SIZE, signed_tree_verified=True)
    save_json(workspace / "teacher-payload.public.json", facts)
    save_json(workspace / "payload-copy.public.json", dict(facts, scope="exact_accepted_payload_cross_account_copy",
        source_account=SOURCE_ACCOUNT, source_bucket=SOURCE_BUCKET, source_key=SOURCE_KEY,
        all_payload_files_verified=len(manifest["files"]), target_get_object_full_sha256_verified=True,
        short_lived_source_url_transported_only_encrypted=True, admin_or_aws_access_keys_transferred=False,
        class_ready=False))
    print("CLASS193548_PAYLOAD_COPY_COMPLETE; exact bytes, full signature tree and destination GET verified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("receiver-prepare", "sender-export", "receive-copy"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--certificate", type=Path)
    parser.add_argument("--certificate-sha256")
    parser.add_argument("--ciphertext", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    import boto3
    session = boto3.Session(region_name="us-east-1")
    if args.command == "receiver-prepare": receive_prepare(session, args.workspace)
    elif args.command == "sender-export": sender_export(session, args.workspace, args.certificate, args.certificate_sha256)
    else: receive_copy(session, args.workspace, args.ciphertext.read_bytes())


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        # A URL in an HTTP exception is a bearer secret; never print the exception.
        print("CLASS_PAYLOAD_TRANSFER_FAILED=" + type(exc).__name__, flush=True)
        raise SystemExit(2)
