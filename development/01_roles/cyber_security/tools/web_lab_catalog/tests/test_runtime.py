"""Real PostgreSQL runtime/permission acceptance. Uses only the local fixture.

Run after provision_fixture.py with the offline catalog venv. Every test rolls
back its own changes. It neither creates nor flushes a database as catalog_app.
"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='jdu_catalog.settings',
    DJANGO_SECRET_KEY='fictional-local-fixture-only-'+'x'*50,
    DJANGO_ALLOWED_HOSTS='admin.lab.test,web.lab.test,127.0.0.1',
    DB_NAME='jdu_catalog',DB_USER='catalog_app',
    DB_PASSWORD='fictional-local-runtime-only-2026',DB_HOST='127.0.0.1',DB_PORT='55439')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection,transaction,DatabaseError
from django.test import Client
from catalog.models import Item


class RuntimeAcceptance(unittest.TestCase):
    def setUp(self):
        self.atomic=transaction.atomic();self.atomic.__enter__()
        self.client=Client(enforce_csrf_checks=True,HTTP_HOST='admin.lab.test',
            REMOTE_ADDR='127.0.0.1',HTTP_X_JDU_ENTRY='admin')

    def tearDown(self):
        transaction.set_rollback(True);self.atomic.__exit__(None,None,None)

    def login(self,user='lab_admin',password='Fictional-Admin-Only-2026!'):
        self.assertEqual(self.client.get('/admin/login/').status_code,200)
        return self.client.post('/admin/login/',{'username':user,'password':password,
            'csrfmiddlewaretoken':self.client.cookies['csrftoken'].value,'next':'/admin/'})

    def post_item(self,code='TEST-ITEM-001',**changes):
        self.client.get('/admin/catalog/item/add/')
        fields=dict(code=code,name='架空テスト備品',quantity='2',location='架空棚',
            description='<script>fixture</script>',is_public='on',_save='保存')
        fields.update(changes)
        fields['csrfmiddlewaretoken']=self.client.cookies['csrftoken'].value
        return self.client.post('/admin/catalog/item/add/',fields)

    def test_public_reads_database_and_escapes(self):
        public=Client(HTTP_HOST='web.lab.test',REMOTE_ADDR='127.0.0.1',HTTP_X_JDU_ENTRY='public')
        page=public.get('/').content.decode()
        self.assertIn('DEMO-PC-001',page);self.assertNotIn('DEMO-PRIVATE-001',page)
        self.assertNotIn('/admin',page)
        Item.objects.create(code='TEST-PUBLIC',name='<img src=x>',quantity=0,location='架空',is_public=True)
        page=public.get('/').content.decode()
        self.assertIn('TEST-PUBLIC',page);self.assertIn('&lt;img src=x&gt;',page)
        self.assertNotIn('<img src=x>',page)
        self.assertEqual(public.post('/').status_code,405)

    def test_public_and_direct_requests_cannot_forge_admin(self):
        for ip,entry in [('127.0.0.1','public'),('10.20.1.10','admin'),('127.0.0.1','')]:
            c=Client(HTTP_HOST='web.lab.test',REMOTE_ADDR=ip,HTTP_X_JDU_ENTRY=entry)
            for path in ['/admin','/admin/','/admin/catalog/item/add/']:
                self.assertEqual(c.get(path).status_code,404)

    def test_staff_add_edit_visibility_and_logout(self):
        self.assertEqual(self.login().status_code,302)
        admin=get_user_model().objects.get(username='lab_admin')
        self.assertTrue(admin.is_staff);self.assertFalse(admin.is_superuser)
        self.assertEqual(set(admin.get_all_permissions()),{'catalog.view_item','catalog.add_item','catalog.change_item'})
        self.assertEqual(self.post_item().status_code,302)
        item=Item.objects.get(code='TEST-ITEM-001')
        self.assertEqual(item.quantity,2)
        page=Client(HTTP_HOST='web.lab.test').get('/').content.decode()
        self.assertIn(item.code,page);self.assertNotIn('<script>fixture</script>',page)
        path=f'/admin/catalog/item/{item.pk}/change/'
        self.client.get(path)
        response=self.client.post(path,dict(code=item.code,name='編集後の架空備品',quantity=7,
            location='架空棚',description='',_save='保存',csrfmiddlewaretoken=self.client.cookies['csrftoken'].value))
        self.assertEqual(response.status_code,302)
        item.refresh_from_db();self.assertEqual(item.quantity,7);self.assertFalse(item.is_public)
        self.assertNotIn(item.code,Client(HTTP_HOST='web.lab.test').get('/').content.decode())
        self.assertEqual(self.client.get(f'/admin/catalog/item/{item.pk}/delete/').status_code,403)
        self.assertEqual(self.client.get('/admin/auth/user/').status_code,404)
        self.assertEqual(self.client.get('/admin/password_change/').status_code,404)
        self.assertEqual(self.client.post('/admin/logout/',{'csrfmiddlewaretoken':self.client.cookies['csrftoken'].value}).status_code,200)
        self.assertEqual(self.client.get(path).status_code,302)

    def test_bad_auth_anonymous_and_no_permissions_do_not_write(self):
        before=Item.objects.count()
        self.assertEqual(self.login(password='wrong-fixture-password').status_code,200)
        self.assertEqual(self.client.get('/admin/catalog/item/add/').status_code,302)
        self.assertEqual(self.login(user='deny_staff',password='Fictional-Denied-Only-2026!').status_code,302)
        self.assertEqual(self.client.get('/admin/catalog/item/add/').status_code,403)
        token=self.client.cookies['csrftoken'].value
        response=self.client.post('/admin/catalog/item/add/',dict(code='DENIED',name='Denied',quantity=1,location='Test',csrfmiddlewaretoken=token))
        self.assertEqual(response.status_code,403);self.assertEqual(Item.objects.count(),before)

    def test_csrf_and_invalid_input_do_not_write(self):
        self.login();before=Item.objects.count()
        self.assertEqual(self.client.post('/admin/catalog/item/add/',{'code':'CSRF'}).status_code,403)
        self.assertEqual(self.post_item(quantity='-1').status_code,200)
        self.assertEqual(self.post_item(code='DEMO-PC-001').status_code,200)
        self.assertEqual(self.post_item(name='').status_code,200)
        self.assertEqual(Item.objects.count(),before)

    def test_column_only_password_reset_and_existing_user_protection(self):
        user=get_user_model().objects.get(username='lab_admin')
        prior=(user.is_staff,user.is_superuser,user.last_login)
        with patch('catalog.management.commands.set_lab_password.password_for',return_value='Different-Fixture-Only-2026!'):
            call_command('set_lab_password',username='lab_admin',verbosity=0)
        user.refresh_from_db();self.assertTrue(user.check_password('Different-Fixture-Only-2026!'))
        self.assertEqual((user.is_staff,user.is_superuser,user.last_login),prior)
        with self.assertRaisesRegex(CommandError,'already exists'):
            call_command('create_lab_admin',username='lab_admin')

    def test_actual_runtime_sql_denials_and_allowed_columns(self):
        with connection.cursor() as c:
            c.execute("SELECT current_user,has_schema_privilege(current_user,'public','CREATE'),has_database_privilege(current_user,current_database(),'CREATE')")
            self.assertEqual(c.fetchone(),('catalog_app',False,False))
            for table in ['auth_group','auth_permission','auth_user_groups','auth_user_user_permissions','auth_group_permissions','django_content_type']:
                for action in ['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']:
                    c.execute('SELECT has_table_privilege(current_user,%s,%s)',[table,action]);self.assertFalse(c.fetchone()[0],(table,action))
            for action in ['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']:
                c.execute("SELECT has_table_privilege(current_user,'django_migrations',%s)",[action]);self.assertFalse(c.fetchone()[0],action)
            c.execute("SELECT has_table_privilege(current_user,'catalog_item','DELETE'),has_table_privilege(current_user,'django_admin_log','UPDATE'),has_table_privilege(current_user,'django_admin_log','DELETE')")
            self.assertEqual(c.fetchone(),(False,False,False))
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='auth_user' ORDER BY ordinal_position")
            for column, in c.fetchall():
                c.execute("SELECT has_column_privilege(current_user,'auth_user',%s,'UPDATE')",[column])
                self.assertEqual(c.fetchone()[0],column in ('password','last_login'),column)
            for table in ['catalog_item','django_admin_log']:
                c.execute("SELECT has_sequence_privilege(current_user,pg_get_serial_sequence(%s,'id'),'USAGE'),has_sequence_privilege(current_user,pg_get_serial_sequence(%s,'id'),'UPDATE')",[table,table])
                self.assertEqual(c.fetchone(),(True,False))
        # Safe denial checks on test transactions; no DROP/TRUNCATE is attempted.
        for query in ["UPDATE auth_user SET is_superuser=true WHERE username='lab_admin'",
                      "DELETE FROM catalog_item WHERE code='DOES-NOT-EXIST'",
                      "SELECT * FROM django_migrations LIMIT 1"]:
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    with connection.cursor() as c:c.execute(query)

    def test_setup_disabled_and_table_manifest(self):
        # The runtime cannot read pg_authid. Use the isolated fixture owner socket.
        import psycopg
        sock=Path.home()/'.cache/jdu-web-builds/2026-10-15/catalog-pg-socket'
        with psycopg.connect(host=str(sock),port=55439,user='fixture_owner',dbname='jdu_catalog') as conn:
            role=conn.execute("SELECT rolcanlogin,rolpassword IS NULL FROM pg_authid WHERE rolname='catalog_setup'").fetchone()
            self.assertEqual(role,(False,True))
            tables={r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
            self.assertEqual(tables,{'catalog_item','auth_group','auth_group_permissions','auth_permission','auth_user','auth_user_groups','auth_user_user_permissions','django_content_type','django_admin_log','django_session','django_migrations'})
            self.assertFalse(conn.execute("SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member='catalog_app'::regrole)").fetchone()[0])
            self.assertFalse(conn.execute("SELECT EXISTS(SELECT 1 FROM pg_class WHERE relnamespace='public'::regnamespace AND relowner='catalog_app'::regrole)").fetchone()[0])


if __name__=='__main__':unittest.main(verbosity=2)
