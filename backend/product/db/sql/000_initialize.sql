\connect atlasdb

-- CREATE ROLE "AtlasOwner" NOLOGIN;
-- CREATE ROLE "AtlasAPI"  NOLOGIN;

-- DO $$
-- DECLARE
--     _role text := :'atlas_api_user';
--     _pwd  text := :'atlas_api_password';
-- BEGIN
--     IF NOT EXISTS (
--         SELECT 1 FROM pg_roles WHERE rolname = _role
--     ) THEN
--         EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', _role, _pwd);
--     END IF;

--     EXECUTE format('GRANT "AtlasAPI" TO %I', _role);
-- END$$;

-- GRANT "AtlasOwner" TO "atlas-owner";
-- GRANT "AtlasAPI"  TO "AtlasOwner";
