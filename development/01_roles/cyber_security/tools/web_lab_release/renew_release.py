"""Re-sign the accepted r2 runtime for a specified term, never reset a Lab.

Run in the teacher's existing WSL signing environment. The original release
is authenticated as historical source bytes, not accepted for operational use.
Only validity envelopes and the reviewed course/distribution helpers change.
The core's executables, template, payload, key and assessment remain identical.
"""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

from release_tools import digest, encoded, parse, read, tree, verify, verifier

HERE = Path(__file__).resolve().parent
FP = '65EC6784750CCFA703BA7179519284E45155EC2A'
SOURCE = 'ab5e1f9edbd10c20f81b1cdd8bfb7deac1a42a60e9314849b775b32f98b18a99'


def deadline(value, now):
    expiry = datetime.fromisoformat(value)
    if expiry.tzinfo is None or not timedelta(0) < expiry-now <= timedelta(days=120):
        raise ValueError('An explicit future expiry within 120 days with timezone is required')
    return expiry.astimezone(timezone.utc)


def historical_source(root):
    raw = read(root/'course-release.json')
    if digest(raw) != SOURCE:
        raise ValueError('Only the independently pinned accepted r2 source may be renewed')
    validation = verifier(root)
    key = read(root/'package-signing-public.asc')
    key_expiry = validation.verify_signature(raw, read(root/'course-release.json.asc'), key, FP)
    release = parse(raw)
    expected = {entry['path']:(entry['sha256'],entry['size_bytes']) for entry in release['files']}
    files = tree(root)
    if set(files) != set(expected) | {'course-release.json','course-release.json.asc'}:
        raise ValueError('Historical source inventory changed')
    for name, (sha,size) in expected.items():
        if (digest(files[name]),len(files[name])) != (sha,size):
            raise ValueError('Historical source bytes changed')
    # Authenticate every signed layer explicitly; do not call an expired runtime.
    for name in ('foundation/distribution-release.json', 'foundation/core/deployment-manifest.json', 'assessment.tar.gz'):
        validation.verify_signature(files[name], files[name+'.asc'], key, FP)
    return release,files,key_expiry


def pack(root, target):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as tar:
        for name,raw in sorted(tree(root).items()):
            item=tarfile.TarInfo('jdu-web-course/'+name)
            item.size=len(raw);item.mode=0o600;item.mtime=0
            tar.addfile(item,io.BytesIO(raw))
    with target.open('xb') as stream:
        stream.write(gzip.compress(out.getvalue(),mtime=0))


def renew(source, output, signing_home, expires_at, distribution_id):
    now=datetime.now(timezone.utc)
    expiry=deadline(expires_at,now)
    old,source_files,key_expiry=historical_source(source)
    if expiry.timestamp()>key_expiry:
        raise ValueError('Requested release would outlive its existing signing key')
    if not __import__('re').fullmatch('[a-z0-9][a-z0-9-]{2,79}',distribution_id):
        raise ValueError('Invalid new distribution ID')
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,raw in source_files.items():
        target=output/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        target.write_bytes(raw)
    signing=['gpg','--no-options','--homedir',str(signing_home),'--batch','--digest-algo','SHA256','--local-user',FP,'--armor','--detach-sign']
    def sign(path):
        # These signatures are in this newly created output only, never old r2.
        subprocess.run(signing+['--yes','--output',str(path)+'.asc',str(path)],check=True,capture_output=True,timeout=45)
    core=output/'foundation/core'
    manifest=parse(read(core/'deployment-manifest.json'))
    manifest.update(created_at=now.isoformat(),expires_at=expiry.isoformat())
    (core/'deployment-manifest.json').write_bytes(encoded(manifest));sign(core/'deployment-manifest.json')
    new_core=digest(read(core/'deployment-manifest.json'))
    # Fresh deadlines do not change any executable, template, payload or key.
    for name,raw in tree(core).items():
        if name not in ('deployment-manifest.json','deployment-manifest.json.asc') and raw!=source_files['foundation/core/'+name]:
            raise ValueError('Unexpected core runtime change')
    for name in ('student.py','teacher.py','release_tools.py','STUDENT.md','TEACHER.md','RELEASE.md'):
        shutil.copyfile(HERE/name,output/name)
    shutil.copyfile(HERE.parent/'web_lab_distribution/distribution.py',output/'foundation/distribution.py')
    renewal=dict(scope='same_runtime_validity_renewal',original_release_sha256=SOURCE,
        original_distribution_id=old['distribution_id'],original_core_manifest_sha256=old['core_manifest_sha256'],
        renewed_core_manifest_sha256=new_core,runtime_artifacts_unchanged=True,
        assessment_archive_sha256=old['assessment_archive_sha256'],created_at=now.isoformat(),
        expires_at=expiry.isoformat(),fresh_initial_walkthrough_verified=False)
    (output/'RENEWAL.json').write_bytes(encoded(renewal))
    (output/'ACCEPTANCE.json').write_bytes(encoded(dict(scope='renewal_of_previously_accepted_runtime',
        source_release_sha256=SOURCE,runtime_artifacts_unchanged=True,assessment_archive_unchanged=True,
        retained_state_compatibility='explicit signed RENEWAL.json; no state writes',
        fresh_student_create_tested=False,class_ready=False)))
    foundation=output/'foundation'
    foundation_meta=parse(read(foundation/'distribution-release.json'))
    foundation_meta.update(distribution_id=distribution_id+'-foundation',created_at=now.isoformat(),
        expires_at=expiry.isoformat(),core_manifest_sha256=new_core)
    # Keep the historical foundation acceptance as a reference, with its old hash.
    foundation_meta['files']=[dict(path=n,sha256=digest(v),size_bytes=len(v))
        for n,v in sorted(tree(foundation).items()) if n not in ('distribution-release.json','distribution-release.json.asc')]
    (foundation/'distribution-release.json').write_bytes(encoded(foundation_meta));sign(foundation/'distribution-release.json')
    release=dict(old,distribution_id=distribution_id,created_at=now.isoformat(),expires_at=expiry.isoformat(),
        foundation_distribution_sha256=digest(read(foundation/'distribution-release.json')),core_manifest_sha256=new_core)
    release['files']=[dict(path=n,sha256=digest(v),size_bytes=len(v))
        for n,v in sorted(tree(output).items()) if n not in ('course-release.json','course-release.json.asc')]
    (output/'course-release.json').write_bytes(encoded(release));sign(output/'course-release.json')
    checked=verify(output,FP)
    archive=Path(str(output)+'.tar.gz');pack(output,archive);sign(archive)
    receipt=dict(renewal,distribution_id=distribution_id,archive_sha256=digest(read(archive)),
        archive_size_bytes=archive.stat().st_size,course_release_sha256=checked['sha256'],
        all_signature_layers_verified=True,expires_at_uzt=expiry.astimezone(timezone(timedelta(hours=5))).isoformat(),
        old_distribution_modified=False,servers_or_credentials_modified=False)
    Path(str(output)+'.public.json').write_bytes(encoded(receipt))
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','signing-home'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--expires-at',required=True);p.add_argument('--distribution-id',required=True)
    a=p.parse_args()
    print(json.dumps(renew(a.source,a.output,a.signing_home,a.expires_at,a.distribution_id),indent=2))
