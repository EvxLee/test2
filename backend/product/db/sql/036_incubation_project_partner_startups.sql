-- 036_incubation_project_partner_startups.sql
-- Partner startups per stage for Incubation Projects board items.
-- One row per (project item, stage, startup). Full-refresh on every ingest.

CREATE TABLE IF NOT EXISTS master_dashboard.incubation_project_partner_startups (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    monday_item_id          BIGINT      NOT NULL,
    source_board            TEXT        NOT NULL,
    project_name            TEXT,
    stage                   TEXT        NOT NULL,
    stage_column_id         TEXT,
    stage_column_title      TEXT,
    startup_monday_item_id  BIGINT      NULL,
    startup_name            TEXT        NOT NULL,
    source_display_value    TEXT,
    ingested_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_proj_stage_startup
        UNIQUE (monday_item_id, stage, startup_name)
);

CREATE INDEX IF NOT EXISTS ix_ipps_monday_item_id
    ON master_dashboard.incubation_project_partner_startups (monday_item_id);

CREATE INDEX IF NOT EXISTS ix_ipps_source_board
    ON master_dashboard.incubation_project_partner_startups (source_board);
