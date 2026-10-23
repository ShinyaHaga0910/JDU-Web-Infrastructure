"""Prepare a reviewed new teacher stack; apply is an explicit human-run step."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from review_class_environment import inspect


BASE_SHA256 = "e1638632af38462d00a167945646d2f9daf121319bac5eee9a3b03975097467e"
STACK = "jdu-web-progress-2026"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
                   "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def private_json(path):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077 or info.st_nlink != 1):
        raise ValueError("An individual private regular plan is required")
    return json.loads(path.read_text())


def validate_review(report, account, class_id, subnet_id, now):
    checked = datetime.fromisoformat(report["checked_at"])
    if (report["scope"] != "read_only_class_environment_inventory_not_deployment_approval"
            or report["aws_account"] != account or report["operator_class_id"] != class_id
            or report["operator_role"] != "teacher" or report["region"] != "us-east-1"
            or checked.tzinfo is None or not timedelta(0) <= now - checked <= timedelta(minutes=30)):
        raise ValueError("Fresh inventory of this teacher and Class is required")
    if (not all(report[key] for key in ("official_fixed_ami_available", "existing_lab_role_present",
                                       "existing_lab_instance_profile_matches"))
            or len(report["nonterminated_instances"]) + 1 > 9
            or any(stack["stack_name"] == STACK for stack in report["web_stacks"])):
        raise ValueError("New teacher prerequisites failed; existing resources retained")
    subnets = [subnet for subnet in report["public_subnet_candidates"]
               if subnet["SubnetId"] == subnet_id and subnet["AvailableIpAddressCount"] >= 2]
    if len(subnets) != 1:
        raise ValueError("One live public subnet is required")
    return subnets[0]


def distribution_template(base, account, class_id):
    template = json.loads(json.dumps(base))
    bucket = "jdu-web-class" + str(class_id) + "-" + account
    if "DistributionBucket" in template["Resources"]:
        raise ValueError("Existing bucket configuration retained")
    template["Resources"]["DistributionBucket"] = {
        "Type": "AWS::S3::Bucket", "DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain",
        "Properties": {"BucketName": bucket,
            "PublicAccessBlockConfiguration": {"BlockPublicAcls": True, "IgnorePublicAcls": True,
                                               "BlockPublicPolicy": True, "RestrictPublicBuckets": True},
            "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
            "BucketEncryption": {"ServerSideEncryptionConfiguration": [
                {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}}}
    template["Outputs"]["DistributionBucket"] = {"Value": {"Ref": "DistributionBucket"}}
    return template, bucket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("--expected-account", required=True)
    parser.add_argument("--class-id", required=True, type=int)
    parser.add_argument("--subnet-id")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--confirmed-access", action="store_true")
    args = parser.parse_args()
    if args.class_id <= 0 or args.expected_account in ("144753397193", "965244652544"):
        raise ValueError("This is a new teacher deployment, not Test2 or its student account")
    import boto3
    session = boto3.Session(region_name="us-east-1")
    here = Path(__file__).resolve().parent
    deploy = here / "deploy_teacher.py"
    runner = Path(__file__).resolve()
    now = datetime.now(timezone.utc)
    if args.command == "apply":
        if not args.confirmed_access:
            raise ValueError("Explicit reviewed access confirmation is required")
        plan = private_json(args.plan)
        if (plan["scope"] != "new_class_teacher_deployment_plan"
                or plan["account"] != args.expected_account or plan["class_id"] != args.class_id
                or plan["runner_sha256"] != digest(runner) or plan["deploy_sha256"] != digest(deploy)
                or plan["stack_name"] != STACK
                or not timedelta(0) <= now - datetime.fromisoformat(plan["planned_at"]) <= timedelta(hours=1)):
            raise ValueError("Reviewed plan identity, source or freshness differs")
        template_path = args.plan.parent / plan["template_file"]
        if template_path.parent.resolve() != args.plan.parent.resolve() or digest(template_path) != plan["template_sha256"]:
            raise ValueError("Reviewed template differs")
        subnet_id = plan["subnet_id"]
    else:
        if not args.subnet_id or args.plan.exists():
            raise ValueError("New plan and explicit subnet required")
        subnet_id = args.subnet_id
    report = inspect(session, args.class_id, "teacher", args.expected_account,
                     ("144753397193", "965244652544"))
    now = datetime.now(timezone.utc)
    subnet = validate_review(report, args.expected_account, args.class_id, subnet_id, now)
    offerings = session.client("ec2", region_name="us-east-1").describe_instance_type_offerings(
        LocationType="availability-zone", Filters=[{"Name": "instance-type", "Values": ["t3a.small"]},
            {"Name": "location", "Values": [subnet["AvailabilityZone"]]}])["InstanceTypeOfferings"]
    if not offerings:
        raise ValueError("Reviewed teacher instance type unavailable in this subnet")
    state = Path.home() / ".jdu-web-teacher"
    if any((state / name).exists() for name in ("identity.json", "admin.key", "teacher.credentials.json")):
        raise ValueError("Existing teacher state retained; new credential creation refused")
    cfn = session.client("cloudformation", region_name="us-east-1")
    if args.command == "plan":
        base_path = here / "web-teacher.template.json"
        if digest(base_path) != BASE_SHA256:
            raise ValueError("Accepted base teacher template differs")
        template, bucket = distribution_template(json.loads(base_path.read_text()), args.expected_account, args.class_id)
        template_path = args.plan.with_suffix(".template.json")
        save_new(template_path, template)
        if template_path.stat().st_size > 51200:
            raise ValueError("Teacher template exceeds direct CloudFormation limit")
        cfn.validate_template(TemplateBody=template_path.read_text())
        if bucket in {item["Name"] for item in session.client("s3").list_buckets()["Buckets"]}:
            raise ValueError("Existing distribution bucket retained")
        plan = dict(scope="new_class_teacher_deployment_plan", account=args.expected_account,
            class_id=args.class_id, planned_at=now.isoformat(), stack_name=STACK,
            vpc_id=subnet["VpcId"], subnet_id=subnet_id, availability_zone=subnet["AvailabilityZone"],
            template_file=template_path.name, template_sha256=digest(template_path),
            deploy_sha256=digest(deploy), runner_sha256=digest(runner), distribution_bucket=bucket,
            resources=len(template["Resources"]), existing_instances=len(report["nonterminated_instances"]),
            new_ec2=1, instance_type="t3a.small", encrypted_root_gib=16, fixed_eip=1,
            public_ingress_tcp=[443], public_ssh=False, lambda_execution_role="LabRole",
            private_distribution_bucket_public_access_blocked=True,
            aws_resources_created=0, lab_credentials_created=0, class_ready=False)
        save_new(args.plan, plan)
        print("TEACHER_PLAN_READY; no resources or credentials created")
        return
    if plan["vpc_id"] != subnet["VpcId"] or plan["availability_zone"] != subnet["AvailabilityZone"]:
        raise ValueError("Reviewed network changed")
    cfn.validate_template(TemplateBody=template_path.read_text())
    intent = args.plan.with_suffix(args.plan.suffix + ".create-intent.json")
    save_new(intent, dict(account=args.expected_account, class_id=args.class_id,
                          template_sha256=plan["template_sha256"], started_at=now.isoformat()))
    result = subprocess.run([sys.executable, "-B", str(deploy), "create", "--template", str(template_path),
                             "--vpc-id", plan["vpc_id"], "--subnet-id", subnet_id], check=False)
    if result.returncode:
        raise ValueError("Creation did not finish normally; retain state and inspect, do not repeat apply")
    print("TEACHER_CREATE_REQUESTED; retain this plan and credential state")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("CLASS_TEACHER_DEPLOY_FAILED=" + type(exc).__name__)
        raise SystemExit(2)
