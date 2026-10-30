"""Bounded extraction of a signature-bound controller archive before imports."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile


def controller_files(data):
    if len(data)>4*1024*1024:raise ValueError('Controller bundle too large')
    files={};total=0
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
        for m in tar:
            if (not m.isfile() or not m.name.startswith('controller/') or len(m.name.split('/'))!=2
                    or m.name.split('/')[1] in ('','.','..') or '\\' in m.name or ':' in m.name
                    or m.name in files or m.size<0 or m.size>256*1024 or len(files)>=100):
                raise ValueError('Unsafe controller archive')
            total+=m.size
            if total>4*1024*1024:raise ValueError('Controller archive too large')
            files[m.name]=tar.extractfile(m).read()
    m=json.loads(files['controller/CONTROLLER-MANIFEST.json']);entries={e['path']:e for e in m['files']}
    if (m['artifact']!='jdu-web-student-controller' or m['credentials_included'] is not False
            or len(entries)!=len(m['files']) or set(files)!={'controller/'+n for n in entries}|{'controller/CONTROLLER-MANIFEST.json'}):
        raise ValueError('Controller inventory differs')
    for name,e in entries.items():
        if (hashlib.sha256(files['controller/'+name]).hexdigest(),len(files['controller/'+name]))!=(e['sha256'],e['size_bytes']):
            raise ValueError('Controller source hash differs')
    return {n.removeprefix('controller/'):v for n,v in files.items()}


def install_controller(data,target):
    files=controller_files(data);target=Path(target)
    if any(p.is_symlink() for p in [target,*target.parents]):raise ValueError('Linked controller cache refused')
    if target.exists():
        if {p.name for p in target.iterdir()}!=set(files):raise ValueError('Controller cache inventory changed')
        for n,raw in files.items():
            p=target/n;s=p.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o077 or p.read_bytes()!=raw:
                raise ValueError('Controller cache changed')
    else:
        target.mkdir(mode=0o700,parents=True)
        for name,raw in files.items():
            with os.fdopen(os.open(target/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
    return target
