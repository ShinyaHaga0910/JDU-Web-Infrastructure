"""Teacher-only, reversible WEB-02 acceptance fixture. Never in student bundle.

Refuses an existing student Nginx installation/configuration. Saves the original
package inventory, installs only signed internal packages, preserves its test
files in the fixture workspace when restoring the original package state.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path('/var/lib/jdu-web/web02-acceptance-v1')


def command(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=480).stdout


def packages():
    result = command(['dpkg-query', '-W', '-f=${Package}\t${db:Status-Status}\n'])
    return sorted(line.split('\t')[0] for line in result.splitlines() if line.endswith('\tinstalled'))


def run(r):
    if os.geteuid() != 0: raise ValueError('Root fixture helper required')
    b = json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if b['role'] != 'web' or any(b[k] != r[k] for k in ('lab_id', 'deployment_id', 'instance_id')):
        raise ValueError('Wrong Web node')
    if r['operation'] == 'install':
        before = packages()
        if ('nginx' in before or 'nginx-common' in before or Path('/etc/nginx').exists()
                or Path('/var/www/html').exists() or ROOT.exists()):
            raise ValueError('Existing student state retained; not a clean fixture target')
        ROOT.mkdir(mode=0o700)
        state = dict(deployment_id=b['deployment_id'], instance_id=b['instance_id'], before=before,
                     stage='prepared', original_nginx_absent=True)
        (ROOT/'state.json').write_text(json.dumps(state))
        prefix = 'http://10.20.2.30/releases/' + b['release_id'] + '/'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(prefix + 'manifests/deb-packages.json',timeout=15) as response:
            versions = {p['package']:p['version'] for p in json.loads(response.read(4*1024*1024))}
        # The repository is already pinned to the verified signing key by bootstrap.
        source = ROOT/'internal.sources'
        source.write_text('Types: deb\nURIs: '+prefix+'apt/\nSuites: jdu-noble\nComponents: main\nArchitectures: amd64\nSigned-By: /usr/share/keyrings/jdu-web-archive-keyring.gpg\n')
        for name in ('lists','cache'): (ROOT/name).mkdir()
        apt = ['apt-get','-o','Dir::Etc::sourcelist='+str(source),'-o','Dir::Etc::sourceparts=-',
            '-o','Dir::State::lists='+str(ROOT/'lists'),'-o','Dir::Cache::archives='+str(ROOT/'cache'),
            '-o','Dpkg::Lock::Timeout=480']
        command(apt+['update','-o','APT::Update::Error-Mode=any'])
        command(apt+['install','-y','--no-install-recommends','nginx='+versions['nginx']])
        state['added'] = sorted(set(packages())-set(before)); state['stage']='installed'
        (ROOT/'state.json').write_text(json.dumps(state))
        return dict(operation='install',added_packages=state['added'],signed_internal_repository_only=True)
    state = json.loads((ROOT/'state.json').read_text())
    if any(state[k]!=b[k] for k in ('deployment_id','instance_id')) or state['stage']=='restored':
        raise ValueError('Wrong or already restored fixture')
    op = r['operation']
    if op in ('practice','mission','wrong','loopback','normal'):
        if op in ('practice','mission','wrong'):
            if op == 'practice':
                (Path('/var/www/html')/'practice.txt').write_text('JDU WEB-02 practice: HTTP response verified.\n')
            else:
                (Path('/var/www/html')/'mission.txt').write_text('wrong response\n' if op=='wrong'
                    else 'JDU WEB-02 mission: independent HTTP delivery.\n')
            for p in Path('/var/www/html').glob('*.txt'):p.chmod(0o644)
        if op in ('loopback','normal'):
            path=Path('/etc/nginx/sites-enabled/default')
            original=ROOT/'default.site'
            if not original.exists():original.write_bytes(path.read_bytes())
            data=original.read_text()
            if op=='loopback':
                data=data.replace('listen 80 default_server;', 'listen 127.0.0.1:80 default_server;')
                data=data.replace('listen [::]:80 default_server;', '# IPv6 disabled in loopback negative fixture')
            path.write_text(data)
        command(['/usr/sbin/nginx','-t']);command(['systemctl','restart','nginx'])
        return dict(operation=op,fixture_ready=True)
    if op=='restore':
        current=set(packages())
        if current-set(state['before']) != set(state['added']):
            raise ValueError('Other package changes detected; automatic fixture restore refused')
        command(['systemctl','stop','nginx'])
        # Retain every fixture/config/log byte in the workspace before package removal.
        command(['tar','-czf',str(ROOT/'fixture-files.tar.gz'),'/etc/nginx','/var/www/html','/var/log/nginx'])
        command(['apt-get','-y','purge',*state['added']])
        for name in ('practice.txt','mission.txt'):
            p=Path('/var/www/html')/name
            if p.exists():p.rename(ROOT/name)
        if packages()!=state['before']: raise ValueError('Original package inventory not restored')
        state['stage']='restored';(ROOT/'state.json').write_text(json.dumps(state))
        return dict(operation='restore',original_package_inventory_restored=True,original_nginx_absent=True,
                    fixture_bytes_preserved=True,credentials_created=False)
    raise ValueError('Unsupported fixture operation')


if __name__=='__main__':
    try:print(json.dumps(run(json.loads(sys.stdin.read(65537))),separators=(',',':')))
    except Exception as exc:
        print('HTTP_FIXTURE_STOPPED='+type(exc).__name__)
        raise SystemExit(2)
