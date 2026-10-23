"""One-time fictional practice fixture, only in the retained WSL loopback PostgreSQL."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent
APP = ROOT.parent / 'web_lab_catalog'
CACHE = Path.home() / '.cache/jdu-web-builds/2026-10-15'
SOCKET = str(CACHE / 'catalog-pg-socket')
RUNTIME_PASSWORD = 'fictional-local-practice-runtime-only-2026'


def connection(database='postgres', **kwargs):
    return psycopg.connect(host=SOCKET, port=55439, user='fixture_owner', dbname=database, **kwargs)


def main():
    marker = CACHE / 'd11-practice-fixture.json'
    expected = dict(kind='local-fictional-d11-practice', database='jdu_catalog_practice', port=55439, socket=SOCKET)
    if marker.exists():
        if json.loads(marker.read_text()) != expected:
            raise ValueError('Different local fixture retained')
        print('LOCAL_PRACTICE_FIXTURE_ALREADY_EXISTS; no credentials or data changed')
        return
    with connection(autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname='jdu_catalog_practice'").fetchone():
            raise ValueError('Existing unmarked database retained')
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname IN ('catalog_practice_setup','catalog_practice_app')").fetchone():
            raise ValueError('Existing unmarked roles retained')
        conn.execute('CREATE ROLE catalog_practice_setup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        conn.execute(sql.SQL('CREATE ROLE catalog_practice_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(RUNTIME_PASSWORD)))
        conn.execute("CREATE DATABASE jdu_catalog_practice OWNER catalog_practice_setup ENCODING 'UTF8' TEMPLATE template0")
    finish_fixture()
    with marker.open('x') as stream:
        json.dump(expected, stream)
    print('LOCAL_PRACTICE_FIXTURE_CREATED; fictional data only; mission retained')


def finish_fixture():
    sys.path.insert(0, str(APP))
    from profile_sql import render
    # Only strip psql's fixed ON_ERROR_STOP directive; all SQL comes from the reviewed template.
    def execute_file(filename):
        text = '\n'.join(line for line in render('practice', filename).splitlines() if not line.startswith('\\'))
        with connection('jdu_catalog_practice', autocommit=True) as conn:
            conn.execute(text)
    execute_file('02_prepare_schema.sql')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', DJANGO_SETTINGS_MODULE='jdu_catalog.settings',
        DJANGO_SECRET_KEY='fictional-local-practice-' + 'x' * 50,
        DJANGO_ALLOWED_HOSTS='admin.lab.test,web.lab.test,127.0.0.1', DB_NAME='jdu_catalog_practice',
        DB_USER='catalog_practice_setup', DB_PASSWORD='fictional-unused-unix-socket-only', DB_HOST=SOCKET, DB_PORT='55439',
        DJANGO_STATIC_ROOT=str(CACHE / 'catalog-proxy-fixture/static'))
    subprocess.run([sys.executable, str(APP / 'manage.py'), 'migrate', '--noinput', '--verbosity', '0'],
        cwd=APP, env=env, check=True, capture_output=True)
    subprocess.run([sys.executable, str(APP / 'manage.py'), 'seed_catalog'], cwd=APP, env=env, check=True, capture_output=True)
    code = '''import django;django.setup()
from django.contrib.auth.models import User,Permission
u=User.objects.create_user(username='practice_admin',password='Fictional-Practice-Admin-Only-2026!',is_staff=True,is_superuser=False)
u.user_permissions.set(Permission.objects.filter(content_type__app_label='catalog',codename__in=['view_item','add_item','change_item']))
'''
    subprocess.run([sys.executable, '-B', '-c', code], cwd=APP, env=env, check=True, capture_output=True)
    execute_file('03_runtime_grants.sql')
    execute_file('04_disable_setup.sql')


if __name__ == '__main__':
    main()
