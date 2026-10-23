\set ON_ERROR_STOP on
-- Run as postgres, connected to jdu_catalog, before the fixed migrations.
REVOKE ALL ON DATABASE jdu_catalog FROM PUBLIC;
GRANT CONNECT ON DATABASE jdu_catalog TO catalog_setup,catalog_app;
ALTER SCHEMA public OWNER TO catalog_setup;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO catalog_app;
ALTER ROLE catalog_setup IN DATABASE jdu_catalog SET search_path=public;
ALTER ROLE catalog_app IN DATABASE jdu_catalog SET search_path=public;
