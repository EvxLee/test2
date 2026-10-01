-- 031_contract_status_add_columns.sql
-- Adds columns for the new "New Contract" Monday board.
-- Old columns (detail_scope, status_label, etc.) are kept for historical data;
-- they will not be populated from the new board going forward.

ALTER TABLE master_dashboard.contract_status
  ADD COLUMN IF NOT EXISTS category TEXT,
  ADD COLUMN IF NOT EXISTS team     TEXT,
  ADD COLUMN IF NOT EXISTS pjt_task TEXT,
  ADD COLUMN IF NOT EXISTS stage    TEXT;

COMMENT ON COLUMN master_dashboard.contract_status.category IS 'Monday "Category" status column (e.g. Contract, Agreement)';
COMMENT ON COLUMN master_dashboard.contract_status.team     IS 'Monday "Team" status column (e.g. Marketing, Incubation, GCED)';
COMMENT ON COLUMN master_dashboard.contract_status.pjt_task IS 'Monday "Project / Task" text column';
COMMENT ON COLUMN master_dashboard.contract_status.stage    IS 'Monday "Stage (PJT)" status column';
