"""Inspect an unmodified Ubuntu EC2 base without installing packages or using the network.

Used only as temporary teacher probe UserData, not student initialization.
The full report is gzip/base64 encoded for EC2 console retrieval.
"""

import base64
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile


def run(arguments, timeout=20):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout)
        return {"returncode": result.returncode, "text": (result.stdout or result.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired):
        return {"returncode": -1, "text": "unavailable_or_timeout"}


def main():
    os.umask(0o077)
    os_release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    packages = run(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${db:Status-Status}\n"])
    inventory = [line.split("\t")[:2] for line in packages["text"].splitlines()
                 if len(line.split("\t")) == 3 and line.split("\t")[2] == "installed"]
    commands = {
        "bash": ["bash", "--version"], "python3": ["python3", "--version"],
        "cloud-init": ["cloud-init", "--version"], "curl": ["curl", "--version"],
        "gpg": ["gpg", "--version"], "gpgv": ["gpgv", "--version"],
        "openssl": ["openssl", "version"], "tar": ["tar", "--version"],
        "gzip": ["gzip", "--version"], "xz": ["xz", "--version"],
        "flock": ["flock", "--version"], "timeout": ["timeout", "--version"],
        "dpkg": ["dpkg", "--version"], "apt-get": ["apt-get", "--version"],
        "ssh": ["ssh", "-V"], "ssh-keygen": None, "sshd": None,
        "sha256sum": ["sha256sum", "--version"], "aws": None, "cfn-signal": None,
    }
    tools = {}
    for name, arguments in commands.items():
        path = shutil.which(name)
        result = run(arguments) if path and arguments else None
        tools[name] = {"path": path, "returncode": result["returncode"] if result else None,
                       "version": result["text"].splitlines()[:1] if result else []}
    crypto = {"sha256": hashlib.sha256(b"jdu-probe").hexdigest()}
    try:
        crypto["ca_count"] = len(ssl.create_default_context().get_ca_certs())
    except Exception:
        crypto["ca_count"] = 0
    archive_test = False
    with tempfile.TemporaryDirectory(prefix="jdu-ami-tar-") as directory:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            info = tarfile.TarInfo("fixture.txt")
            content = b"jdu-local-archive-test\n"
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        stream.seek(0)
        try:
            with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                archive.extractall(directory, filter="data")
            archive_test = (Path(directory) / "fixture.txt").read_bytes() == content
        except Exception:
            pass
    installed = {name.split(":")[0]: version for name, version in inventory}
    forbidden = [name for name in ("bind9", "nginx", "nginx-core", "nginx-full", "postgresql-16", "xrdp", "firefox") if name in installed]
    required = ("bash", "python3", "cloud-init", "curl", "gpg", "openssl", "tar", "gzip", "flock", "timeout", "dpkg", "apt-get", "sha256sum")
    checks = {
        "ubuntu_24_04": os_release.get("ID", "").strip('"') == "ubuntu" and os_release.get("VERSION_ID", "").strip('"') == "24.04",
        "x86_64": platform.machine() == "x86_64", "python_3_12_or_newer": sys.version_info >= (3, 12),
        "required_commands": all(tools[name]["path"] and tools[name]["returncode"] == 0 for name in required),
        "tls_ca_available": crypto["ca_count"] > 0, "tar_data_filter_works": archive_test,
        "target_services_absent": not forbidden, "package_inventory_collected": packages["returncode"] == 0 and len(inventory) > 100,
    }
    report = {"schema_version": 1, "scope": "ubuntu_base_probe_only", "collected_at": datetime.now(timezone.utc).isoformat(),
              "os_release": os_release, "architecture": platform.machine(), "kernel": platform.release(),
              "python": sys.version, "tools": tools, "crypto": crypto, "checks": checks,
              "unexpected_packages": forbidden, "package_count": len(inventory), "packages": inventory,
              "disk": {"total": shutil.disk_usage("/").total, "free": shutil.disk_usage("/").free}}
    data = json.dumps(report, sort_keys=True).encode()
    print("JDU_AMI_BASE_SUMMARY=" + json.dumps({"checks": checks, "package_count": len(inventory), "tools": tools}), flush=True)
    print("JDU_AMI_BASE_SHA256=" + hashlib.sha256(data).hexdigest(), flush=True)
    print("JDU_AMI_BASE_REPORT=" + base64.b64encode(gzip.compress(data, mtime=0)).decode(), flush=True)
    print("JDU_AMI_BASE_DONE", flush=True)


if __name__ == "__main__":
    main()
