-- =====================================================
-- Keyword Search Support for RAG (FTS)
--
-- Adds GIN indexes to support keyword / exact-phrase style search
-- over:
--   - llm.document_chunks.chunk_text
--   - llm.documents.file_name
--
-- Note: this is safe to run on fresh installs and existing DBs.
-- =====================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Full-text search index for chunk text
CREATE INDEX IF NOT EXISTS idx_llm_document_chunks_fts
ON llm.document_chunks
USING GIN (to_tsvector('english', COALESCE(chunk_text, '')));

-- Full-text search index for file names
CREATE INDEX IF NOT EXISTS idx_llm_documents_file_name_fts
ON llm.documents
USING GIN (to_tsvector('simple', COALESCE(file_name, '')));

-- Trigram index to speed up ILIKE matches on file_name (exact-ish filename queries)
CREATE INDEX IF NOT EXISTS idx_llm_documents_file_name_trgm
ON llm.documents
USING GIN (file_name gin_trgm_ops);

