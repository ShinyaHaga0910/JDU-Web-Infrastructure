"""Rootless local Nginx/Gunicorn integration with captured binaries and wheels.

Ports, static/log paths and the simulated Bastion IP differ from deployment.
The actual two-server template, middleware and PostgreSQL runtime are used.
"""
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
CACHE=Path.home()/'.cache/jdu-web-builds/2026-10-15'
WORK=CACHE/'catalog-proxy-fixture'
WORK.mkdir(exist_ok=True)
ENV={**os.environ,'PYTHONDONTWRITEBYTECODE':'1',
    'DJANGO_SECRET_KEY':'fictional-local-fixture-only-'+'x'*50,
    'DJANGO_ALLOWED_HOSTS':'admin.lab.test,web.lab.test,127.0.0.1',
    'DB_NAME':'jdu_catalog','DB_USER':'catalog_app','DB_PASSWORD':'fictional-local-runtime-only-2026',
    'DB_HOST':'127.0.0.1','DB_PORT':'55439','DJANGO_STATIC_ROOT':str(WORK/'static')}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class ProxyAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable,str(ROOT/'manage.py'),'collectstatic','--noinput','--verbosity','0'],cwd=ROOT,env=ENV,check=True)
        for name in ('body','proxy','fastcgi','uwsgi','scgi'):(WORK/name).mkdir(exist_ok=True)
        (WORK/'http-root').mkdir(exist_ok=True)
        (WORK/'http-root/practice.txt').write_text('JDU WEB-02 practice: HTTP response verified.\n')
        (WORK/'http-root/mission.txt').write_text('JDU WEB-02 mission: independent HTTP delivery.\n')
        servers=(ROOT/'config/jdu-catalog.nginx.conf').read_text()
        for old,new in [('listen 80 default_server','listen 127.0.0.1:55440 default_server'),
                ('listen 10.20.1.20:8080','listen 127.0.0.1:55441'),('allow 10.20.1.10;','allow 127.0.0.1;'),
                ('127.0.0.1:8000','127.0.0.1:55442'),('/var/lib/jdu-catalog/static/',str(WORK/'static')+'/'),
                ('/var/log/nginx/',str(WORK)+'/'),('/var/www/html',str(WORK/'http-root'))]:
            if old not in servers:raise RuntimeError('Fixture substitution does not match reviewed template')
            servers=servers.replace(old,new)
        conf='pid '+str(WORK/'nginx.pid')+';\nerror_log '+str(WORK/'nginx.error.log')+';\nevents {}\nhttp {\n'
        conf+='types { text/css css; application/javascript js; image/svg+xml svg; }\n'
        for kind in ('client_body','proxy','fastcgi','uwsgi','scgi'):
            conf+=kind+'_temp_path '+str(WORK/('body' if kind=='client_body' else kind))+';\n'
        conf+=servers+'\n}\n'
        (WORK/'nginx.conf').write_text(conf)
        nginx=CACHE/'catalog-nginx-tools/usr/sbin/nginx'
        subprocess.run([str(nginx),'-t','-p',str(WORK)+'/', '-c',str(WORK/'nginx.conf'),'-e',str(WORK/'nginx.error.log')],check=True,capture_output=True)
        cls.log=(WORK/'gunicorn.log').open('a')
        cls.gunicorn=subprocess.Popen([str(CACHE/'catalog-venv/bin/gunicorn'),'--workers','1','--bind','127.0.0.1:55442',
            '--error-logfile','-','jdu_catalog.wsgi:application'],cwd=ROOT,env=ENV,stdout=cls.log,stderr=cls.log)
        cls.nginx=subprocess.Popen([str(nginx),'-p',str(WORK)+'/', '-c',str(WORK/'nginx.conf'),'-e',str(WORK/'nginx.error.log'),'-g','daemon off;'],stdout=cls.log,stderr=cls.log)
        cls.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        cls.addClassCleanup(cls.close_processes)
        for _ in range(40):
            try:
                status,_,_=cls.request(55440,'/')
                if status==200:break
            except OSError:pass
            time.sleep(.1)
        else:raise RuntimeError('Fixture did not become ready; inspect private local logs')

    @classmethod
    def close_processes(cls):
        for process in (cls.nginx,cls.gunicorn):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        cls.log.close()

    @classmethod
    def request(cls,port,path,fields=None,extra=None,host=None):
        headers={'Host':host or ('admin.lab.test:8080' if port==55441 else 'web.lab.test')}
        headers.update(extra or {})
        data=None if fields is None else urllib.parse.urlencode(fields).encode()
        req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=data,headers=headers)
        try:response=cls.opener.open(req,timeout=5)
        except urllib.error.HTTPError as exc:response=exc
        with response:return response.status,dict(response.headers),response.read().decode()

    def test_public_static_and_admin_spoof_denial(self):
        status,headers,html=self.request(55440,'/')
        self.assertEqual(status,200);self.assertIn('DEMO-PC-001',html);self.assertNotIn('DEMO-PRIVATE-001',html)
        status,headers,css=self.request(55440,'/static/catalog/inventory.css')
        self.assertEqual(status,200);self.assertIn('text/css',headers['Content-Type'])
        self.assertEqual(self.request(55440,'/',fields={})[0],403)
        for path in ['/admin','/admin/','/admin/catalog/item/add/','//admin/','/%61dmin/']:
            status,_,_=self.request(55440,path,extra={'X-JDU-Entry':'admin'},host='admin.lab.test:8080')
            self.assertEqual(status,404,path)

    def test_admin_host_port_csrf_and_session(self):
        status,headers,html=self.request(55441,'/admin/login/')
        self.assertEqual(status,200)
        token=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',html)[1]
        status,headers,_=self.request(55441,'/admin/login/',fields={'username':'lab_admin','password':'Fictional-Admin-Only-2026!',
            'csrfmiddlewaretoken':token,'next':'/admin/'},extra={'Origin':'http://admin.lab.test:8080'})
        self.assertEqual(status,302);self.assertEqual(headers['Location'],'/admin/')
        status,_,html=self.request(55441,'/admin/catalog/item/')
        self.assertEqual(status,200);self.assertIn('DEMO-PC-001',html);self.assertIn('lab_admin',html)
        self.assertEqual(self.request(55441,'/')[0],404)
        # The private proxy also overwrites a forged public marker.
        self.assertEqual(self.request(55441,'/admin/',extra={'X-JDU-Entry':'public'})[0],200)
        token=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',html)[1]
        self.assertEqual(self.request(55441,'/admin/logout/',fields={'csrfmiddlewaretoken':token},extra={'Origin':'http://admin.lab.test:8080'})[0],200)
        self.assertEqual(self.request(55441,'/admin/catalog/item/')[0],302)


if __name__=='__main__':unittest.main(verbosity=2)
