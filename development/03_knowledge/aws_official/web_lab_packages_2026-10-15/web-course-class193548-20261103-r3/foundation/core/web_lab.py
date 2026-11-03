"""Signed release verification and read-only planning; no provisioning commands."""

import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import uuid

from release_validation import ValidationError, json_bytes, read_regular, verify_release


READ_OPERATIONS = frozenset({
    ("sts", "get-caller-identity"),
    ("cloudformation", "describe-stacks"), ("cloudformation", "validate-template"),
    ("ec2", "describe-images"), ("ec2", "describe-key-pairs"),
    ("ec2", "describe-managed-prefix-lists"), ("ec2", "describe-instance-types"),
    ("ec2", "describe-availability-zones"), ("ec2", "describe-instance-type-offerings"),
    ("pricing", "get-products"),
})


class AwsReadError(RuntimeError):
    pass


class StackMissing(AwsReadError):
    pass


def aws_json(service, operation, region, *arguments):
    if (service, operation) not in READ_OPERATIONS:
        raise ValidationError("AWS operation is outside the read-only allowlist")
    command = ["aws", service, operation, "--region", region, "--output", "json",
               "--no-cli-pager", "--cli-connect-timeout", "10", "--cli-read-timeout", "20", *arguments]
    environment = dict(os.environ, AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off", AWS_MAX_ATTEMPTS="2")
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=50, env=environment)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AwsReadError(f"AWS CLI unavailable or timed out: {service} {operation}") from exc
    if result.returncode:
        # Only the exact absent-stack error permits a new plan. Never treat AccessDenied as absent.
        if (service, operation) == ("cloudformation", "describe-stacks"):
            name = arguments[arguments.index("--stack-name") + 1] if "--stack-name" in arguments else None
            absent = ("An error occurred (ValidationError) when calling the DescribeStacks operation: "
                      f"Stack with id {name} does not exist")
            if name and result.stderr.strip() == absent:
                raise StackMissing("No existing stack")
        # Do not forward raw CLI output, credentials, URLs or identifiers to logs.
        raise AwsReadError(f"AWS read failed: {service} {operation}; check session and permissions")
    try:
        value = json_bytes(result.stdout.encode("utf-8"))
        if type(value) is not dict:
            raise ValidationError("AWS response is not an object")
        return value
    except ValidationError as exc:
        raise AwsReadError(f"Malformed AWS response: {service} {operation}") from exc


def ssh_public_key(data):
    """Compare OpenSSH wire bytes, independent of EC2 fingerprint conventions/comments."""
    try:
        lines = data.decode("ascii").strip().splitlines()
        if len(lines) != 1:
            raise ValueError()
        fields = lines[0].split()
        if len(fields) < 2 or fields[0] not in ("ssh-rsa", "ssh-ed25519"):
            raise ValueError()
        wire = base64.b64decode(fields[1], validate=True)
        offset = 0

        def field():
            nonlocal offset
            length = struct.unpack(">I", wire[offset:offset + 4])[0]
            offset += 4
            result = wire[offset:offset + length]
            offset += length
            if len(result) != length:
                raise ValueError()
            return result

        algorithm = field().decode("ascii")
        if algorithm != fields[0]:
            raise ValueError()
        if algorithm == "ssh-ed25519":
            if len(field()) != 32:
                raise ValueError()
        else:
            exponent, modulus = field(), field()
            if int.from_bytes(exponent, "big") < 3 or int.from_bytes(modulus, "big").bit_length() < 2048:
                raise ValueError()
        if offset != len(wire):
            raise ValueError()
        return algorithm, wire
    except (ValueError, UnicodeError, struct.error, binascii.Error) as exc:
        raise ValidationError("Use one OpenSSH RSA/ED25519 public key; never upload a private key") from exc


def check_ami(release, response):
    expected = release["ami"]
    images = response.get("Images", [])
    if len(images) != 1:
        raise ValidationError("Pinned AMI is unavailable or ambiguous in the release region")
    image = images[0]
    checks = {"ImageId": expected["id"], "OwnerId": expected["owner_id"],
              "Name": expected["image_name"], "Architecture": "x86_64", "State": "available",
              "VirtualizationType": "hvm", "RootDeviceType": "ebs",
              "RootDeviceName": expected["root_device_name"], "Public": True}
    roots = [mapping.get("Ebs", {}) for mapping in image.get("BlockDeviceMappings", [])
             if mapping.get("DeviceName") == expected["root_device_name"]]
    if (any(image.get(key) != value for key, value in checks.items()) or len(roots) != 1
            or roots[0].get("VolumeSize") != expected["root_min_gib"]):
        raise ValidationError("Live AMI metadata differs from the signed Ubuntu baseline")


def check_aws_inputs(verified, lab_id, key_name, public_key):
    release, files = verified["manifest"], verified["files"]
    region, stack_name = release["region"], "jdu-web-" + lab_id
    identity = aws_json("sts", "get-caller-identity", region)
    account = identity.get("Account", "")
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValidationError("AWS caller account is unavailable")
    try:
        aws_json("cloudformation", "describe-stacks", region, "--stack-name", stack_name)
    except StackMissing:
        pass
    else:
        raise ValidationError("Stack already exists; preserve its state and use the future status/diagnose command")
    check_ami(release, aws_json("ec2", "describe-images", region, "--image-ids", release["ami"]["id"]))
    keys = aws_json("ec2", "describe-key-pairs", region,
                    "--key-names", key_name, "--include-public-key").get("KeyPairs", [])
    if (len(keys) != 1 or keys[0].get("KeyName") != key_name
            or ssh_public_key(keys[0].get("PublicKey", "").encode("ascii")) != public_key):
        raise ValidationError("AWS KeyName does not match the supplied public key")
    prefix_id = release["network"]["s3_prefix_list_id"]
    lists = aws_json("ec2", "describe-managed-prefix-lists", region,
                     "--prefix-list-ids", prefix_id).get("PrefixLists", [])
    if (len(lists) != 1 or lists[0].get("PrefixListId") != prefix_id
            or lists[0].get("OwnerId") != "AWS" or lists[0].get("AddressFamily") != "IPv4"
            or lists[0].get("PrefixListName") != f"com.amazonaws.{region}.s3"):
        raise ValidationError("S3 prefix list differs from the release region or AWS-managed IPv4 list")
    # ValidateTemplate accepts inline bodies up to 51,200 bytes. Larger templates are unsupported here.
    read_regular(files["template"], 51200).decode("utf-8")
    aws_json("cloudformation", "validate-template", region,
             "--template-body", "file://" + files["template"].resolve().as_posix())
    return account, stack_name


def select_instances(verified, catalog, exclude_families, exclude_pairs):
    # This is executable teacher code only after its signature-bound hash has passed.
    spec = importlib.util.spec_from_file_location("jdu_verified_selector", verified["files"]["selector"])
    if spec is None or spec.loader is None:
        raise ValidationError("Verified selector cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.aws_json = aws_json
    try:
        data = module.discover(verified["manifest"]["region"], catalog, exclude_families, exclude_pairs)
        return module.select_plan(data, exclude_families, exclude_pairs)
    except AwsReadError:
        raise
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # Avoid echoing arbitrary catalog contents or other local inputs.
        raise ValidationError("Instance/price selection failed; check availability and a complete fresh price catalog") from exc


def save_plan(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o600), "wb") as output:
            output.write(data)
    except OSError as exc:
        raise ValidationError("Cannot save a new plan; existing files are never overwritten") from exc


def make_plan(verified, lab_id, key_name, public_key_path, output,
              catalog=None, exclude_families=(), exclude_pairs=()):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,31}", lab_id):
        raise ValidationError("Lab ID must be 3-32 lowercase letters, digits or hyphens, without a leading hyphen")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", key_name):
        raise ValidationError("Use a simple EC2 KeyName without spaces")
    if any(not re.fullmatch(r"t[1-9][0-9]*[a-z]*", item) for item in exclude_families):
        raise ValidationError("Invalid excluded T family")
    if any(not re.fullmatch(r"t[1-9][0-9]*[a-z]*@[a-z0-9-]+", item) for item in exclude_pairs):
        raise ValidationError("Invalid excluded family@AZ")
    if Path(output).exists() or Path(output).is_symlink() or not Path(output).parent.is_dir():
        raise ValidationError("Plan needs a new file in an existing directory")
    public_key = ssh_public_key(read_regular(public_key_path, 16384))
    account, stack_name = check_aws_inputs(verified, lab_id, key_name, public_key)
    selection = select_instances(verified, catalog, exclude_families, exclude_pairs)
    release = verified["manifest"]
    plan = {"schema_version": 1, "stage": "PLAN_READY", "resources_created": False,
            "deployment_id": str(uuid.uuid4()), "planned_at": datetime.now(timezone.utc).isoformat(),
            "release_id": release["release_id"], "manifest_sha256": verified["manifest_sha256"],
            "trusted_fingerprint": verified["trusted_fingerprint"], "account_id": account,
            "region": release["region"], "lab_id": lab_id, "stack_name": stack_name,
            "key_name": key_name,
            "ssh_public_key_sha256": hashlib.sha256(public_key[1]).hexdigest(),
            "ami_id": release["ami"]["id"], "selection": selection,
            "bundle_verified_locally": verified["bundle_verified_locally"],
            "limitations": ["Read-only planning only; EC2/CloudFormation resources were not created.",
                            "RunInstances/stack creation permissions, quotas and live capacity are untested.",
                            "No S3 download, GUI, SSH, grading or classroom readiness has been tested.",
                            "A future create command must reverify the release, account, expiry and plan before use."]}
    save_plan(output, plan)
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "plan", "student"):
        command = commands.add_parser(name)
        command.add_argument("--deployment-manifest", required=True)
        command.add_argument("--signature", required=True)
        command.add_argument("--public-key", required=True, help="Teacher's release signing public key")
        command.add_argument("--trusted-fingerprint", required=True, help="Full fingerprint confirmed independently")
        command.add_argument("--artifact-root", required=True)
        command.add_argument("--gpg", default="gpg")
        if name == "plan":
            command.add_argument("--lab-id", required=True)
            command.add_argument("--key-name", required=True)
            command.add_argument("--public-key-file", required=True, help="Student's SSH public key only")
            command.add_argument("--output", required=True)
            command.add_argument("--price-catalog")
            command.add_argument("--exclude-family", action="append", default=[])
            command.add_argument("--exclude-pair", action="append", default=[])
        if name == 'student':
            command.add_argument('operation',choices=('plan','create','status','diagnose','lock-prepare','lock-review','lock-apply',
                'ssm','ssh-plan','ssh-apply','ssh-verify','register-plan','register-apply','register-verify','install-commands','preflight'))
            for field in ('state','plan','output','lab-id','key-name','price-catalog','student-config','bootstrap-url-file','bin-directory'):
                command.add_argument('--'+field)
            command.add_argument('--confirmed-access',action='store_true')
            command.add_argument('--gui-confirmed',action='store_true')
            command.add_argument('--role',choices=('bastion','web','dns','db','repo'),default='bastion')
    args = parser.parse_args(argv)
    try:
        verified = verify_release(args.deployment_manifest, args.signature, args.public_key,
                                  args.trusted_fingerprint, args.artifact_root, args.gpg,
                                  include_bundle=args.command == "verify")
        if args.command == "verify":
            result = {"stage": "RELEASE_VERIFIED", "scope": "local_files_only", "aws_checked": False,
                      "bundle_verified_locally": True,
                      "release_id": verified["manifest"]["release_id"],
                      "manifest_sha256": verified["manifest_sha256"]}
        elif args.command == 'student':
            # Both the loader and controller code are hashes inside the verified outer signature.
            if not {'controller_bundle','controller_validation'} <= set(verified['files']):
                raise ValidationError('Signed student controller artifacts are required')
            loader_spec=importlib.util.spec_from_file_location('jdu_verified_controller_loader',verified['files']['controller_validation'])
            loader=importlib.util.module_from_spec(loader_spec);loader_spec.loader.exec_module(loader)
            data=verified['files']['controller_bundle'].read_bytes()
            target=Path.home()/'.local/share/jdu-web/controllers'/hashlib.sha256(data).hexdigest()
            sys.dont_write_bytecode=True
            installed=loader.install_controller(data,target);sys.path.insert(0,str(installed))
            spec=importlib.util.spec_from_file_location('jdu_verified_student_controller',installed/'student_controller.py')
            controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)
            try:result=controller.run(verified,args)
            except Exception as exc:
                # A create call can have an unknown outcome. Never claim nothing changed.
                print('STUDENT_OPERATION_STOPPED='+type(exc).__name__+'; preserve state and inspect status')
                return 2
        else:
            plan = make_plan(verified, args.lab_id, args.key_name, args.public_key_file, args.output,
                             args.price_catalog, args.exclude_family, args.exclude_pair)
            result = {"stage": plan["stage"], "resources_created": False,
                      "family": plan["selection"]["family"],
                      "availability_zone": plan["selection"]["availability_zone"],
                      "compute_hourly_usd": plan["selection"]["compute_hourly_usd"]}
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result.get('current_foundation_passed') is False else 0
    except AwsReadError as exc:
        print(f"ERROR: {exc}. No AWS resources were changed.", file=sys.stderr)
        return 3
    except (ValidationError, OSError, UnicodeError, KeyError, TypeError, ValueError):
        # Detailed input values and subprocess stderr are intentionally not logged.
        print("ERROR: Validation failed; check release files, trusted key, inputs and existing state. No AWS resources were changed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
