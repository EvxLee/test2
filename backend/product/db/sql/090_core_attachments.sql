SET search_path TO master_dashboard;

CREATE TABLE IF NOT EXISTS master_dashboard.core_attachments (
    id           bigserial PRIMARY KEY,
    owner_schema text      NOT NULL,
    owner_table  text      NOT NULL,
    owner_id     text      NOT NULL,
    name         text,
    url          text      NOT NULL,
    source       text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_core_attachments_owner_url
  ON master_dashboard.core_attachments (owner_schema, owner_table, owner_id, url);

CREATE INDEX IF NOT EXISTS ix_core_attachments_owner
  ON master_dashboard.core_attachments (owner_schema, owner_table, owner_id);
