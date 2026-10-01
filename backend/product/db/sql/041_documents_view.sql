-- =====================================================
-- Documents View for Frontend
-- Provides a clean interface for the Documents tab
-- =====================================================

CREATE SCHEMA IF NOT EXISTS master_dashboard;

CREATE OR REPLACE VIEW master_dashboard.documents AS
SELECT
    f.monday_file_id AS id,
    f.file_name AS "fileName",
    f.public_url AS "fileUrl",
    COALESCE(f.category, 'Uncategorized') AS category,
    COALESCE(f.owner_name, 'Unknown') AS owner,
    f.updated_at AS "lastUpdate",
    COALESCE(f.summary, 'No summary available') AS summary,
    COALESCE(LOWER(SUBSTRING(f.file_name FROM '\.([^.]+)$')), '') AS "fileType",
    f.created_at AS "uploadDate"
FROM monday.files f
WHERE f.public_url IS NOT NULL
    AND f.file_name IS NOT NULL
    AND f.board_id = '10000000003'  -- AI - Locate a specific file board
ORDER BY f.updated_at DESC;
