-- 042_contract_status_project_fk.sql
-- Adds project_id and project_stage_id FK columns to contract_status.
-- These are populated by _map_contract_status / _link_contract_status_to_projects.

ALTER TABLE master_dashboard.contract_status
    ADD COLUMN IF NOT EXISTS project_id       UUID REFERENCES master_dashboard.projects(id),
    ADD COLUMN IF NOT EXISTS project_stage_id UUID REFERENCES master_dashboard.project_stages(id);

CREATE INDEX IF NOT EXISTS ix_cs_project_id
    ON master_dashboard.contract_status (project_id);
