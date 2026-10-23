"""Classroom PostgreSQL configuration; missing secrets fail closed."""
import os
from pathlib import Path
import re
from django.core.exceptions import ImproperlyConfigured

BASE_DIR=Path(__file__).resolve().parent.parent


def required(name,minimum=1):
    value=os.environ.get(name,'')
    if len(value)<minimum or (value.startswith('<') and value.endswith('>')) or value.startswith('CHANGE_ME'):
        raise ImproperlyConfigured('Required configuration is missing or invalid: '+name)
    return value


SECRET_KEY=required('DJANGO_SECRET_KEY',50)
DEBUG=False
ALLOWED_HOSTS=[x.strip() for x in required('DJANGO_ALLOWED_HOSTS').split(',')]
if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*',x) for x in ALLOWED_HOSTS):
    raise ImproperlyConfigured('Use explicit hostnames or IPv4 addresses')
CATALOG_SITE_NAME=os.environ.get('CATALOG_SITE_NAME','JDU 備品カタログ')[:100]
INSTALLED_APPS=[
    'django.contrib.admin.apps.SimpleAdminConfig','django.contrib.auth',
    'django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages',
    'django.contrib.staticfiles','catalog.apps.CatalogConfig']
MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware','jdu_catalog.middleware.AdminEntryMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='jdu_catalog.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates',
    'DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':[
        'django.template.context_processors.request','django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='jdu_catalog.wsgi.application'
DATABASES={'default':{'ENGINE':'django.db.backends.postgresql',
    'NAME':required('DB_NAME'),'USER':required('DB_USER'),'PASSWORD':required('DB_PASSWORD',16),
    'HOST':required('DB_HOST'),'PORT':os.environ.get('DB_PORT','5432'),
    'CONN_MAX_AGE':0,'OPTIONS':{'sslmode':'prefer','connect_timeout':5}}}
AUTH_PASSWORD_VALIDATORS=[
    {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='ja'
TIME_ZONE='Asia/Tashkent'
USE_I18N=True
USE_TZ=True
STATIC_URL='/static/'
STATIC_ROOT=Path(os.environ.get('DJANGO_STATIC_ROOT',str(BASE_DIR/'static-collected')))
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
CSRF_COOKIE_SAMESITE='Lax'
CSRF_TRUSTED_ORIGINS=['http://admin.lab.test:8080']
X_FRAME_OPTIONS='DENY'
# The agreed classroom endpoints use HTTP 80/8080. External grading uses HTTPS.
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
USE_X_FORWARDED_HOST=False
SECURE_REFERRER_POLICY='same-origin'
