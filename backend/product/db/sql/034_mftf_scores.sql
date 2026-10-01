-- Add MFTF Cycle evaluation score columns to gced_mftf25_startups
ALTER TABLE master_dashboard.gced_mftf25_startups
  ADD COLUMN IF NOT EXISTS overall_startup_strength NUMERIC(4,2),
  ADD COLUMN IF NOT EXISTS collaboration_potential   NUMERIC(4,2);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_overall_startup_strength
  ON master_dashboard.gced_mftf25_startups (overall_startup_strength);

CREATE INDEX IF NOT EXISTS ix_gced_mftf25_collaboration_potential
  ON master_dashboard.gced_mftf25_startups (collaboration_potential);
