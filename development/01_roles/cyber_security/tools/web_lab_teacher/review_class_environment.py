"""Read-only AWS inventory before a teacher/student cross-account candidate.

Class and role labels are operator context, not an AWS identity assertion.
No saved credential files are opened and no AWS mutation API is called.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re


REGION = "us-east-1"
AMI = "ami-0fa5967347d08d2df"
CANONICAL = "099720109477"


def account_guard(actual, expected=None, excluded=()):
    if not re.fullmatch(r"[0-9]{12}", actual):
        raise ValueError("Invalid AWS account identity")
    if actual in excluded or (expected is not None and actual != expected):
        raise ValueError("Wrong AWS environment; no further inspection performed")


def public_subnets(subnets, route_tables, internet_gateways):
    """A candidate needs an available subnet, an attached IGW and active route."""
    main = {}
    explicit = {}
    for table in route_tables:
        for association in table.get("Associations", []):
            if association.get("Main"):
                main[table["VpcId"]] = table
            if association.get("SubnetId"):
                explicit[association["SubnetId"]] = table
    attached = {
        (gateway["InternetGatewayId"], item["VpcId"])
        for gateway in internet_gateways
        for item in gateway.get("Attachments", [])
        if item.get("State") == "available"
    }
    result = []
    for subnet in subnets:
        table = explicit.get(subnet["SubnetId"], main.get(subnet["VpcId"], {}))
        usable = any(
            route.get("DestinationCidrBlock") == "0.0.0.0/0"
            and route.get("State") == "active"
            and (route.get("GatewayId"), subnet["VpcId"]) in attached
            for route in table.get("Routes", [])
        )
        if subnet.get("State") == "available" and usable:
            result.append({key: subnet[key] for key in
                           ("SubnetId", "VpcId", "AvailabilityZone", "AvailableIpAddressCount")})
    return result


def inspect(session, class_id, role, expected=None, excluded=()):
    account = session.client("sts", region_name=REGION).get_caller_identity()["Account"]
    account_guard(account, expected, excluded)
    ec2 = session.client("ec2", region_name=REGION)
    nodes = [node for page in ec2.get_paginator("describe_instances").paginate(
        Filters=[{"Name": "instance-state-name", "Values":
                  ["pending", "running", "stopping", "stopped", "shutting-down"]}])
        for reservation in page["Reservations"] for node in reservation["Instances"]]
    image = ec2.describe_images(ImageIds=[AMI])["Images"]
    image_ok = (len(image) == 1 and image[0]["ImageId"] == AMI
                and image[0]["OwnerId"] == CANONICAL
                and image[0]["Architecture"] == "x86_64"
                and image[0]["State"] == "available")
    subnets = public_subnets(
        ec2.describe_subnets()["Subnets"],
        ec2.describe_route_tables()["RouteTables"],
        ec2.describe_internet_gateways()["InternetGateways"])
    iam = session.client("iam", region_name=REGION)
    profile = iam.get_instance_profile(InstanceProfileName="LabInstanceProfile")["InstanceProfile"]
    profile_ok = (profile["InstanceProfileName"] == "LabInstanceProfile"
                  and len(profile["Roles"]) == 1 and profile["Roles"][0]["RoleName"] == "LabRole")
    role_ok = iam.get_role(RoleName="LabRole")["Role"]["RoleName"] == "LabRole"
    stacks = [stack for page in session.client("cloudformation", region_name=REGION)
              .get_paginator("list_stacks").paginate()
              for stack in page["StackSummaries"] if stack["StackStatus"] != "DELETE_COMPLETE"]
    new_count = 1 if role == "teacher" else 5
    return {
        "scope": "read_only_class_environment_inventory_not_deployment_approval",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "operator_class_id": class_id, "operator_role": role,
        "aws_account": account, "region": REGION,
        "aws_mutations": 0, "lab_credentials_created_or_read": 0,
        "official_fixed_ami_available": image_ok,
        "existing_lab_role_present": role_ok,
        "existing_lab_instance_profile_matches": profile_ok,
        "public_subnet_candidates": subnets,
        "nonterminated_instances": [{
            "instance_id": node["InstanceId"], "state": node["State"]["Name"],
            "type": node["InstanceType"],
            "root_volume_ids": [item["Ebs"]["VolumeId"] for item in node.get("BlockDeviceMappings", [])
                                if item["DeviceName"] == node.get("RootDeviceName") and "Ebs" in item]
        } for node in nodes],
        "active_stack_count": len(stacks),
        "web_stacks": [{"stack_name": stack["StackName"], "status": stack["StackStatus"]}
                       for stack in stacks if stack["StackName"].startswith("jdu-web-")],
        "conservative_resource_plan": {
            "existing_nonterminated": len(nodes), "proposed_new_instances": new_count,
            "pilot_ceiling": 9, "within_pilot_ceiling": len(nodes) + new_count <= 9,
            "is_aws_quota_claim": False},
        "notes": ["IAM PassRole, service limits and actual deployment permissions remain unproven.",
                  "No create/status deployment helper or saved credential state was invoked."],
        "deployment_approved": False, "class_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-id", required=True, type=int)
    parser.add_argument("--role", required=True, choices=("teacher", "student"))
    parser.add_argument("--expected-account")
    parser.add_argument("--exclude-account", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.class_id <= 0:
        raise ValueError("Positive Academy Class ID required")
    if args.output.exists():
        raise ValueError("Existing report retained; select a new output")
    import boto3
    report = inspect(boto3.Session(region_name=REGION), args.class_id, args.role,
                     args.expected_account, args.exclude_account)
    # Report paths are explicit; never create or touch a credential directory.
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
                   "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print("READ_ONLY_ENVIRONMENT_REVIEW_SAVED; no AWS changes or credentials")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("READ_ONLY_ENVIRONMENT_REVIEW_FAILED=" + type(exc).__name__)
        raise SystemExit(2)
