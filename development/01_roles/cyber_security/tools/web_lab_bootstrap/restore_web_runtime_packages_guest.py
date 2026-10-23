"""Restore the six packages added only by the Web runtime acceptance probe.

The verified app/venv/wheels and all probe evidence remain in the teacher test
workspace. Student installation work stays uncompleted. Existing versions and
the initial pre-fixture package inventory must be unchanged.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def run(r):
    if os.geteuid()!=0:raise ValueError('Root restore helper required')
    c=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if c['role']!='web' or any(c[k]!=r[k] for k in ('deployment_id','instance_id')):raise ValueError('Wrong Web node')
    expected=r['added_since_clean_classroom']
    if (set(expected)!={'python3-pip','python3-pip-whl','python3-setuptools-whl','python3-venv','python3-wheel','python3.12-venv'}
            or r['missing_original'] or r['existing_package_upgrades_during_runtime']):
        raise ValueError('Only the reviewed six runtime probe packages may be restored')
    env=dict(os.environ,LC_ALL='C',DEBIAN_FRONTEND='noninteractive',PYTHONDONTWRITEBYTECODE='1')
    def command(args):return subprocess.run(args,capture_output=True,text=True,check=True,timeout=480,env=env).stdout
    def inventory():
        result=command(['dpkg-query','-W','-f=${Package}\t${Version}\t${db:Status-Status}\n'])
        return {a:b for a,b,s in (line.split('\t') for line in result.splitlines()) if s=='installed'}
    original=json.loads(Path('/var/lib/jdu-web/web02-acceptance-v1/state.json').read_text())
    if original['stage']!='restored' or original['deployment_id']!=c['deployment_id']:raise ValueError('Wrong clean package baseline')
    baseline=set(original['before']);before=inventory()
    if baseline&{'nginx','python3-venv','python3-pip'}:raise ValueError('Initial student package baseline differs')
    if set(before)!=baseline|set(expected) or any(before[p]!=v for p,v in expected.items()):
        raise ValueError('Current package inventory differs from the reviewed probe changes')
    work=Path('/var/lib/jdu-web/catalog-runtime-candidate-v1');record=work/'classroom-package-restoration.public.json'
    if record.exists():raise ValueError('Existing restoration retained')
    (work/'before-classroom-package-restoration.json').write_text(json.dumps(before,indent=2))
    simulation=command(['apt-get','--simulate','purge',*sorted(expected)])
    planned={m[1].split(':')[0] for line in simulation.splitlines() if (m:=re.match(r'(?:Remv|Purg)\s+(\S+)',line))}
    if planned!=set(expected) or any(line.startswith('Inst ') for line in simulation.splitlines()):
        raise ValueError('Package restoration would change unrelated packages')
    (work/'classroom-package-restoration-simulation.txt').write_text(simulation)
    result=command(['apt-get','-y','purge',*sorted(expected)])
    (work/'classroom-package-restoration.log').write_text(result)
    after=inventory()
    if set(after)!=baseline or any(after[p]!=before[p] for p in baseline):raise ValueError('Original package versions not restored')
    if command(['dpkg','--audit']).strip():raise ValueError('Package audit incomplete')
    python=str(work/'venv/bin/python');command([python,'-m','pip','--isolated','check'])
    versions=json.loads(command([python,'-c',"import django,gunicorn,psycopg,json;print(json.dumps(dict(django=django.get_version(),gunicorn=gunicorn.__version__,psycopg=psycopg.__version__)))"]))
    if versions!={'django':'5.2.18','gunicorn':'26.2.0','psycopg':'3.3.6'}:raise ValueError('Retained test environment differs')
    public=dict(deployment_id=c['deployment_id'],instance_id=c['instance_id'],scope='teacher_runtime_probe_cleanup_not_student_setup',
        restored_packages=sorted(expected),initial_classroom_package_names_restored=True,existing_package_versions_unchanged=True,
        student_nginx_venv_pip_uninstalled=True,test_app_venv_wheels_and_evidence_retained=True,retained_venv_pip_check=True,
        classroom_app_service_configured=False,credentials_created=False,class_ready=False)
    with record.open('x') as f:json.dump(public,f,indent=2)
    return public


if __name__=='__main__':
    try:print(json.dumps(run(json.loads(sys.stdin.read(65537))),separators=(',',':')))
    except Exception as e:
        print('WEB_RUNTIME_PACKAGE_RESTORE_STOPPED='+type(e).__name__+': '+str(e));raise SystemExit(2)
