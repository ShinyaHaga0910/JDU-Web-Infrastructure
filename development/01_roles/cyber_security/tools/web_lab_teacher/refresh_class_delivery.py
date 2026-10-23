"""Repackage Class193548's existing student credential with a fresh payload URL.

No credential is issued, rotated, registered, or given broader access. The old
issuance receipt and the current DynamoDB credential must agree. Only ciphertext
leaves the teacher's CloudShell, addressed to this same student's new recipient.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

import class_student_delivery as delivery

LAB_ID = "class193548-test1"
MANIFEST_SHA = "a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2"
ORIGINAL_CIPHER_SHA = "5e98abb15e4d182d94ba4854511484e5597255a89de654bead9fdc7333abb26f"


def existing_credential(session, workspace):
    delivery.identity(session, delivery.TEACHER)
    receipt = json.loads(delivery.read(workspace / "issued.public.json", private=True))
    cipher = delivery.read(workspace / "student-delivery.encrypted.cms", limit=65536, private=True)
    if (receipt.get("scope") != "one_student_delivery_issued"
            or receipt.get("class_id") != delivery.CLASS_ID
            or receipt.get("teacher_account") != delivery.TEACHER
            or receipt.get("student_account") != delivery.STUDENT
            or receipt.get("lab_id") != LAB_ID
            or receipt.get("teacher_admin_transferred") is not False
            or receipt.get("ciphertext_sha256") != ORIGINAL_CIPHER_SHA
            or delivery.digest(cipher) != ORIGINAL_CIPHER_SHA):
        raise ValueError("Original issuance evidence differs")
    path = workspace / "own-student.credentials.json"
    raw = delivery.read(path, private=True)
    credential = json.loads(raw)
    if (set(credential) != {"schema_version", "api_base_url", "fixed_ingress_ipv4", "release_id", "lab_id", "lab_token"}
            or credential["schema_version"] != 1 or credential["lab_id"] != LAB_ID
            or credential["release_id"] != "web-2026-10-r1"
            or credential["api_base_url"] != "https://7ilp8ph6ki.execute-api.us-east-1.amazonaws.com"
            or credential["fixed_ingress_ipv4"] != "50.16.41.7"
            or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", credential["lab_token"])):
        raise ValueError("Only the original student's credential may be repackaged")
    stacks = session.client("cloudformation", region_name="us-east-1").describe_stacks(
        StackName="jdu-web-progress-2026")["Stacks"]
    if len(stacks) != 1 or stacks[0]["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
        raise ValueError("Teacher stack is not ready")
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stacks[0]["Outputs"]}
    table = outputs["TableName"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,255}", table):
        raise ValueError("Teacher table identity unavailable")
    item = session.client("dynamodb", region_name="us-east-1").get_item(
        TableName=table, Key={"pk": {"S": "LAB#" + LAB_ID}, "sk": {"S": "META"}},
        ConsistentRead=True).get("Item", {})
    if (item.get("lab_id") != {"S": LAB_ID}
            or item.get("release_id") != {"S": credential["release_id"]}
            or item.get("active") != {"BOOL": True}
            or not hmac.compare_digest(item.get("token_hash", {}).get("S", ""),
                hashlib.sha256(credential["lab_token"].encode()).hexdigest())):
        raise ValueError("Existing student credential is inactive or differs from the teacher record")
    return credential, raw, item.get("deployment_id", {}).get("S")


def refresh(session, args, tools, now=None):
    now = now or datetime.now(timezone.utc)
    delivery.identity(session, delivery.TEACHER)
    if tools["manifest_sha256"] != MANIFEST_SHA:
        raise ValueError("Use the accepted Class193548 signed v7")
    delivery.validate_manifest(tools["manifest"])
    request = delivery.validate_request(json.loads(delivery.read(args.request)), args.recipient_sha256, now)
    if request["lab_id"] != LAB_ID:
        raise ValueError("Recipient belongs to another student Lab")
    credential, original, bound_deployment = existing_credential(session, args.issued_workspace)
    if args.output_workspace.exists() or args.output_workspace.is_symlink():
        raise ValueError("A new refresh output workspace is required")
    from botocore.config import Config
    s3 = session.client("s3", region_name="us-east-1", config=Config(signature_version="s3v4"))
    head = s3.head_object(Bucket=delivery.BUCKET, Key=delivery.OBJECT, ExpectedBucketOwner=delivery.TEACHER)
    if head["ContentLength"] != delivery.PAYLOAD_SIZE or head.get("Metadata", {}).get("sha256") != delivery.PAYLOAD_SHA:
        raise ValueError("Accepted private payload differs")
    value = dict(scope="one_student_credentials_and_payload_url",
        request_sha256=delivery.digest(json.dumps(request, sort_keys=True).encode()), manifest_sha256=MANIFEST_SHA,
        class_id=delivery.CLASS_ID, student_account=delivery.STUDENT, teacher_account=delivery.TEACHER,
        created_at=now.isoformat(), expires_at=min(now + timedelta(hours=1),
            datetime.fromisoformat(request["expires_at"])).isoformat(), credentials=credential,
        bootstrap_url=s3.generate_presigned_url("get_object", Params={"Bucket": delivery.BUCKET,
            "Key": delivery.OBJECT}, ExpiresIn=3600))
    delivery.validate_envelope(value, request, MANIFEST_SHA, now)
    from enroll_five_node_progress import encrypt
    ciphertext = encrypt(request["certificate_pem"].encode(), json.dumps(value).encode())
    if delivery.read(args.issued_workspace / "own-student.credentials.json", private=True) != original:
        raise ValueError("Existing credential changed during preparation")
    args.output_workspace.mkdir(mode=0o700, exist_ok=False)
    delivery.save(args.output_workspace / "student-delivery.encrypted.cms", ciphertext)
    delivery.save_json(args.output_workspace / "refresh.public.json", dict(
        scope="existing_student_credential_repackaged", class_id=delivery.CLASS_ID, lab_id=LAB_ID,
        teacher_account=delivery.TEACHER, student_account=delivery.STUDENT, manifest_sha256=MANIFEST_SHA,
        created_at=value["created_at"], expires_at=value["expires_at"], ciphertext_sha256=delivery.digest(ciphertext),
        original_ciphertext_sha256=ORIGINAL_CIPHER_SHA, recipient_sha256=args.recipient_sha256,
        bound_deployment_id=bound_deployment, existing_credential_preserved=True, new_credential_issued=False,
        teacher_admin_transferred=False, resources_created=False, class_ready=False))
    print("EXISTING_STUDENT_DELIVERY_REFRESHED_ENCRYPTED; original credential preserved; no new credential issued")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "issued-workspace", "output-workspace", "tools"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--recipient-sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    import boto3
    session = boto3.Session(region_name="us-east-1")
    delivery.identity(session, delivery.TEACHER)
    refresh(session, args, delivery.verified_tools(args.tools))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("EXISTING_STUDENT_DELIVERY_REFRESH_STOPPED=" + type(exc).__name__)
        raise SystemExit(2)
