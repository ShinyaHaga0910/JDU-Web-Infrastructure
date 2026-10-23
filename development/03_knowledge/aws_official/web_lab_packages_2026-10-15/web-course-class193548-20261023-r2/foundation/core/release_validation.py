"""Fail-closed local validation of the signed Web Lab deployment manifest."""

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile


class ValidationError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Invalid timestamp") from exc
    if result.tzinfo is None:
        raise ValidationError("Timestamp timezone is required")
    return result


def read_regular(path, limit):
    path = Path(path)
    if path.is_symlink():
        raise ValidationError("Symlink input is not permitted")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        with os.fdopen(os.open(path, flags), "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ValidationError("Input must be a regular file within its size limit")
            data = source.read(limit + 1)
    except OSError as exc:
        raise ValidationError("Required local file is unavailable") from exc
    if len(data) > limit:
        raise ValidationError("Input exceeds its size limit")
    return data


def json_bytes(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValidationError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValidationError("Non-finite JSON number")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValidationError("Invalid UTF-8 JSON") from exc


def validate_shape(value, rule, schema, location="manifest"):
    """Only the vocabulary used by the bundled schema, not a general JSON Schema engine."""
    if "$ref" in rule:
        reference = rule["$ref"]
        if not reference.startswith("#/$defs/"):
            raise ValidationError("Unsupported schema reference")
        return validate_shape(value, schema["$defs"][reference.split("/")[-1]], schema, location)
    expected = rule["type"]
    matches = {"object": type(value) is dict, "array": type(value) is list,
               "string": type(value) is str, "integer": type(value) is int}
    if not matches.get(expected, False):
        raise ValidationError(f"Incorrect JSON type at {location}")
    if "const" in rule and value != rule["const"]:
        raise ValidationError(f"Fixed policy value differs at {location}")
    if "enum" in rule and value not in rule["enum"]:
        raise ValidationError(f"Unsupported policy value at {location}")
    if expected == "object":
        properties = rule["properties"]
        if set(rule["required"]) - value.keys():
            raise ValidationError(f"Required fields missing at {location}")
        if rule.get("additionalProperties") is not False or value.keys() - properties.keys():
            raise ValidationError(f"Unknown fields at {location}")
        for key, item in value.items():
            validate_shape(item, properties[key], schema, location + "." + key)
    elif expected == "array":
        if not rule.get("minItems", 0) <= len(value) <= rule.get("maxItems", 10000):
            raise ValidationError(f"Incorrect item count at {location}")
        if rule.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            raise ValidationError(f"Duplicate items at {location}")
        for item in value:
            validate_shape(item, rule["items"], schema, location + "[]")
    elif expected == "string":
        if not rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", 100000):
            raise ValidationError(f"Incorrect length at {location}")
        if "pattern" in rule and not re.fullmatch(rule["pattern"], value):
            raise ValidationError(f"Invalid format at {location}")
    elif not rule.get("minimum", -1e100) <= value <= rule.get("maximum", 1e100):
        raise ValidationError(f"Value outside allowed range at {location}")


def relative_file(root, name, require_exists=True):
    path = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or path.is_absolute()
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValidationError("Artifact path must stay inside the release directory")
    root = Path(root).resolve(strict=True)
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValidationError("Linked artifact paths are not permitted")
    try:
        current.resolve(strict=require_exists).relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValidationError("Artifact is missing or outside the release directory") from exc
    return current


def file_digest(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    digest, count = hashlib.sha256(), 0
    try:
        with os.fdopen(os.open(path, flags), "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValidationError("Artifact must be a regular file")
            for block in iter(lambda: source.read(1024 * 1024), b""):
                count += len(block)
                digest.update(block)
    except OSError as exc:
        raise ValidationError("Artifact cannot be read") from exc
    return digest.hexdigest(), count


def gpg_path(executable, path):
    """Git for Windows ships an MSYS GPG that expects /c/... rather than C:\\...."""
    absolute = Path(path).resolve().as_posix()
    if os.name == "nt" and Path(executable).parent.parent.name.lower() == "usr":
        return "/" + absolute[0].lower() + absolute[2:]
    return absolute


def run_gpg(executable, home, *arguments, data=None):
    try:
        # Public-key verification needs no secret-key agent. CloudShell's minimal
        # GnuPG may omit gpg-agent; never start or depend on one for key import.
        result = subprocess.run([executable, "--no-options", "--batch", "--no-tty", "--no-autostart",
            "--homedir", gpg_path(executable, home), "--no-auto-key-retrieve", "--auto-key-locate", "clear",
            *arguments], input=data, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationError("GnuPG verification tool unavailable or timed out") from exc
    return result


def verify_signature(manifest_data, signature_data, key_data, fingerprint, gpg="gpg"):
    fingerprint = fingerprint.upper()
    if not re.fullmatch(r"[0-9A-F]{40}", fingerprint):
        raise ValidationError("A full trusted primary fingerprint is required")
    executable = shutil.which(gpg)
    if executable is None:
        raise ValidationError("GnuPG is required; signature validation cannot be skipped")
    now = int(utc_now().timestamp())
    with tempfile.TemporaryDirectory(prefix="jdu-web-verify-") as directory:
        home = Path(directory)
        home.chmod(0o700)
        imported = run_gpg(executable, home, "--import", data=key_data)
        if imported.returncode:
            raise ValidationError("Public key import failed")
        listing = run_gpg(executable, home, "--with-colons", "--with-fingerprint",
                          "--with-subkey-fingerprint", "--list-keys")
        if listing.returncode:
            raise ValidationError("Public key metadata unavailable")
        keys, primary, current = {}, [], None
        for line in listing.stdout.decode("utf-8", errors="replace").splitlines():
            fields = line.split(":")
            if fields[0] in ("pub", "sub"):
                current = {"kind": fields[0], "validity": fields[1], "bits": int(fields[2]),
                           "algo": int(fields[3]), "created": int(fields[5]),
                           "expires": int(fields[6] or 0)}
            elif fields[0] == "fpr" and current is not None:
                keys[fields[9]] = current
                if current["kind"] == "pub":
                    primary.append(fields[9])
                current = None
        if primary != [fingerprint]:
            raise ValidationError("Public key differs from the independently trusted fingerprint")
        root = keys[fingerprint]
        if (root["validity"] in ("r", "e", "d", "i") or root["created"] > now
                or root["expires"] <= now or root["bits"] < 3072 or root["algo"] not in (1, 3)):
            raise ValidationError("Primary signing key is expired, revoked or outside the RSA3072 policy")
        source, signature = home / "manifest.json", home / "manifest.sig"
        source.write_bytes(manifest_data)
        signature.write_bytes(signature_data)
        verified = run_gpg(executable, home, "--status-fd", "1", "--verify",
                           gpg_path(executable, signature), gpg_path(executable, source))
        statuses = [line.split()[1:] for line in verified.stdout.decode("ascii", errors="replace").splitlines()
                    if line.startswith("[GNUPG:] ") and len(line.split()) > 1]
        bad = {"BADSIG", "ERRSIG", "EXPSIG", "EXPKEYSIG", "REVKEYSIG", "NO_PUBKEY", "FAILURE", "ERROR", "NODATA"}
        valid = [row for row in statuses if row[0] == "VALIDSIG"]
        if verified.returncode or any(row[0] in bad for row in statuses) or len(valid) != 1:
            raise ValidationError("Detached manifest signature is invalid or expired")
        values = valid[0][1:]
        if len(values) < 9 or any(not value.isdigit() for value in (values[2], values[3], values[6], values[7])):
            raise ValidationError("Incomplete GnuPG signature metadata")
        signer = keys.get(values[0])
        primary_fpr = values[9] if len(values) > 9 else values[0]
        if (primary_fpr != fingerprint or signer is None or signer["bits"] < 3072
                or signer["algo"] not in (1, 3) or signer["validity"] in ("r", "e", "d", "i")
                or signer["created"] > now or (signer["expires"] and signer["expires"] <= now)
                or int(values[2]) > now
                or int(values[6]) not in (1, 3) or int(values[7]) not in (8, 9, 10)
                or (int(values[3]) and int(values[3]) <= now)):
            raise ValidationError("Signature does not satisfy pinned signer, expiry or SHA256 policy")
        return min(root["expires"], signer["expires"] or root["expires"])


def validate_semantics(manifest, key_expiry):
    created, expires, now = parse_time(manifest["created_at"]), parse_time(manifest["expires_at"]), utc_now()
    if not created <= now < expires or expires.timestamp() > key_expiry:
        raise ValidationError("Manifest is future dated, expired or outlives its signing key")
    if len(set(manifest["ami"]["id"][4:])) == 1:
        raise ValidationError("Placeholder AMI ID is not permitted")
    try:
        address = ipaddress.IPv4Address(manifest["grading"]["ipv4"])
        cidrs = [ipaddress.IPv4Network(value, strict=True) for value in manifest["network"]["rdp_ipv4_cidrs"]]
    except ValueError as exc:
        raise ValidationError("Invalid IPv4 address or CIDR") from exc
    if not address.is_global or address.is_multicast:
        raise ValidationError("Grading ingress must be a public unicast IPv4 address")
    if any(not net.network_address.is_global or not net.broadcast_address.is_global
           or net.prefixlen < 8 or net.is_multicast for net in cidrs):
        raise ValidationError("RDP allowlist must contain specific public IPv4 networks")
    if any(left.overlaps(right) for index, left in enumerate(cidrs) for right in cidrs[index + 1:]):
        raise ValidationError("RDP allowlist contains overlapping CIDRs")
    host = manifest["grading"]["fqdn"]
    labels = host.split(".")
    if (len(labels) < 2 or host != host.lower() or len(labels[-1]) < 2
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            or labels[-1] in ("test", "invalid", "example", "localhost", "local")
            or any(host == suffix or host.endswith("." + suffix) for suffix in ("example.com", "example.org", "example.net"))):
        raise ValidationError("Grading FQDN must be a real lowercase DNS name, not a placeholder")
    bucket = manifest["bootstrap"]["bucket"]
    if ".." in bucket or re.fullmatch(r"[0-9.]+", bucket) or any(word in bucket for word in ("replace-me", "changeme", "example-bucket")):
        raise ValidationError("Bootstrap bucket is invalid or a placeholder")
    prefix = manifest["bootstrap"]["release_prefix"]
    if any(part in ("", ".", "..") for part in prefix[:-1].split("/")) or manifest["release_id"] not in prefix.split("/"):
        raise ValidationError("Bootstrap prefix must identify this release without traversal")


def verify_release(manifest_path, signature_path, key_path, trusted_fingerprint, artifact_root,
                   gpg="gpg", include_bundle=True):
    data = read_regular(manifest_path, 1024 * 1024)
    key_data = read_regular(key_path, 256 * 1024)
    signature = read_regular(signature_path, 64 * 1024)
    expiry = verify_signature(data, signature, key_data, trusted_fingerprint, gpg)
    manifest = json_bytes(data)
    schema_path = Path(__file__).with_name("deployment-manifest.schema.json")
    schema = json_bytes(read_regular(schema_path, 128 * 1024))
    validate_shape(manifest, schema, schema)
    if manifest["signing"]["primary_fingerprint"] != trusted_fingerprint.upper():
        raise ValidationError("Manifest fingerprint differs from the trusted signing key")
    validate_semantics(manifest, expiry)
    used, files = set(), {}
    for role, artifact in manifest["artifacts"].items():
        deferred = role == "repo_bundle" and not include_bundle
        path = relative_file(artifact_root, artifact["path"], require_exists=not deferred)
        if path in used or path == Path(manifest_path).resolve():
            raise ValidationError("Duplicate or self-referential artifact path")
        used.add(path)
        files[role] = path
        if deferred:
            # CloudShell needs only the small tools archive. Repo must verify this hash
            # after downloading the S3 object, before extraction/installation (future code).
            continue
        actual, size = file_digest(path)
        if actual != artifact["sha256"] or size != artifact["size_bytes"]:
            raise ValidationError(f"Artifact hash or size mismatch: {role}")
    for role, local in {"wrapper": Path(__file__).with_name("web_lab.py"),
                        "validation": Path(__file__), "schema": schema_path}.items():
        if file_digest(local) != file_digest(files[role]):
            raise ValidationError("Running validation tool is not bound to this release")
    if read_regular(files["public_key"], 256 * 1024) != key_data:
        raise ValidationError("Artifact public key differs from verification input")
    return {"manifest": manifest, "manifest_sha256": hashlib.sha256(data).hexdigest(),
            "files": files, "trusted_fingerprint": trusted_fingerprint.upper(),
            "bundle_verified_locally": include_bundle}
