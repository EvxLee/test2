SET search_path TO master_dashboard;

-- projects
CREATE INDEX IF NOT EXISTS idx_projects_vertical_id ON projects(vertical_id);
CREATE INDEX IF NOT EXISTS idx_projects_location_id ON projects(location_id);
CREATE INDEX IF NOT EXISTS idx_projects_current_stage_id ON projects(current_stage_id);

-- project_stages
CREATE INDEX IF NOT EXISTS idx_project_stages_project_id ON project_stages(project_id);
CREATE INDEX IF NOT EXISTS idx_project_stages_stage_type ON project_stages(stage_type_id);
CREATE INDEX IF NOT EXISTS idx_project_stages_seq ON project_stages(project_id, sequence_no);

-- project_summaries
CREATE INDEX IF NOT EXISTS idx_project_summaries_project ON project_summaries(project_id);

-- project_org_roles
CREATE INDEX IF NOT EXISTS idx_proj_org_roles_project ON project_org_roles(project_id);
CREATE INDEX IF NOT EXISTS idx_proj_org_roles_org ON project_org_roles(org_id);

-- project_owners
CREATE INDEX IF NOT EXISTS idx_project_owners_project ON project_owners(project_id);
CREATE INDEX IF NOT EXISTS idx_project_owners_person ON project_owners(person_id);

-- stage_documents
CREATE INDEX IF NOT EXISTS idx_stage_docs_stage ON stage_documents(project_stage_id);

-- stage_expenditures
CREATE INDEX IF NOT EXISTS idx_stage_exp_stage ON stage_expenditures(project_stage_id);
CREATE INDEX IF NOT EXISTS idx_stage_exp_stage_asof ON stage_expenditures(project_stage_id, as_of_date);

-- marketing_activities
CREATE INDEX IF NOT EXISTS idx_marketing_project ON marketing_activities(project_id);
CREATE INDEX IF NOT EXISTS idx_marketing_activity_date ON marketing_activities(activity_date);

-- raw_records
CREATE INDEX IF NOT EXISTS idx_raw_records_project ON raw_records(project_id);
CREATE INDEX IF NOT EXISTS idx_raw_payload ON raw_records USING GIN (payload_json);
