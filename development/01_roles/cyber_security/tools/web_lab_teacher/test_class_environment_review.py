import unittest
from types import SimpleNamespace

from review_class_environment import account_guard, inspect, public_subnets


class EnvironmentReviewTests(unittest.TestCase):
    def test_wrong_account_stops_before_inventory_calls(self):
        calls = []
        def client(name, **kwargs):
            calls.append(name)
            if name != "sts":
                self.fail("Inventory accessed before wrong-account rejection")
            return SimpleNamespace(get_caller_identity=lambda: {"Account": "144753397193"})
        with self.assertRaises(ValueError):
            inspect(SimpleNamespace(client=client), 193548, "student", excluded=["144753397193"])
        self.assertEqual(calls, ["sts"])

    def test_expected_account_must_match(self):
        account_guard("123456789012", "123456789012")
        for actual, expected in [("123456789012", "123456789013"), ("invalid", None)]:
            with self.assertRaises(ValueError):
                account_guard(actual, expected)

    def test_explicit_private_route_overrides_public_main(self):
        subnets = [{"SubnetId": "public", "VpcId": "v", "State": "available",
                    "AvailabilityZone": "az", "AvailableIpAddressCount": 240},
                   {"SubnetId": "private", "VpcId": "v", "State": "available",
                    "AvailabilityZone": "az", "AvailableIpAddressCount": 240}]
        tables = [{"VpcId": "v", "Associations": [{"Main": True}], "Routes": [
            {"DestinationCidrBlock": "0.0.0.0/0", "State": "active", "GatewayId": "igw"}]},
            {"VpcId": "v", "Associations": [{"SubnetId": "private"}], "Routes": []}]
        gateways = [{"InternetGatewayId": "igw", "Attachments": [{"VpcId": "v", "State": "available"}]}]
        self.assertEqual([s["SubnetId"] for s in public_subnets(subnets, tables, gateways)], ["public"])
        self.assertEqual(public_subnets(subnets, tables, []), [])

    def test_missing_teacher_stack_does_not_create_credentials(self):
        allowed = {"sts": {"get_caller_identity"}, "ec2": {
            "get_paginator", "describe_images", "describe_subnets", "describe_route_tables",
            "describe_internet_gateways"}, "iam": {"get_instance_profile", "get_role"},
            "cloudformation": {"get_paginator"}}
        class ReadOnlyClient:
            def __init__(self, service): self.service = service
            def __getattr__(self, method):
                if method not in allowed[self.service]:
                    raise AssertionError("Unexpected API: " + method)
                def call(**kwargs):
                    if method == "get_caller_identity": return {"Account": "123456789012"}
                    if method == "describe_images": return {"Images": []}
                    if method == "describe_subnets": return {"Subnets": []}
                    if method == "describe_route_tables": return {"RouteTables": []}
                    if method == "describe_internet_gateways": return {"InternetGateways": []}
                    if method == "get_role": return {"Role": {"RoleName": "LabRole"}}
                    if method == "get_instance_profile": return {"InstanceProfile": {
                        "InstanceProfileName": "LabInstanceProfile", "Roles": [{"RoleName": "LabRole"}]}}
                if method == "get_paginator":
                    def paginate(name):
                        if name == "describe_instances":
                            return SimpleNamespace(paginate=lambda **kw: [{"Reservations": []}])
                        if name == "list_stacks":
                            return SimpleNamespace(paginate=lambda **kw: [{"StackSummaries": []}])
                        raise AssertionError("Unexpected paginator")
                    return paginate
                return call
        session = SimpleNamespace(client=lambda name, **kw: ReadOnlyClient(name))
        for role, proposed in [("teacher", 1), ("student", 5)]:
            report = inspect(session, 193548, role)
            self.assertEqual(report["aws_mutations"], 0)
            self.assertEqual(report["lab_credentials_created_or_read"], 0)
            self.assertFalse(report["official_fixed_ami_available"])
            self.assertEqual(report["web_stacks"], [])
            self.assertEqual(report["conservative_resource_plan"]["proposed_new_instances"], proposed)
            self.assertFalse(report["deployment_approved"])


if __name__ == "__main__":
    unittest.main()
