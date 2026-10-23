"""Reassemble a signed teacher candidate from an existing private capture.

Only metadata moves through the terminal; package bytes already in S3 are reused.
No signing secret or student credential is needed on this system.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def extract(path, destination, prefix):
    destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    with tarfile.open(path,"r:gz") as archive:
        members=archive.getmembers()
        if len(members)>10000 or sum(m.size for m in members)>2*1024**3:
            raise ValueError("Archive exceeds teacher capture bounds")
        seen=set()
        for member in members:
            name=PurePosixPath(member.name)
            if (not name.parts or name.parts[0]!=prefix or name.is_absolute()
                    or ".." in name.parts or "\\" in member.name or member.name in seen
                    or not (member.isdir() or member.isfile())):
                raise ValueError("Unsafe or duplicate capture member")
            seen.add(member.name)
        archive.extractall(destination,members=members,filter="data")
    return destination/prefix


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("metadata","metadata-sha256","capture-archive","capture-sha256","workspace","fingerprint","bucket"):
        parser.add_argument("--"+name,required=True)
    parser.add_argument("--resume-verified-tree",action="store_true")
    parser.add_argument("--candidate-id",default="c1")
    args=parser.parse_args(); os.umask(0o077)
    if digest(args.metadata)!=args.metadata_sha256 or digest(args.capture_archive)!=args.capture_sha256:
        raise ValueError("Teacher transfer hash mismatch")
    workspace=Path(args.workspace)
    if args.resume_verified_tree:
        if not workspace.is_dir() or workspace.is_symlink():
            raise ValueError("Missing teacher workspace")
        release=workspace/"metadata/release"
    else:
        workspace.mkdir(mode=0o700,parents=True,exist_ok=False)
        capture=extract(args.capture_archive,workspace/"source","capture")
        release=extract(args.metadata,workspace/"metadata","release")
        for name in ("apt/pool","artifacts/python/wheelhouse"):
            target=release/name; target.mkdir(parents=True,exist_ok=False)
            for source in (capture/name).iterdir():
                if not source.is_file() or source.is_symlink():
                    raise ValueError("Unexpected captured package entry")
                os.link(source,target/source.name)
    verifier=release/"artifacts/bootstrap/payload_runtime.py"
    key=release/"artifacts/bootstrap/archive-key.asc"
    checked=subprocess.run([sys.executable,str(verifier),"verify","--root",str(release),"--public-key",str(key),
        "--fingerprint",args.fingerprint,"--release-id","web-2026-10-r1","--package-candidate"],capture_output=True,text=True)
    if checked.returncode:
        raise ValueError("Reassembled signed candidate did not verify")
    print("CLOUDSHELL_CANDIDATE_TREE_VERIFIED",flush=True)
    bundle=workspace/"repo-bundle.tar.gz"
    if bundle.exists():
        raise ValueError("Existing teacher bundle retained")
    with tarfile.open(bundle,"w:gz",compresslevel=1) as archive:
        archive.add(release,arcname="release")
    import boto3
    s3=boto3.client("s3",region_name="us-east-1")
    if not __import__('re').fullmatch(r'c[1-9][0-9]*',args.candidate_id):
        raise ValueError('Invalid teacher candidate ID')
    object_key="teacher-candidates/web-2026-10-r1/"+args.candidate_id+"/repo-bundle.tar.gz"
    try:
        s3.head_object(Bucket=args.bucket,Key=object_key)
    except s3.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404","NoSuchKey"):
            raise
    else:
        raise ValueError("Existing immutable candidate object retained")
    sha=digest(bundle)
    s3.upload_file(str(bundle),args.bucket,object_key,ExtraArgs={"Metadata":{"sha256":sha}})
    result={"scope":"signed_candidate_reassembled_not_os_acceptance","bucket":args.bucket,"key":object_key,
        "bundle_sha256":sha,"bundle_size_bytes":bundle.stat().st_size,"metadata_sha256":args.metadata_sha256,
        "fingerprint":args.fingerprint,"release_id":"web-2026-10-r1","student_release_ready":False}
    (workspace/"candidate-result.json").write_text(json.dumps(result,indent=2)+"\n")
    print("CLOUDSHELL_CANDIDATE_RESULT="+json.dumps(result),flush=True)


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("CLOUDSHELL_ASSEMBLY_FAILED="+type(exc).__name__,flush=True)
        if isinstance(exc,ValueError):
            print("CLOUDSHELL_PUBLIC_VALIDATION="+str(exc),flush=True)
        raise SystemExit(2)
