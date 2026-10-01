-- =====================================================
-- LLM Schema Refactor: llm.documents + llm.document_chunks
--
-- Safe for both:
--   1. Legacy schemas where llm.document_chunks still has source_type,
--      source_id, source_table, and content.
--   2. Fresh installs where 040_llm_embeddings.sql already created the
--      final llm.documents + chunk_text/document_id schema.
-- =====================================================

-- Step 1: Create llm.documents table
CREATE TABLE IF NOT EXISTS llm.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,
    source_id UUID NOT NULL,
    source_table VARCHAR(100),
    file_name TEXT,
    spaces_key TEXT,
    category TEXT,
    owner TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_document_source UNIQUE (source_type, source_id)
);

-- Step 2: Backfill llm.documents from legacy chunk rows when the old
-- source_* columns still exist on llm.document_chunks.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'llm'
          AND table_name = 'document_chunks'
          AND column_name = 'source_type'
    ) THEN
        INSERT INTO llm.documents (
            source_type,
            source_id,
            source_table,
            file_name,
            spaces_key,
            category,
            owner,
            metadata
        )
        SELECT DISTINCT
            dc.source_type,
            dc.source_id,
            dc.source_table,
            dc.metadata ->> 'file_name',
            dc.metadata ->> 'spaces_key',
            dc.metadata ->> 'category',
            dc.metadata ->> 'owner',
            COALESCE(dc.metadata, '{}'::jsonb)
        FROM llm.document_chunks dc
        ON CONFLICT (source_type, source_id) DO UPDATE
        SET
            source_table = COALESCE(EXCLUDED.source_table, llm.documents.source_table),
            file_name = COALESCE(EXCLUDED.file_name, llm.documents.file_name),
            spaces_key = COALESCE(EXCLUDED.spaces_key, llm.documents.spaces_key),
            category = COALESCE(EXCLUDED.category, llm.documents.category),
            owner = COALESCE(EXCLUDED.owner, llm.documents.owner),
            metadata = CASE
                WHEN llm.documents.metadata IS NULL OR llm.documents.metadata = '{}'::jsonb
                    THEN EXCLUDED.metadata
                ELSE llm.documents.metadata
            END,
            updated_at = now();
    END IF;
END $$;

-- Step 3: Add new columns to document_chunks
ALTER TABLE llm.document_chunks
    ADD COLUMN IF NOT EXISTS document_id UUID REFERENCES llm.documents(id),
    ADD COLUMN IF NOT EXISTS page_number INTEGER,
    ADD COLUMN IF NOT EXISTS section_title TEXT;

-- Step 4: Rename legacy content to chunk_text if needed.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'llm'
          AND table_name = 'document_chunks'
          AND column_name = 'content'
    ) THEN
        ALTER TABLE llm.document_chunks RENAME COLUMN content TO chunk_text;
    END IF;
END $$;

-- Step 5: Backfill document_id on legacy rows.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'llm'
          AND table_name = 'document_chunks'
          AND column_name = 'source_type'
    ) THEN
        UPDATE llm.document_chunks dc
        SET document_id = d.id
        FROM llm.documents d
        WHERE d.source_type = dc.source_type
          AND d.source_id = dc.source_id
          AND dc.document_id IS NULL;
    END IF;
END $$;

-- Step 6: Replace the legacy uniqueness rule with the new document-level one.
ALTER TABLE llm.document_chunks DROP CONSTRAINT IF EXISTS uq_chunk_source;
ALTER TABLE llm.document_chunks DROP CONSTRAINT IF EXISTS uq_chunk_document;
DROP INDEX IF EXISTS llm.uq_chunk_document_hash;
CREATE UNIQUE INDEX IF NOT EXISTS uq_chunk_document_hash
ON llm.document_chunks(document_id, md5(chunk_text));

-- Step 7: document_id is required once backfill has completed.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'llm'
          AND table_name = 'document_chunks'
          AND column_name = 'document_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM llm.document_chunks
        WHERE document_id IS NULL
    ) THEN
        ALTER TABLE llm.document_chunks
            ALTER COLUMN document_id SET NOT NULL;
    END IF;
END $$;

-- Step 8: Drop legacy document identity columns after backfill.
ALTER TABLE llm.document_chunks DROP COLUMN IF EXISTS source_type;
ALTER TABLE llm.document_chunks DROP COLUMN IF EXISTS source_id;
ALTER TABLE llm.document_chunks DROP COLUMN IF EXISTS source_table;

-- Step 9: Index on document_id for fast chunk lookups
CREATE INDEX IF NOT EXISTS idx_chunks_document_id
ON llm.document_chunks(document_id);

-- Step 10: Update semantic_search() to join llm.documents
CREATE OR REPLACE FUNCTION llm.semantic_search(
    query_embedding vector(1024),
    match_count INT DEFAULT 5,
    filter_source_type VARCHAR DEFAULT NULL,
    filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    source_type VARCHAR,
    source_id UUID,
    chunk_text TEXT,
    page_number INTEGER,
    section_title TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        d.source_type,
        d.source_id,
        dc.chunk_text,
        dc.page_number,
        dc.section_title,
        dc.metadata,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM llm.document_chunks dc
    JOIN llm.documents d ON d.id = dc.document_id
    WHERE
        (filter_source_type IS NULL OR d.source_type = filter_source_type)
        AND (filter_metadata IS NULL OR dc.metadata @> filter_metadata)
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
