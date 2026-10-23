"""Reviewed encrypted delivery of one Class193548 student's credentials and URL.

The human executes issue and receive. Administrator credentials stay in the
teacher CloudShell; the student receives only their own Lab token and one
short-lived GET URL. Public software is distributed and verified separately.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
import web_progress

TEACHER = "170126527713"
STUDENT = "965244652544"
CLASS_ID = 193548
FINGERPRINT = "65EC6784750CCFA703BA7179519284E45155EC2A"
BUCKET = "jdu-web-class193548-170126527713"
OBJECT = "teacher-candidates/web-2026-10-r1/c7/repo-bundle.tar.gz"
PAYLOAD_SHA = "60fbd303712672e34848c02f2d7d697ce21318eb7af91bf67665c88688f4deeb"
PAYLOAD_SIZE = 741180532


def save(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(data)


def save_json(path, value):
    save(path, (json.dumps(value, indent=2) + "\n").encode())


def read(path, limit=131072, private=False):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size > limit or info.st_nlink != 1
            or (private and (info.st_uid != os.geteuid() or info.st_mode & 0o077))):
        raise ValueError("Expected bounded individual file")
    return path.read_bytes()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(session, expected):
    if session.client("sts").get_caller_identity()["Account"] != expected:
        raise ValueError("Wrong Class193548 AWS account")


def validate_request(value, certificate_sha, now):
    required = {"scope", "class_id", "teacher_account", "student_account", "lab_id",
                "release_id", "created_at", "expires_at", "certificate_pem", "certificate_sha256"}
    if (set(value) != required or value["scope"] != "one_student_private_delivery_request"
            or value["class_id"] != CLASS_ID or value["teacher_account"] != TEACHER
            or value["student_account"] != STUDENT or value["release_id"] != "web-2026-10-r1"
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,31}", value["lab_id"])
            or value["certificate_sha256"] != certificate_sha
            or digest(value["certificate_pem"].encode()) != certificate_sha):
        raise ValueError("Student recipient identity differs")
    created, expiry = (datetime.fromisoformat(value[k]) for k in ("created_at", "expires_at"))
    if (created.tzinfo is None or expiry.tzinfo is None or not created <= now < expiry
            or not timedelta(0) < expiry - created <= timedelta(days=1)):
        raise ValueError("Student recipient request expired or future dated")
    return value


def validate_manifest(manifest):
    if (manifest["release_id"] != "web-2026-10-r1" or manifest["region"] != "us-east-1"
            or manifest["bootstrap"] != {"bucket": BUCKET, "release_prefix": OBJECT.rsplit("/", 1)[0] + "/"}
            or manifest["artifacts"]["repo_bundle"] != {
                "path": "repo-bundle.tar.gz", "sha256": PAYLOAD_SHA, "size_bytes": PAYLOAD_SIZE}
            or manifest["grading"] != {"ipv4": "50.16.41.7",
                "fqdn": "7ilp8ph6ki.execute-api.us-east-1.amazonaws.com", "submit_path": "/api/web/submit"}):
        raise ValueError("Intended signed teacher and payload differ")


def verified_tools(root):
    import importlib.util
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("class_delivery_signed_validation", root / "release_validation.py")
    validation = importlib.util.module_from_spec(spec); spec.loader.exec_module(validation)
    result = validation.verify_release(root / "deployment-manifest.json", root / "deployment-manifest.json.asc",
        root / "package-signing-public.asc", FINGERPRINT, root, include_bundle=False)
    validate_manifest(result["manifest"])
    spec = importlib.util.spec_from_file_location("class_delivery_signed_controller_runtime", result["files"]["controller_validation"])
    runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
    controller = runtime.install_controller(result["files"]["controller_bundle"].read_bytes(),
        root.parent / ("delivery-controller-" + result["manifest_sha256"]))
    if read(controller / "web_progress.py") != Path(web_progress.__file__).read_bytes():
        raise ValueError("Progress client differs from the signed controller")
    sys.path.insert(0, str(controller))
    return result


def validate_envelope(value, request, manifest_sha, now):
    required = {"scope", "request_sha256", "manifest_sha256", "class_id", "student_account",
                "teacher_account", "created_at", "expires_at", "credentials", "bootstrap_url"}
    if (set(value) != required or value["scope"] != "one_student_credentials_and_payload_url"
            or value["request_sha256"] != digest(json.dumps(request, sort_keys=True).encode())
            or value["manifest_sha256"] != manifest_sha or value["class_id"] != CLASS_ID
            or value["student_account"] != STUDENT or value["teacher_account"] != TEACHER):
        raise ValueError("Student envelope binding differs")
    created, expiry = (datetime.fromisoformat(value[k]) for k in ("created_at", "expires_at"))
    if (created.tzinfo is None or expiry.tzinfo is None or not created <= now < expiry
            or not timedelta(0) < expiry - created <= timedelta(hours=1)):
        raise ValueError("Student delivery expired or future dated")
    credential = value["credentials"]
    expected = {"schema_version", "api_base_url", "fixed_ingress_ipv4", "release_id", "lab_id", "lab_token"}
    if (set(credential) != expected or credential["schema_version"] != 1
            or credential["api_base_url"] != "https://7ilp8ph6ki.execute-api.us-east-1.amazonaws.com"
            or credential["fixed_ingress_ipv4"] != "50.16.41.7"
            or credential["release_id"] != request["release_id"] or credential["lab_id"] != request["lab_id"]
            or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", credential["lab_token"])):
        raise ValueError("Only the student's own credential may be received")
    # Reuse the actual student's URL guard after its signed controller is loaded.
    from student_controller import validate_bootstrap_url
    validate_bootstrap_url(value["bootstrap_url"], {"region": "us-east-1", "bootstrap": {"bucket": BUCKET}}, OBJECT)
    return credential


def prepare_receiver(session, workspace, lab_id):
    identity(session, STUDENT)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,31}", lab_id or ""):
        raise ValueError("One anonymous Lab ID is required")
    workspace.mkdir(mode=0o700, exist_ok=False)
    subprocess.run(["openssl", "req", "-new", "-x509", "-newkey", "rsa:3072", "-sha256", "-days", "1",
        "-nodes", "-keyout", str(workspace / "recipient.key"), "-out", str(workspace / "recipient.crt"),
        "-subj", "/CN=Class193548StudentSoftwareTransport"], capture_output=True, check=True)
    for name in ("recipient.key", "recipient.crt"):
        (workspace / name).chmod(0o600)
    cert = read(workspace / "recipient.crt", private=True).decode()
    now = datetime.now(timezone.utc)
    request = dict(scope="one_student_private_delivery_request", class_id=CLASS_ID, teacher_account=TEACHER,
        student_account=STUDENT, release_id="web-2026-10-r1", lab_id=lab_id, created_at=now.isoformat(),
        expires_at=(now + timedelta(days=1)).isoformat(), certificate_pem=cert, certificate_sha256=digest(cert.encode()))
    save_json(workspace / "recipient-request.public.json", request)
    print("STUDENT_DELIVERY_RECIPIENT_READY; public request only; no Lab credential issued")


def teacher_plan(session, args, tools):
    identity(session, TEACHER)
    now = datetime.now(timezone.utc)
    request = validate_request(json.loads(read(args.request)), args.recipient_sha256, now)
    head = session.client("s3", region_name="us-east-1").head_object(
        Bucket=BUCKET, Key=OBJECT, ExpectedBucketOwner=TEACHER)
    if head["ContentLength"] != PAYLOAD_SIZE or head["Metadata"].get("sha256") != PAYLOAD_SHA:
        raise ValueError("Accepted private payload is not present")
    plan = dict(scope="reviewed_one_student_delivery", request=request, manifest_sha256=tools["manifest_sha256"],
        self_sha256=digest(Path(__file__).read_bytes()), planned_at=now.isoformat(),
        expires_at=min(datetime.fromisoformat(request["expires_at"]), now + timedelta(hours=1)).isoformat(),
        new_lab_credential_issued=False, teacher_admin_transferred=False)
    save_json(args.plan, plan)
    print("STUDENT_DELIVERY_PLAN_READY; no credential issued; human issue/receive required")


def teacher_issue(session, args, tools):
    identity(session, TEACHER)
    if not args.confirmed_access:
        raise ValueError("Human confirmation for one student's new credential is required")
    plan = json.loads(read(args.plan, private=True)); now = datetime.now(timezone.utc)
    request = plan["request"]
    validate_request(request, args.recipient_sha256, now)
    if (plan["scope"] != "reviewed_one_student_delivery" or plan["self_sha256"] != digest(Path(__file__).read_bytes())
            or plan["manifest_sha256"] != tools["manifest_sha256"]
            or not datetime.fromisoformat(plan["planned_at"]) <= now < datetime.fromisoformat(plan["expires_at"])):
        raise ValueError("Reviewed student delivery plan differs or expired")
    config = web_progress.private_json(args.teacher_config)
    for key, expected in (("api_base_url", "https://" + tools["manifest"]["grading"]["fqdn"]),
                          ("fixed_ingress_ipv4", tools["manifest"]["grading"]["ipv4"]), ("release_id", request["release_id"])):
        if config.get(key) != expected:
            raise ValueError("Teacher private configuration differs from signed destination")
    args.workspace.mkdir(mode=0o700, exist_ok=False)  # Exclusive intent before issuing anything.
    save_json(args.workspace / "issue-intent.private.json", {"plan_sha256": digest(read(args.plan)), "issued_at": now.isoformat()})
    credential_path = args.workspace / "own-student.credentials.json"
    web_progress.issue(config, request["lab_id"], credential_path)
    from botocore.config import Config
    s3 = session.client("s3", region_name="us-east-1", config=Config(signature_version="s3v4"))
    url = s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": OBJECT}, ExpiresIn=3600)
    value = dict(scope="one_student_credentials_and_payload_url", request_sha256=digest(json.dumps(request, sort_keys=True).encode()),
        manifest_sha256=tools["manifest_sha256"], class_id=CLASS_ID, student_account=STUDENT, teacher_account=TEACHER,
        created_at=now.isoformat(), expires_at=(now + timedelta(hours=1)).isoformat(),
        credentials=web_progress.private_json(credential_path), bootstrap_url=url)
    validate_envelope(value, request, tools["manifest_sha256"], now)
    from enroll_five_node_progress import encrypt
    ciphertext = encrypt(request["certificate_pem"].encode(), json.dumps(value).encode())
    save(args.workspace / "student-delivery.encrypted.cms", ciphertext)
    save_json(args.workspace / "issued.public.json", dict(scope="one_student_delivery_issued", class_id=CLASS_ID,
        lab_id=request["lab_id"], student_account=STUDENT, teacher_account=TEACHER, expires_at=value["expires_at"],
        ciphertext_sha256=digest(ciphertext), teacher_admin_transferred=False, class_ready=False))
    print("STUDENT_DELIVERY_ISSUED_ENCRYPTED; teacher administrator remains private")


def receive(session, args, tools):
    identity(session, STUDENT)
    if not args.confirmed_access:
        raise ValueError("Human execution to receive the student's credential is required")
    request = json.loads(read(args.workspace / "recipient-request.public.json", private=True))
    validate_request(request, args.recipient_sha256, datetime.now(timezone.utc))
    cipher = read(args.ciphertext, limit=65536)
    description = subprocess.run(["openssl", "cms", "-cmsout", "-inform", "DER", "-print"],
        input=cipher, capture_output=True, check=True).stdout
    if any(part not in description for part in (b"id-smime-ct-authEnvelopedData", b"aes-256-gcm", b"rsaesOaep")):
        raise ValueError("Authenticated student transport required")
    read(args.workspace / "recipient.key", private=True)
    clear = subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
        "-recip", str(args.workspace / "recipient.crt"), "-inkey", str(args.workspace / "recipient.key")],
        input=cipher, capture_output=True, check=True).stdout
    value = json.loads(clear)
    credential = validate_envelope(value, request, tools["manifest_sha256"], datetime.now(timezone.utc))
    # A new directory is an exclusive intent marker. Partial deliveries remain private for review.
    output = args.workspace / "received"; output.mkdir(mode=0o700, exist_ok=False)
    save_json(output / "own-student.credentials.json", credential)
    save(output / "bootstrap-url.private.txt", (value["bootstrap_url"] + "\n").encode())
    save_json(output / "received.public.json", dict(scope="own_student_private_delivery_received", class_id=CLASS_ID,
        student_account=STUDENT, teacher_account=TEACHER, lab_id=request["lab_id"],
        manifest_sha256=tools["manifest_sha256"], expires_at=value["expires_at"], teacher_admin_received=False, class_ready=False))
    print("OWN_STUDENT_DELIVERY_RECEIVED; only own Lab token and bounded software URL; no resources created")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("recipient", "plan", "issue", "receive"))
    for name in ("workspace", "tools", "request", "plan", "teacher-config", "ciphertext"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--lab-id"); parser.add_argument("--recipient-sha256")
    parser.add_argument("--confirmed-access", action="store_true")
    args = parser.parse_args(); os.umask(0o077)
    import boto3
    session = boto3.Session(region_name="us-east-1")
    if args.command == "recipient":
        prepare_receiver(session, args.workspace, args.lab_id)
    else:
        identity(session, STUDENT if args.command == "receive" else TEACHER)
        tools = verified_tools(args.tools)
        if args.command == "plan": teacher_plan(session, args, tools)
        elif args.command == "issue": teacher_issue(session, args, tools)
        else: receive(session, args, tools)


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        # HTTP exceptions and decrypted data can contain bearer secrets.
        print("CLASS_STUDENT_DELIVERY_STOPPED=" + type(exc).__name__, flush=True)
        raise SystemExit(2)
