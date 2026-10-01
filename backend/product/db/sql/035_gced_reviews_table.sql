-- 035_gced_reviews_table.sql
-- Separate reviewer subitems into their own table linked to gced_mftf25_startups.
-- This resolves the bug where "Reviewer 1/2/3" rows were being ingested as startups.

SET search_path TO master_dashboard;

CREATE TABLE IF NOT EXISTS master_dashboard.gced_mftf25_reviews (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Link back to the startup this review belongs to
  startup_id        UUID NOT NULL REFERENCES master_dashboard.gced_mftf25_startups(id)
                    ON DELETE CASCADE,

  source            TEXT NOT NULL DEFAULT 'monday',
  monday_board_id   TEXT,
  monday_item_id    TEXT,     -- the reviewer subitem's Monday item ID
  monday_item_name  TEXT,     -- e.g. "Reviewer 1", "Reviewer 2", "Reviewer 3"

  overall_startup_strength  NUMERIC(4,2),
  collaboration_potential   NUMERIC(4,2),

  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_gced_mftf25_reviews_source
    UNIQUE (source, monday_board_id, monday_item_id)
);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_reviews_startup_id
  ON master_dashboard.gced_mftf25_reviews (startup_id);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_reviews_board_id
  ON master_dashboard.gced_mftf25_reviews (monday_board_id);

DROP TRIGGER IF EXISTS trg_gced_mftf25_reviews_touch
  ON master_dashboard.gced_mftf25_reviews;

CREATE TRIGGER trg_gced_mftf25_reviews_touch
BEFORE UPDATE ON master_dashboard.gced_mftf25_reviews
FOR EACH ROW EXECUTE FUNCTION master_dashboard.trg_touch_updated_at();

-- One-time cleanup: remove any rows previously ingested as startups
-- that actually correspond to Monday subitems.
DELETE FROM master_dashboard.gced_mftf25_startups g
USING monday.items it
WHERE g.monday_item_id::text = it.monday_id::text
  AND COALESCE(
        it.raw_json->>'parent_item_id',
        it.raw_json->>'parentItemId'
      ) IS NOT NULL;
