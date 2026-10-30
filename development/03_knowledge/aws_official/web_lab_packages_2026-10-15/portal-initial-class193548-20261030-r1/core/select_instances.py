"""Read-only EC2/price discovery and a same-family, single-AZ Web Lab plan."""

import argparse
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import subprocess
import sys


SIZES = {"micro": (1024, 1), "small": (2048, 1), "medium": (4096, 2)}
ROLES = {"Bastion": "medium", "Web": "small", "Dns": "micro",
         "Db": "small", "Package": "small"}
TYPE = re.compile(r"(t[1-9][0-9]*[a-z]*)\.(micro|small|medium)")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def positive_price(value):
    try:
        price = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid hourly price") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError("Hourly prices must be positive finite USD values")
    return price


def compatible_types(items):
    result = {}
    for item in items:
        name = item["InstanceType"]
        match = TYPE.fullmatch(name)
        if not match or "x86_64" not in item["ProcessorInfo"]["SupportedArchitectures"]:
            continue
        memory, cpus = SIZES[match[2]]
        if (item["MemoryInfo"]["SizeInMiB"] < memory
                or item["VCpuInfo"]["DefaultVCpus"] < cpus
                or "hvm" not in item.get("SupportedVirtualizationTypes", [])
                or "ebs" not in item.get("SupportedRootDeviceTypes", [])):
            continue
        result[name] = item
    return result


def feasible_pairs(data, exclude_families=(), exclude_pairs=()):
    metadata = compatible_types(data["instance_types"])
    zones = {z["ZoneName"]: z for z in data["zones"]
             if z["State"] == "available" and z.get("ZoneType", "availability-zone") == "availability-zone"}
    offered = {(o["InstanceType"], o["Location"]) for o in data["offerings"]}
    families = {TYPE.fullmatch(name)[1] for name in metadata} - set(exclude_families)
    pairs = []
    for family in families:
        for az, zone in zones.items():
            if f"{family}@{az}" in exclude_pairs:
                continue
            if all(f"{family}.{size}" in metadata
                   and (f"{family}.{size}", az) in offered for size in SIZES):
                pairs.append((family, az, zone.get("ZoneId", az)))
    if not pairs:
        raise ValueError("No x86_64 T-family has micro/small/medium together in one available AZ")
    return metadata, pairs


def select_plan(data, exclude_families=(), exclude_pairs=()):
    metadata, pairs = feasible_pairs(data, exclude_families, exclude_pairs)
    required = {f"{family}.{size}" for family, _, _ in pairs for size in SIZES}
    missing = required - data["prices"].keys()
    if missing:
        raise ValueError("Cannot compare all feasible candidates; missing prices: " + ", ".join(sorted(missing)))
    prices = {name: positive_price(data["prices"][name]) for name in required}
    ranked = []
    for family, az, az_id in pairs:
        hourly = sum((prices[f"{family}.{size}"] for size in ROLES.values()), Decimal(0))
        ranked.append((hourly, family, az_id, az))
    ranked.sort()
    hourly, family, az_id, az = ranked[0]
    roles = {role: {"instance_type": f"{family}.{size}",
                    "hourly_usd": str(prices[f"{family}.{size}"]),
                    "memory_mib": metadata[f"{family}.{size}"]["MemoryInfo"]["SizeInMiB"],
                    "vcpus": metadata[f"{family}.{size}"]["VCpuInfo"]["DefaultVCpus"]}
             for role, size in ROLES.items()}
    parameters = [{"ParameterKey": "LabAvailabilityZone", "ParameterValue": az}]
    parameters.extend({"ParameterKey": role + "InstanceType", "ParameterValue": value["instance_type"]}
                      for role, value in roles.items())
    return {"schema_version": 1, "region": data["region"], "selected_at": stamp(),
            "selection_mode": "new", "architecture": "x86_64", "credit_mode": "standard",
            "family": family, "availability_zone": az, "availability_zone_id": az_id,
            "roles": roles, "compute_hourly_usd": str(hourly),
            "price_source": data.get("price_source", "offline test input"),
            "cloudformation_parameters": parameters,
            "ranked_candidates": [{"family": f, "availability_zone": z,
                                   "compute_hourly_usd": str(p)} for p, f, _, z in ranked],
            "limitations": ["Offering is not a capacity reservation or a Lab authorization check.",
                            "Prices cover Linux/Shared On-Demand compute only; EBS/IPv4/etc. are separate.",
                            "Reuse the deployed AZ/types on updates and stop/start."]}


def aws_json(service, operation, region, *args):
    # A fixed argument list, no shell, no provisioning or credential printing.
    command = ["aws", service, operation, "--region", region, "--output", "json",
               "--no-cli-pager", "--cli-connect-timeout", "10", "--cli-read-timeout", "20", *args]
    env = dict(os.environ, AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off", AWS_MAX_ATTEMPTS="2")
    try:
        response = subprocess.run(command, capture_output=True, text=True, timeout=50, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"AWS CLI unavailable or timed out: {service} {operation}") from exc
    if response.returncode:
        raise ValueError(f"AWS read failed: {service} {operation}; check Lab permissions/session. No resources were changed.")
    return json.loads(response.stdout)


def price_from_products(products, region, name):
    rates = set()
    expected = {"regionCode": region, "instanceType": name, "operatingSystem": "Linux",
                "tenancy": "Shared", "preInstalledSw": "NA", "capacitystatus": "Used"}
    now = datetime.now(timezone.utc)
    for encoded in products:
        product = json.loads(encoded) if isinstance(encoded, str) else encoded
        if product["product"].get("productFamily") != "Compute Instance":
            continue
        attributes = product["product"]["attributes"]
        if any(attributes.get(key) != value for key, value in expected.items()):
            continue
        for term in product.get("terms", {}).get("OnDemand", {}).values():
            effective = datetime.fromisoformat(term["effectiveDate"].replace("Z", "+00:00"))
            if effective > now:
                continue
            for dimension in term["priceDimensions"].values():
                if (dimension.get("unit") == "Hrs" and dimension.get("beginRange") == "0"
                        and dimension.get("endRange") == "Inf"):
                    rates.add(positive_price(dimension["pricePerUnit"]["USD"]))
    if len(rates) != 1:
        raise ValueError(f"Missing or ambiguous Linux/Shared On-Demand hourly price: {name}")
    return str(rates.pop())


def load_catalog(path, region):
    catalog = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if catalog["region"] != region or catalog["currency"] != "USD" or catalog["source"] != "AWS Price List":
        raise ValueError("Price catalog must identify its region, USD and AWS Price List source")
    collected = datetime.fromisoformat(catalog["collected_at"].replace("Z", "+00:00"))
    if collected.tzinfo is None:
        raise ValueError("Price catalog timestamp must include a timezone")
    age = datetime.now(timezone.utc) - collected
    if age < timedelta(0) or age > timedelta(days=7):
        raise ValueError("Teacher price catalog must be no more than seven days old, not future dated")
    return catalog


def discover(region, catalog_path, exclude_families, exclude_pairs):
    filters = ["Name=instance-type,Values=t*.micro,t*.small,t*.medium",
               "Name=processor-info.supported-architecture,Values=x86_64"]
    data = {"region": region,
            "instance_types": aws_json("ec2", "describe-instance-types", region, "--filters", *filters)["InstanceTypes"],
            "zones": aws_json("ec2", "describe-availability-zones", region,
                              "--filters", "Name=state,Values=available")["AvailabilityZones"],
            "offerings": aws_json("ec2", "describe-instance-type-offerings", region,
                                  "--location-type", "availability-zone", "--filters", filters[0])["InstanceTypeOfferings"]}
    _, pairs = feasible_pairs(data, exclude_families, exclude_pairs)
    required = sorted({f"{family}.{size}" for family, _, _ in pairs for size in SIZES})
    if catalog_path:
        catalog = load_catalog(catalog_path, region)
        data.update(prices=catalog["prices"], price_source={"kind": "teacher AWS Price List catalog",
                    "collected_at": catalog["collected_at"]})
    else:
        data["prices"] = {}
        for name in required:
            attrs = {"regionCode": region, "instanceType": name, "operatingSystem": "Linux",
                     "tenancy": "Shared", "preInstalledSw": "NA", "capacitystatus": "Used"}
            query = [{"Type": "TERM_MATCH", "Field": key, "Value": value} for key, value in attrs.items()]
            products = aws_json("pricing", "get-products", "us-east-1", "--service-code", "AmazonEC2",
                                "--filters", json.dumps(query))["PriceList"]
            data["prices"][name] = price_from_products(products, region, name)
        data["price_source"] = {"kind": "AWS Price List Query API", "collected_at": stamp()}
    return data


def reuse_plan(path, region):
    plan = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if (plan.get("schema_version") != 1 or plan.get("region") != region
            or plan.get("architecture") != "x86_64" or set(plan.get("roles", {})) != set(ROLES)):
        raise ValueError("Existing plan has incompatible schema/region/architecture/roles")
    for role, size in ROLES.items():
        if plan["roles"][role]["instance_type"] != f"{plan['family']}.{size}":
            raise ValueError("Existing plan has inconsistent role types")
    result = copy.deepcopy(plan)
    result["selection_mode"] = "reused_without_reselection"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-1")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--snapshot", help="Offline test JSON; never queries AWS")
    mode.add_argument("--existing-plan", help="Reuse a saved deployed plan without selecting again")
    parser.add_argument("--price-catalog", help="Teacher's region-specific AWS price catalog (max age seven days)")
    parser.add_argument("--exclude-family", action="append", default=[])
    parser.add_argument("--exclude-pair", action="append", default=[], help="Explicitly exclude FAMILY@AZ")
    parser.add_argument("--output", help="New JSON file; refuses to overwrite an existing plan")
    args = parser.parse_args(argv)
    try:
        if args.existing_plan:
            if args.price_catalog or args.exclude_family or args.exclude_pair:
                raise ValueError("Existing plans cannot be repriced or reselected with exclusions")
            plan = reuse_plan(args.existing_plan, args.region)
        else:
            if args.snapshot and args.price_catalog:
                raise ValueError("Offline snapshots already contain prices")
            data = (json.loads(Path(args.snapshot).read_text(encoding="utf-8-sig")) if args.snapshot
                    else discover(args.region, args.price_catalog, args.exclude_family, args.exclude_pair))
            if data["region"] != args.region:
                raise ValueError("Snapshot region differs from requested region")
            plan = select_plan(data, args.exclude_family, args.exclude_pair)
            if args.snapshot:
                plan["selection_mode"] = "offline_test_only"
        serialized = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with Path(args.output).open("x", encoding="utf-8") as target:
                target.write(serialized)
        else:
            sys.stdout.write(serialized)
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
