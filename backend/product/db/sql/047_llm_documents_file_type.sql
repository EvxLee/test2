-- =====================================================
-- Add file_type column to llm.documents
-- Backfill from existing file_name values
-- =====================================================

ALTER TABLE llm.documents
    ADD COLUMN IF NOT EXISTS file_type TEXT;

-- Backfill from file_name for existing rows
UPDATE llm.documents
SET file_type = LOWER(SPLIT_PART(file_name, '.', -1))
WHERE file_type IS NULL
  AND file_name IS NOT NULL
  AND file_name LIKE '%.%';
