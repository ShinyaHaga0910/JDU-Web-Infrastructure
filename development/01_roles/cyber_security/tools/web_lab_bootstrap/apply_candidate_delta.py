"""Reassemble a new signed candidate without changing the existing release.

Reuse unchanged bytes by hard link, but never write a changed file through a
link to the old release. Both full trees are independently signature verified.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile

from payload_runtime import verify_tree
from release_validation import file_digest


def assemble(base, delta, output, fingerprint, delta_sha256):
    base=Path(base).resolve();output=Path(output)
    key=base/'artifacts/bootstrap/archive-key.asc'
    verify_tree(base,key,fingerprint,'web-2026-10-r1',allow_package_candidate=True)
    data=Path(delta).read_bytes()
    if len(data)>4*1024*1024 or hashlib.sha256(data).hexdigest()!=delta_sha256:
        raise ValueError('Public delta transport hash differs')
    files={};total=0
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
        for m in tar:
            if (not m.isfile() or m.name in files or m.size<0 or m.size>2*1024*1024
                    or len(files)>100 or '\\' in m.name or ':' in m.name
                    or any(p in ('','.','..') for p in m.name.split('/'))
                    or not (m.name=='DELTA-MANIFEST.json' or m.name.startswith('release/'))):
                raise ValueError('Unsafe public delta')
            total+=m.size
            if total>8*1024*1024:raise ValueError('Public delta too large')
            files[m.name]=tar.extractfile(m).read()
    manifest=json.loads(files.pop('DELTA-MANIFEST.json'))
    if (manifest['removed'] or file_digest(base/'manifests/release.json')[0]!=manifest['base_manifest_sha256']
            or set(files)!={'release/'+n for n in manifest['changed']}
            or len(manifest['changed'])!=len(set(manifest['changed']))):
        raise ValueError('Unexpected delta base, inventory or deletion')
    if any(p.is_symlink() for p in [output,*output.parents]):raise ValueError('Linked output path refused')
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    for source in base.rglob('*'):
        if source.is_file():
            name=source.relative_to(base).as_posix()
            if name in manifest['changed']:continue
            target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
            os.link(source,target)
    for name,data in files.items():
        target=output.joinpath(*PurePosixPath(name).parts[1:]);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(data)
        target.chmod(0o644)
    full=verify_tree(output,output/'artifacts/bootstrap/archive-key.asc',fingerprint,'web-2026-10-r1')
    if file_digest(output/'manifests/release.json')[0]!=manifest['target_manifest_sha256']:
        raise ValueError('Target release manifest differs')
    return dict(base_signature_verified=True,new_signature_verified=True,exact_full_inventory_verified=True,
        unchanged_old_release=True,changed_files=manifest['changed'],assessment=full['assessment'],
        package_count=full['package_count'],wheel_count=full['wheel_count'],
        student_release_ready=False,class_ready=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','delta','output','fingerprint','delta-sha256'):p.add_argument('--'+n,required=True)
    a=p.parse_args();print('SIGNED_CANDIDATE_REASSEMBLED='+json.dumps(assemble(**vars(a)),separators=(',',':')))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('CANDIDATE_REASSEMBLY_STOPPED='+type(exc).__name__);raise SystemExit(2)
