import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock

import install_teacher as installer


class InstallTeacherTests(TestCase):
    def test_template_uses_fresh_network_and_bucket(self):
        raw = Path(__file__).with_name("web-teacher.template.json").read_text(encoding="utf-8").encode()
        with mock.patch.object(installer.subprocess, "check_output", return_value=raw):
            template = json.loads(installer.load_template("us-east-1b", "t3.small"))
        resources = template["Resources"]
        self.assertNotIn("VpcId", template["Parameters"])
        self.assertNotIn("SubnetId", template["Parameters"])
        self.assertEqual(resources["TeacherInstance"]["Properties"]["NetworkInterfaces"][0]["SubnetId"],
                         {"Ref": "TeacherSubnet"})
        self.assertEqual(resources["TeacherSubnet"]["Properties"]["AvailabilityZone"], "us-east-1b")
        self.assertEqual(resources["TeacherInstance"]["Properties"]["InstanceType"], "t3.small")
        self.assertEqual(resources["TeacherRouteTable"]["Properties"]["VpcId"], {"Ref": "TeacherVpc"})
        self.assertNotIn("BucketName", resources["DistributionBucket"]["Properties"])
        self.assertTrue(all(resources["DistributionBucket"]["Properties"]["PublicAccessBlockConfiguration"].values()))
        self.assertLess(len(json.dumps(template, separators=(",", ":")).encode()), 51200)

    def test_reject_unverified_template(self):
        with mock.patch.object(installer.subprocess, "check_output", return_value=b"{}"):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                installer.load_template("us-east-1a", "t3a.small")

    def test_capacity_falls_back_to_available_alternative(self):
        ec2 = mock.Mock()
        ec2.describe_availability_zones.return_value = {"AvailabilityZones": [{"ZoneName": "us-east-1b"}]}
        ec2.get_paginator.return_value.paginate.return_value = [{"InstanceTypeOfferings": [
            {"Location": "us-east-1a", "InstanceType": "t3a.small"},
            {"Location": "us-east-1b", "InstanceType": "t3.small"},
        ]}]
        self.assertEqual(installer.select_capacity(ec2), ("us-east-1b", "t3.small"))

    def test_https_checks_use_the_new_fixed_ip_and_reject_an_open_dashboard(self):
        hostname = "newexample.execute-api.us-east-1.amazonaws.com"
        outputs = {"ApiBaseUrl": f"https://{hostname}", "FixedIngressIpv4": "192.0.2.10",
                   "DistributionBucket": "new-bucket", "TableName": "new-table"}
        stack = {"Outputs": [{"OutputKey": key, "OutputValue": value} for key, value in outputs.items()]}
        session = mock.Mock()
        client = session.client.return_value
        client.get_public_access_block.return_value = {"PublicAccessBlockConfiguration": installer.PUBLIC_ACCESS_BLOCK}
        client.get_bucket_encryption.return_value = {"ServerSideEncryptionConfiguration": {"Rules": [
            {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}},
        ]}}
        client.describe_table.return_value = {"Table": {"TableStatus": "ACTIVE"}}
        health = mock.Mock(returncode=0, stdout=b'{"ok":true,"service":"jdu-web-progress"}')
        with mock.patch.object(installer.subprocess, "run", return_value=health) as request, \
                mock.patch.object(installer.subprocess, "check_output", side_effect=[b"401", b"200"]), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(installer.verify_services(session, stack), outputs)
            with self.assertRaisesRegex(ValueError, "拒否されません"):
                installer.verify_services(session, stack)
        self.assertIn(f"{hostname}:443:192.0.2.10", request.call_args.args[0])

    def test_existing_unowned_stack_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as directory:
            cfn = mock.Mock()
            with mock.patch.object(installer, "find_stack", return_value={"StackStatus": "CREATE_COMPLETE"}):
                with self.assertRaisesRegex(ValueError, "構築記録がありません"):
                    installer.install(mock.Mock(), cfn, mock.Mock(), "246801357924", "24680", "new", Path(directory))
            cfn.create_stack.assert_not_called()

    def test_create_then_recheck_same_stack_for_another_teacher(self):
        account, class_id, name = "246801357924", "24680", "jdu-web-teacher-24680-test"
        stack_id = f"arn:aws:cloudformation:us-east-1:{account}:stack/{name}/test"
        stack = {"StackId": stack_id, "StackStatus": "CREATE_COMPLETE",
                 "Tags": [{"Key": installer.OWNER_TAG, "Value": "abc"}]}
        outputs = {"ApiBaseUrl": "https://api.example.test", "FixedIngressIpv4": "192.0.2.10",
                   "DistributionBucket": "fresh-test-bucket"}
        cfn = mock.Mock()
        cfn.create_stack.return_value = {"StackId": stack_id}
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(installer, "find_stack", side_effect=[None, stack, stack]), \
                mock.patch.object(installer, "select_capacity", return_value=("us-east-1b", "t3a.small")), \
                mock.patch.object(installer, "load_template", return_value="{}"), \
                mock.patch.object(installer, "preflight"), \
                mock.patch.object(installer, "verify_services", return_value=outputs) as verify, \
                mock.patch.object(installer.secrets, "token_hex", return_value="abc"), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            work = Path(directory)
            installer.install(mock.Mock(), cfn, mock.Mock(), account, class_id, name, work)
            installer.install(mock.Mock(), cfn, mock.Mock(), account, class_id, name, work)
            credentials = installer.read_private(work / "teacher.credentials.json")
            self.assertEqual(credentials["api_base_url"], outputs["ApiBaseUrl"])
            self.assertEqual((work / "teacher.credentials.json").stat().st_mode & 0o777, 0o600)
        cfn.create_stack.assert_called_once()
        cfn.get_waiter.return_value.wait.assert_called_once_with(StackName=stack_id)
        self.assertEqual(verify.call_count, 2)
