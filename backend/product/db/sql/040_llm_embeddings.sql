-- LLM Embeddings Schema for RAG
-- Requires pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS llm;

-- Document-level registry: one row per source document / entity
CREATE TABLE IF NOT EXISTS llm.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,   -- 'project', 'organization', 'pitchbook_deal', 'file'
    source_id UUID NOT NULL,            -- Reference to source record
    source_table VARCHAR(100),          -- e.g., 'monday.files'
    file_name TEXT,
    spaces_key TEXT,
    category TEXT,
    owner TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_document_source UNIQUE (source_type, source_id)
);

-- Store document chunks with embeddings
CREATE TABLE IF NOT EXISTS llm.document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document reference
    document_id UUID NOT NULL REFERENCES llm.documents(id) ON DELETE CASCADE,

    -- Content
    chunk_text TEXT NOT NULL,
    page_number INTEGER,                -- PDF page number, PPTX slide number; NULL for DOCX/non-paged
    section_title TEXT,                 -- PPTX slide title, DOCX heading; NULL if unavailable
    metadata JSONB DEFAULT '{}',        -- Additional metadata (file_name, category, etc.)

    -- Embedding (Amazon Titan v2 produces 1024-dim vectors)
    embedding vector(1024),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Enforce idempotent chunk upserts without indexing the full chunk text.
CREATE UNIQUE INDEX IF NOT EXISTS uq_chunk_document_hash
ON llm.document_chunks(document_id, md5(chunk_text));

-- IVFFlat index for approximate nearest neighbour search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
ON llm.document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for fast chunk lookup by document
CREATE INDEX IF NOT EXISTS idx_chunks_document_id
ON llm.document_chunks(document_id);

-- GIN index for metadata filtering
CREATE INDEX IF NOT EXISTS idx_chunks_metadata
ON llm.document_chunks
USING GIN (metadata);

-- Chat history for conversation memory
CREATE TABLE IF NOT EXISTS llm.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES llm.chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system', 'tool'
    content TEXT NOT NULL,
    tool_calls JSONB,           -- For AI messages with tool calls
    tool_call_id VARCHAR(100),  -- For tool response messages
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_session
ON llm.chat_messages(session_id, created_at);

-- View for easy project context retrieval
CREATE OR REPLACE VIEW llm.project_context AS
SELECT
    p.id AS project_id,
    p.project_code,
    p.name AS project_name,
    p.company_name,
    p.description,
    p.stage_name,
    p.status_category,
    p.is_ongoing,
    p.start_date,
    p.end_date,
    v.vertical_name,
    l.display_name AS location,
    l.country,
    l.city,
    ps.summary_text AS summary_en,
    COALESCE(
        string_agg(DISTINCT ppl.full_name, ', ') FILTER (WHERE ppl.full_name IS NOT NULL),
        ''
    ) AS owners,
    COALESCE(
        string_agg(DISTINCT org.org_name || ' (' || por.role || ')', ', ') FILTER (WHERE org.org_name IS NOT NULL),
        ''
    ) AS organizations
FROM master_dashboard.projects p
LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
LEFT JOIN master_dashboard.locations l ON p.location_id = l.id
LEFT JOIN master_dashboard.project_summaries ps ON ps.project_id = p.id AND ps.lang = 'en'
LEFT JOIN master_dashboard.project_owners po ON po.project_id = p.id
LEFT JOIN master_dashboard.people ppl ON ppl.id = po.person_id
LEFT JOIN master_dashboard.project_org_roles por ON por.project_id = p.id
LEFT JOIN master_dashboard.organizations org ON org.id = por.org_id
GROUP BY
    p.id, p.project_code, p.name, p.company_name, p.description,
    p.stage_name, p.status_category, p.is_ongoing, p.start_date, p.end_date,
    v.vertical_name, l.display_name, l.country, l.city, ps.summary_text;

-- Function for semantic search
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
