"""Reversible DNS/DB package installation from signed internal resources only.

Refuses existing student services/data and any simulated change to an installed
package. Keeps test configuration/data in a private archive before restoration.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request


def run(request):
    if os.geteuid()!=0:raise ValueError('Root package probe required')
    sys.dont_write_bytecode=True
    c=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text());role=c['role']
    if role not in ('dns','db') or any(c[k]!=request[k] for k in ('lab_id','deployment_id','instance_id','role')):
        raise ValueError('Only the selected clean DNS/DB node is allowed')
    library=Path('/usr/local/lib/jdu-web/web-2026-10-r1')
    for name in ('payload_runtime.py','release_validation.py'):
        if hashlib.sha256((library/name).read_bytes()).hexdigest()!=request['library_sha256'][name]:
            raise ValueError('Signed verification library differs')
    sys.path.insert(0,str(library));from payload_runtime import signed_manifest
    manifest,sums=signed_manifest('/var/lib/jdu-web/initial/client-metadata','/var/lib/jdu-web/initial/archive-key.asc',
        c['fingerprint'],c['release_id'],allow_package_candidate=True)
    selected=manifest['role_packages'][role+'_student_install']
    if not selected or len(selected)!=len(set(selected)):raise ValueError('Invalid role package contract')
    def command(args):
        return subprocess.run(args,capture_output=True,text=True,check=True,timeout=480,
            env=dict(os.environ,LC_ALL='C',DEBIAN_FRONTEND='noninteractive')).stdout
    def inventory():
        output=command(['dpkg-query','-W','-f=${Package}\t${Version}\t${db:Status-Status}\n'])
        return {a:b for a,b,status in (x.split('\t') for x in output.splitlines()) if status=='installed'}
    before=inventory();package='bind9' if role=='dns' else 'postgresql-16'
    if package in before or (role=='db' and Path('/var/lib/postgresql/16/main').exists()):
        raise ValueError('Existing student package or data retained')
    previous=Path('/var/lib/jdu-web')/(role+'-package-acceptance-v2')/'before-inventory.json'
    if previous.exists() and json.loads(previous.read_text())!=before:
        raise ValueError('Previous probe package restoration differs')
    work=Path('/var/lib/jdu-web')/(role+'-package-acceptance-v3');work.mkdir(mode=0o700,exist_ok=False)
    (work/'before-inventory.json').write_text(json.dumps(before,indent=2))
    prefix='http://10.20.2.30/releases/'+c['release_id']+'/'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(prefix+'manifests/deb-packages.json',timeout=30) as r:raw=r.read(4*1024*1024)
    if hashlib.sha256(raw).hexdigest()!=sums['manifests/deb-packages.json']:raise ValueError('Package manifest differs')
    versions={p['package']:p['version'] for p in json.loads(raw)}
    for name in ('lists','cache'):(work/name).mkdir()
    assert not list((work/'lists').iterdir()) and not list((work/'cache').iterdir())
    source=work/'internal.sources';source.write_text('Types: deb\nURIs: '+prefix+'apt/\nSuites: jdu-noble\nComponents: main\nArchitectures: amd64\nSigned-By: /usr/share/keyrings/jdu-web-archive-keyring.gpg\n')
    apt=['apt-get','-o','Dir::Etc::sourcelist='+str(source),'-o','Dir::Etc::sourceparts=-',
        '-o','Dir::State::lists='+str(work/'lists'),'-o','Dir::Cache::archives='+str(work/'cache'),'-o','Dpkg::Lock::Timeout=480']
    direct=[p+'='+versions[p] for p in selected]
    command(apt+['update','-o','APT::Update::Error-Mode=any'])
    simulated=command(apt+['--simulate','install','--no-install-recommends',*direct]);(work/'install-simulation.txt').write_text(simulated)
    if any(re.match(r'Inst\s+\S+\s+\[',line) or line.startswith('Remv ') for line in simulated.splitlines()):
        raise ValueError('Existing package change required; installation not attempted')
    install_attempted=False;success=False;added=[];version='';service=False
    try:
        install_attempted=True;command(apt+['install','-y','--no-install-recommends',*direct])
        after=inventory();added=sorted(set(after)-set(before))
        if any(after.get(p)!=v for p,v in before.items()):raise ValueError('Existing installed versions changed')
        if any(after[p]!=versions[p] for p in selected):raise ValueError('Role package version differs')
        if role=='dns':
            version=command(['/usr/sbin/named','-v']).strip();checkconf=shutil.which('named-checkconf')
            if not checkconf:raise ValueError('BIND configuration checker missing from PATH')
            command([checkconf])
            service=subprocess.run(['systemctl','is-active','--quiet','named']).returncode==0
        else:
            version=command(['/usr/lib/postgresql/16/bin/postgres','--version']).strip()
            command(['/usr/lib/postgresql/16/bin/pg_isready','-h','/var/run/postgresql','-p','5432'])
            service=subprocess.run(['systemctl','is-active','--quiet','postgresql@16-main']).returncode==0
        if not service:raise ValueError('Default role service did not start')
        success=True
    finally:
        if install_attempted:
            current=inventory();added=sorted(set(current)-set(before))
            if any(current.get(p)!=v for p,v in before.items()) or not set(added)<=set(versions):
                raise ValueError('Unexpected package changes; preserve for diagnosis')
            if package in current:
                subprocess.run(['systemctl','stop','named' if role=='dns' else 'postgresql@16-main'],check=True)
            paths=['/etc/bind','/var/cache/bind'] if role=='dns' else ['/etc/postgresql','/var/lib/postgresql','/var/log/postgresql']
            existing=[p for p in paths if Path(p).exists()]
            if existing:command(['tar','-czf',str(work/'test-config-and-data.tar.gz'),*existing])
            if added:command(['apt-get','-y','purge',*added])
            if inventory()!=before:raise ValueError('Original installed package versions not restored')
    if not success:raise ValueError('Offline role installation did not complete')
    return dict(deployment_id=c['deployment_id'],instance_id=c['instance_id'],role=role,scope='offline_role_package_not_classroom_configuration',
        empty_apt_cache_at_start=True,signed_internal_ip_repository_only=True,pinned_role_packages=selected,
        added_packages=added,service_started=True,version=version,original_package_versions_restored=True,
        fixture_config_and_data_archived=True,new_passwords_or_keys_created=False,root_free_bytes=shutil.disk_usage('/').free,class_ready=False)


if __name__=='__main__':
    try:print(json.dumps(run(json.loads(sys.stdin.read(65537))),separators=(',',':')))
    except Exception as e:
        print('ROLE_PACKAGE_PROBE_STOPPED='+type(e).__name__+': '+str(e));raise SystemExit(2)
