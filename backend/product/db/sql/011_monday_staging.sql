-- =====================================================
-- Monday.com JSON-first Staging Schema (LEGACY MODEL)
-- Compatible with monday.hydrate_from_staging()
-- =====================================================

CREATE SCHEMA IF NOT EXISTS monday_staging;

-- ----------------------------
-- Ingestion run metadata
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.ingestion_runs (
    run_id        uuid PRIMARY KEY,
    status        text NOT NULL,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    summary_jsonb jsonb
);

-- ----------------------------
-- Raw item JSON
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.items_json (
    run_id        uuid NOT NULL,
    item_id       text NOT NULL,
    payload_jsonb jsonb NOT NULL,
    PRIMARY KEY (run_id, item_id)
);

-- ----------------------------
-- Raw group data
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.groups_json (
    run_id        uuid NOT NULL,
    group_id      text NOT NULL,
    board_id      text,
    payload_jsonb jsonb NOT NULL,
    PRIMARY KEY (run_id, group_id)
);

-- ----------------------------
-- Raw column definitions
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.columns_json (
    run_id        uuid NOT NULL,
    column_id     text NOT NULL,
    board_id      text,
    payload_jsonb jsonb NOT NULL,
    PRIMARY KEY (run_id, column_id)
);

-- ----------------------------
-- Raw asset information
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.assets_json (
    run_id        uuid NOT NULL,
    asset_id      text NOT NULL,
    payload_jsonb jsonb NOT NULL,
    PRIMARY KEY (run_id, asset_id)
);

-- ----------------------------
-- Raw file information
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.files_json (
    run_id        uuid NOT NULL,
    item_id       text NOT NULL,
    file_id       text,
    payload_jsonb jsonb NOT NULL,
    PRIMARY KEY (run_id, item_id, file_id)
);

-- ----------------------------
-- Raw labels
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.labels_json (
    run_id        uuid NOT NULL,
    board_id      text NOT NULL,
    label_id      text NOT NULL,
    payload_jsonb jsonb NOT NULL,
    PRIMARY KEY (run_id, board_id, label_id)
);

-- ----------------------------
-- Raw item links
-- ----------------------------
CREATE TABLE IF NOT EXISTS monday_staging.links_json (
    run_id        uuid NOT NULL,
    item_id       text NOT NULL,
    payload_jsonb jsonb NOT NULL,
    PRIMARY KEY (run_id, item_id)
);

-- ----------------------------
-- items_norm VIEW (must match hydrate function)
-- ----------------------------
DROP VIEW IF EXISTS monday_staging.items_norm CASCADE;

CREATE VIEW monday_staging.items_norm (board_id, item_id, raw_json, run_id) AS
SELECT
  (ij.payload_jsonb->'board'->>'id')::bigint AS board_id,
  CASE
    WHEN ij.item_id ~ '^\d+$' THEN ij.item_id::bigint
    ELSE (ij.payload_jsonb->>'id')::bigint
  END AS item_id,
  ij.payload_jsonb AS raw_json,
  ij.run_id
FROM monday_staging.items_json ij;
