CREATE EXTENSION IF NOT EXISTS pgcrypto;
SET search_path TO master_dashboard;
CREATE TABLE IF NOT EXISTS master_dashboard.gced_mftf25_startups (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  source            TEXT NOT NULL DEFAULT 'monday',
  monday_board_id   TEXT,
  monday_item_id    TEXT,
  monday_item_name  TEXT,

  startup_name      TEXT,
  hubspot_link      TEXT,
  switchpitch_link  TEXT,

  startup_source    TEXT,
  track             TEXT,
  startup_type      TEXT,
  venture           TEXT,

  gced_scrub_label  TEXT,
  team_decision     TEXT,
  pitch_deck_rec    TEXT,
  sosa_status       TEXT,

  average_score     NUMERIC(4,2),
  due_date          DATE,
  last_updated_at   TIMESTAMPTZ,

  pre_cap_notes     TEXT,

  people_label      TEXT,
  team_label        TEXT,

  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'gced_mftf25_unique_source'
  ) THEN
    ALTER TABLE master_dashboard.gced_mftf25_startups
      ADD CONSTRAINT gced_mftf25_unique_source
      UNIQUE (source, monday_board_id, monday_item_id);
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_startup_name
  ON master_dashboard.gced_mftf25_startups (startup_name);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_track
  ON master_dashboard.gced_mftf25_startups (track);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_team_decision
  ON master_dashboard.gced_mftf25_startups (team_decision);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_startup_source
  ON master_dashboard.gced_mftf25_startups (startup_source);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_average_score
  ON master_dashboard.gced_mftf25_startups (average_score);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_due_date
  ON master_dashboard.gced_mftf25_startups (due_date);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_sosa_status
  ON master_dashboard.gced_mftf25_startups (sosa_status);

DROP TRIGGER IF EXISTS trg_gced_mftf25_touch ON master_dashboard.gced_mftf25_startups;

CREATE TRIGGER trg_gced_mftf25_touch
BEFORE UPDATE ON master_dashboard.gced_mftf25_startups
FOR EACH ROW EXECUTE FUNCTION master_dashboard.trg_touch_updated_at();
