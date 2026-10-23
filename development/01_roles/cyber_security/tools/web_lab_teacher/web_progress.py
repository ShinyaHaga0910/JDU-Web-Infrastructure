"""Teacher credential issuance and student register/submit/session commands."""
import argparse
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import sys
from urllib.parse import urlsplit

API_HOST = re.compile(r"[a-z0-9]+[.]execute-api[.]us-east-1[.]amazonaws[.]com")
LAB = re.compile(r"[a-z0-9][a-z0-9-]{2,31}")


class ProgressError(Exception):
    pass


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Override only the TCP destination. Preserve SNI and hostname/CA checks."""
    def __init__(self, hostname, fixed_ipv4):
        super().__init__(hostname, timeout=20, context=ssl.create_default_context())
        self.fixed_ipv4 = fixed_ipv4

    def connect(self):
        raw = socket.create_connection((self.fixed_ipv4, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def private_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128*1024:
        raise ProgressError("Configuration must be a small regular file")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise ProgressError("Credential configuration requires mode 0600")
    return json.loads(path.read_text(encoding="utf-8"))


def save_private(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def request(config, path, body, secret, *, fixed=True):
    endpoint = urlsplit(config["api_base_url"])
    if (endpoint.scheme != "https" or not API_HOST.fullmatch(endpoint.hostname or "")
            or endpoint.port not in (None,443) or endpoint.path not in ("","/")
            or endpoint.query or endpoint.fragment or endpoint.username or endpoint.password):
        raise ProgressError("Use the expected AWS HTTPS API endpoint")
    if not path.startswith("/api/web/"):
        raise ProgressError("Unsupported progress API path")
    address = ipaddress.IPv4Address(config["fixed_ingress_ipv4"])
    if not address.is_global or address.is_multicast:
        raise ProgressError("Teacher ingress must be a public IPv4")
    conn = PinnedHTTPSConnection(endpoint.hostname, str(address)) if fixed else http.client.HTTPSConnection(
        endpoint.hostname, timeout=20, context=ssl.create_default_context())
    try:
        conn.request("POST", path, body=json.dumps(body).encode(), headers={
            "Content-Type":"application/json","Authorization":"Bearer "+secret})
        response = conn.getresponse()
        data = response.read(128*1024+1)
        if len(data)>128*1024:
            raise ProgressError("Progress response exceeds its limit")
        if response.status != 200:
            raise ProgressError("Progress API rejected request: HTTP "+str(response.status))
        return json.loads(data)
    finally:
        conn.close()


def issue(config, lab_id, output):
    if not LAB.fullmatch(lab_id):
        raise ProgressError("Invalid anonymous Lab ID")
    path = Path(output)
    if path.exists():
        student = private_json(path)
        if (student.get("lab_id") != lab_id or student.get("release_id") != config["release_id"]
                or student.get("api_base_url") != config["api_base_url"]
                or student.get("fixed_ingress_ipv4") != config["fixed_ingress_ipv4"]):
            raise ProgressError("Existing credential file belongs to another deployment")
    else:
        student = {k:config[k] for k in ("api_base_url","fixed_ingress_ipv4","release_id")}
        student.update(schema_version=1, lab_id=lab_id, lab_token=secrets.token_urlsafe(32))
        save_private(path,student)
    result = request(config,"/api/web/admin/issue", {k:student[k] for k in ("lab_id","release_id","lab_token")},
                     config["admin_key"], fixed=False)
    if result.get("lab_id") != lab_id or result.get("release_id") != student["release_id"]:
        raise ProgressError("Teacher receipt mismatch")
    return {"credential_file":str(path),"lab_id":lab_id,"issued":True}


def register(config, deployment):
    body = {k:deployment[k] for k in ("deployment_id","instances")}
    body.update(lab_id=config["lab_id"], release_id=config["release_id"])
    if deployment.get("release_id") != config["release_id"] or deployment.get("lab_id") != config["lab_id"]:
        raise ProgressError("Lab state differs from the issued credential")
    result = request(config,"/api/web/register",body,config["lab_token"])
    if any(result.get(k)!=body[k] for k in ("lab_id","release_id","deployment_id")) or not result.get("registered"):
        raise ProgressError("Registration receipt mismatch")
    return result


def submit(config, report):
    if report.get("lab_id") != config["lab_id"] or report.get("release_id") != config["release_id"]:
        raise ProgressError("Report differs from the issued credential")
    result = request(config,"/api/web/submit",report,config["lab_token"])
    if any(result.get(k)!=report[k] for k in ("lab_id","release_id","deployment_id","request_id","kind")) or not result.get("stored"):
        raise ProgressError("Submission receipt mismatch")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",required=True)
    commands=parser.add_subparsers(dest="command",required=True)
    issuance=commands.add_parser("issue")
    issuance.add_argument("--lab-id",required=True); issuance.add_argument("--output",required=True)
    registration=commands.add_parser("register")
    registration.add_argument("--state",required=True); registration.add_argument("--receipt",required=True)
    submission=commands.add_parser("submit")
    submission.add_argument("--report",required=True); submission.add_argument("--receipt",required=True)
    session=commands.add_parser("session")
    session.add_argument("--teacher",action="store_true"); session.add_argument("--output",required=True)
    args=parser.parse_args(argv)
    try:
        config=private_json(args.config)
        if args.command=="issue":
            result=issue(config,args.lab_id,args.output)
        elif args.command=="register":
            result=register(config,json.loads(Path(args.state).read_text()))
            save_private(args.receipt,result)
        elif args.command=="submit":
            result=submit(config,json.loads(Path(args.report).read_text()))
            save_private(args.receipt,result)
        else:
            path="/api/web/admin/session" if args.teacher else "/api/web/student/session"
            body={} if args.teacher else {"lab_id":config["lab_id"]}
            result=request(config,path,body,config["admin_key"] if args.teacher else config["lab_token"],fixed=not args.teacher)
            save_private(args.output,result)
            result={"session_file":args.output,"expires_at":result["expires_at"]}
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except ProgressError as exc:
        print("ERROR: "+str(exc),file=sys.stderr)
    except Exception:
        print("ERROR: Progress operation failed; the credential and pending report are retained.",file=sys.stderr)
    return 2


if __name__=="__main__":
    raise SystemExit(main())
