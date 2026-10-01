CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS master_dashboard.contract_status (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  source TEXT NOT NULL DEFAULT 'monday',
  monday_board_id TEXT,
  monday_item_id TEXT,
  monday_item_name TEXT,
  contract TEXT NOT NULL,
  detail_scope TEXT,
  lms_number TEXT,
  contract_amount NUMERIC,
  start_date DATE,
  end_date DATE,
  request_date DATE,
  requestor_id UUID,
  priority_label TEXT,
  status_label TEXT,
  start_legal_review DATE,
  completed_legal_review DATE,
  reviewer_id UUID,
  days_in_legal_review INTEGER,
  signed_on DATE,
  is_standard BOOLEAN,
  is_invoiced BOOLEAN,
  invoiced_details TEXT,
  files_hint TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE master_dashboard.contract_status
  ADD COLUMN IF NOT EXISTS requestor_id UUID,
  ADD COLUMN IF NOT EXISTS reviewer_id UUID,
  ADD COLUMN IF NOT EXISTS start_date DATE,
  ADD COLUMN IF NOT EXISTS end_date DATE;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_contract_status_requestor'
  ) THEN
    ALTER TABLE master_dashboard.contract_status
      ADD CONSTRAINT fk_contract_status_requestor
      FOREIGN KEY (requestor_id) REFERENCES master_dashboard.people(id)
      ON UPDATE CASCADE ON DELETE SET NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_contract_status_reviewer'
  ) THEN
    ALTER TABLE master_dashboard.contract_status
      ADD CONSTRAINT fk_contract_status_reviewer
      FOREIGN KEY (reviewer_id) REFERENCES master_dashboard.people(id)
      ON UPDATE CASCADE ON DELETE SET NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_contract_status_dates_order'
  ) THEN
    ALTER TABLE master_dashboard.contract_status
      ADD CONSTRAINT chk_contract_status_dates_order
      CHECK (start_date IS NULL OR end_date IS NULL OR end_date >= start_date);
  END IF;
END$$;

ALTER TABLE master_dashboard.contract_status
  DROP CONSTRAINT IF EXISTS contract_status_unique_source;

CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_status_monday_item
  ON master_dashboard.contract_status (source, monday_board_id, monday_item_id)
  WHERE monday_board_id IS NOT NULL AND monday_item_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_contract_status_contract ON master_dashboard.contract_status (contract);
CREATE INDEX IF NOT EXISTS ix_contract_status_dates ON master_dashboard.contract_status (start_date, end_date);
CREATE INDEX IF NOT EXISTS ix_contract_status_requestor ON master_dashboard.contract_status (requestor_id);
CREATE INDEX IF NOT EXISTS ix_contract_status_reviewer ON master_dashboard.contract_status (reviewer_id);
CREATE INDEX IF NOT EXISTS ix_contract_status_status ON master_dashboard.contract_status (status_label);
CREATE INDEX IF NOT EXISTS ix_contract_status_priority ON master_dashboard.contract_status (priority_label);
CREATE INDEX IF NOT EXISTS ix_contract_status_invoiced_standard ON master_dashboard.contract_status (is_invoiced, is_standard);

CREATE OR REPLACE FUNCTION master_dashboard.trg_touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_contract_status_touch ON master_dashboard.contract_status;
CREATE TRIGGER trg_contract_status_touch
BEFORE UPDATE ON master_dashboard.contract_status
FOR EACH ROW EXECUTE FUNCTION master_dashboard.trg_touch_updated_at();

DROP INDEX IF EXISTS uq_contract_status_monday_item;

ALTER TABLE master_dashboard.contract_status
  ADD CONSTRAINT contract_status_unique_source
  UNIQUE (source, monday_board_id, monday_item_id);
