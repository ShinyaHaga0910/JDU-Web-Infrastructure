\set ON_ERROR_STOP on
-- Run as postgres in jdu_catalog AFTER migrations, seed and staff creation.
BEGIN;
DO $guard$
DECLARE observed text[];
BEGIN
 SELECT array_agg(tablename::text ORDER BY tablename) INTO observed FROM pg_tables WHERE schemaname='public';
 IF observed IS DISTINCT FROM ARRAY['auth_group','auth_group_permissions','auth_permission','auth_user',
   'auth_user_groups','auth_user_user_permissions','catalog_item','django_admin_log','django_content_type',
   'django_migrations','django_session']::text[] THEN
   RAISE EXCEPTION 'Unexpected table manifest; stop and inspect migrations';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='catalog_app' AND
   (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
   OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member='catalog_app'::regrole)
   OR EXISTS(SELECT 1 FROM pg_class WHERE relnamespace='public'::regnamespace AND relowner='catalog_app'::regrole)
   OR (SELECT datdba FROM pg_database WHERE datname=current_database())<>'catalog_setup'::regrole
   OR (SELECT nspowner FROM pg_namespace WHERE nspname='public')<>'catalog_setup'::regrole THEN
   RAISE EXCEPTION 'Unsafe runtime ownership or role privileges; fix before granting';
 END IF;
END;
$guard$;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC,catalog_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC,catalog_app;
-- Table revocation does not remove old column-level grants.
DO $columns$
DECLARE item record;
BEGIN
 FOR item IN SELECT table_name,string_agg(quote_ident(column_name),',' ORDER BY ordinal_position) AS names
   FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name LOOP
   EXECUTE format('REVOKE ALL (%s) ON TABLE public.%I FROM PUBLIC,catalog_app',item.names,item.table_name);
 END LOOP;
END;
$columns$;
GRANT SELECT,INSERT,UPDATE ON public.catalog_item TO catalog_app;
GRANT SELECT ON public.auth_user,public.auth_group,public.auth_permission,
 public.auth_user_groups,public.auth_user_user_permissions,public.auth_group_permissions,public.django_content_type TO catalog_app;
GRANT UPDATE(last_login,password) ON public.auth_user TO catalog_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.django_session TO catalog_app;
GRANT SELECT,INSERT ON public.django_admin_log TO catalog_app;
DO $sequences$
DECLARE table_name text;sequence_name text;
BEGIN
 FOREACH table_name IN ARRAY ARRAY['catalog_item','django_admin_log'] LOOP
   sequence_name:=pg_get_serial_sequence('public.'||table_name,'id');
   IF sequence_name IS NULL THEN RAISE EXCEPTION 'Expected generated ID sequence missing'; END IF;
   EXECUTE format('GRANT USAGE ON SEQUENCE %s TO catalog_app',sequence_name);
 END LOOP;
END;
$sequences$;
COMMIT;
