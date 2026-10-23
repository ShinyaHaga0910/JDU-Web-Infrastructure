"""Small trusted template loader: check bundle hash before loading its verifier."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import tarfile
import urllib.request


def main(base=None):
    os.umask(0o022)
    base=Path(base or '/var/lib/jdu-repo-acceptance')
    config=json.loads((base/'private.json').read_text())
    bundle=base/'payload.tar.gz'
    with urllib.request.urlopen(config['bundle_url'],timeout=120) as response,bundle.open('xb') as stream:
        while block:=response.read(1024*1024):
            stream.write(block)
    with bundle.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=config['bundle_sha256']:
            raise ValueError('Pinned teacher bundle hash mismatch')
    # The hash is supplied by the trusted teacher template, not by the download.
    # Only these two regular files are loaded; full extraction and GPG verification
    # are performed before installation by the verifier bound to that hash.
    with tarfile.open(bundle,'r:gz') as archive:
        members=archive.getmembers()
        for name in ('payload_runtime.py','release_validation.py'):
            selected=[m for m in members if m.name=='release/artifacts/bootstrap/'+name]
            if len(selected)!=1 or not selected[0].isfile() or selected[0].size>128*1024:
                raise ValueError('Missing or ambiguous pinned verifier')
            with (base/name).open('xb') as stream:
                stream.write(archive.extractfile(selected[0]).read())
            (base/name).chmod(0o644)
    print('JDU_OFFLINE_REPO_LOADER=BUNDLE_HASH_AND_VERIFIER_BOUND',flush=True)
    runpy.run_path(str(base/'probe_offline_repo.py'),run_name='__main__')


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('JDU_OFFLINE_LOADER_FAILED='+type(exc).__name__,flush=True)
        try:
            config=json.loads(Path('/var/lib/jdu-repo-acceptance/private.json').read_text())
            data=json.dumps({'Status':'FAILURE','Reason':'Teacher loader failed: '+type(exc).__name__,
                'UniqueId':'teacher-repo','Data':'candidate-only'}).encode()
            request=urllib.request.Request(config['signal_url'],data=data,method='PUT',headers={'Content-Type':''})
            with urllib.request.urlopen(request,timeout=30) as response:
                if response.status!=200: raise ValueError('Failure signal not accepted')
        except Exception:
            print('JDU_OFFLINE_LOADER_FAILURE_SIGNAL_FAILED',flush=True)
        raise SystemExit(2)
