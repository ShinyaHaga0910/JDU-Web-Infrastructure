"""Build and sign a fixed APT/wheel payload on the teacher's Ubuntu system.

Package-only candidates are explicitly incomplete and cannot be student releases.
No private key, credential or deployment state is copied into the payload.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

from release_validation import ValidationError, file_digest, relative_file, verify_signature


def checked_capture(root):
    root=Path(root).resolve()
    summary=json.loads((root/"capture-summary.json").read_text())
    profile=json.loads((root/"capture-evidence/package-profile.json").read_text())
    packages=json.loads((root/"deb-packages.json").read_text())
    wheels=json.loads((root/"python-packages.json").read_text())
    if (summary.get("empty_status_resolution") is not True
            or summary.get("python_offline_install_and_pip_check") is not True
            or summary["package_count"]!=len(packages) or summary["wheel_count"]!=len(wheels)):
        raise ValidationError("Capture is incomplete")
    local_profile=Path(__file__).with_name("package-profile.json")
    if (summary.get("profile_sha256")!=file_digest(local_profile)[0]
            or profile!=json.loads(local_profile.read_text())):
        raise ValidationError("Capture profile differs from the teacher's pinned profile")
    seen=set()
    for entry in packages:
        path=relative_file(root,entry["path"])
        if path in seen or not entry["path"].startswith("apt/pool/"):
            raise ValidationError("Duplicate or misplaced Debian package")
        seen.add(path)
        if file_digest(path)!=(entry["sha256"],entry["size_bytes"]) or entry["architecture"] not in ("all","amd64"):
            raise ValidationError("Debian package hash, size or architecture differs")
    if {p.resolve() for p in (root/"apt/pool").glob("*.deb")}!=seen:
        raise ValidationError("Unlisted Debian package in capture")
    targets={p for group in profile["roles"].values() for p in group}
    if not targets<={p["package"] for p in packages}:
        raise ValidationError("Direct package missing")
    wheel_paths=set()
    for entry in wheels:
        path=relative_file(root,"artifacts/python/wheelhouse/"+entry["filename"])
        if path in wheel_paths or file_digest(path)!=(entry["sha256"],entry["size_bytes"]):
            raise ValidationError("Wheel differs from captured lock")
        wheel_paths.add(path)
    if {p.resolve() for p in (root/"artifacts/python/wheelhouse").glob("*")}!=wheel_paths:
        raise ValidationError("Unlisted Python artifact in capture")
    return root,summary,profile,packages,wheels


def run(args, *, cwd=None, data=None):
    return subprocess.run(args,cwd=cwd,input=data,capture_output=True,check=True).stdout


def validate_application_bundles(app, checker):
    """Validate bounded inventories before granting even unaccepted payload scope."""
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'web_lab_teacher'))
    from install_checker_bundle import checked_archive
    from verify_catalog_runtime_guest import extract_app
    a=Path(app);c=Path(checker)
    if a.is_symlink() or c.is_symlink() or any(p.stat().st_size>4*1024*1024 for p in (a,c)):
        raise ValidationError('Invalid application/checker bundle')
    _,manifest=checked_archive(c.read_bytes())
    with tempfile.TemporaryDirectory(prefix='jdu-web-app-inventory-') as work:
        count=extract_app(a.read_bytes(),Path(work)/'app')
    return dict(app_file_count=count,checker_file_count=len(manifest['files']),
                supported_tasks=manifest['supported_tasks'],scope='web02_only_no_course_points')


def build(args):
    root,summary,profile,packages,wheels=checked_capture(args.capture)
    if not args.package_only and (not args.app_bundle or not args.checker_bundle):
        raise ValidationError("A student release requires real app and checker bundles")
    assessment=None
    if not args.package_only:
        assessment=validate_application_bundles(args.app_bundle,args.checker_bundle)
    output=Path(args.output).resolve()
    output.mkdir(parents=True,mode=0o755,exist_ok=False)
    if not re.fullmatch(r"web-[0-9]{4}-[0-9]{2}-r[1-9][0-9]*",args.release_id):
        raise ValidationError("Invalid release ID")
    apt=output/"apt"
    pool=apt/"pool"; pool.mkdir(parents=True)
    for package in packages:
        source=root/package["path"]; target=pool/source.name
        try:
            os.link(source,target)
        except OSError:
            shutil.copy2(source,target)
    shutil.copytree(root/"artifacts",output/"artifacts")
    manifests=output/"manifests"; manifests.mkdir()
    for name in ("deb-packages.json","deb-packages.csv","python-packages.json","capture-summary.json"):
        shutil.copy2(root/name,manifests/name)
    with (manifests/"python-packages.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(wheels[0]))
        writer.writeheader(); writer.writerows(wheels)
    for name,source in (("app/jdu-catalog.tar.gz",args.app_bundle),("checker/checker-bundle.tar.gz",args.checker_bundle)):
        if source:
            destination=output/"artifacts"/name; destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)
    bootstrap=output/"artifacts/bootstrap"; bootstrap.mkdir()
    for source in ("package-profile.json","payload_runtime.py","release_validation.py","node_bootstrap.py","network_probe.py"):
        shutil.copy2(Path(__file__).with_name(source),bootstrap/source)
    if not args.package_only:
        student=output/'artifacts/student';student.mkdir()
        shutil.copy2(Path(__file__).parent.parent/'web_lab_teacher/install_checker_bundle.py',student/'install_checker_bundle.py')
    key_data=run(["gpg","--no-options","--homedir",args.signing_home,"--batch","--armor","--export",args.fingerprint])
    if not key_data:
        raise ValidationError("Signing key not available")
    (bootstrap/"archive-key.asc").write_bytes(key_data)
    dist=apt/"dists/jdu-noble"; binary=dist/"main/binary-amd64"; binary.mkdir(parents=True)
    index=run(["apt-ftparchive","packages","pool"],cwd=apt)
    (binary/"Packages").write_bytes(index)
    (binary/"Packages.gz").write_bytes(gzip.compress(index,mtime=0))
    now=datetime.now(timezone.utc); expires=now+timedelta(days=180)
    options=[]
    fields={"Origin":"JDU-WebLab","Label":"JDU-WebLab","Suite":"jdu-noble","Codename":"jdu-noble",
            "Architectures":"amd64","Components":"main","Date":format_datetime(now,usegmt=True),
            "Valid-Until":format_datetime(expires,usegmt=True)}
    for key,value in fields.items():
        options+=["-o","APT::FTPArchive::Release::"+key+"="+value]
    release=run(["apt-ftparchive",*options,"release","dists/jdu-noble"],cwd=apt)
    if b"Valid-Until:" not in release:
        release=b"Valid-Until: "+format_datetime(expires,usegmt=True).encode()+b"\n"+release
    (dist/"Release").write_bytes(release)
    signing=["gpg","--no-options","--homedir",args.signing_home,"--batch","--yes","--digest-algo","SHA256",
             "--local-user",args.fingerprint]
    run([*signing,"--clearsign","--output",str(dist/"InRelease"),str(dist/"Release")])
    run([*signing,"--armor","--detach-sign","--output",str(dist/"Release.gpg"),str(dist/"Release")])
    inventory=[]
    for path in sorted(output.rglob("*")):
        if path.is_symlink():
            raise ValidationError("Payload links are not permitted")
        if path.is_file():
            sha,size=file_digest(path)
            inventory.append({"path":path.relative_to(output).as_posix(),"sha256":sha,"size_bytes":size})
    manifest={"schema_version":1,"release_id":args.release_id,"created_at":now.isoformat(),"expires_at":expires.isoformat(),
              "ubuntu":"24.04","architecture":"amd64","python_abi":"cp312","ami_id":profile["ami_id"],
              "primary_fingerprint":args.fingerprint.upper(),"scope":"package_only_candidate" if args.package_only else "student_payload",
              "package_count":len(packages),"wheel_count":len(wheels),"role_packages":profile["roles"],
              "offline_os_acceptance":False,"student_release_ready":False,"class_ready":False,
              "assessment":assessment,"files":inventory}
    (manifests/"release.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    checks=[]
    for path in sorted(output.rglob("*")):
        if path.is_file():
            checks.append(file_digest(path)[0]+"  "+path.relative_to(output).as_posix()+"\n")
    sums=manifests/"SHA256SUMS"; sums.write_text("".join(checks))
    signature=manifests/"SHA256SUMS.asc"
    run([*signing,"--armor","--detach-sign","--output",str(signature),str(sums)])
    key_expiry=verify_signature(sums.read_bytes(),signature.read_bytes(),key_data,args.fingerprint)
    if expires.timestamp()>key_expiry:
        raise ValidationError("APT and manifest expiry outlive the signing key")
    archive=output.with_name(output.name+".tar.gz")
    if archive.exists():
        raise ValidationError("Existing bundle is immutable")
    with tarfile.open(archive,"w:gz") as stream:
        stream.add(output,arcname="release")
    sha,size=file_digest(archive)
    return {"stage":"SIGNED_PACKAGE_CANDIDATE" if args.package_only else "SIGNED_PAYLOAD_UNACCEPTED",
            "package_count":len(packages),"wheel_count":len(wheels),"bundle_sha256":sha,"bundle_size_bytes":size,
            "fingerprint":args.fingerprint.upper(),"student_release_ready":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("capture","output","release-id","signing-home","fingerprint"):
        parser.add_argument("--"+name,required=True)
    parser.add_argument("--package-only",action="store_true")
    parser.add_argument("--app-bundle"); parser.add_argument("--checker-bundle")
    args=parser.parse_args()
    try:
        print(json.dumps(build(args)))
    except Exception as exc:
        print("PACKAGE_REPOSITORY_BUILD_FAILED="+type(exc).__name__)
        raise SystemExit(2)


if __name__=="__main__":
    main()
