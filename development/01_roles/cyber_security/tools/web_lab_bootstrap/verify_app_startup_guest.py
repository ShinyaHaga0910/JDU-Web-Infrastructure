"""Start the verified app briefly on loopback with non-working fixture settings.

Accepts Python/WSGI startup only. Does not configure a real database, create an
authentication account, or install/start the classroom application service.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def run(request):
    if os.geteuid()!=0:raise ValueError('Root probe required')
    c=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    if c['role']!='web' or any(c[k]!=request[k] for k in ('lab_id','deployment_id','instance_id')):
        raise ValueError('Wrong Web node')
    root=Path('/var/lib/jdu-web/catalog-runtime-candidate-v1');app=root/'app'
    manifest=json.loads((app/'APP-MANIFEST.json').read_text())
    for f in manifest['files']:
        p=app/f['path']
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:
            raise ValueError('Verified application files changed')
    with socket.socket() as test:
        test.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);test.bind(('127.0.0.1',18080))
    # These deliberately invalid fixture values are never registered as accounts
    # or saved to the classroom settings. No DB operation is made by the 404 path.
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',DJANGO_SETTINGS_MODULE='jdu_catalog.settings',
        DJANGO_SECRET_KEY='unused-loopback-startup-fixture-only-not-an-authentication-account-2026',
        DJANGO_ALLOWED_HOSTS='127.0.0.1',DB_NAME='fixture_not_provisioned',DB_USER='fixture_not_provisioned',
        DB_PASSWORD='fixture-not-a-real-account-2026',DB_HOST='127.0.0.1',DB_PORT='1')
    log_path=root/'loopback-startup-probe.log'
    with log_path.open('x') as log:
        process=subprocess.Popen([str(root/'venv/bin/gunicorn'),'--bind','127.0.0.1:18080','--workers','1',
            '--user','nobody','--group','nogroup','--access-logfile','-','--error-logfile','-',
            'jdu_catalog.wsgi:application'],cwd=app,env=env,stdout=log,stderr=subprocess.STDOUT)
        accepted=False
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(30):
                if process.poll() is not None:raise ValueError('WSGI process exited before acceptance')
                try:
                    opener.open('http://127.0.0.1:18080/__d08_startup_probe__/',timeout=2)
                    raise ValueError('Expected Django 404 response')
                except urllib.error.HTTPError as e:
                    body=e.read(65536)
                    if e.code!=404 or e.headers.get('X-Frame-Options')!='DENY' or 'gunicorn' not in e.headers.get('Server',''):
                        raise ValueError('Response did not come from the running Django/Gunicorn application')
                    workers=Path('/proc/'+str(process.pid)+'/task/'+str(process.pid)+'/children').read_text().split()
                    if not workers or any(int(next(x for x in Path('/proc/'+pid+'/status').read_text().splitlines()
                            if x.startswith('Uid:')).split()[1])!=pwd.getpwnam('nobody').pw_uid for pid in workers):
                        raise ValueError('Actual WSGI worker uid differs')
                    accepted=True;break
                except urllib.error.URLError:time.sleep(.5)
            if not accepted:raise ValueError('WSGI startup timeout')
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
    with socket.socket() as test:
        test.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);test.bind(('127.0.0.1',18080))
    return dict(deployment_id=c['deployment_id'],instance_id=c['instance_id'],scope='loopback_python_wsgi_startup_not_database_function_acceptance',
        signed_app_inventory_unchanged=True,gunicorn_worker_started=True,django_response_status=404,
        application_security_headers_present=True,loopback_only=True,non_root_worker=True,temporary_process_stopped=True,
        database_or_authentication_accounts_created=False,classroom_app_service_configured=False,class_ready=False)


if __name__=='__main__':
    try:print(json.dumps(run(json.loads(sys.stdin.read(65537))),separators=(',',':')))
    except Exception as e:
        print('APP_STARTUP_PROBE_STOPPED='+type(e).__name__+': '+str(e));raise SystemExit(2)
