\set ON_ERROR_STOP on
-- Run inside the DB server as OS postgres, connected to database postgres.
-- Existing names intentionally fail; this is not a reset command.
CREATE ROLE catalog_setup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE catalog_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE jdu_catalog OWNER catalog_setup ENCODING 'UTF8' TEMPLATE template0;
-- Use psql's interactive \password separately for two different Lab passwords.
