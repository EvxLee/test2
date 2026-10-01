"""fix_llm_source_id_uuid_to_text_and_ivfflat_to_hnsw

Revision ID: 9d08f2ea3af2
Revises: ee4c8a1b9d20
Create Date: 2026-04-12 20:33:08.882477

Changes:
- llm.documents.source_id: UUID -> TEXT (Monday item IDs are plain strings, not UUIDs)
- llm.document_chunks embedding index: IVFFlat -> HNSW (no manual reindex required)
- llm.semantic_search(): update return type source_id UUID -> TEXT

⚠️  ALTER COLUMN TYPE briefly locks llm.documents (ACCESS EXCLUSIVE).
    Safe to run — table is small and lock is released immediately after the cast.
"""
from typing import Sequence, Union
from alembic import op


revision: str = '9d08f2ea3af2'
down_revision: Union[str, Sequence[str], None] = 'ee4c8a1b9d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Change source_id from UUID -> TEXT.
    #    Existing UUID values cast automatically to their text representation.
    #    The unique constraint uq_document_source covers (source_type, source_id)
    #    and remains valid after the type change.
    op.execute("""
        ALTER TABLE llm.documents
            ALTER COLUMN source_id TYPE TEXT
            USING source_id::TEXT
    """)

    # 2. Replace IVFFlat index with HNSW.
    #    IVFFlat requires a manual REINDEX after new rows are inserted.
    #    HNSW updates incrementally on every insert — no manual maintenance needed.
    op.execute("DROP INDEX IF EXISTS llm.idx_chunks_embedding")
    op.execute("""
        CREATE INDEX idx_chunks_embedding
        ON llm.document_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)

    # 3. Update semantic_search() return type to match the new TEXT column.
    #    Must DROP first — PostgreSQL disallows changing return type via CREATE OR REPLACE.
    op.execute("DROP FUNCTION IF EXISTS llm.semantic_search(vector, integer, character varying, jsonb)")
    op.execute("""
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
            source_id TEXT,
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
        $$
    """)


def downgrade() -> None:
    # Restore semantic_search() with UUID return type
    op.execute("""
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
                d.source_id::UUID,
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
        $$
    """)

    # Restore IVFFlat index
    op.execute("DROP INDEX IF EXISTS llm.idx_chunks_embedding")
    op.execute("""
        CREATE INDEX idx_chunks_embedding
        ON llm.document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Revert source_id TEXT -> UUID (will fail if any non-UUID values exist)
    op.execute("""
        ALTER TABLE llm.documents
            ALTER COLUMN source_id TYPE UUID
            USING source_id::UUID
    """)
