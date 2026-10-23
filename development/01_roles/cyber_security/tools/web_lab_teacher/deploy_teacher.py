"""CloudShell deployment; preserves existing Web keys and never targets Linux."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets

import boto3
from botocore.exceptions import ClientError

STACK = "jdu-web-progress-2026"


def stack_or_none(client):
    try:
        return client.describe_stacks(StackName=STACK)["Stacks"][0]
    except ClientError as exc:
        if (exc.response["Error"]["Code"]=="ValidationError"
                and exc.response["Error"]["Message"]==f"Stack with id {STACK} does not exist"):
            return None
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("create","status"))
    parser.add_argument("--template",default=str(Path(__file__).with_name("web-teacher.template.json")))
    parser.add_argument("--vpc-id",default="vpc-09f338ec134c8a339")
    parser.add_argument("--subnet-id",default="subnet-01b518e6362ee568e")
    args=parser.parse_args()
    os.umask(0o077)
    state=Path.home()/".jdu-web-teacher"
    state.mkdir(mode=0o700,exist_ok=True)
    cfn=boto3.client("cloudformation",region_name="us-east-1")
    account=boto3.client("sts",region_name="us-east-1").get_caller_identity()["Account"]
    old=stack_or_none(cfn)
    key_path=state/"admin.key"
    identity_path=state/"identity.json"
    if identity_path.exists():
        identity=json.loads(identity_path.read_text())
        if identity!={"account":account,"region":"us-east-1","stack_name":STACK}:
            raise ValueError("Teacher state belongs to another AWS environment")
    else:
        if old:
            raise ValueError("Existing Web stack has no matching local teacher state")
        identity_path.write_text(json.dumps({"account":account,"region":"us-east-1","stack_name":STACK}))
    if old and not key_path.exists():
        raise ValueError("Existing Web teacher key is missing; it will not be regenerated")
    if not key_path.exists():
        with os.fdopen(os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"w") as stream:
            stream.write(secrets.token_urlsafe(48))
    key=key_path.read_text().strip()
    key_hash=hashlib.sha256(key.encode()).hexdigest()
    if old:
        actual={p["ParameterKey"]:p["ParameterValue"] for p in old.get("Parameters",[])}
        # NoEcho values may be masked, so the local identity and key are retained.
        if actual.get("VpcId")!=args.vpc_id or actual.get("SubnetId")!=args.subnet_id:
            raise ValueError("Existing teacher network differs from local inputs")
    if args.command=="create":
        if old:
            raise ValueError("Web teacher stack already exists; use status, not create")
        template=Path(args.template).read_bytes()
        if len(template)>51200:
            raise ValueError("Template exceeds direct CloudFormation input limit")
        cfn.validate_template(TemplateBody=template.decode())
        parameters=[{"ParameterKey":k,"ParameterValue":v} for k,v in {
            "VpcId":args.vpc_id,"SubnetId":args.subnet_id,"AdminKeyHash":key_hash,"LambdaExecutionRoleName":"LabRole"}.items()]
        cfn.create_stack(StackName=STACK,TemplateBody=template.decode(),Parameters=parameters,DisableRollback=True)
        (state/"template.sha256").write_text(hashlib.sha256(template).hexdigest()+"\n")
        print(json.dumps({"stack":STACK,"stage":"CREATE_REQUESTED","credentials_printed":False}))
        return
    if not old:
        raise ValueError("Web teacher stack has not been created")
    outputs={x["OutputKey"]:x["OutputValue"] for x in old.get("Outputs",[])}
    result={"stack":STACK,"stage":old["StackStatus"],"proxy_live_acceptance":False}
    if old["StackStatus"]=="CREATE_COMPLETE":
        function=cfn.describe_stack_resource(StackName=STACK,LogicalResourceId="ProgressFunction")["StackResourceDetail"]["PhysicalResourceId"]
        variables=boto3.client("lambda",region_name="us-east-1").get_function_configuration(FunctionName=function)["Environment"]["Variables"]
        if variables.get("ADMIN_KEY_HASH")!=key_hash:
            raise ValueError("Saved teacher key differs from the deployed API")
        config={"schema_version":1,"api_base_url":outputs["ApiBaseUrl"],
                "fixed_ingress_ipv4":outputs["FixedIngressIpv4"],"release_id":"web-2026-10-r1","admin_key":key}
        (state/"teacher.credentials.json").write_text(json.dumps(config,indent=2)+"\n")
        result.update(api_base_url=outputs["ApiBaseUrl"],fixed_ingress_ipv4=outputs["FixedIngressIpv4"],
                      teacher_instance_id=outputs["TeacherInstanceId"],config_saved=True)
    print(json.dumps(result))


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        # Never forward SDK request data or key material into ordinary logs.
        print("TEACHER_DEPLOY_FAILED="+type(exc).__name__)
        raise SystemExit(2)
