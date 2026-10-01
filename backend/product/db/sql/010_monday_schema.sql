CREATE SCHEMA IF NOT EXISTS monday;

CREATE TABLE IF NOT EXISTS monday.boards (
  monday_board_id text PRIMARY KEY,
  name            text,
  created_at      timestamptz,
  updated_at      timestamptz,
  as_of           timestamptz DEFAULT now(),
  raw_json        jsonb
);

CREATE TABLE IF NOT EXISTS monday.items (
  monday_id       text PRIMARY KEY,
  board_id        text REFERENCES monday.boards(monday_board_id),
  name            text,
  group_id        text,
  created_at      timestamptz,
  updated_at      timestamptz,
  is_active       boolean DEFAULT true,
  deactivated_at  timestamptz,
  as_of           timestamptz DEFAULT now(),
  raw_json        jsonb
);

CREATE TABLE IF NOT EXISTS monday.item_properties (
  monday_item_id  text,
  column_id       text,
  value_text      text,
  value_date      date,
  value_number    double precision,
  raw_json        jsonb,
  PRIMARY KEY (monday_item_id, column_id),
  FOREIGN KEY (monday_item_id) REFERENCES monday.items(monday_id)
);

CREATE TABLE IF NOT EXISTS monday.item_assignees (
  monday_item_id  text,
  monday_user_id  text,
  PRIMARY KEY (monday_item_id, monday_user_id),
  FOREIGN KEY (monday_item_id) REFERENCES monday.items(monday_id)
);

CREATE TABLE IF NOT EXISTS monday.files (
  monday_file_id  text PRIMARY KEY,
  asset_id        text,
  item_id         text,
  column_id       text,
  board_id        text,
  file_name       text,
  public_url      text,
  spaces_key      text,
  category        text,
  owner_name      text,
  summary         text,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  FOREIGN KEY (item_id) REFERENCES monday.items(monday_id),
  FOREIGN KEY (board_id) REFERENCES monday.boards(monday_board_id)
);
