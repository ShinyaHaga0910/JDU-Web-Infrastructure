"""Read the official us-east-1 EC2 CSV into a fresh T-family price catalog."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import urllib.request

URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv"
TYPE = re.compile(r"t[1-9][0-9]*[a-z]*\.(micro|small|medium)")


def parse(lines, now):
    reader = csv.reader(lines)
    metadata = [next(reader) for _ in range(5)]
    meta = dict(metadata)
    if meta.get("OfferCode") != "AmazonEC2" or meta.get("FormatVersion") != "v1.0":
        raise ValueError("Unexpected AWS price list metadata")
    published = datetime.fromisoformat(meta["Publication Date"].replace("Z", "+00:00"))
    if published.tzinfo is None or published > now:
        raise ValueError("Future-dated AWS price list")
    header = next(reader)
    fields = {name: index for index, name in enumerate(header)}
    expected = {"TermType": "OnDemand", "Product Family": "Compute Instance", "serviceCode": "AmazonEC2",
        "Region Code": "us-east-1", "Tenancy": "Shared", "Operating System": "Linux", "Pre Installed S/W": "NA",
        "CapacityStatus": "Used", "Unit": "Hrs", "StartingRange": "0", "EndingRange": "Inf", "Currency": "USD",
        "operation": "RunInstances"}
    for name in (*expected, "Instance Type", "EffectiveDate", "PricePerUnit", "SKU", "RateCode"):
        if name not in fields: raise ValueError("AWS price list fields changed")
    rows = []; prices = {}
    for values in reader:
        if len(values) != len(header): raise ValueError("Incomplete AWS CSV row")
        name = values[fields["Instance Type"]]
        if not TYPE.fullmatch(name) or any(values[fields[k]] != v for k, v in expected.items()): continue
        effective = datetime.fromisoformat(values[fields["EffectiveDate"]].replace("Z", "+00:00"))
        if effective.tzinfo is None: effective = effective.replace(tzinfo=timezone.utc)
        if effective > now: continue
        price = Decimal(values[fields["PricePerUnit"]])
        if not price.is_finite() or price <= 0: raise ValueError("Invalid AWS hourly price")
        if name in prices and Decimal(prices[name]) != price: raise ValueError("Ambiguous AWS hourly price")
        prices[name] = str(price)
        rows.append(dict(zip(header, values)))
    if not prices: raise ValueError("No matching AWS T-family prices")
    return metadata, rows, dict(sorted(prices.items()))


def collect(output, evidence):
    if any(p.exists() or not p.parent.is_dir() for p in (output, evidence)):
        raise ValueError("Use new files in existing directories")
    digest = hashlib.sha256(); size = 0
    with urllib.request.urlopen(URL, timeout=30) as response:
        if response.status != 200 or response.geturl() != URL: raise ValueError("Expected official AWS CSV")
        length = int(response.headers.get("Content-Length", "0"))
        if not 0 < length <= 1024 * 1024 * 1024: raise ValueError("Price list length unavailable or excessive")
        modified = response.headers.get("Last-Modified")
        def lines():
            nonlocal size
            for raw in response:
                size += len(raw)
                if size > length: raise ValueError("Price list length changed")
                digest.update(raw)
                yield raw.decode("utf-8-sig")
        metadata, rows, prices = parse(lines(), datetime.now(timezone.utc))
    if size != length: raise ValueError("Truncated AWS price list")
    facts = dict(source_url=URL, source_last_modified=modified, source_sha256=digest.hexdigest(), source_size_bytes=size)
    catalog = dict(region="us-east-1", currency="USD", source="AWS Price List",
        collected_at=datetime.now(timezone.utc).isoformat(), prices=prices, **facts)
    for path, value in ((evidence, dict(csv_metadata=metadata, rows=rows, **facts)), (output, catalog)):
        with path.open("x", encoding="utf-8", newline="\n") as stream: json.dump(value, stream, indent=2); stream.write("\n")
    print(json.dumps(dict(scope="official_ec2_price_list_refresh", types=len(prices), source_bytes=size,
        source_sha256=facts["source_sha256"], catalog_sha256=hashlib.sha256(output.read_bytes()).hexdigest())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output, args.evidence)
