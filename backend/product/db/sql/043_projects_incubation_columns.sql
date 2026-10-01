-- 043_projects_incubation_columns.sql
-- Add Incubation Projects board milestone-tracking fields directly to
-- master_dashboard.projects so that all project data (including incubation
-- pipeline stages) lives in one canonical table and can be joined to
-- contract_status via project_id.
--
-- Fields map 1-to-1 with Monday board columns on the "Incubation Projects"
-- board (id: 1000000001), excluding IP TAM and POC Proposal TAM.

-- General incubation context
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS cycle_name           TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS project_stage        TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS project_status       TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS atlas_project_stage  TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS tech_lead            TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS team                 TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS notify               TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS report_out_deadline  TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS next_presentation_date DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS links                TEXT;

-- Idea Proposal (IP) milestone
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS idea_proposal_status TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS ip_planned_date      DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS ip_actual_date       DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS ip_decision_date     DATE;

-- PoC Proposal milestone
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_proposal_status        TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_proposal_date_planned  DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_proposal_date_updated  DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_proposal_decision_date DATE;

-- PoC Results milestone
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_results_status        TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_results_planned_date  DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_results_date_updated  DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_results_decision_date DATE;

-- CMBU Proposal milestone
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS cmbu_proposal_status        TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS cmbu_proposal_date_planned  DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS cmbu_proposal_date_updated  DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS cmbu_proposal_decision_date DATE;

-- Seed Results milestone
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS seed_results_status       TEXT;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS seed_results_planned_date DATE;
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS seed_results_date_updated DATE;

-- POC Status (mirror column from Monday — populated on ingest when available)
ALTER TABLE master_dashboard.projects ADD COLUMN IF NOT EXISTS poc_status TEXT;
