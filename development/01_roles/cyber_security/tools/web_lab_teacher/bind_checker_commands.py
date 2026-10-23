"""Bind an already signature-verified checker to existing personal deployment state.

No credentials are read, created or copied. The previous launcher/config remain
available for rollback. This does not create or register a new deployment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat


def bind(root, original, target, launcher):
    root=Path(root).resolve();original=Path(original);target=Path(target);launcher=Path(launcher)
    for path in (original,launcher):
        s=path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o077:
            raise ValueError('Existing personal state/launcher must remain private')
    manifest=json.loads((root/'CHECKER-MANIFEST.json').read_text())
    for e in manifest['files']:
        p=root/e['path']
        if p.is_symlink() or (hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size)!=(e['sha256'],e['size_bytes']):
            raise ValueError('Installed signed inventory changed')
    if target.exists() or Path(str(launcher)+'.before-signed-web02').exists():
        raise ValueError('Existing command binding retained')
    c=json.loads(original.read_text())
    c.update(scope='signed_checker_candidate_web02_only',bootstrap_tools=str(root))
    for key,name in [('guest_source','post_restart_guest.py'),('submission_source','bootstrap_submission_guest.py')]:
        c[key]=str(root/name);c[key+'_sha256']=hashlib.sha256((root/name).read_bytes()).hexdigest()
    with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w') as f:
        json.dump(c,f,indent=2)
    backup=Path(str(launcher)+'.before-signed-web02')
    with os.fdopen(os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700),'wb') as f:f.write(launcher.read_bytes())
    staged=Path(str(launcher)+'.signed-web02-new')
    with os.fdopen(os.open(staged,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700),'w') as f:
        f.write('#!/usr/bin/env bash\nset -euo pipefail\nexec python3 '+shlex.quote(str(root/'check_dispatch.py'))+' "$@" --command-state '+shlex.quote(str(target))+'\n')
    os.replace(staged,launcher)
    return dict(signed_inventory_verified=True,old_launcher_preserved=True,old_config_preserved=True,
        credentials_read=False,credentials_created=False,supported_tasks=['bootstrap','P1','M1'],class_ready=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('root','original','target','launcher'):p.add_argument('--'+n,required=True)
    a=p.parse_args();os.umask(0o077)
    try:print('SIGNED_CHECKER_BOUND='+json.dumps(bind(**vars(a)),separators=(',',':')))
    except Exception as exc:
        print('SIGNED_CHECKER_BIND_STOPPED='+type(exc).__name__);raise SystemExit(2)
