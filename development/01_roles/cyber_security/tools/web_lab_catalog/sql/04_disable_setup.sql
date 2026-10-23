\set ON_ERROR_STOP on
-- Run as postgres after runtime checks and after setup helpers have disconnected.
ALTER ROLE catalog_setup NOLOGIN PASSWORD NULL;
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
 WHERE usename='catalog_setup' AND pid<>pg_backend_pid();
