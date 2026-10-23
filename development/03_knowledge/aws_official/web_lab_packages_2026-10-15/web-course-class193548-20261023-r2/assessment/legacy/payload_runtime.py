"""Verified extraction, signed payload checks and offline first repo installation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode=True
from release_validation import (ValidationError, file_digest, json_bytes, parse_time,
                                read_regular, relative_file, verify_signature)


def safe_extract(archive_path, destination, expected_sha256, maximum_bytes=8*1024**3):
    archive_path=Path(archive_path)
    if file_digest(archive_path)[0]!=expected_sha256:
        raise ValidationError("Bundle hash mismatch")
    destination=Path(destination)
    destination.mkdir(mode=0o755,parents=True,exist_ok=False)
    total,seen=0,set()
    with tarfile.open(archive_path,"r:gz") as archive:
        for index,member in enumerate(archive):
            path=PurePosixPath(member.name)
            if (index>=100000 or path.is_absolute() or not path.parts or path.parts[0]!="release"
                    or any(p in (".","..","") for p in path.parts) or "\\" in member.name
                    or not (member.isdir() or member.isreg()) or member.name in seen):
                raise ValidationError("Unsafe or duplicate archive member")
            seen.add(member.name); total+=member.size
            if total>maximum_bytes or member.size<0:
                raise ValidationError("Unpacked bundle exceeds size limit")
            target=destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True,mode=0o755,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,mode=0o755,exist_ok=True)
                source=archive.extractfile(member)
                with target.open("xb") as stream:
                    shutil.copyfileobj(source,stream,length=1024*1024)
                target.chmod(0o644)
    return destination/"release"


def signed_manifest(root, public_key, fingerprint, release_id, *, allow_package_candidate=False):
    root=Path(root).resolve()
    sums=read_regular(root/"manifests/SHA256SUMS",16*1024**2)
    signature=read_regular(root/"manifests/SHA256SUMS.asc",64*1024)
    key=read_regular(public_key,256*1024)
    expiry=verify_signature(sums,signature,key,fingerprint)
    entries={}
    for line in sums.decode("ascii").splitlines():
        match=re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9_./%+~:=-]*)",line)
        if not match or match[2] in entries or match[2] in ("manifests/SHA256SUMS","manifests/SHA256SUMS.asc"):
            raise ValidationError("Invalid signed checksum list")
        relative_file(root,match[2],require_exists=False)
        entries[match[2]]=match[1]
    manifest_path=root/"manifests/release.json"
    data=read_regular(manifest_path,16*1024**2)
    if entries.get("manifests/release.json")!=hashlib.sha256(data).hexdigest():
        raise ValidationError("Release manifest is not bound to the signature")
    manifest=json_bytes(data); now=datetime.now(timezone.utc)
    if (manifest.get("schema_version")!=1 or manifest.get("release_id")!=release_id
            or manifest.get("primary_fingerprint")!=fingerprint.upper()
            or not parse_time(manifest["created_at"])<=now<parse_time(manifest["expires_at"])
            or parse_time(manifest["expires_at"]).timestamp()>expiry):
        raise ValidationError("Release identity or expiry differs")
    if manifest.get("scope")!="student_payload" and not (allow_package_candidate and manifest.get("scope")=="package_only_candidate"):
        raise ValidationError("Incomplete package candidate is not a student release")
    declared={entry["path"]:entry for entry in manifest["files"]}
    if (len(declared)!=len(manifest["files"])
            or set(entries)!=(set(declared)|{"manifests/release.json"})):
        raise ValidationError("Signed file lists differ")
    return manifest,entries


def verify_tree(root, public_key, fingerprint, release_id, *, allow_package_candidate=False):
    root=Path(root).resolve()
    manifest,entries=signed_manifest(root,public_key,fingerprint,release_id,allow_package_candidate=allow_package_candidate)
    expected=set(entries)|{"manifests/SHA256SUMS","manifests/SHA256SUMS.asc"}
    actual=set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValidationError("Payload links are not permitted")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if expected!=actual:
        raise ValidationError("Missing or unexpected payload files")
    sizes={entry["path"]:entry["size_bytes"] for entry in manifest["files"]}
    for name,sha in entries.items():
        actual_sha,size=file_digest(relative_file(root,name))
        if actual_sha!=sha or (name in sizes and size!=sizes[name]):
            raise ValidationError("Payload file hash or size differs")
    return manifest


def apt_command(command, source_file, lists_dir, cache_dir, *arguments):
    environment=dict(os.environ,DEBIAN_FRONTEND="noninteractive",LC_ALL="C")
    args=["apt-get","-o","Dir::Etc::sourcelist="+str(source_file),"-o","Dir::Etc::sourceparts=-",
          "-o","Dir::State::lists="+str(lists_dir),"-o","Dir::Cache::archives="+str(cache_dir),
          "-o","Dpkg::Lock::Timeout=600","-o","Acquire::Retries=2",command,*arguments]
    subprocess.run(args,check=True,env=environment)


def install_repo(root, public_key, fingerprint, release_id, *, allow_package_candidate=False):
    if os.geteuid()!=0:
        raise ValidationError("Repo installation requires root")
    release=verify_tree(root,public_key,fingerprint,release_id,allow_package_candidate=allow_package_candidate)
    os_release=dict(line.split("=",1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    if os_release.get("ID")!="ubuntu" or os_release.get("VERSION_ID","").strip('"')!="24.04":
        raise ValidationError("Repo installation requires Ubuntu 24.04")
    if subprocess.check_output(["dpkg","--print-architecture"],text=True).strip()!="amd64":
        raise ValidationError("Repo installation requires amd64")
    target=Path("/srv/jdu-repo/releases")/release_id
    state=Path("/var/lib/jdu-web/bootstrap/repo-state.json")
    if state.exists() or target.exists():
        raise ValidationError("Existing repository is retained; use check-only")
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(root,target)
    target.chmod(0o755)
    workspace=Path("/var/lib/jdu-web/offline-apt")
    workspace.mkdir(mode=0o755,parents=True,exist_ok=False)
    lists=workspace/"lists"; lists.mkdir(mode=0o755)
    cache=workspace/"archives"; cache.mkdir(mode=0o755)
    (cache/"partial").mkdir()
    for source in (target/"apt/pool").glob("*.deb"):
        try:
            os.link(source,cache/source.name)
        except OSError:
            shutil.copy2(source,cache/source.name)
    keyring=Path("/usr/share/keyrings/jdu-web-archive-keyring.gpg")
    if keyring.exists():
        raise ValidationError("Existing archive key is retained")
    subprocess.run(["gpg","--batch","--yes","--dearmor","--output",str(keyring),str(public_key)],check=True)
    keyring.chmod(0o644)
    source_file=workspace/"local.sources"
    source_file.write_text(f"Types: deb\nURIs: file:{target}/apt/\nSuites: jdu-noble\nComponents: main\nArchitectures: amd64\nSigned-By: {keyring}\n")
    apt_command("update",source_file,lists,cache,"-o","APT::Update::Error-Mode=any")
    packages=json.loads((target/"manifests/deb-packages.json").read_text())
    versions={p["package"]:p["version"] for p in packages}
    direct=sorted(set(release["role_packages"]["common"]+release["role_packages"]["repo"]))
    apt_command("install",source_file,lists,cache,"-y","--no-download",*[p+"="+versions[p] for p in direct])
    # External sources are parked only after verified local installation succeeds.
    sources=Path("/etc/apt/sources.list.d")
    for path in sources.iterdir():
        if path.suffix in (".sources",".list") and path.name!="jdu-web.sources":
            backup=path.with_name(path.name+".jdu-disabled")
            if backup.exists():
                raise ValidationError("Existing source backup must be checked manually")
            path.rename(backup)
    legacy=Path("/etc/apt/sources.list")
    if legacy.is_file() and legacy.read_text().strip():
        backup=legacy.with_name("sources.list.jdu-disabled")
        if backup.exists():
            raise ValidationError("Existing source backup must be checked manually")
        legacy.rename(backup)
    (sources/"jdu-web.sources").write_text(f"Types: deb\nURIs: http://10.20.2.30/releases/{release_id}/apt/\nSuites: jdu-noble\nComponents: main\nArchitectures: amd64\nSigned-By: {keyring}\n")
    Path("/etc/chrony/conf.d/jdu-web.conf").write_text("server 169.254.169.123 prefer iburst minpoll 4 maxpoll 4\n")
    nginx=Path("/etc/nginx/nginx.conf")
    nginx.write_text("user www-data;\nworker_processes auto;\nevents { worker_connections 256; }\nhttp { include /etc/nginx/mime.types; server { listen 80 default_server; root /srv/jdu-repo;\n"
        f"location /releases/{release_id}/ {{ try_files $uri =404; }}\nlocation / {{ return 404; }}\n}} }}\n")
    subprocess.run(["nginx","-t"],check=True)
    subprocess.run(["systemctl","enable","--now","nginx","chrony"],check=True)
    subprocess.run(["systemctl","restart","nginx","chrony"],check=True)
    # No BASE_READY: this is one repository, not five role-accepted hosts.
    status={"schema_version":1,"role":"repo","release_id":release_id,
            "scope":release["scope"],"stage":"REPO_INSTALLED_PENDING_HTTP_ACCEPTANCE",
            "student_release_ready":False}
    state.parent.mkdir(parents=True,exist_ok=True); state.write_text(json.dumps(status,indent=2)+"\n")
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("extract","verify","install-repo"))
    parser.add_argument("--root"); parser.add_argument("--public-key"); parser.add_argument("--fingerprint")
    parser.add_argument("--release-id"); parser.add_argument("--package-candidate",action="store_true")
    parser.add_argument("--archive"); parser.add_argument("--destination"); parser.add_argument("--sha256")
    args=parser.parse_args()
    try:
        if args.command=="extract":
            result={"extracted":str(safe_extract(args.archive,args.destination,args.sha256))}
        elif args.command=="verify":
            result=verify_tree(args.root,args.public_key,args.fingerprint,args.release_id,allow_package_candidate=args.package_candidate)
            result={"stage":"PAYLOAD_VERIFIED","scope":result["scope"],"student_release_ready":False}
        else:
            result=install_repo(args.root,args.public_key,args.fingerprint,args.release_id,allow_package_candidate=args.package_candidate)
        print(json.dumps(result))
    except Exception as exc:
        print("PAYLOAD_FAILED="+type(exc).__name__)
        raise SystemExit(2)


if __name__=="__main__":
    main()
