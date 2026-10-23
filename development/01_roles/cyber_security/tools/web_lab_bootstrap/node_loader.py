"""Small trusted first-boot loader. Verify pinned bytes before loading code."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import tarfile
import urllib.request

BASE=Path('/var/lib/jdu-web/initial')


def fetch(url,target,limit):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    size=0
    with opener.open(url,timeout=120) as response,target.open('xb') as stream:
        if response.status!=200: raise ValueError('Unexpected bootstrap response')
        while block:=response.read(1024*1024):
            size+=len(block)
            if size>limit: raise ValueError('Bootstrap resource exceeds bound')
            stream.write(block)


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    os.umask(0o022)
    config=json.loads((BASE/'private.json').read_text())
    pins=config['script_pins']
    if set(pins)!={'node_bootstrap.py','payload_runtime.py','release_validation.py','network_probe.py'}:
        raise ValueError('Unexpected pinned bootstrap scripts')
    if config['role']=='repo':
        bundle=BASE/'payload.tar.gz'; fetch(config['bundle_url'],bundle,2*1024**3)
        if sha(bundle)!=config['bundle_sha256']: raise ValueError('Pinned bundle hash mismatch')
        with tarfile.open(bundle,'r:gz') as archive:
            members=archive.getmembers()
            for name,expected in pins.items():
                found=[m for m in members if m.name=='release/artifacts/bootstrap/'+name]
                if len(found)!=1 or not found[0].isfile() or found[0].size>128*1024:
                    raise ValueError('Missing or ambiguous pinned bootstrap script')
                (BASE/name).write_bytes(archive.extractfile(found[0]).read())
                if sha(BASE/name)!=expected: raise ValueError('Pinned bootstrap script differs')
    else:
        for name,expected in pins.items():
            target=BASE/name
            fetch('http://10.20.2.30/releases/'+config['release_id']+'/artifacts/bootstrap/'+name,target,128*1024)
            if sha(target)!=expected: raise ValueError('Pinned bootstrap script differs')
    print('JDU_NODE_LOADER=PINNED_SCRIPTS_VERIFIED',flush=True)
    runpy.run_path(str(BASE/'node_bootstrap.py'),run_name='__main__')


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('JDU_NODE_LOADER_FAILED='+type(exc).__name__,flush=True)
        try:
            config=json.loads((BASE/'private.json').read_text())
            body=json.dumps({'Status':'FAILURE','Reason':'Bootstrap loader failed: '+type(exc).__name__,
                'UniqueId':'failed-'+config['role'],'Data':'not-ready'}).encode()
            request=urllib.request.Request(config['signal_url'],data=body,method='PUT',headers={'Content-Type':''})
            with urllib.request.urlopen(request,timeout=30) as response:
                if response.status!=200: raise ValueError('Failure signal rejected')
        except Exception:
            print('JDU_NODE_LOADER_FAILURE_SIGNAL_FAILED',flush=True)
        raise SystemExit(2)
