"""Role bootstrap: repo/GUI are prepared, DNS/DB/Web construction stays with students."""
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.dont_write_bytecode=True
import payload_runtime as runtime
from release_validation import ValidationError, file_digest, json_bytes, relative_file

BASE=Path('/var/lib/jdu-web/initial')
IPS={'bastion':'10.20.1.10','web':'10.20.1.20','dns':'10.20.2.10','db':'10.20.2.20','repo':'10.20.2.30'}
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
BOOTSTRAP_STAGE='configuration'
STAGES={'configuration','identity','access_validation','repo_extract','repo_verify','repo_install',
    'client_metadata','client_install','ssh','rdp','role_checks','host_state','signal'}


def enter_stage(stage):
    global BOOTSTRAP_STAGE
    if stage not in STAGES:raise ValueError('Unknown bootstrap stage')
    BOOTSTRAP_STAGE=stage


def failure_detail(exc,stage):
    """Only fixed labels and numeric exit codes; never exception text or argv."""
    result={'stage':stage if stage in STAGES else 'configuration','error_class':type(exc).__name__}
    if isinstance(exc,subprocess.CalledProcessError):
        command=exc.cmd[0] if isinstance(exc.cmd,(list,tuple)) and exc.cmd else None
        if command in {'apt-get','gpg','dpkg-query','ssh-keygen','sshd','systemctl','useradd','chpasswd','usermod'}:
            result['command']=command
        if type(exc.returncode) is int:result['returncode']=exc.returncode
    return result


def get(url,limit=16*1024**2,headers=None,method='GET'):
    request=urllib.request.Request(url,headers=headers or {},method=method)
    for attempt in range(3):
        try:
            with OPENER.open(request,timeout=30) as response:
                data=response.read(limit+1)
                if response.status!=200 or len(data)>limit: raise ValidationError('Invalid bootstrap response')
                return data
        except (OSError,urllib.error.URLError):
            if attempt==2: raise
            time.sleep(attempt+1)


def identity(config):
    required={'schema_version','lab_id','deployment_id','release_id','role','fingerprint','expected_scope',
        'script_pins','signal_url','student_public_key','grading_api_url','grading_ipv4','s3_probe_ipv4','direct_api_probe_ipv4'}
    optional={'bundle_url','bundle_sha256','rdp_hash','peer_instances'}
    if set(config)-required-optional or not required<=set(config) or type(config['schema_version']) is not int or config['schema_version']!=1:
        raise ValidationError('Bootstrap configuration fields differ')
    if (not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}',config['lab_id'])
            or not re.fullmatch(r'web-[0-9]{4}-[0-9]{2}-r[1-9][0-9]*',config['release_id'])
            or config['role'] not in IPS or not re.fullmatch(r'[A-F0-9]{40}',config['fingerprint'])
            or config['expected_scope'] not in ('student_payload','package_only_candidate')):
        raise ValidationError('Bootstrap identity differs')
    deployment=uuid.UUID(config['deployment_id'])
    if str(deployment)!=config['deployment_id'] or deployment.version!=4:
        raise ValidationError('Expected a deployment UUID v4')
    if any(not ipaddress.IPv4Address(config[k]).is_global for k in ('grading_ipv4','s3_probe_ipv4','direct_api_probe_ipv4')):
        raise ValidationError('Network control addresses must be public IPv4')
    release=dict(line.split('=',1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if (os.geteuid()!=0 or release.get('ID')!='ubuntu' or release.get('VERSION_ID','').strip('"')!='24.04'
            or platform.machine()!='x86_64' or sys.version_info[:2]!=(3,12)):
        raise ValidationError('Expected root / Ubuntu 24.04 / x86_64 / Python 3.12')
    token=get('http://169.254.169.254/latest/api/token',256,{'X-aws-ec2-metadata-token-ttl-seconds':'21600'},'PUT').decode()
    headers={'X-aws-ec2-metadata-token':token}
    instance=get('http://169.254.169.254/latest/meta-data/instance-id',64,headers).decode()
    address=get('http://169.254.169.254/latest/meta-data/local-ipv4',64,headers).decode()
    if not re.fullmatch(r'i-[0-9a-f]{17}',instance) or address!=IPS[config['role']]:
        raise ValidationError('Instance role/private IP mismatch')
    return instance


def fetch_metadata(config):
    root=BASE/'client-metadata'; (root/'manifests').mkdir(parents=True,exist_ok=False)
    prefix='http://10.20.2.30/releases/'+config['release_id']+'/'
    for name in ('SHA256SUMS','SHA256SUMS.asc','release.json'):
        (root/'manifests'/name).write_bytes(get(prefix+'manifests/'+name))
    manifest,entries=runtime.signed_manifest(root,BASE/'archive-key.asc',config['fingerprint'],config['release_id'],
        allow_package_candidate=config['expected_scope']=='package_only_candidate')
    if manifest['scope']!=config['expected_scope']: raise ValidationError('Payload scope differs')
    for name in ('manifests/deb-packages.json','artifacts/bootstrap/package-profile.json'):
        data=get(prefix+name)
        if hashlib.sha256(data).hexdigest()!=entries.get(name): raise ValidationError('Signed package metadata differs')
        path=relative_file(root,name,require_exists=False); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    return root,manifest


def keyring_and_source(root,config):
    keyring=Path('/usr/share/keyrings/jdu-web-archive-keyring.gpg')
    if keyring.exists(): raise ValidationError('Existing archive key retained')
    subprocess.run(['gpg','--batch','--yes','--dearmor','--output',str(keyring),str(BASE/'archive-key.asc')],check=True)
    keyring.chmod(0o644)
    workspace=Path('/var/lib/jdu-web/offline-apt'); workspace.mkdir(mode=0o755,parents=True,exist_ok=False)
    lists=workspace/'lists'; lists.mkdir(mode=0o755); cache=workspace/'archives'; cache.mkdir(mode=0o755)
    source=workspace/'internal.sources'
    source.write_text('Types: deb\nURIs: http://10.20.2.30/releases/'+config['release_id']+'/apt/\nSuites: jdu-noble\nComponents: main\nArchitectures: amd64\nSigned-By: '+str(keyring)+'\n')
    source.chmod(0o644)
    return source,lists,cache


def park_external_sources(source):
    directory=Path('/etc/apt/sources.list.d')
    for path in directory.iterdir():
        if path.suffix in ('.list','.sources'):
            target=path.with_name(path.name+'.jdu-disabled')
            if target.exists(): raise ValidationError('Existing APT backup retained')
            path.rename(target)
    legacy=Path('/etc/apt/sources.list')
    if legacy.exists() and legacy.read_text().strip():
        target=legacy.with_name('sources.list.jdu-disabled')
        if target.exists(): raise ValidationError('Existing legacy APT backup retained')
        legacy.rename(target)
    shutil.copy2(source,directory/'jdu-web.sources')


def install_client(root,manifest,config):
    source,lists,cache=keyring_and_source(root,config)
    packages=json_bytes((root/'manifests/deb-packages.json').read_bytes())
    versions={p['package']:p['version'] for p in packages}
    targets=set(manifest['role_packages']['common'])
    if config['role']=='bastion': targets.update(manifest['role_packages']['bastion'])
    runtime.apt_command('update',source,lists,cache,'-o','APT::Update::Error-Mode=any')
    runtime.apt_command('install',source,lists,cache,'-y',*[p+'='+versions[p] for p in sorted(targets)])
    park_external_sources(source)
    Path('/etc/chrony/conf.d/jdu-web.conf').write_text('server 169.254.169.123 prefer iburst minpoll 4 maxpoll 4\n')
    subprocess.run(['systemctl','enable','--now','chrony'],check=True)
    subprocess.run(['systemctl','restart','chrony'],check=True)


def validate_access(config):
    public=config['student_public_key'].split()
    if len(public)!=2 or public[0] not in ('ssh-rsa','ssh-ed25519'):
        raise ValidationError('Expected a normalized student public key')
    authorized=Path('/home/ubuntu/.ssh/authorized_keys').read_text().splitlines()
    if not any(line.split()[:2]==public for line in authorized):
        raise ValidationError('EC2 key differs from the planned student public key')
    if config['role']=='bastion':
        if not re.fullmatch(r'\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}',config.get('rdp_hash','')):
            raise ValidationError('Expected a Lab-specific SHA512 crypt hash')
        try: pwd.getpwnam('labuser')
        except KeyError: pass
        else: raise ValidationError('Existing RDP user retained')
    return public


def prepare_sshd_runtime(path=Path('/run/sshd')):
    """sshd -t runs before systemd creates its root-owned runtime directory."""
    try:
        path.mkdir(mode=0o755)
    except FileExistsError:
        pass
    info=path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_gid!=0
            or stat.S_IMODE(info.st_mode)!=0o755):
        raise ValidationError('Unsafe SSH runtime directory')


def configure_ssh(config):
    public=validate_access(config)
    directory=Path('/etc/jdu-web'); directory.mkdir(mode=0o755,exist_ok=True)
    (directory/'student.pub').write_text(' '.join(public)+'\n'); (directory/'student.pub').chmod(0o644)
    subprocess.run(['ssh-keygen','-lf',str(directory/'student.pub')],check=True,stdout=subprocess.DEVNULL)
    path=Path('/etc/ssh/sshd_config.d/05-jdu-web-key-only.conf')
    if path.exists(): raise ValidationError('Existing SSH policy retained')
    path.write_text('PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\nPubkeyAuthentication yes\n')
    prepare_sshd_runtime()
    subprocess.run(['sshd','-t'],check=True); subprocess.run(['systemctl','restart','ssh'],check=True)


def configure_bastion(config):
    secret=config.get('rdp_hash','')
    if not re.fullmatch(r'\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}',secret):
        raise ValidationError('Expected a Lab-specific SHA512 crypt hash')
    try: pwd.getpwnam('labuser')
    except KeyError: pass
    else: raise ValidationError('Existing RDP user retained')
    subprocess.run(['useradd','--create-home','--shell','/bin/bash','labuser'],check=True)
    subprocess.run(['chpasswd','--encrypted'],input=('labuser:'+secret+'\n').encode(),check=True)
    user=pwd.getpwnam('labuser'); home=Path(user.pw_dir); home.chmod(0o700)
    session=home/'.xsession'; session.write_text('unset DBUS_SESSION_BUS_ADDRESS\nexec dbus-run-session -- startxfce4\n'); session.chmod(0o700); os.chown(session,user.pw_uid,user.pw_gid)
    policies=Path('/etc/firefox/policies'); policies.mkdir(parents=True,exist_ok=True)
    target=policies/'policies.json'
    if target.exists(): raise ValidationError('Existing Firefox policies retained')
    target.write_text(json.dumps({'policies':{'DNSOverHTTPS':{'Enabled':False,'Locked':True},'DisableAppUpdate':True,'DisableTelemetry':True,'DisableFirefoxStudies':True,'OverrideFirstRunPage':'','OverridePostUpdatePage':''}},indent=2)+'\n')
    subprocess.run(['usermod','-a','-G','ssl-cert','xrdp'],check=True)
    subprocess.run(['systemctl','enable','--now','xrdp'],check=True)
    subprocess.run(['systemctl','restart','xrdp'],check=True)


def check_initial(config,manifest,root):
    checks={'ssh_active':subprocess.run(['systemctl','is-active','--quiet','ssh']).returncode==0,
        'chrony_active':subprocess.run(['systemctl','is-active','--quiet','chrony']).returncode==0}
    forbidden={'dns':'bind9','db':'postgresql-16','web':'nginx'}
    role=config['role']
    packages=json_bytes((root/'manifests/deb-packages.json').read_bytes())
    versions={p['package']:p['version'] for p in packages}
    expected=set(manifest['role_packages']['common'])
    if role in ('bastion','repo'): expected.update(manifest['role_packages'][role])
    installed=subprocess.run(['dpkg-query','-W','-f=${Package}\t${Version}\t${db:Status-Status}\n',*sorted(expected)],capture_output=True,text=True,check=True)
    observed={parts[0]:(parts[1],parts[2]) for line in installed.stdout.splitlines() if len(parts:=line.split('\t'))==3}
    checks['pinned_role_packages_installed']=all(observed.get(p)==(versions[p],'installed') for p in expected)
    if role in forbidden:
        status=subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}',forbidden[role]],capture_output=True,text=True)
        checks['student_service_not_installed']=status.stdout.strip()!='installed'
    if role=='bastion':
        checks['rdp_active']=subprocess.run(['systemctl','is-active','--quiet','xrdp']).returncode==0
        checks['desktop_browser_and_dbus_present']=all(shutil.which(p) for p in ('startxfce4','firefox','dbus-run-session'))
        checks['rdp_user_not_admin']=subprocess.run(['id','-nG','labuser'],capture_output=True,text=True).stdout.split().count('sudo')==0
    if role=='repo':
        data=get('http://10.20.2.30/releases/'+config['release_id']+'/manifests/release.json')
        checks['repo_http_manifest_served']=json_bytes(data)['release_id']==config['release_id']
    space=shutil.disk_usage('/'); checks['root_free_space']=space.free>=2*1024**3 and space.free/space.total>=.2
    if not all(checks.values()): raise ValidationError('A required role preparation check failed')
    return checks


def signal(config,status,reason,instance,data):
    body=json.dumps({'Status':status,'Reason':reason,'UniqueId':instance,'Data':data}).encode()
    request=urllib.request.Request(config['signal_url'],data=body,method='PUT',headers={'Content-Type':''})
    for attempt in range(3):
        try:
            with OPENER.open(request,timeout=30) as response:
                if response.status!=200: raise ValidationError('Role signal not accepted')
            return
        except (OSError,urllib.error.URLError):
            if attempt==2: raise
            time.sleep(attempt+1)


def main():
    os.umask(0o022)
    enter_stage('configuration');config=json_bytes((BASE/'private.json').read_bytes())
    enter_stage('identity');instance=identity(config)
    state=Path('/var/lib/jdu-web/bootstrap/role-state.json')
    if state.exists(): raise ValidationError('Existing host state retained; use read-only checks')
    if any(Path('/var/cache/apt/archives').glob('*.deb')):
        raise ValidationError('Initial global APT cache is not empty')
    enter_stage('access_validation');validate_access(config)
    candidate=config['expected_scope']=='package_only_candidate'
    if config['role']=='repo':
        enter_stage('repo_extract')
        root=runtime.safe_extract(BASE/'payload.tar.gz',BASE/'stage',config['bundle_sha256'])
        enter_stage('repo_verify')
        manifest=runtime.verify_tree(root,BASE/'archive-key.asc',config['fingerprint'],config['release_id'],allow_package_candidate=candidate)
        if manifest['scope']!=config['expected_scope']: raise ValidationError('Payload scope differs')
        enter_stage('repo_install')
        runtime.install_repo(root,BASE/'archive-key.asc',config['fingerprint'],config['release_id'],allow_package_candidate=candidate)
    else:
        enter_stage('client_metadata');root,manifest=fetch_metadata(config)
        enter_stage('client_install');install_client(root,manifest,config)
    enter_stage('ssh')
    configure_ssh(config)
    if config['role']=='bastion':
        enter_stage('rdp');configure_bastion(config)
    enter_stage('role_checks')
    checks=check_initial(config,manifest,root)
    checks['initial_global_apt_cache_empty']=True
    public={k:config[k] for k in ('schema_version','lab_id','deployment_id','release_id','role','fingerprint','expected_scope','grading_api_url','grading_ipv4','s3_probe_ipv4','direct_api_probe_ipv4')}
    public.update(instance_id=instance,private_ip=IPS[config['role']])
    if config['role']=='bastion':
        peers=config.get('peer_instances',{})
        if set(peers)!=set(IPS)-{'bastion'} or any(not re.fullmatch(r'i-[0-9a-f]{17}',v) for v in peers.values()):
            raise ValidationError('Expected four concrete peer instance IDs')
        public['instances']=dict(peers,bastion=instance)
    enter_stage('host_state')
    destination=Path('/etc/jdu-web/bootstrap.json'); destination.write_text(json.dumps(public,indent=2)+'\n'); destination.chmod(0o644)
    library=Path('/usr/local/lib/jdu-web')/config['release_id']; library.mkdir(mode=0o755,parents=True,exist_ok=False)
    for name in config['script_pins']:
        shutil.copy2(BASE/name,library/name); (library/name).chmod(0o644)
    Path('/etc/systemd/system/jdu-web-network-probe.service').write_text('[Unit]\nDescription=Temporary Web Lab foundation network check\nAfter=network-online.target\n[Service]\nType=oneshot\nExecStart=/usr/bin/python3 '+str(library/'network_probe.py')+'\n')
    Path('/etc/systemd/system/jdu-web-network-probe.timer').write_text('[Unit]\nDescription=Temporary Web Lab close-transition check\n[Timer]\nOnBootSec=30\nOnUnitActiveSec=30\nAccuracySec=2\n[Install]\nWantedBy=timers.target\n')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','jdu-web-network-probe.timer'],check=True)
    result={k:public[k] for k in ('lab_id','deployment_id','release_id','role','instance_id','expected_scope')}
    result.update(stage='ROLE_PREPARED',checked_at=datetime.now(timezone.utc).isoformat(),checks=checks,student_release_ready=False)
    state.parent.mkdir(parents=True,exist_ok=True); state.write_text(json.dumps(result,indent=2)+'\n')
    print('JDU_NODE_ROLE_RESULT='+json.dumps(result),flush=True)
    enter_stage('signal')
    signal(config,'SUCCESS','Role preparation checks passed',instance,
        json.dumps({'role':config['role'],'instance_id':instance,'deployment_id':config['deployment_id']}))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('JDU_NODE_BOOTSTRAP_FAILED='+type(exc).__name__,flush=True)
        print('JDU_NODE_FAILURE_DETAIL='+json.dumps(failure_detail(exc,BOOTSTRAP_STAGE),sort_keys=True),flush=True)
        try:
            config=json_bytes((BASE/'private.json').read_bytes())
            signal(config,'FAILURE','Role preparation failed: '+type(exc).__name__,'failed-'+config['role'],'not-ready')
        except Exception:
            print('JDU_NODE_BOOTSTRAP_FAILURE_SIGNAL_FAILED',flush=True)
        raise SystemExit(2)
