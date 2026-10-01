CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS master_dashboard;

SET search_path TO master_dashboard;

CREATE TABLE IF NOT EXISTS verticals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vertical_name VARCHAR(100) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS locations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country text,
  state_region text,
  city text,
  display_name text UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS people (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL,
  email text,
  dept VARCHAR(100),
  title VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_people_email UNIQUE (email),
  CONSTRAINT uq_people_full_name UNIQUE (full_name)
);

CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_name text NOT NULL,
  org_type VARCHAR(50),
  website VARCHAR(300),
  country VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_org_name UNIQUE (org_name)
);

CREATE TABLE IF NOT EXISTS stage_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stage_name VARCHAR(100) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ
);

-- CORE ENTITIES --
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_code VARCHAR(100),
  name VARCHAR(300) NOT NULL,
  vertical_id UUID REFERENCES verticals(id),
  location_id UUID REFERENCES locations(id),
  start_date DATE,
  end_date DATE,
  is_ongoing BOOLEAN,
  current_stage_id UUID,
  source_board VARCHAR(100),
  source_item_id VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_project_code UNIQUE (project_code)
);

CREATE TABLE IF NOT EXISTS project_stages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  stage_type_id UUID NOT NULL REFERENCES stage_types(id),
  sequence_no INT NOT NULL,
  start_date DATE,
  end_date DATE,
  duration_days INT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_project_stage_seq UNIQUE (project_id, sequence_no),
  CONSTRAINT ck_stage_dates CHECK (end_date IS NULL OR start_date IS NULL OR start_date <= end_date)
);

ALTER TABLE projects
  DROP CONSTRAINT IF EXISTS fk_projects_current_stage;

ALTER TABLE projects
  ADD CONSTRAINT fk_projects_current_stage
  FOREIGN KEY (current_stage_id) REFERENCES project_stages(id);

ALTER TABLE master_dashboard.projects
  ADD COLUMN IF NOT EXISTS company_name TEXT,
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS stage_name TEXT,
  ADD COLUMN IF NOT EXISTS status_category TEXT,
  ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES master_dashboard.people(id);

DROP VIEW IF EXISTS vw_master_dashboard CASCADE;

ALTER TABLE master_dashboard.projects 
    ALTER COLUMN project_code TYPE text,
    ALTER COLUMN name TYPE text,
    ALTER COLUMN source_board TYPE text,
    ALTER COLUMN source_item_id TYPE text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM   pg_constraint c
    WHERE  c.conname = 'ux_projects_source'
    AND    c.conrelid = 'master_dashboard.projects'::regclass
  ) THEN
    ALTER TABLE master_dashboard.projects
      ADD CONSTRAINT ux_projects_source
      UNIQUE (source_board, source_item_id);
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS project_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  lang VARCHAR(10) NOT NULL,
  summary_text TEXT,
  CONSTRAINT uq_project_summary_lang UNIQUE (project_id, lang)
);

ALTER TABLE master_dashboard.project_summaries 
    ALTER COLUMN summary_text TYPE text;

CREATE TABLE IF NOT EXISTS project_org_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  org_id UUID NOT NULL REFERENCES organizations(id),
  role VARCHAR(30) NOT NULL,
  external_program VARCHAR(100),
  external_key VARCHAR(100),
  CONSTRAINT uq_proj_org_role UNIQUE (project_id, org_id, role)
);

CREATE TABLE IF NOT EXISTS project_owners (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  person_id UUID NOT NULL REFERENCES people(id),
  CONSTRAINT uq_project_owners UNIQUE (project_id, person_id)
);

ALTER TABLE master_dashboard.project_owners
  ADD COLUMN IF NOT EXISTS role VARCHAR(100),
  ADD COLUMN IF NOT EXISTS source_board VARCHAR(50),
  ADD COLUMN IF NOT EXISTS source_item_id VARCHAR(50);

CREATE TABLE IF NOT EXISTS stage_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_stage_id UUID NOT NULL REFERENCES project_stages(id),
  doc_type VARCHAR(50) NOT NULL,
  title VARCHAR(300) NOT NULL,
  url_or_path VARCHAR(1000),
  source_board VARCHAR(100),
  source_item_id VARCHAR(100),
  CONSTRAINT uq_stage_doc UNIQUE (project_stage_id, doc_type, title)
);

CREATE TABLE IF NOT EXISTS stage_expenditures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_stage_id UUID NOT NULL REFERENCES project_stages(id),
  amount NUMERIC(14, 2),
  currency VARCHAR(10),
  category VARCHAR(50),
  as_of_date DATE NOT NULL,
  source_board VARCHAR(100),
  source_item_id VARCHAR(100),
  CONSTRAINT ck_expense_amount CHECK (amount IS NULL OR amount >= 0)
);

CREATE TABLE IF NOT EXISTS marketing_activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  activity_date DATE NOT NULL,
  channel VARCHAR(50),
  description TEXT,
  source_board VARCHAR(100),
  source_item_id VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS raw_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_board VARCHAR(100) NOT NULL,
  source_item_id VARCHAR(100) NOT NULL,
  project_id UUID REFERENCES projects(id),
  ingested_at TIMESTAMPTZ DEFAULT now(),
  payload_json JSONB,
  CONSTRAINT uq_raw_source UNIQUE (source_board, source_item_id)
);
