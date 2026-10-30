"""Place only public lesson files; never install packages or configure services."""
import base64
import json
import os
from pathlib import Path
import stat


def directory(path):
    s=path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:
        raise ValueError('Root-controlled lesson directory required')


def stage(request,*,root=Path('/var/lib/jdu-web/lesson-resources-r1'),bootstrap=Path('/etc/jdu-web/bootstrap.json')):
    b=json.loads(bootstrap.read_text())
    if (os.geteuid()!=0 or b.get('role') not in ('web','db') or set(request)!={'lab_id','deployment_id','instance_id','role','files'}
            or any(b.get(k)!=request[k] for k in ('lab_id','deployment_id','instance_id','role'))
            or set(request['files'])!={'catalog-app.tar.gz','registry.py','assessment-registry.json','database_secret.py','offline_assets.py'}):
        raise ValueError('Own registered lesson target required')
    files={name:base64.b64decode(value,validate=True) for name,value in request['files'].items()}
    if any(len(v)>256*1024 for v in files.values()):raise ValueError('Public lesson file exceeds limit')
    for parent in root.parents:directory(parent)
    if not root.exists() and not root.is_symlink():root.mkdir(mode=0o755)
    directory(root)
    # Inspect every existing file before writing a missing one. A partial
    # initial staging can be resumed, but no different file is overwritten.
    if set(p.name for p in root.iterdir())-set(files):raise ValueError('Existing unrelated lesson content retained')
    for name,data in files.items():
        target=root/name
        if target.exists() or target.is_symlink():
            s=target.lstat()
            if (not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or stat.S_IMODE(s.st_mode)!=0o644
                    or s.st_nlink!=1 or target.read_bytes()!=data):
                raise ValueError('Existing different lesson content retained')
    for name,data in files.items():
        target=root/name
        if not target.exists():
            with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644),'wb') as stream:
                os.fchmod(stream.fileno(),0o644);stream.write(data)
    return {'public_resources_ready':True,'role':b['role'],'file_count':len(files),'services_changed':False}


if __name__=='__main__':
    import sys
    try:
        os.umask(0o022)
        print(json.dumps(stage(json.loads(sys.stdin.read(1024*1024))),separators=(',',':')))
    except Exception:
        print('PUBLIC_LESSON_STAGING_UNAVAILABLE')
        raise SystemExit(2)
