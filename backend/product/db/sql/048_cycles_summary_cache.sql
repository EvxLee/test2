CREATE SCHEMA IF NOT EXISTS cycles;

CREATE TABLE IF NOT EXISTS cycles.summary_cache (
    cycle_id       TEXT PRIMARY KEY,
    response       JSONB NOT NULL,
    generated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_summary_cache_generated_at
    ON cycles.summary_cache (generated_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlas-api-user') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA cycles TO "atlas-api-user"';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON cycles.summary_cache TO "atlas-api-user"';
    END IF;
END
$$;
