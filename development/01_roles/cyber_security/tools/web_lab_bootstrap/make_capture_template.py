"""Generate the teacher-only, outbound-only dependency collector template."""

import base64
import gzip
import json
from pathlib import Path


def make_template(directory=None):
    directory = Path(directory or Path(__file__).parent)
    files = []
    for name in ("collect_packages.py", "package-profile.json"):
        files.append({"path": "/var/lib/jdu-web-collector/" + name,
                      "owner": "root:root", "permissions": "0600", "encoding": "gz+b64",
                      "content": base64.b64encode(gzip.compress((directory / name).read_bytes(), mtime=0)).decode()})
    files.append({"path": "/var/lib/jdu-web-collector/upload-config.json", "owner": "root:root",
                  "permissions": "0600", "encoding": "b64", "content": "${UploadConfigBase64}"})
    config = {"package_update": False, "package_upgrade": False, "write_files": files,
              "bootcmd": [["bash", "-c", "shutdown -P +90 >/dev/null 2>&1"]],
              "runcmd": [["bash", "-c", "set -o pipefail; timeout 3600 python3 /var/lib/jdu-web-collector/collect_packages.py --profile /var/lib/jdu-web-collector/package-profile.json --output /srv/jdu-capture --upload-config /var/lib/jdu-web-collector/upload-config.json 2>&1 | tee /var/log/jdu-web-collector.log > /dev/ttyS0"]],
              "power_state": {"mode": "poweroff", "delay": 10, "timeout": 60, "condition": True},
              "final_message": "JDU_CAPTURE_CLOUD_INIT_FINAL"}
    user_data = "#cloud-config\n" + json.dumps(config) + "\n"
    if len(user_data.encode()) >= 16384:
        raise ValueError("Collector UserData exceeds 16 KiB")
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Teacher dependency collector only. No inbound or IAM; temporary Internet HTTP/HTTPS, public IPv4; encrypted 32 GiB. Never a student template.",
        "Parameters": {"VpcId": {"Type": "AWS::EC2::VPC::Id"},
                       "SubnetId": {"Type": "AWS::EC2::Subnet::Id"},
                       "UploadConfigBase64": {"Type": "String", "NoEcho": True, "AllowedPattern": "^[A-Za-z0-9+/=]+$"}},
        "Resources": {
            "CollectorSecurityGroup": {"Type": "AWS::EC2::SecurityGroup", "Properties": {
                "VpcId": {"Ref": "VpcId"}, "GroupDescription": "Teacher capture: no inbound; download-only HTTP HTTPS",
                "SecurityGroupIngress": [], "SecurityGroupEgress": [
                    {"IpProtocol": "tcp", "FromPort": port, "ToPort": port, "CidrIp": "0.0.0.0/0"} for port in (80, 443)]}},
            "CollectorInstance": {"Type": "AWS::EC2::Instance", "Properties": {
                "ImageId": "ami-0fa5967347d08d2df", "InstanceType": "t3a.small",
                "CreditSpecification": {"CPUCredits": "standard"},
                "MetadataOptions": {"HttpTokens": "required", "HttpEndpoint": "enabled", "HttpPutResponseHopLimit": 1},
                "InstanceInitiatedShutdownBehavior": "stop",
                "BlockDeviceMappings": [{"DeviceName": "/dev/sda1", "Ebs": {
                    "VolumeSize": 32, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True}}],
                "NetworkInterfaces": [{"DeviceIndex": "0", "SubnetId": {"Ref": "SubnetId"},
                    "AssociatePublicIpAddress": True, "GroupSet": [{"Ref": "CollectorSecurityGroup"}]}],
                "UserData": {"Fn::Base64": {"Fn::Sub": user_data}},
                "Tags": [{"Key": "Name", "Value": "jdu-web-teacher-collector-20261015"},
                         {"Key": "Purpose", "Value": "teacher-package-capture-only"}]}}
        },
        "Outputs": {"CollectorInstanceId": {"Value": {"Ref": "CollectorInstance"}},
                    "CollectorSecurityGroupId": {"Value": {"Ref": "CollectorSecurityGroup"}}}}


if __name__ == "__main__":
    destination = Path(__file__).with_name("teacher-capture.template.json")
    destination.write_text(json.dumps(make_template(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(destination.name)
