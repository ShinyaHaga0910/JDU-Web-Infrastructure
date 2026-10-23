"""Teacher-only candidate acceptance on a private Ubuntu node without Internet."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import time
import urllib.request

import payload_runtime as runtime


def main():
    os.umask(0o022)
    base=Path('/var/lib/jdu-repo-acceptance')
    config=json.loads((base/'private.json').read_text())
    result={'scope':'one_private_repo_package_candidate_not_student_five_node_acceptance','checks':{}}
    checks=result['checks']
    # Baseline evidence before any package operation.
    checks['initial_apt_cache_empty']=not any(Path('/var/cache/apt/archives').glob('*.deb'))
    if not checks['initial_apt_cache_empty']:
        raise ValueError('Probe cache must start empty')
    bundle=base/'payload.tar.gz'
    if not bundle.is_file():
        raise ValueError('The pinned loader must fetch the bundle first')
    with bundle.open('rb') as stream:
        sha=hashlib.file_digest(stream,'sha256').hexdigest()
    if sha!=config['bundle_sha256']:
        raise ValueError('Candidate transfer hash mismatch')
    checks['bundle_hash_verified']=True
    root=runtime.safe_extract(bundle,base/'stage',sha)
    key=base/'archive-key.asc'
    release=runtime.verify_tree(root,key,config['fingerprint'],config['release_id'],allow_package_candidate=True)
    checks['signature_and_all_file_hashes_verified']=True
    runtime.install_repo(root,key,config['fingerprint'],config['release_id'],allow_package_candidate=True)
    checks['common_and_nginx_installed_without_download']=True
    prefix='http://10.20.2.30/releases/'+config['release_id']+'/'
    for name in ('manifests/release.json','apt/dists/jdu-noble/InRelease','artifacts/python/requirements.lock'):
        with urllib.request.urlopen(prefix+name,timeout=15) as response:
            data=response.read(16*1024**2)
            expected=(root/name).read_bytes()
            if response.status!=200 or data!=expected:
                raise ValueError('Internal HTTP resource mismatch')
    checks['internal_http_resources_match']=True
    fresh=base/'http-apt'; fresh.mkdir(); (fresh/'lists').mkdir(); (fresh/'archives').mkdir()
    source=Path('/etc/apt/sources.list.d/jdu-web.sources')
    runtime.apt_command('update',source,fresh/'lists',fresh/'archives','-o','APT::Update::Error-Mode=any')
    checks['fresh_http_apt_signed_update']=True
    packages=json.loads((root/'manifests/deb-packages.json').read_text())
    versions={p['package']:p['version'] for p in packages}
    targets=sorted({p for role in ('dns_student_install','db_student_install','web_student_install') for p in release['role_packages'][role]})
    runtime.apt_command('install',source,fresh/'lists',fresh/'archives','--download-only','-y',*[p+'='+versions[p] for p in targets])
    checks['student_package_downloads_from_internal_http']=True
    checks['student_services_remain_uninstalled']=all(subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}',p],capture_output=True,text=True).stdout.strip()!='installed' for p in ('bind9','postgresql-16'))
    if not checks['student_services_remain_uninstalled']:
        raise ValueError('Teacher download check installed a student service')
    # The known-live teacher ingress must be unreachable from this repo.
    # CloudShell separately verifies VPC routes/SG/no public IP; an EC2 guest
    # normally has an OS default route even when its VPC has no Internet route.
    try:
        connection=socket.create_connection((config['teacher_ipv4'],443),timeout=5)
    except OSError:
        checks['known_live_teacher_ingress_denied_from_repo']=True
    else:
        connection.close()
        raise ValueError('Unexpected repo egress to teacher ingress')
    free=__import__('shutil').disk_usage('/'); checks['root_space_at_least_20pct_and_2gib']=free.free>=2*1024**3 and free.free/free.total>=.2
    result.update(package_count=release['package_count'],wheel_count=release['wheel_count'],bundle_sha256=sha,
        release_id=config['release_id'],all_checks_passed=all(checks.values()),student_release_ready=False)
    if not result['all_checks_passed']:
        raise ValueError('Offline repo acceptance has a failed check')
    (base/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('JDU_OFFLINE_REPO_RESULT='+json.dumps(result),flush=True)
    signal(config['signal_url'],'SUCCESS','Teacher candidate repo checks passed')


def signal(url,status,reason):
    data=json.dumps({'Status':status,'Reason':reason,'UniqueId':'teacher-repo','Data':'candidate-only'}).encode()
    for attempt in range(3):
        try:
            request=urllib.request.Request(url,data=data,method='PUT',headers={'Content-Type':''})
            with urllib.request.urlopen(request,timeout=30) as response:
                if response.status!=200: raise ValueError('Wait signal was not accepted')
            return
        except Exception:
            if attempt==2: raise
            time.sleep(3)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('JDU_OFFLINE_REPO_FAILED='+type(exc).__name__,flush=True)
        try:
            config=json.loads(Path('/var/lib/jdu-repo-acceptance/private.json').read_text())
            signal(config['signal_url'],'FAILURE','Teacher repo check failed: '+type(exc).__name__)
        except Exception:
            print('JDU_OFFLINE_SIGNAL_FAILED',flush=True)
        raise SystemExit(2)
