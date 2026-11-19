#!/usr/bin/env python3
"""Create and verify a fresh Web teacher foundation from AWS Academy CloudShell."""

import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit


REGION = "us-east-1"
REPO = "https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure"
BASE_REVISION = "5e126115bbe04db280c3baee6b641113fe682f30"
BASE_SHA256 = "e1638632af38462d00a167945646d2f9daf121319bac5eee9a3b03975097467e"
BASE_PATH = "development/01_roles/cyber_security/tools/web_lab_teacher/web-teacher.template.json"
OWNER_TAG = "JduWebTeacherInstallation"
PUBLIC_ACCESS_BLOCK = dict.fromkeys(
    ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"), True
)
CURL = ["curl", "-q", "--proto", "=https", "--connect-timeout", "5", "--max-time", "15", "-sS"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_template(availability_zone, instance_type):
    raw = subprocess.check_output(CURL + ["--fail", f"{REPO}/{BASE_REVISION}/{BASE_PATH}"])
    if digest(raw) != BASE_SHA256:
        raise ValueError("GitHubから取得した教師用テンプレートのSHA-256が一致しません。")
    template = json.loads(raw)
    resources = template["Resources"]
    for name in ("VpcId", "SubnetId"):
        del template["Parameters"][name]
    resources["TeacherSecurityGroup"]["Properties"]["VpcId"] = {"Ref": "TeacherVpc"}
    instance = resources["TeacherInstance"]["Properties"]
    instance["InstanceType"] = instance_type
    instance["NetworkInterfaces"][0]["SubnetId"] = {"Ref": "TeacherSubnet"}
    instance["Tags"][0]["Value"] = {"Ref": "AWS::StackName"}
    resources["TeacherEipAssociation"]["DependsOn"] = ["TeacherInternetRoute", "TeacherRouteAssociation"]

    network = {
        "TeacherVpc": ("VPC", {"CidrBlock": "10.42.0.0/24", "EnableDnsSupport": True, "EnableDnsHostnames": True}),
        "TeacherSubnet": ("Subnet", {"VpcId": {"Ref": "TeacherVpc"}, "CidrBlock": "10.42.0.0/26",
                                     "AvailabilityZone": availability_zone, "MapPublicIpOnLaunch": False}),
        "TeacherInternetGateway": ("InternetGateway", {}),
        "TeacherGatewayAttachment": ("VPCGatewayAttachment", {"VpcId": {"Ref": "TeacherVpc"},
                                                             "InternetGatewayId": {"Ref": "TeacherInternetGateway"}}),
        "TeacherRouteTable": ("RouteTable", {"VpcId": {"Ref": "TeacherVpc"}}),
        "TeacherInternetRoute": ("Route", {"RouteTableId": {"Ref": "TeacherRouteTable"},
                                          "DestinationCidrBlock": "0.0.0.0/0",
                                          "GatewayId": {"Ref": "TeacherInternetGateway"}}),
        "TeacherRouteAssociation": ("SubnetRouteTableAssociation", {"SubnetId": {"Ref": "TeacherSubnet"},
                                                                  "RouteTableId": {"Ref": "TeacherRouteTable"}}),
    }
    for logical_id, (aws_type, properties) in network.items():
        resources[logical_id] = {"Type": f"AWS::EC2::{aws_type}", "Properties": properties}
    resources["TeacherInternetRoute"]["DependsOn"] = "TeacherGatewayAttachment"
    resources["DistributionBucket"] = {
        "Type": "AWS::S3::Bucket", "DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain",
        "Properties": {"PublicAccessBlockConfiguration": PUBLIC_ACCESS_BLOCK,
                       "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
                       "BucketEncryption": {"ServerSideEncryptionConfiguration": [
                           {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}},
    }
    template["Outputs"]["DistributionBucket"] = {"Value": {"Ref": "DistributionBucket"}}
    template["Outputs"]["TeacherVpcId"] = {"Value": {"Ref": "TeacherVpc"}}
    return json.dumps(template, separators=(",", ":"))


def select_capacity(ec2):
    instance_types = ("t3a.small", "t3.small")
    zones = ec2.describe_availability_zones(Filters=[
        {"Name": "state", "Values": ["available"]}, {"Name": "zone-type", "Values": ["availability-zone"]},
    ])["AvailabilityZones"]
    available_zones = {zone["ZoneName"] for zone in zones}
    pages = ec2.get_paginator("describe_instance_type_offerings").paginate(LocationType="availability-zone", Filters=[
        {"Name": "instance-type", "Values": list(instance_types)},
    ])
    offers = [item for page in pages for item in page["InstanceTypeOfferings"] if item["Location"] in available_zones]
    for instance_type in instance_types:
        matches = sorted(item["Location"] for item in offers if item["InstanceType"] == instance_type)
        if matches:
            return matches[0], instance_type
    raise ValueError("このLabの us-east-1 に t3a.small または t3.small を提供する利用可能なAZがありません。")


def preflight(session, ec2, template):
    instance = json.loads(template)["Resources"]["TeacherInstance"]["Properties"]
    images = ec2.describe_images(ImageIds=[instance["ImageId"]], Owners=["099720109477"])["Images"]
    if len(images) != 1 or images[0]["State"] != "available" or images[0]["Architecture"] != "x86_64":
        raise ValueError("このLabで対象のCanonical Ubuntu AMIを利用できません。")
    pages = ec2.get_paginator("describe_instances").paginate(Filters=[
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped", "shutting-down"]},
    ])
    if sum(len(item["Instances"]) for page in pages for item in page["Reservations"]) >= 9:
        raise ValueError("演習のEC2台数上限に達しています。既存EC2を確認してください。")
    session.client("iam").get_role(RoleName="LabRole")


def save_private(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def read_private(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW)) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError(f"所有者のみアクセスできるファイルが必要です: {path}")
        return json.load(stream)


def find_stack(cfn, name):
    from botocore.exceptions import ClientError

    try:
        return cfn.describe_stacks(StackName=name)["Stacks"][0]
    except ClientError as exc:
        error = exc.response["Error"]
        if error["Code"] == "ValidationError" and error["Message"] == f"Stack with id {name} does not exist":
            return None
        raise


def verify_stack_owner(stack, intent):
    if not stack:
        raise ValueError("作成後に対象スタックを再取得できませんでした。")
    tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
    if (tags.get(OWNER_TAG) != intent["installation_id"]
            or stack["StackId"].split(":")[4] != intent["account"]):
        raise ValueError("同名スタックは別の構築に属します。--name で別名を指定してください。")


def verify_services(session, stack):
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}
    bucket = outputs["DistributionBucket"]
    s3 = session.client("s3")
    if s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"] != PUBLIC_ACCESS_BLOCK:
        raise ValueError("教材用S3の公開ブロック設定が一致しません。")
    rules = s3.get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"]["Rules"]
    if not any(rule.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256" for rule in rules):
        raise ValueError("教材用S3の暗号化設定を確認できません。")
    table = session.client("dynamodb").describe_table(TableName=outputs["TableName"])["Table"]
    if table["TableStatus"] != "ACTIVE":
        raise ValueError("採点データ用DynamoDBの準備が完了していません。")
    host = urlsplit(outputs["ApiBaseUrl"]).hostname
    if not host or not re.fullmatch(r"[a-z0-9]+\.execute-api\.us-east-1\.amazonaws\.com", host):
        raise ValueError("出力の採点APIが想定するAWS HTTPSホストと一致しません。")
    ip = str(ipaddress.IPv4Address(outputs["FixedIngressIpv4"]))
    print("新しい固定IPv4を経由して採点APIのHTTPSを確認します。", flush=True)
    curl = CURL + ["--noproxy", "*", "--resolve", f"{host}:443:{ip}"]
    url = f"https://{host}"
    for attempt in range(36):
        result = subprocess.run(curl + ["--fail", url + "/healthz"], capture_output=True, check=False)
        if result.returncode == 0:
            try:
                health = json.loads(result.stdout)
            except ValueError:
                health = {}
            if isinstance(health, dict) and health.get("ok") is True and health.get("service") == "jdu-web-progress":
                break
        if attempt < 35:
            time.sleep(10)
    else:
        raise ValueError("固定IPv4経由のHTTPSが準備時間内に応答しませんでした。同じオプションで再確認できます。")
    status = subprocess.check_output(curl + ["-o", os.devnull, "-w", "%{http_code}", url + "/dashboard"])
    if status != b"401":
        raise ValueError("認証なしの教師ダッシュボードへのアクセスが拒否されませんでした。")
    return outputs


def run(args):
    import boto3

    session = boto3.Session(region_name=REGION)
    account = session.client("sts").get_caller_identity()["Account"]
    if not re.fullmatch(r"[0-9]{12}", account) or (args.expected_account and args.expected_account != account):
        raise ValueError("AWSアカウントが指定と一致しません。")
    class_id = args.class_id or input("AWS AcademyのClass IDを入力してください: ").strip()
    if not re.fullmatch(r"[1-9][0-9]{0,11}", class_id):
        raise ValueError("Class IDにはAWS AcademyのクラスURLにある数字を指定してください。")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,23}", args.name):
        raise ValueError("--name は英小文字で始まる24文字以内の英小文字・数字・ハイフンです。")
    name = f"jdu-web-teacher-{class_id}-{args.name}"
    work = Path.home() / ".local" / "share" / "jdu-web-teacher-install" / account / name
    print(f"AWS {account} / Class {class_id} / {REGION}\nCloudFormation: {name}\n作業先: {work}", flush=True)
    cfn = session.client("cloudformation")
    ec2 = session.client("ec2")
    if args.plan:
        if find_stack(cfn, name):
            raise ValueError("同名スタックがあります。新規計画には --name で別名を指定してください。")
        template = load_template(*select_capacity(ec2))
        preflight(session, ec2, template)
        cfn.validate_template(TemplateBody=template)
        print("計画確認完了。教師用EC2 1台、専用VPC、固定IPv4、採点API、DynamoDB、非公開S3を構築します。")
        return
    if input(f"表示された教師用AWSで構築・再確認する場合はアカウント番号 {account} を入力: ").strip() != account:
        raise ValueError("教師用AWSの確認が一致しません。AWSの作成処理を中止しました。")

    os.umask(0o077)
    work.mkdir(parents=True, exist_ok=True)
    info = work.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("構築には所有者のみアクセスできる新規作業ディレクトリが必要です。")
    with os.fdopen(os.open(work / "install.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("同じスタックの構築・確認が別の端末で実行中です。") from exc
        install(session, cfn, ec2, account, class_id, name, work)


def install(session, cfn, ec2, account, class_id, name, work):
    intent_path = work / "installation.private.json"
    receipt_path = work / "stack.private.json"
    stack = find_stack(cfn, name)
    if receipt_path.exists() and (not stack or read_private(receipt_path)["stack_id"] != stack["StackId"]):
        raise ValueError("構築記録のスタックが見つからないか、置き換えられています。--name で別名を指定してください。")
    if intent_path.exists():
        intent = read_private(intent_path)
        if (intent["account"], intent["class_id"], intent["stack_name"]) != (account, class_id, name):
            raise ValueError("保存済みの構築情報と指定されたAWS・Class・スタックが一致しません。")
    elif stack:
        raise ValueError("同名スタックの構築記録がありません。--name で別名を指定してください。")
    else:
        template = load_template(*select_capacity(ec2))
        preflight(session, ec2, template)
        cfn.validate_template(TemplateBody=template)
        intent = {"account": account, "class_id": class_id, "stack_name": name, "template": template,
                  "installation_id": secrets.token_hex(16), "admin_key": secrets.token_urlsafe(48)}
        save_private(intent_path, intent)
    if stack:
        verify_stack_owner(stack, intent)
        stack_id = stack["StackId"]
    else:
        print("CloudFormationで教師用リソースを作成します。", flush=True)
        created = cfn.create_stack(
            StackName=name, TemplateBody=intent["template"], DisableRollback=True,
            ClientRequestToken=intent["installation_id"],
            Tags=[{"Key": OWNER_TAG, "Value": intent["installation_id"]},
                  {"Key": "JduAcademyClass", "Value": class_id}],
            Parameters=[{"ParameterKey": "AdminKeyHash", "ParameterValue": digest(intent["admin_key"].encode())}],
        )
        stack_id = created["StackId"]
    if not receipt_path.exists():
        save_private(receipt_path, {"stack_id": stack_id})
    if not stack or stack["StackStatus"] == "CREATE_IN_PROGRESS":
        print("CloudFormationの作成完了を待ちます。", flush=True)
        cfn.get_waiter("stack_create_complete").wait(StackName=stack_id)
        stack = find_stack(cfn, stack_id)
        verify_stack_owner(stack, intent)
    if stack["StackStatus"] != "CREATE_COMPLETE":
        raise ValueError(f"CloudFormationの状態は {stack['StackStatus']} です。スタックのイベントを確認してください。")
    outputs = verify_services(session, stack)
    credentials = {"schema_version": 1, "api_base_url": outputs["ApiBaseUrl"],
                   "fixed_ingress_ipv4": outputs["FixedIngressIpv4"], "release_id": "web-2026-10-r1",
                   "admin_key": intent["admin_key"]}
    credential_path = work / "teacher.credentials.json"
    if not credential_path.exists():
        save_private(credential_path, credentials)
    elif read_private(credential_path) != credentials:
        raise ValueError("保存済みの教師用設定が構築結果と一致しません。")
    print(f"教師基盤の構築・確認完了: {name}\n非公開S3: {outputs['DistributionBucket']}\n教師用設定: {credential_path}")
    print("今回の確認範囲は教師基盤です。教材登録、新しい署名済み配布版、Googleログイン付き課題画面は別途準備が必要です。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-id", help="AWS AcademyのClass ID。省略時は実行中に入力します。")
    parser.add_argument("--expected-account", help="AWSアカウントを別途指定して照合する場合に使います。")
    parser.add_argument("--name", default="walkthrough", help="同じClassで複数の環境を分けるための名前。")
    parser.add_argument("--plan", action="store_true", help="AWSの前提とテンプレートを検査します。構築は実行しません。")
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError, EOFError, subprocess.SubprocessError, ImportError) as exc:
        print(f"教師基盤の確認が停止しました: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"AWS処理が停止しました: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
