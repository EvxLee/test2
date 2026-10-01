SET search_path TO monday, master_dashboard;

ALTER TABLE IF EXISTS monday.item_properties
  ADD COLUMN IF NOT EXISTS title        text,
  ADD COLUMN IF NOT EXISTS value_text   text,
  ADD COLUMN IF NOT EXISTS value_number numeric,
  ADD COLUMN IF NOT EXISTS value_date   date,
  ADD COLUMN IF NOT EXISTS raw_json     jsonb;

CREATE INDEX IF NOT EXISTS ix_monday_items_monday_id_text
  ON monday.items ((monday_id::text));

CREATE INDEX IF NOT EXISTS ix_item_props_item_id_text
  ON monday.item_properties ((monday_item_id::text));
