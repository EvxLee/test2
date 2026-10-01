-- 044_project_partner_startups.sql
-- Canonical stage-level startup collaborators for projects sourced from the
-- Monday "Incubation Projects" board.

CREATE TABLE IF NOT EXISTS master_dashboard.project_partner_startups (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID        NOT NULL
                 REFERENCES master_dashboard.projects(id)
                 ON DELETE CASCADE,
    stage        TEXT        NOT NULL,
    startup_name TEXT        NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_partner_startup
        UNIQUE (project_id, stage, startup_name)
);

CREATE INDEX IF NOT EXISTS ix_project_partner_startups_project_id
    ON master_dashboard.project_partner_startups (project_id);

CREATE INDEX IF NOT EXISTS ix_project_partner_startups_stage
    ON master_dashboard.project_partner_startups (stage);
