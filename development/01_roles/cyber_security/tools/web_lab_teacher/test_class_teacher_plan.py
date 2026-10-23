import copy
from datetime import datetime, timedelta, timezone
import unittest

from prepare_class_teacher import distribution_template, validate_review


class TeacherPlanTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)
        self.report = dict(scope="read_only_class_environment_inventory_not_deployment_approval",
            checked_at=self.now.isoformat(), aws_account="170126527713", operator_class_id=193548,
            operator_role="teacher", region="us-east-1", official_fixed_ami_available=True,
            existing_lab_role_present=True, existing_lab_instance_profile_matches=True,
            nonterminated_instances=[], web_stacks=[], public_subnet_candidates=[
                dict(SubnetId="subnet-test", VpcId="vpc-test", AvailabilityZone="us-east-1b",
                     AvailableIpAddressCount=100)])

    def verify(self, value):
        return validate_review(value, "170126527713", 193548, "subnet-test", self.now)

    def test_fresh_matching_teacher(self):
        self.assertEqual(self.verify(self.report)["VpcId"], "vpc-test")

    def test_other_identity_role_or_stale_report_rejected(self):
        for key, value in [("aws_account", "965244652544"), ("operator_class_id", 188571),
                           ("operator_role", "student"),
                           ("checked_at", (self.now - timedelta(hours=1)).isoformat()),
                           ("existing_lab_role_present", False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(dict(self.report, **{key: value}))

    def test_existing_stack_or_wrong_subnet_and_budget_rejected(self):
        for values in [dict(web_stacks=[dict(stack_name="jdu-web-progress-2026")]),
                       dict(public_subnet_candidates=[]), dict(nonterminated_instances=[{}] * 9)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.verify(dict(self.report, **values))

    def test_new_bucket_is_private_and_original_resources_unchanged(self):
        base = dict(Resources=dict(Existing=dict(Type="example", Properties=dict(Value="kept"))), Outputs={})
        original = copy.deepcopy(base)
        template, bucket = distribution_template(base, "170126527713", 193548)
        self.assertEqual(base, original)
        self.assertEqual(template["Resources"]["Existing"], base["Resources"]["Existing"])
        resource = template["Resources"]["DistributionBucket"]
        self.assertEqual(bucket, "jdu-web-class193548-170126527713")
        self.assertTrue(all(resource["Properties"]["PublicAccessBlockConfiguration"].values()))
        self.assertEqual(resource["DeletionPolicy"], "Retain")
        self.assertNotIn("BucketPolicy", resource["Properties"])


if __name__ == "__main__": unittest.main()
