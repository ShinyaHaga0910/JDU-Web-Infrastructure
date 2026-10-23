import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import select_instances as selector


def fixture():
    data = {"region": "us-east-1", "instance_types": [], "prices": {},
            "zones": [{"ZoneName": "us-east-1a", "ZoneId": "use1-az1", "State": "available"},
                      {"ZoneName": "us-east-1b", "ZoneId": "use1-az2", "State": "available"}],
            "offerings": []}
    for family, factor, architecture in [("t2", 3, "x86_64"), ("t3", 2, "x86_64"),
                                          ("t3a", 1, "x86_64"), ("t4g", 0.1, "arm64")]:
        for size, (memory, cpus) in selector.SIZES.items():
            name = f"{family}.{size}"
            data["instance_types"].append({"InstanceType": name, "MemoryInfo": {"SizeInMiB": memory},
                "VCpuInfo": {"DefaultVCpus": cpus}, "ProcessorInfo": {"SupportedArchitectures": [architecture]},
                "SupportedVirtualizationTypes": ["hvm"], "SupportedRootDeviceTypes": ["ebs"]})
            data["prices"][name] = str(factor * {"micro": 0.01, "small": 0.02, "medium": 0.04}[size])
            for zone in data["zones"]:
                data["offerings"].append({"InstanceType": name, "Location": zone["ZoneName"]})
    return data


class SelectionTests(unittest.TestCase):
    def test_cheapest_arm_is_excluded_and_weighted_five_machine_price_is_used(self):
        plan = selector.select_plan(fixture())
        self.assertEqual(plan["family"], "t3a")
        self.assertEqual(plan["compute_hourly_usd"], "0.11")
        self.assertEqual(plan["roles"]["Bastion"]["instance_type"], "t3a.medium")
        self.assertEqual(plan["roles"]["Dns"]["instance_type"], "t3a.micro")

    def test_cheapest_family_uses_an_az_with_all_sizes(self):
        data = fixture()
        data["offerings"] = [o for o in data["offerings"]
                             if not (o["InstanceType"] == "t3a.medium" and o["Location"] == "us-east-1a")]
        self.assertEqual(selector.select_plan(data)["availability_zone"], "us-east-1b")

    def test_sizes_split_across_azs_are_not_combined(self):
        data = fixture()
        data["offerings"] = [o for o in data["offerings"] if not
            (o["InstanceType"].startswith("t3a.") and
             ((o["Location"] == "us-east-1a" and o["InstanceType"].endswith("medium")) or
              (o["Location"] == "us-east-1b" and o["InstanceType"].endswith("small"))))]
        self.assertEqual(selector.select_plan(data)["family"], "t3")

    def test_incomplete_price_data_cannot_claim_cheapest(self):
        data = fixture()
        del data["prices"]["t3.medium"]
        with self.assertRaisesRegex(ValueError, "missing prices"):
            selector.select_plan(data)

    def test_capacity_failure_can_exclude_a_pair_without_mutating_resources(self):
        data = fixture()
        before = copy.deepcopy(data)
        plan = selector.select_plan(data, exclude_pairs=["t3a@us-east-1a"])
        self.assertEqual(plan["availability_zone"], "us-east-1b")
        self.assertEqual(data, before)
        self.assertEqual(selector.select_plan(data, exclude_families=["t3a"])["family"], "t3")

    def test_family_with_insufficient_memory_is_rejected(self):
        data = fixture()
        next(i for i in data["instance_types"] if i["InstanceType"] == "t3a.medium")["MemoryInfo"]["SizeInMiB"] = 2048
        self.assertEqual(selector.select_plan(data)["family"], "t3")

    def test_existing_plan_is_preserved_and_never_calls_aws(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(selector.select_plan(fixture())), encoding="utf-8")
            out = Path(directory) / "reused.json"
            with patch.object(selector, "aws_json", side_effect=AssertionError("AWS must not be called")):
                self.assertEqual(selector.main(["--existing-plan", str(path), "--output", str(out)]), 0)
            saved, reused = json.loads(path.read_text()), json.loads(out.read_text())
            self.assertEqual(saved["cloudformation_parameters"], reused["cloudformation_parameters"])
            self.assertEqual(reused["selection_mode"], "reused_without_reselection")
            self.assertEqual(selector.main(["--existing-plan", str(path), "--output", str(path)]), 2)
            self.assertEqual(json.loads(path.read_text()), saved)

    def test_stale_teacher_catalog_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.json"
            path.write_text(json.dumps({"region": "us-east-1", "currency": "USD", "source": "AWS Price List",
                "collected_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(), "prices": {}}))
            with self.assertRaisesRegex(ValueError, "seven days"):
                selector.load_catalog(path, "us-east-1")

    def test_price_parser_rejects_reserved_windows_and_tiered_prices(self):
        attrs = {"regionCode": "us-east-1", "instanceType": "t3.small", "operatingSystem": "Linux",
                 "tenancy": "Shared", "preInstalledSw": "NA", "capacitystatus": "Used"}
        product = {"product": {"productFamily": "Compute Instance", "attributes": attrs},
                   "terms": {"OnDemand": {"term": {"effectiveDate": "2020-01-01T00:00:00Z",
                   "priceDimensions": {"d": {"unit": "Hrs", "beginRange": "0", "endRange": "Inf",
                                              "pricePerUnit": {"USD": "0.02"}}}}}}}
        windows = copy.deepcopy(product)
        windows["product"]["attributes"]["operatingSystem"] = "Windows"
        reserved = copy.deepcopy(product)
        reserved["terms"] = {"Reserved": reserved["terms"]["OnDemand"]}
        tiered = copy.deepcopy(product)
        tiered["terms"]["OnDemand"]["term"]["priceDimensions"]["d"]["endRange"] = "100"
        self.assertEqual(selector.price_from_products([windows, reserved, tiered, json.dumps(product)],
                                                     "us-east-1", "t3.small"), "0.02")


if __name__ == "__main__":
    unittest.main()
