CREATE EXTENSION IF NOT EXISTS pgcrypto;

SET search_path TO master_dashboard;

CREATE TABLE IF NOT EXISTS korean (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    vertical_id UUID REFERENCES verticals(id),

    project_name        VARCHAR(300) NOT NULL,
    stage               VARCHAR(100),
    vertical            VARCHAR(100),
    status              VARCHAR(100),
    business_theme      TEXT,
    timeline            TEXT,
    main_customer       TEXT,
    monthly_activities  TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_korean_project_id
    ON korean(project_id);

CREATE INDEX IF NOT EXISTS idx_korean_vertical_id
    ON korean(vertical_id);

ALTER TABLE master_dashboard.korean
ADD CONSTRAINT uq_korean_project
UNIQUE (project_id);

