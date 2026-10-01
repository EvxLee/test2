-- 091_core_attachments_asset_id.sql
-- Adds asset_id to core_attachments so Monday file URLs can be refreshed
-- on demand (pre-signed S3 URLs expire after 1 hour).

ALTER TABLE master_dashboard.core_attachments
    ADD COLUMN IF NOT EXISTS asset_id TEXT;

-- Partial unique index on asset_id for Monday file attachments.
-- Replaces the URL-based uniqueness for these rows since URLs expire.
CREATE UNIQUE INDEX IF NOT EXISTS ux_core_attachments_asset_id
    ON master_dashboard.core_attachments (asset_id)
    WHERE asset_id IS NOT NULL;
