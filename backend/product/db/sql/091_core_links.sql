CREATE TABLE IF NOT EXISTS core_links (
  id            BIGSERIAL PRIMARY KEY,
  owner_schema  TEXT NOT NULL,
  owner_table   TEXT NOT NULL,
  owner_id      TEXT NOT NULL,
  rel           TEXT NOT NULL,
  href          TEXT NOT NULL,
  label         TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS core_links_owner_idx
  ON core_links (owner_schema, owner_table, owner_id);
