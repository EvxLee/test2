ALTER TABLE master_dashboard.contract_status
  ADD COLUMN IF NOT EXISTS owner TEXT;

COMMENT ON COLUMN master_dashboard.contract_status.owner IS 'Monday "Owner" people column';
