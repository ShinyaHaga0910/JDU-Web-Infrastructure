"""PostgreSQL16 observations. Queries never expose password verifiers or change data."""
import ipaddress
import json
import os
from pathlib import Path
import stat

from network_checks import active, command
from registry import REGISTRY

TABLES = {'auth_group', 'auth_group_permissions', 'auth_permission', 'auth_user', 'auth_user_groups',
          'auth_user_user_permissions', 'catalog_item', 'django_admin_log', 'django_content_type',
          'django_migrations', 'django_session'}
PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def admin_sql(query, database='postgres'):
    p = command(['sudo', '-n', '-u', 'postgres', '/usr/lib/postgresql/16/bin/psql', '-X', '-qAt',
                 '-v', 'ON_ERROR_STOP=1', '-d', database, '-c', 'BEGIN READ ONLY; ' + query + '; ROLLBACK'], timeout=15)
    if p is None or p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout.strip())
    except ValueError:
        return None


def hba_policy(rows, profile):
    wanted = REGISTRY['profiles'][profile]
    pairs = {(p['db_name'], p['setup_role']) for p in REGISTRY['profiles'].values()}
    pairs |= {(p['db_name'], p['runtime_role']) for p in REGISTRY['profiles'].values()}
    seen = set()
    for r in rows:
        if r.get('error'):
            return False
        if r['auth_method'] == 'reject':
            continue
        if r['type'] == 'local':
            if r['auth_method'] != 'peer' or r['user_name'] not in (['postgres'], ['all']):
                return False
            continue
        if (r['type'] not in ('host', 'hostssl') or r['auth_method'] != 'scram-sha-256'
                or r['address'] != '10.20.1.20' or r['netmask'] != '255.255.255.255'):
            return False
        for db in r['database']:
            for role in r['user_name']:
                if (db, role) not in pairs:
                    return False
                seen.add((db, role))
    return {(wanted['db_name'], wanted['setup_role']), (wanted['db_name'], wanted['runtime_role'])} <= seen


def role_basics(profile):
    p = REGISTRY['profiles'][profile]
    return admin_sql("SELECT json_build_object('roles',COALESCE((SELECT json_agg(json_build_object("
        "'name',rolname,'login',rolcanlogin,'unsafe',rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls,"
        "'memberships',(SELECT count(*) FROM pg_auth_members WHERE member=r.oid),"
        "'password_null',rolpassword IS NULL,'sessions',(SELECT count(*) FROM pg_stat_activity WHERE usename=r.rolname))) "
        "FROM pg_authid r WHERE rolname IN (" + literal(p['setup_role']) + ',' + literal(p['runtime_role']) + ")), '[]'::json),"
        "'database_owner',(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=" + literal(p['db_name']) + "))")


def table_permissions(database, role, tables, expected, column_update=()):
    """Effective table AND column grants, including grant options. No trial DML."""
    checks = []
    for table in tables:
        table_id = 'public.' + table
        for right in PRIVILEGES:
            expected_bool = 'true' if right in expected else 'false'
            checks.append('has_table_privilege(' + literal(role) + ',' + literal(table_id) + ',' + literal(right) + ')=' + expected_bool)
            checks.append('NOT has_table_privilege(' + literal(role) + ',' + literal(table_id) + ',' + literal(right + ' WITH GRANT OPTION') + ')')
        for right in ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES'):
            allowed = 'true' if right in expected else ('a.attname IN (' + ','.join(map(literal, column_update)) + ')' if right == 'UPDATE' and column_update else 'false')
            checks.append('(SELECT COALESCE(bool_and(has_column_privilege(' + literal(role) + ',a.attrelid,a.attnum,'
                + literal(right) + ') = (' + allowed + ') AND NOT has_column_privilege(' + literal(role)
                + ',a.attrelid,a.attnum,' + literal(right + ' WITH GRANT OPTION') + ')),false) FROM pg_attribute a WHERE '
                + 'a.attrelid=' + literal(table_id) + '::regclass AND a.attnum>0 AND NOT a.attisdropped)')
    return admin_sql('SELECT to_json((' + ' AND '.join(checks) + '))', database)


def database_observations(profile, app=False):
    p = REGISTRY['profiles'][profile]
    db, setup, runtime = p['db_name'], p['setup_role'], p['runtime_role']
    service = active('postgresql@16-main')
    out = dict(WEB05_CLUSTER_ACTIVE=service)
    config = admin_sql("SELECT json_build_object('version',current_setting('server_version_num')::int,"
        "'port',current_setting('port'),'listen',current_setting('listen_addresses'),'data',current_setting('data_directory'),"
        "'hba',current_setting('hba_file'),'loaded',extract(epoch from pg_conf_load_time()))")
    if not config:
        out.update(WEB05_CLUSTER_CONFIG=False if not service else None,
                   WEB05_LISTEN_5432=False if not service else None,
                   WEB05_DATABASE_OWNER=False if not service else None,
                   WEB05_ROLE_ATTRIBUTES=False if not service else None,
                   WEB05_HBA_SCRAM=False if not service else None)
        return out
    try:
        data = Path(config['data']).stat()
        import pwd
        data_ok = data.st_uid == pwd.getpwnam('postgres').pw_uid and stat.S_IMODE(data.st_mode) == 0o700
        hba_loaded = Path(config['hba']).stat().st_mtime <= float(config['loaded'])
    except (OSError, KeyError):
        data_ok, hba_loaded = False, False
    out['WEB05_CLUSTER_CONFIG'] = (160000 <= config['version'] < 170000 and config['port'] == '5432'
                                  and config['data'] == '/var/lib/postgresql/16/main' and data_ok)
    listen = command(['ss', '-H', '-ltn'])
    out['WEB05_LISTEN_5432'] = None if listen is None else any(
        len(row.split()) >= 4 and row.split()[3] == '10.20.2.20:5432' for row in listen.stdout.splitlines())
    roles = role_basics(profile)
    owner = admin_sql("SELECT to_json(pg_get_userbyid(nspowner)) FROM pg_namespace WHERE nspname='public'", db)
    out['WEB05_DATABASE_OWNER'] = None if roles is None else roles['database_owner'] == setup and owner == setup
    role_map = {r['name']: r for r in roles['roles']} if roles else {}
    out['WEB05_ROLE_ATTRIBUTES'] = (set(role_map) == {setup, runtime} and role_map[runtime]['login']
                                   and all(not r['unsafe'] and r['memberships'] == 0 for r in role_map.values()))
    hba = admin_sql('SELECT COALESCE(json_agg(row_to_json(r) ORDER BY rule_number),\'[]\'::json) FROM '
                    '(SELECT rule_number,type,database,user_name,address,netmask,auth_method,error FROM pg_hba_file_rules) r')
    # pg_hba_file_rules describes the file, not necessarily the loaded rules.
    out['WEB05_HBA_SCRAM'] = None if hba is None else hba_loaded and hba_policy(hba, profile)
    if not app:
        return out
    tables = admin_sql("SELECT COALESCE(json_agg(tablename ORDER BY tablename),'[]'::json) FROM pg_tables WHERE schemaname='public'", db)
    migrations = admin_sql("SELECT COALESCE(json_agg(app||':'||name),'[]'::json) FROM django_migrations", db)
    needed = {'catalog:0001_initial', 'auth:0012_alter_user_first_name_max_length',
              'admin:0003_logentry_add_action_flag_choices', 'contenttypes:0002_remove_content_type_name', 'sessions:0001_initial'}
    out['WEB06_MIGRATIONS'] = tables is not None and set(tables) == TABLES and migrations is not None and needed <= set(migrations)
    expected = p['records']
    records = admin_sql("SELECT COALESCE(json_agg(json_build_object('code',code,'name',name,'quantity',quantity,"
        "'location',location,'is_public',is_public)),'[]'::json) FROM catalog_item WHERE code IN ("
        + ','.join(literal(r['code']) for r in expected) + ')', db)
    out['WEB06_REQUIRED_RECORDS'] = records is not None and sorted(records, key=lambda r: r['code']) == sorted(expected, key=lambda r: r['code'])
    setup_state = role_map.get(setup)
    out['WEB07_SETUP_ROLE_RETIRED'] = (setup_state is not None and not setup_state['login']
                                     and setup_state['password_null'] and setup_state['sessions'] == 0)
    if not tables or set(tables) != TABLES:
        for cid in ('WEB07_ITEM_PRIVILEGES', 'WEB07_AUTH_USER_PRIVILEGES', 'WEB07_AUTH_LOOKUP_PRIVILEGES',
                    'WEB07_SESSION_PRIVILEGES', 'WEB07_AUDIT_PRIVILEGES', 'WEB07_MIGRATION_PRIVILEGES', 'WEB07_SEQUENCE_PRIVILEGES'):
            out[cid] = False
        out['WEB07_ADMIN_PERMISSIONS'] = False
        return out
    out['WEB07_ITEM_PRIVILEGES'] = table_permissions(db, runtime, ['catalog_item'], {'SELECT', 'INSERT', 'UPDATE'})
    out['WEB07_AUTH_USER_PRIVILEGES'] = table_permissions(db, runtime, ['auth_user'], {'SELECT'}, ('last_login', 'password'))
    out['WEB07_AUTH_LOOKUP_PRIVILEGES'] = table_permissions(db, runtime,
        ['auth_group', 'auth_permission', 'auth_group_permissions', 'auth_user_groups', 'auth_user_user_permissions', 'django_content_type'], {'SELECT'})
    out['WEB07_SESSION_PRIVILEGES'] = table_permissions(db, runtime, ['django_session'], {'SELECT', 'INSERT', 'UPDATE', 'DELETE'})
    out['WEB07_AUDIT_PRIVILEGES'] = table_permissions(db, runtime, ['django_admin_log'], {'SELECT', 'INSERT'})
    no_migration = table_permissions(db, runtime, ['django_migrations'], set())
    no_owner = admin_sql("SELECT to_json(NOT has_schema_privilege(" + literal(runtime) + ",'public','CREATE') AND "
        "has_schema_privilege(" + literal(runtime) + ",'public','USAGE') AND NOT EXISTS(SELECT 1 FROM pg_class WHERE "
        "relnamespace='public'::regnamespace AND relowner=(SELECT oid FROM pg_roles WHERE rolname=" + literal(runtime) + ')))', db)
    out['WEB07_MIGRATION_PRIVILEGES'] = None if no_migration is None or no_owner is None else no_migration and no_owner
    sequences = admin_sql("SELECT COALESCE(json_agg(json_build_object('name',c.oid::regclass::text,'usage',has_sequence_privilege("
        + literal(runtime) + ",c.oid,'USAGE'),'select',has_sequence_privilege(" + literal(runtime)
        + ",c.oid,'SELECT'),'update',has_sequence_privilege(" + literal(runtime) + ",c.oid,'UPDATE'),"
        "'grant',has_sequence_privilege(" + literal(runtime) + ",c.oid,'USAGE WITH GRANT OPTION'))),'[]'::json) "
        "FROM pg_class c WHERE relnamespace='public'::regnamespace AND relkind='S'", db)
    out['WEB07_SEQUENCE_PRIVILEGES'] = None if sequences is None else (
        all((r['usage'] == (r['name'] in {'catalog_item_id_seq', 'django_admin_log_id_seq'}))
            and not r['select'] and not r['update'] and not r['grant'] for r in sequences)
        and {'catalog_item_id_seq', 'django_admin_log_id_seq'} <= {r['name'] for r in sequences})
    admin = admin_sql("SELECT json_build_object('staff',is_staff,'active',is_active,'superuser',is_superuser,'permissions',"
        "COALESCE((SELECT json_agg(DISTINCT ct.app_label||'.'||p.codename) FROM auth_permission p JOIN django_content_type ct ON "
        "ct.id=p.content_type_id WHERE p.id IN (SELECT permission_id FROM auth_user_user_permissions WHERE user_id=u.id UNION "
        "SELECT gp.permission_id FROM auth_group_permissions gp JOIN auth_user_groups ug ON ug.group_id=gp.group_id WHERE ug.user_id=u.id)),"
        "'[]'::json)) FROM auth_user u WHERE username=" + literal(p['app_admin']), db)
    out['WEB07_ADMIN_PERMISSIONS'] = bool(admin and admin['staff'] and admin['active'] and not admin['superuser']
                                         and set(admin['permissions']) == {'catalog.view_item', 'catalog.add_item', 'catalog.change_item'})
    return out


def read_runtime(profile):
    """Root-only, non-sourced environment; no values leave this process except booleans."""
    p = REGISTRY['profiles'][profile]
    candidates = [Path('/etc/jdu-catalog/app.env'), Path(p['db_runtime_env'])]
    for path in candidates:
        try:
            parent = path.parent.lstat()
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                s = os.fstat(stream.fileno())
                if (parent.st_uid != 0 or parent.st_mode & 0o022 or not stat.S_ISDIR(parent.st_mode)
                        or s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o600 or not stat.S_ISREG(s.st_mode) or s.st_nlink != 1):
                    continue
                raw = stream.read(16385)
            if len(raw) > 16384:
                continue
            data = {}
            for line in raw.decode().splitlines():
                if not line or line.startswith('#'):
                    continue
                key, sep, val = line.partition('=')
                if not sep or key in data:
                    raise ValueError('Duplicate environment key')
                data[key] = json.loads(val)
            if (data.get('DB_NAME') == p['db_name'] and data.get('DB_USER') == p['runtime_role']
                    and data.get('DB_HOST') == 'db.lab.test' and data.get('DB_PORT') == '5432'
                    and type(data.get('DB_PASSWORD')) is str and len(data['DB_PASSWORD']) >= 16):
                return data
        except (OSError, ValueError, UnicodeError):
            continue
    return None


def authenticated_sql(profile, host, *, bad_password=False, db_override=None, user_override=None, query=None):
    config = read_runtime(profile)
    if config is None:
        return None
    env = dict(PATH='/usr/bin:/bin', LANG='C', PGCONNECT_TIMEOUT='4', PGPASSWORD=(
        'deliberately-incorrect-' + os.urandom(12).hex() if bad_password else config['DB_PASSWORD']))
    sql = query or 'SELECT json_build_object(\'database\',current_database(),\'user\',current_user,\'value\',1)'
    p = command(['/usr/bin/psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-h', host, '-p', '5432',
                 '-U', user_override or config['DB_USER'], '-d', db_override or config['DB_NAME'], '-c', sql], env=env)
    if p is None:
        return None
    if p.returncode == 0:
        try:
            return dict(ok=True, value=json.loads(p.stdout.strip()))
        except ValueError:
            return dict(ok=False, authentication_rejected=False)
    return dict(ok=False, authentication_rejected=any(text in p.stderr for text in
        ('password authentication failed', 'no pg_hba.conf entry', 'pg_hba.conf rejects connection', 'not permitted to log in', 'permission denied for database')))


def web_database(profile, host):
    p = REGISTRY['profiles'][profile]
    good = authenticated_sql(profile, host)
    valid = None if good is None else good['ok'] and good['value'] == {'database': p['db_name'], 'user': p['runtime_role'], 'value': 1}
    out = {'WEB05_WEB_SQL': valid}
    if valid is not True:
        out.update(WEB05_BAD_PASSWORD_DENIED=None, WEB05_WRONG_TARGET_DENIED=None)
        return out
    wrong = authenticated_sql(profile, host, bad_password=True)
    out['WEB05_BAD_PASSWORD_DENIED'] = None if wrong is None else not wrong['ok'] and wrong['authentication_rejected']
    attempts = [authenticated_sql(profile, host, user_override='postgres'),
                authenticated_sql(profile, host, db_override='postgres')]
    other = 'mission' if profile == 'practice' else 'practice'
    attempts.append(authenticated_sql(profile, host, db_override=REGISTRY['profiles'][other]['db_name']))
    out['WEB05_WRONG_TARGET_DENIED'] = None if any(a is None for a in attempts) else all(not a['ok'] and a['authentication_rejected'] for a in attempts)
    return out
