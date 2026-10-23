"""Teacher-only capture on the fixed Ubuntu AMI; no student host uses this tool.

Run as root on a new disposable collector with outbound HTTP/HTTPS. APT verifies
upstream signed indexes. Resolve against an empty dpkg status so dependencies
already installed on the collector cannot silently disappear from the payload.
"""

import argparse
import csv
from datetime import datetime, timezone
import email
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile


def run(command, *, capture=False, cwd=None):
    return subprocess.run(command, check=True, text=True, cwd=cwd,
                          stdout=subprocess.PIPE if capture else None,
                          env=dict(os.environ, DEBIAN_FRONTEND="noninteractive",
                                   LC_ALL="C", APT_LISTCHANGES_FRONTEND="none")).stdout


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def wheel_lock(wheelhouse, output):
    rows = []
    names = set()
    for path in sorted(Path(wheelhouse).glob("*.whl")):
        with zipfile.ZipFile(path) as archive:
            metadata_paths = [p for p in archive.namelist() if p.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise ValueError("Invalid wheel metadata")
            metadata = email.message_from_bytes(archive.read(metadata_paths[0]))
        name = re.sub(r"[-_.]+", "-", metadata["Name"]).lower()
        version = metadata["Version"]
        if not re.fullmatch(r"[a-z0-9-]+", name) or not re.fullmatch(r"[A-Za-z0-9.!+_-]+", version) or name in names:
            raise ValueError("Ambiguous wheel version or duplicate project")
        names.add(name)
        rows.append({"name": name, "version": version, "filename": path.name,
                     "sha256": digest(path), "size_bytes": path.stat().st_size})
    if not {"django", "gunicorn", "psycopg", "psycopg-binary"} <= names:
        raise ValueError("Required Python distributions are missing")
    Path(output).write_text("".join(f'{r["name"]}=={r["version"]} --hash=sha256:{r["sha256"]}\n' for r in rows))
    return rows


def collect(profile_path, destination):
    profile = json.loads(Path(profile_path).read_text())
    os_release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    if os.geteuid() != 0 or os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID", "").strip('"') != "24.04":
        raise ValueError("Capture requires root on Ubuntu 24.04")
    if platform.machine() != "x86_64" or sys.version_info[:2] != (3, 12):
        raise ValueError("Capture requires x86_64 and Python 3.12")
    destination = Path(destination).resolve()
    destination.mkdir(mode=0o755, parents=True, exist_ok=False)
    evidence = destination / "capture-evidence"
    evidence.mkdir()
    baseline = run(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${db:Status-Status}\n"], capture=True)
    (evidence / "collector-start-packages.tsv").write_text(baseline)
    save_json(evidence / "package-profile.json", profile)
    print("JDU_CAPTURE_STAGE=UPSTREAM_METADATA",flush=True)

    key = Path("/etc/apt/keyrings/jdu-builder-mozilla.asc")
    key.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen("https://packages.mozilla.org/apt/repo-signing-key.gpg", timeout=60) as response:
        key.write_bytes(response.read(100000))
    key.chmod(0o644)
    key_metadata = run(["gpg", "--batch", "--with-colons", "--show-keys", str(key)], capture=True)
    fingerprints = [line.split(":")[9] for line in key_metadata.splitlines() if line.startswith("fpr:")]
    if not fingerprints or fingerprints[0] != profile["mozilla_fingerprint"]:
        raise ValueError("Mozilla signing key fingerprint mismatch")
    Path("/etc/apt/sources.list.d/jdu-builder-mozilla.list").write_text(
        f"deb [arch=amd64 signed-by={key}] https://packages.mozilla.org/apt mozilla main\n")
    Path("/etc/apt/preferences.d/jdu-builder-mozilla").write_text(
        "Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n\n"
        "Package: firefox\nPin: release o=Ubuntu\nPin-Priority: -1\n")
    run(["apt-get", "update", "-o", "APT::Update::Error-Mode=any"])
    # These are teacher capture tools, never preinstalled on dns/db/web students.
    run(["apt-get", "install", "-y", "--no-install-recommends", *profile["roles"]["teacher_only"]])
    (evidence / "mozilla-key.asc").write_bytes(key.read_bytes())
    (evidence / "mozilla-key-metadata.txt").write_text(key_metadata)
    signed_indexes = evidence / "signed-upstream-indexes"
    signed_indexes.mkdir()
    for path in sorted(Path("/var/lib/apt/lists").glob("*InRelease")):
        (signed_indexes / path.name).write_bytes(path.read_bytes())
    (evidence / "apt-policy.txt").write_text(run(["apt-cache", "policy"], capture=True))

    apt_root = destination / "apt"
    pool = apt_root / "pool"
    pool.mkdir(parents=True)
    (pool / "partial").mkdir()
    empty_status = evidence / "empty-dpkg-status"
    empty_status.touch()
    targets = sorted({p for group in profile["roles"].values() for p in group})
    options = ["-o", f"Dir::State::status={empty_status}", "-o", f"Dir::Cache::archives={pool}",
               "-o", f"APT::Install-Recommends={'true' if profile['install_recommends'] else 'false'}"]
    plan = run(["apt-get", *options, "--print-uris", "--yes", "--download-only", "install", *targets], capture=True)
    (evidence / "apt-download-plan.txt").write_text(plan)
    run(["apt-get", *options, "--yes", "--download-only", "install", *targets])
    print("JDU_CAPTURE_STAGE=DEBIAN_INVENTORY",flush=True)
    uris = {}
    for line in plan.splitlines():
        match = re.match(r"^'([^']+)'\s+(\S+)\s+(\d+)\s+(\S+)", line)
        if match:
            parsed = urllib.parse.urlsplit(match[1])
            if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
                raise ValueError("Unexpected APT download source")
            uris[match[2]] = match[1]
            uris[urllib.parse.unquote(match[2])] = match[1]
    packages = []
    for path in sorted(pool.glob("*.deb")):
        fields = run(["dpkg-deb", "-f", str(path), "Package", "Version", "Architecture"], capture=True)
        metadata = dict(line.split(": ", 1) for line in fields.splitlines())
        if metadata["Architecture"] not in ("amd64", "all"):
            raise ValueError("Non-amd64 package in release")
        source = uris.get(path.name)
        if not source:
            raise ValueError(f"Package provenance missing: {path.name}")
        packages.append({"package": metadata["Package"], "version": metadata["Version"],
                         "architecture": metadata["Architecture"], "path": "apt/pool/" + path.name,
                         "sha256": digest(path), "size_bytes": path.stat().st_size, "source": source})
    if not set(targets) <= {p["package"] for p in packages}:
        raise ValueError("Direct package missing from closure")
    firefox = [p for p in packages if p["package"] == "firefox"]
    if len(firefox) != 1 or urllib.parse.urlsplit(firefox[0]["source"]).hostname != "packages.mozilla.org":
        raise ValueError("Firefox must be the Mozilla DEB, not the Snap transition")
    # Empty apt bookkeeping directories are not distribution payload.
    (pool / "partial").rmdir()
    (pool / "lock").unlink(missing_ok=True)
    save_json(destination / "deb-packages.json", packages)
    print("JDU_CAPTURE_DEB_COUNT="+str(len(packages)),flush=True)
    with (destination / "deb-packages.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(packages[0]))
        writer.writeheader()
        writer.writerows(packages)

    python_root = destination / "artifacts/python"
    wheelhouse = python_root / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    venv = Path("/var/lib/jdu-web-collector/venv")
    if venv.exists():
        raise ValueError("Collector venv already exists")
    run(["python3", "-m", "venv", str(venv)])
    pip = [str(venv / "bin/python"), "-m", "pip", "--disable-pip-version-check"]
    run([*pip, "download", "--only-binary=:all:", "--dest", str(wheelhouse), *profile["python_requirements"]])
    print("JDU_CAPTURE_STAGE=OFFLINE_WHEEL_CHECK",flush=True)
    wheels = wheel_lock(wheelhouse, python_root / "requirements.lock")
    run([*pip, "install", "--no-index", "--find-links", str(wheelhouse), "--only-binary=:all:",
         "--require-hashes", "-r", str(python_root / "requirements.lock")])
    pip_check = run([*pip, "check"], capture=True)
    (evidence / "python-pip-check.txt").write_text(pip_check)
    save_json(destination / "python-packages.json", wheels)
    summary = {"schema_version": 1, "scope": "teacher_upstream_capture_not_offline_acceptance",
               "collected_at": datetime.now(timezone.utc).isoformat(), "release_id": profile["release_id"],
               "profile_sha256": digest(profile_path), "package_count": len(packages), "wheel_count": len(wheels),
               "total_deb_bytes": sum(p["size_bytes"] for p in packages),
               "empty_status_resolution": True, "python_offline_install_and_pip_check": True,
               "student_os_offline_acceptance": False}
    save_json(destination / "capture-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--upload-config", help="root-only JSON with a scoped presigned PUT URL; never printed")
    args = parser.parse_args()
    os.umask(0o022)
    try:
        summary = collect(args.profile, args.output)
        archive_path = Path(args.output).with_suffix(".tar.gz")
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(args.output, arcname="capture")
        summary.update(archive_sha256=digest(archive_path), archive_size_bytes=archive_path.stat().st_size)
        # Persist and report success before network delivery, so a failed PUT
        # cannot hide whether capture and local wheel validation completed.
        save_json(Path(args.output).parent/"capture-delivery.json",summary)
        print("JDU_CAPTURE_ARCHIVE="+json.dumps(summary,sort_keys=True),flush=True)
        if args.upload_config:
            config_path = Path(args.upload_config)
            config = json.loads(config_path.read_text())
            url = urllib.parse.urlsplit(config["put_url"])
            if url.scheme != "https" or not url.hostname.endswith(".amazonaws.com") or url.username or url.password:
                raise ValueError("Invalid scoped S3 upload URL")
            curl_config=config_path.with_name("capture-put.curl")
            curl_config.write_text("url = "+json.dumps(config["put_url"])+"\nupload-file = "+json.dumps(str(archive_path))+
                "\nrequest = \"PUT\"\nfail\nsilent\nshow-error\nconnect-timeout = 30\nmax-time = 1800\n")
            curl_config.chmod(0o600)
            try:
                upload=subprocess.run(["curl","--config",str(curl_config),"-w","%{http_code}"],capture_output=True,text=True)
                print("JDU_CAPTURE_PUT_HTTP="+upload.stdout[-3:]+" CURL_EXIT="+str(upload.returncode),flush=True)
                if upload.returncode:
                    raise ValueError("S3 object upload failed; local capture retained")
            finally:
                curl_config.unlink()
            config_path.unlink()
            summary["archive_uploaded"] = True
        print("JDU_CAPTURE_RESULT=" + json.dumps(summary, sort_keys=True), flush=True)
        return 0
    except Exception as exc:
        # Signed URLs, commands and remote error bodies must never reach console.
        print("JDU_CAPTURE_FAILED=" + type(exc).__name__, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
