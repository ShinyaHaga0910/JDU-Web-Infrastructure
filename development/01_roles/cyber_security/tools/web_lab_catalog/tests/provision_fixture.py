"""Create a new, local disposable PostgreSQL fixture; never point at an AWS DB.

The test cluster must already run as the current WSL user on its private socket.
All values below are fictional local-test credentials, never deployment defaults.
Existing database/roles intentionally fail without resetting or deleting data.
"""
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
CACHE=Path.home()/'.cache/jdu-web-builds/2026-10-15'
PG=CACHE/'catalog-pg-tools/usr'
sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='jdu_catalog.settings',
    DJANGO_SECRET_KEY='fictional-local-fixture-only-'+'x'*50,
    DJANGO_ALLOWED_HOSTS='admin.lab.test,web.lab.test,127.0.0.1',
    DB_NAME='jdu_catalog',DB_USER='catalog_setup',
    DB_PASSWORD='fictional-local-setup-only-2026',DB_HOST='127.0.0.1',DB_PORT='55439')
env={**os.environ,'PGHOST':str(CACHE/'catalog-pg-socket'),'PGPORT':'55439',
    'PGUSER':'fixture_owner','LD_LIBRARY_PATH':str(PG/'lib/x86_64-linux-gnu')}

def sql_file(name,database):
    subprocess.run([str(PG/'lib/postgresql/16/bin/psql'),'-X','-v','ON_ERROR_STOP=1',
        '-d',database,'-f',str(ROOT/'sql'/name)],env=env,check=True)

sql_file('01_create_roles.sql','postgres')
sql_file('02_prepare_schema.sql','jdu_catalog')
import psycopg
from psycopg import sql
with psycopg.connect(host=env['PGHOST'],port=55439,user='fixture_owner',dbname='postgres',autocommit=True) as conn:
    for role,password in [('catalog_setup',os.environ['DB_PASSWORD']),
            ('catalog_app','fictional-local-runtime-only-2026')]:
        conn.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
call_command('check')
call_command('makemigrations','--check','--dry-run')
call_command('migrate',interactive=False,verbosity=1)
call_command('seed_catalog')
with patch('catalog.management.commands.create_lab_admin.password_for',return_value='Fictional-Admin-Only-2026!'):
    call_command('create_lab_admin')
get_user_model().objects.create_user(username='deny_staff',password='Fictional-Denied-Only-2026!',is_staff=True)
from django.db import connections
connections.close_all()
sql_file('03_runtime_grants.sql','jdu_catalog')
sql_file('04_disable_setup.sql','jdu_catalog')
print('LOCAL_FIXTURE_READY: PostgreSQL16, fixed migrations, 11 tables, runtime grants, setup disabled')
