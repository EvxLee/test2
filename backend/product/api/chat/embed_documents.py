"""
Script to generate embeddings for documents in the Atlas database.

This script:
1. Fetches data from various sources (projects, organizations, PitchBook, files)
2. Chunks the text content using a paragraph-aware strategy
3. Generates embeddings using Amazon Titan (concurrently per document)
4. Stores embeddings in the llm.document_chunks table

Usage:
    python -m chat.embed_documents --source projects
    python -m chat.embed_documents --source files
    python -m chat.embed_documents --source all
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any, Generator

from display.core.db import fetch_all, get_conn
from board_config_db import get_board_ids_by_mapper_type
from .llm_client import get_embedding_client
from .file_extractor import extract_text, TextSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Titan v2 supports up to 8,192 tokens. At ~4 chars/token this is ~32,768 chars.
# We guard at 6,000 tokens (~24,000 chars) to leave headroom for edge cases.
_MAX_SAFE_TOKENS = 6000

# Conservative concurrency — Bedrock default quota is typically 5-10 per model.
_MAX_EMBED_WORKERS = 5
_DEFAULT_FILES_BOARD_ID = "10000000003"
_DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024


def _resolve_files_board_id(board_id: str | None = None) -> str:
    """Resolve the Monday board ID used for file embeddings."""
    configured_ids = get_board_ids_by_mapper_type("ai_locate_file", "file_metadata")
    return (
        board_id
        or (sorted(configured_ids)[0] if configured_ids else None)
        or os.getenv("EMBED_FILES_BOARD_ID")
        or _DEFAULT_FILES_BOARD_ID
    )


def _resolve_max_file_bytes(max_file_bytes: int | None = None) -> int:
    """Resolve the extraction size guard; <= 0 disables the limit."""
    if max_file_bytes is not None:
        return max_file_bytes

    raw = os.getenv("EMBED_MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE_BYTES))
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Invalid EMBED_MAX_FILE_BYTES '{raw}', using {_DEFAULT_MAX_FILE_BYTES}")
        return _DEFAULT_MAX_FILE_BYTES


def _estimate_tokens(text: str) -> int:
    """Estimate token count using a conservative chars-per-token ratio."""
    return len(text) // 4


def _chunk_by_sentences(text: str, chunk_size: int = 1500, overlap: int = 0) -> List[str]:
    """
    Sentence-boundary character chunker.

    Splits text at sentence-ending punctuation when possible, falling back
    to a hard character cut. Used as a fallback for oversized paragraphs
    inside chunk_text() and for the token-guard force-split.

    Args:
        text:       Text to split.
        chunk_size: Maximum characters per chunk.
        overlap:    Characters to repeat at the start of the next chunk.
                    Defaults to 0 because chunk_text() applies overlap
                    as a post-processing step.

    Returns:
        List of non-empty text chunks.
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            for punct in ['. ', '! ', '? ', '\n\n', '\n']:
                last_punct = text[start:end].rfind(punct)
                if last_punct > chunk_size // 2:
                    end = start + last_punct + len(punct)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 300) -> List[str]:
    """
    Paragraph-aware text chunker.

    Strategy:
      1. Split on double-newlines to recover natural paragraph boundaries.
      2. Greedily group consecutive paragraphs up to chunk_size characters.
      3. Paragraphs that individually exceed chunk_size are split by sentence
         boundary (via _chunk_by_sentences).
      4. Any chunk that still exceeds _MAX_SAFE_TOKENS is force-split.
      5. Overlap is applied uniformly as a post-processing step: the last
         `overlap` characters of chunk N are prepended to chunk N+1.

    Args:
        text:       The text to chunk.
        chunk_size: Target maximum characters per chunk (default 1500 ≈ 375 tokens).
        overlap:    Characters of context to share between adjacent chunks
                    (default 300).

    Returns:
        List of non-empty text chunks.
    """
    if not text or not text.strip():
        return []

    stripped = text.strip()
    if len(stripped) <= chunk_size and _estimate_tokens(stripped) <= _MAX_SAFE_TOKENS:
        return [stripped]

    paragraphs = [p.strip() for p in stripped.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    raw_chunks: List[str] = []
    current_group: List[str] = []

    for para in paragraphs:
        if len(para) > chunk_size:
            if current_group:
                raw_chunks.append("\n\n".join(current_group))
                current_group = []
            raw_chunks.extend(_chunk_by_sentences(para, chunk_size=chunk_size, overlap=0))
            continue

        current_len = (
            sum(len(p) for p in current_group) + 2 * (len(current_group) - 1)
            if current_group else 0
        )
        sep = 2 if current_group else 0

        if current_group and current_len + sep + len(para) > chunk_size:
            raw_chunks.append("\n\n".join(current_group))
            current_group = []

        current_group.append(para)

    if current_group:
        raw_chunks.append("\n\n".join(current_group))

    # Token guard: force-split any chunk that exceeds the safe token limit.
    guarded: List[str] = []
    for chunk in raw_chunks:
        if _estimate_tokens(chunk) > _MAX_SAFE_TOKENS:
            guarded.extend(
                _chunk_by_sentences(chunk, chunk_size=chunk_size // 2, overlap=0)
            )
        else:
            guarded.append(chunk)

    # Apply overlap as a uniform post-processing step
    if overlap > 0 and len(guarded) > 1:
        with_overlap = [guarded[0]]
        for i in range(1, len(guarded)):
            prev_tail = guarded[i - 1][-overlap:]
            with_overlap.append(prev_tail + "\n\n" + guarded[i])
        return [c for c in with_overlap if c.strip()]

    return [c for c in guarded if c.strip()]


def fetch_projects(since: datetime | None = None) -> Generator[Dict[str, Any], None, None]:
    """Fetch project data for embedding."""
    sql = """
        SELECT
            p.id,
            p.project_code,
            p.name,
            p.company_name,
            p.description,
            p.stage_name,
            p.status_category,
            v.vertical_name,
            l.display_name AS location,
            ps.summary_text AS summary
        FROM master_dashboard.projects p
        LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
        LEFT JOIN master_dashboard.locations l ON p.location_id = l.id
        LEFT JOIN master_dashboard.project_summaries ps
            ON ps.project_id = p.id AND ps.lang = 'en'
        WHERE p.name IS NOT NULL
    """
    params: list = []
    if since:
        sql += " AND p.updated_at > %s"
        params.append(since)
    rows = fetch_all(sql, params)

    for row in rows:
        content_parts = []

        if row.get('name'):
            content_parts.append(f"Project: {row['name']}")
        if row.get('company_name'):
            content_parts.append(f"Company: {row['company_name']}")
        if row.get('vertical_name'):
            content_parts.append(f"Vertical: {row['vertical_name']}")
        if row.get('stage_name'):
            content_parts.append(f"Stage: {row['stage_name']}")
        if row.get('location'):
            content_parts.append(f"Location: {row['location']}")
        if row.get('description'):
            content_parts.append(f"\nDescription:\n{row['description']}")
        if row.get('summary'):
            content_parts.append(f"\nSummary:\n{row['summary']}")

        content = "\n".join(content_parts)

        yield {
            "source_type": "project",
            "source_id": str(row['id']),
            "source_table": "master_dashboard.projects",
            "content": content,
            "segments": [TextSegment(text=content)],
            "metadata": {
                "project_name": row.get('name'),
                "company_name": row.get('company_name'),
                "vertical": row.get('vertical_name'),
                "stage": row.get('stage_name'),
                "location": row.get('location'),
            }
        }


def fetch_organizations(since: datetime | None = None) -> Generator[Dict[str, Any], None, None]:
    """Fetch organization data for embedding."""
    sql = """
        SELECT
            o.id,
            o.org_name,
            o.org_type,
            o.website,
            o.country
        FROM master_dashboard.organizations o
        WHERE o.org_name IS NOT NULL
    """
    params: list = []
    if since:
        sql += " AND o.updated_at > %s"
        params.append(since)
    rows = fetch_all(sql, params)

    for row in rows:
        content_parts = [f"Organization: {row['org_name']}"]

        if row.get('org_type'):
            content_parts.append(f"Type: {row['org_type']}")
        if row.get('country'):
            content_parts.append(f"Country: {row['country']}")
        if row.get('website'):
            content_parts.append(f"Website: {row['website']}")

        content = "\n".join(content_parts)

        yield {
            "source_type": "organization",
            "source_id": str(row['id']),
            "source_table": "master_dashboard.organizations",
            "content": content,
            "segments": [TextSegment(text=content)],
            "metadata": {
                "org_name": row.get('org_name'),
                "org_type": row.get('org_type'),
                "country": row.get('country'),
            }
        }


def fetch_pitchbook_deals() -> Generator[Dict[str, Any], None, None]:
    """Fetch PitchBook deal data for embedding.

    dp.pitchbook_deals has no updated_at column, so incremental filtering
    is not supported. This source always does a full scan.
    """
    sql = """
        SELECT
            deal_id,
            startups,
            deal_type,
            deal_size,
            deal_date,
            primary_industry_sector,
            hq_location,
            investors,
            description
        FROM dp.pitchbook_deals
        WHERE startups IS NOT NULL
    """

    try:
        rows = fetch_all(sql, ())
    except Exception as e:
        logger.warning(f"Could not fetch PitchBook data: {e}")
        return

    for row in rows:
        content_parts = [f"Company: {row['startups']}"]

        if row.get('deal_type'):
            content_parts.append(f"Deal Type: {row['deal_type']}")
        if row.get('deal_size'):
            content_parts.append(f"Deal Size: ${row['deal_size']}")
        if row.get('primary_industry_sector'):
            content_parts.append(f"Industry: {row['primary_industry_sector']}")
        if row.get('hq_location'):
            content_parts.append(f"Location: {row['hq_location']}")
        if row.get('investors'):
            content_parts.append(f"Investors: {row['investors']}")
        if row.get('description'):
            content_parts.append(f"\nDescription:\n{row['description']}")

        content = "\n".join(content_parts)

        yield {
            "source_type": "pitchbook_deal",
            "source_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(row['deal_id']))),
            "source_table": "dp.pitchbook_deals",
            "content": content,
            "segments": [TextSegment(text=content)],
            "metadata": {
                "company_name": row.get('startups'),
                "deal_type": row.get('deal_type'),
                "industry": row.get('primary_industry_sector'),
                "location": row.get('hq_location'),
            }
        }


def fetch_pitchbook_companies(since: datetime | None = None) -> Generator[Dict[str, Any], None, None]:
    """Fetch PitchBook company-profile data for embedding.

    dp.pitchbook_companies has an updated_at column, so incremental filtering
    is supported.
    """
    since_filter = "AND updated_at > %(since)s" if since else ""
    sql = f"""
        SELECT
            company_id,
            company_name,
            description,
            primary_industry_sector,
            primary_industry_group,
            verticals,
            keywords,
            hq_city,
            hq_state_province,
            hq_country_region,
            hq_global_region,
            total_raised,
            last_financing_date,
            last_financing_deal_type_1,
            active_investors,
            employees,
            year_founded,
            competitors
        FROM dp.pitchbook_companies
        WHERE company_name IS NOT NULL
        {since_filter}
    """

    params = {"since": since} if since else {}
    try:
        rows = fetch_all(sql, params)
    except Exception as e:
        logger.warning(f"Could not fetch PitchBook companies: {e}")
        return

    for row in rows:
        content_parts = [f"Company: {row['company_name']}"]

        if row.get('primary_industry_sector'):
            content_parts.append(f"Industry: {row['primary_industry_sector']}")
        if row.get('primary_industry_group'):
            content_parts.append(f"Industry Group: {row['primary_industry_group']}")

        location_parts = [p for p in [row.get('hq_city'), row.get('hq_state_province'), row.get('hq_country_region')] if p]
        if location_parts:
            content_parts.append(f"Location: {', '.join(location_parts)}")
        if row.get('hq_global_region'):
            content_parts.append(f"Region: {row['hq_global_region']}")

        if row.get('year_founded'):
            content_parts.append(f"Founded: {row['year_founded']}")
        if row.get('employees'):
            content_parts.append(f"Employees: {row['employees']}")
        if row.get('total_raised'):
            content_parts.append(f"Total Raised: ${row['total_raised']}")
        if row.get('last_financing_date'):
            content_parts.append(f"Last Financing: {row['last_financing_date']} ({row.get('last_financing_deal_type_1', '')})")
        if row.get('active_investors'):
            content_parts.append(f"Investors: {row['active_investors']}")
        if row.get('competitors'):
            content_parts.append(f"Competitors: {row['competitors']}")
        if row.get('verticals'):
            content_parts.append(f"Verticals: {row['verticals']}")
        if row.get('keywords'):
            content_parts.append(f"Keywords: {row['keywords']}")
        if row.get('description'):
            content_parts.append(f"\nDescription:\n{row['description']}")

        content = "\n".join(content_parts)

        yield {
            "source_type": "pitchbook_company",
            "source_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(row['company_id']))),
            "source_table": "dp.pitchbook_companies",
            "content": content,
            "segments": [TextSegment(text=content)],
            "metadata": {
                "company_name": row.get('company_name'),
                "industry": row.get('primary_industry_sector'),
                "location": ", ".join(location_parts) if location_parts else None,
                "year_founded": row.get('year_founded'),
            }
        }


def fetch_monday_items(since: datetime | None = None) -> Generator[Dict[str, Any], None, None]:
    """Fetch Monday.com board items for embedding.

    Joins monday.items with monday.boards for board context, and aggregates
    monday.item_properties into readable key/value text. Uses monday_item_id
    (TEXT) as source_id.
    """
    since_filter = "AND i.updated_at > %(since)s" if since else ""
    sql = f"""
        SELECT
            i.monday_id AS monday_item_id,
            i.name AS item_name,
            i.board_id AS board_id,
            b.name AS board_name,
            string_agg(
                CASE WHEN ip.value_text IS NOT NULL AND ip.value_text <> ''
                     THEN ip.column_id || ': ' || ip.value_text
                     ELSE NULL END,
                E'\n' ORDER BY ip.column_id
            ) AS properties_text,
            COUNT(DISTINCT f.monday_file_id) AS file_count,
            string_agg(DISTINCT f.file_name, ', ' ORDER BY f.file_name)
                FILTER (WHERE f.file_name IS NOT NULL) AS file_names
        FROM monday.items i
        JOIN monday.boards b ON i.board_id = b.monday_board_id
        LEFT JOIN monday.item_properties ip ON i.monday_id = ip.monday_item_id
        LEFT JOIN monday.files f ON f.item_id = i.monday_id
        WHERE i.is_active = TRUE
          AND i.name IS NOT NULL
          {since_filter}
        GROUP BY i.monday_id, i.name, b.name
    """

    try:
        rows = fetch_all(sql, {"since": since} if since else {})
    except Exception as e:
        logger.warning(f"Could not fetch Monday items: {e}")
        return

    # Build board-type lookup sets once from board_config.
    nvp_ids = get_board_ids_by_mapper_type("new_venture_proposals")
    cs_ids = get_board_ids_by_mapper_type("contract_status")
    gced_ids = get_board_ids_by_mapper_type("gced")
    incubation_ids = get_board_ids_by_mapper_type("incubation")

    for row in rows:
        content_parts = [f"Item: {row['item_name']}"]

        if row.get('board_name'):
            content_parts.append(f"Board: {row['board_name']}")

        board_id = row.get('board_id') or ''
        if board_id in nvp_ids:
            board_type = "New Venture Proposals (NVP)"
        elif board_id in cs_ids:
            board_type = "Contract Status"
        elif board_id in gced_ids:
            board_type = "GCED"
        elif board_id in incubation_ids:
            board_type = "Incubation"
        else:
            board_type = None

        if board_type:
            content_parts.append(f"Board Type: {board_type}")

        if row.get('properties_text'):
            content_parts.append(f"\nProperties:\n{row['properties_text']}")

        file_count = row.get('file_count') or 0
        if file_count > 0:
            content_parts.append(f"Has Attachments: Yes")
            if row.get('file_names'):
                content_parts.append(f"Attached Files: {row['file_names']}")

        content = "\n".join(content_parts)

        yield {
            "source_type": "monday_item",
            "source_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(row['monday_item_id']))),
            "source_table": "monday.items",
            "content": content,
            "segments": [TextSegment(text=content)],
            "metadata": {
                "item_name": row.get('item_name'),
                "board_name": row.get('board_name'),
                "board_type": board_type,
            },
        }


def fetch_contracts(since: datetime | None = None) -> Generator[Dict[str, Any], None, None]:
    """Fetch contract status data for embedding."""
    sql = """
        SELECT
            cs.id,
            cs.contract,
            cs.category,
            cs.team,
            cs.status_label,
            cs.priority_label,
            cs.stage,
            cs.contract_amount,
            cs.start_date,
            cs.end_date,
            cs.pjt_task,
            cs.detail_scope,
            cs.owner,
            p.name AS project_name
        FROM master_dashboard.contract_status cs
        LEFT JOIN master_dashboard.projects p ON cs.project_id = p.id
        WHERE cs.contract IS NOT NULL
    """
    params: list = []
    if since:
        sql += " AND cs.updated_at > %s"
        params.append(since)

    try:
        rows = fetch_all(sql, params)
    except Exception as e:
        logger.warning(f"Could not fetch contracts: {e}")
        return

    for row in rows:
        content_parts = [f"Contract: {row['contract']}"]

        if row.get('category'):
            content_parts.append(f"Category: {row['category']}")
        if row.get('team'):
            content_parts.append(f"Team: {row['team']}")
        if row.get('status_label'):
            content_parts.append(f"Status: {row['status_label']}")
        if row.get('priority_label'):
            content_parts.append(f"Priority: {row['priority_label']}")
        if row.get('stage'):
            content_parts.append(f"Stage: {row['stage']}")
        if row.get('project_name'):
            content_parts.append(f"Project: {row['project_name']}")
        if row.get('owner'):
            content_parts.append(f"Owner: {row['owner']}")
        if row.get('contract_amount') is not None:
            content_parts.append(f"Amount: ${row['contract_amount']}")
        if row.get('start_date'):
            content_parts.append(f"Start: {row['start_date']}")
        if row.get('end_date'):
            content_parts.append(f"End: {row['end_date']}")
        if row.get('pjt_task'):
            content_parts.append(f"Project/Task: {row['pjt_task']}")
        if row.get('detail_scope'):
            content_parts.append(f"\nScope:\n{row['detail_scope']}")

        content = "\n".join(content_parts)

        yield {
            "source_type": "contract",
            "source_id": str(row['id']),
            "source_table": "master_dashboard.contract_status",
            "content": content,
            "segments": [TextSegment(text=content)],
            "metadata": {
                "contract": row.get('contract'),
                "category": row.get('category'),
                "team": row.get('team'),
                "status": row.get('status_label'),
                "project_name": row.get('project_name'),
            },
        }


def fetch_documents(since: datetime | None = None) -> Generator[Dict[str, Any], None, None]:
    """Fetch Monday.com file data for embedding."""
    sql = """
        SELECT
            monday_file_id,
            file_name,
            category,
            owner_name,
            summary,
            created_at
        FROM monday.files
        WHERE summary IS NOT NULL
          AND summary != 'No summary available'
    """
    params: list = []
    if since:
        sql += " AND updated_at > %s"
        params.append(since)
    rows = fetch_all(sql, params)

    for row in rows:
        file_name = row.get('file_name')
        file_type = (
            file_name.rsplit(".", 1)[-1].lower()
            if file_name and "." in file_name
            else None
        )
        content = f"File: {file_name}\n\nSummary:\n{row['summary']}"

        yield {
            "source_type": "document",
            "source_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(row['monday_file_id']))),
            "source_table": "monday.files",
            "content": content,
            "metadata": {
                "file_name": file_name,
                "file_type": file_type,
                "upload_date": row['created_at'].isoformat() if row.get('created_at') else None,
                "category": row.get('category'),
                "owner_name": row.get('owner_name'),
            }
        }


def fetch_files(
    board_id: str | None = None,
    max_file_bytes: int | None = None,
    since: datetime | None = None,
) -> Generator[Dict[str, Any], None, None]:
    """Fetch files from DO Spaces and extract their text for embedding."""
    resolved_board_id = _resolve_files_board_id(board_id)
    resolved_max_file_bytes = _resolve_max_file_bytes(max_file_bytes)
    sql = """
        SELECT
            monday_file_id AS id,
            file_name AS "fileName",
            spaces_key AS "spacesKey",
            category,
            owner_name AS owner
        FROM monday.files
        WHERE spaces_key IS NOT NULL
          AND file_name IS NOT NULL
          AND board_id = %s
    """
    params: list = [resolved_board_id]
    if since:
        sql += " AND updated_at > %s"
        params.append(since)
    rows = fetch_all(sql, params)

    from files import spaces

    for row in rows:
        file_name = row["fileName"]
        spaces_key = row["spacesKey"]

        try:
            file_bytes = spaces.download(spaces_key)
        except Exception as e:
            logger.warning(f"Could not download {file_name}: {e}")
            continue

        if resolved_max_file_bytes > 0 and len(file_bytes) > resolved_max_file_bytes:
            logger.warning(
                f"Skipping {file_name}: size {len(file_bytes)} bytes exceeds "
                f"limit {resolved_max_file_bytes} bytes"
            )
            continue

        segments = extract_text(file_bytes, file_name)
        if not segments:
            logger.warning(f"No text extracted from {file_name}, skipping")
            continue

        # monday_file_id is a numeric Monday.com ID, not a UUID.
        # Derive a deterministic UUID so it fits the source_id UUID column.
        source_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(row["id"])))

        content = "\n\n".join(s.text for s in segments)

        yield {
            "source_type": "file",
            "source_id": source_id,
            "source_table": "monday.files",
            "content": content,
            "segments": segments,
            "metadata": {
                "file_name": file_name,
                "spaces_key": spaces_key,
                "category": row.get("category"),
                "owner": row.get("owner"),
            },
        }


def _upsert_document(doc: Dict[str, Any]) -> str:
    """
    Upsert a document into llm.documents and return its UUID.

    Uses (source_type, source_id) as the unique key so re-runs are idempotent.
    """
    sql = """
        INSERT INTO llm.documents
            (source_type, source_id, source_table,
             file_name, spaces_key, category, owner, file_type, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (source_type, source_id) DO UPDATE
            SET source_table = EXCLUDED.source_table,
                file_name = EXCLUDED.file_name,
                spaces_key = EXCLUDED.spaces_key,
                category = EXCLUDED.category,
                owner = EXCLUDED.owner,
                file_type = EXCLUDED.file_type,
                metadata = EXCLUDED.metadata,
                updated_at = now()
        RETURNING id
    """
    meta = doc.get("metadata", {})
    file_name = meta.get("file_name")
    file_type = meta.get("file_type") or (
        file_name.rsplit(".", 1)[-1].lower()
        if file_name and "." in file_name
        else None
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                doc["source_type"],
                doc["source_id"],
                doc["source_table"],
                file_name,
                meta.get("spaces_key"),
                meta.get("category"),
                meta.get("owner"),
                file_type,
                json.dumps(meta),
            ))
            return str(cur.fetchone()[0])


def embed_and_store(
    documents: Generator[Dict[str, Any], None, None],
    embedding_client,
    batch_size: int = 10,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Generate embeddings and store in database.

    For each document:
      - Upserts a row into llm.documents, obtaining a document_id.
      - Chunks each TextSegment's text using the paragraph-aware chunker.
      - Prepends a metadata context header to the text sent to the embedding
        model so the vector captures category/file context. The clean chunk
        text (without header) is what gets stored in the DB.
      - Carries page_number and section_title from the segment to each chunk.
      - Embeds all chunks for a document concurrently via a thread pool.
      - Accumulates a cross-document batch and writes to DB at batch_size.

    Args:
        documents:         Generator of document dicts.
        embedding_client:  Embedding client instance.
        batch_size:        Number of chunks to accumulate before a DB commit.
        dry_run:           If True, embed but do not store.

    Returns:
        Stats dict with processed / errors / skipped counts.
    """
    stats = {"processed": 0, "errors": 0, "skipped": 0}
    batch = []

    with ThreadPoolExecutor(max_workers=_MAX_EMBED_WORKERS) as pool:
        for doc in documents:
            try:
                if not dry_run:
                    document_id = _upsert_document(doc)
                else:
                    document_id = str(uuid.uuid4())  # placeholder for dry-run

                # Fetch already-embedded chunk hashes so we can skip unchanged content.
                existing_hashes: set[str] = (
                    _fetch_existing_chunk_hashes(document_id) if not dry_run else set()
                )

                segments: list[TextSegment] = doc.get("segments") or [
                    TextSegment(text=doc["content"])
                ]

                # Build metadata context header
                meta = doc.get("metadata", {})
                header_parts = [p for p in [
                    f"Category: {meta['category']}" if meta.get("category") else None,
                    f"File: {meta['file_name']}" if meta.get("file_name") else None,
                ] if p]
                header = f"[{' | '.join(header_parts)}]\n" if header_parts else ""

                # Collect (chunk_text, embed_text, page_number, section_title) tuples
                # and a parallel list of md5 hashes for skip-detection.
                chunk_items: List[tuple[str, str, int | None, str | None]] = []
                chunk_hashes: List[str] = []
                for seg in segments:
                    chunks = chunk_text(seg.text, chunk_size=1500, overlap=300)
                    for chunk in chunks:
                        if not chunk.strip():
                            stats["skipped"] += 1
                            continue
                        embed_text = f"{header}{chunk}" if header else chunk
                        chunk_items.append((chunk, embed_text, seg.page_number, seg.section_title))
                        chunk_hashes.append(hashlib.md5(chunk.encode()).hexdigest())

                if not chunk_items:
                    logger.info(
                        f"[{doc.get('source_type', '?')}] Skipped "
                        f"'{meta.get('file_name') or doc.get('source_id', '?')}': no chunks produced"
                    )
                    continue

                # Determine which chunks are new vs. already embedded.
                new_indices = [i for i, h in enumerate(chunk_hashes) if h not in existing_hashes]
                cached_count = len(chunk_items) - len(new_indices)
                stats["skipped"] += cached_count

                label = meta.get('file_name') or doc.get('source_id', '?')
                if new_indices:
                    logger.info(
                        f"[{doc.get('source_type', '?')}] Embedding '{label}'"
                        f" — {len(new_indices)} chunk(s)"
                        + (f" ({cached_count} cached)" if cached_count else "")
                    )
                else:
                    logger.debug(f"[{doc.get('source_type', '?')}] Skipping '{label}': all {cached_count} chunk(s) cached")
                    continue

                # Embed only new chunks concurrently
                embeddings: Dict[int, List[float]] = {}
                future_to_idx = {
                    pool.submit(embedding_client.embed, chunk_items[i][1]): i
                    for i in new_indices
                }
                for future in as_completed(future_to_idx):
                    i = future_to_idx[future]
                    try:
                        embeddings[i] = future.result()
                    except Exception as e:
                        logger.error(f"Embedding error: {e}")
                        stats["errors"] += 1

                # Assemble batch from new chunks only
                for i in new_indices:
                    if i not in embeddings:
                        continue

                    chunk, _, page_number, section_title = chunk_items[i]
                    batch.append({
                        "document_id": document_id,
                        "chunk_text": chunk,
                        "page_number": page_number,
                        "section_title": section_title,
                        "metadata": json.dumps(doc.get("metadata", {})),
                        "embedding": embeddings[i],
                    })

                    if len(batch) >= batch_size:
                        if not dry_run:
                            _store_batch(batch)
                        stats["processed"] += len(batch)
                        logger.info(f"Processed {stats['processed']} chunks...")
                        batch = []

            except Exception as e:
                logger.error(f"Document processing error: {e}")
                stats["errors"] += 1

    # Store remaining batch
    if batch:
        if not dry_run:
            _store_batch(batch)
        stats["processed"] += len(batch)

    return stats


def _store_batch(batch: List[Dict]):
    """Store a batch of embeddings in the database."""
    sql = """
        INSERT INTO llm.document_chunks
            (document_id, chunk_text, page_number, section_title, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::vector)
        ON CONFLICT (document_id, (md5(chunk_text)))
        DO UPDATE SET
            page_number = EXCLUDED.page_number,
            section_title = EXCLUDED.section_title,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            updated_at = now()
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            for item in batch:
                embedding_str = "[" + ",".join(str(x) for x in item["embedding"]) + "]"

                cur.execute(sql, (
                    item["document_id"],
                    item["chunk_text"],
                    item["page_number"],
                    item["section_title"],
                    item["metadata"],
                    embedding_str,
                ))


def _fetch_existing_chunk_hashes(document_id: str) -> set[str]:
    """Return the set of md5(chunk_text) values already stored for this document."""
    sql = "SELECT md5(chunk_text) AS md5 FROM llm.document_chunks WHERE document_id = %s"
    rows = fetch_all(sql, (document_id,))
    return {r["md5"] for r in rows}


def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for Atlas documents")
    parser.add_argument(
        "--source",
        choices=[
            "projects",
            "organizations",
            "pitchbook",
            "pitchbook_companies",
            "monday_items",
            "contracts",
            "documents",
            "files",
            "all",
        ],
        default="all",
        help="Data source to embed",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for database commits",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually store embeddings",
    )
    parser.add_argument(
        "--files-board-id",
        help="Override the Monday board ID used for file embeddings",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        help="Skip file extraction when downloaded bytes exceed this limit; <= 0 disables the limit",
    )

    args = parser.parse_args()

    try:
        embedding_client = get_embedding_client()
        logger.info("Embedding client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize embedding client: {e}")
        sys.exit(1)

    sources = {
        "projects": fetch_projects,
        "organizations": fetch_organizations,
        "pitchbook": fetch_pitchbook_deals,
        "pitchbook_companies": fetch_pitchbook_companies,
        "monday_items": fetch_monday_items,
        "contracts": fetch_contracts,
        "documents": fetch_documents,
        "files": lambda: fetch_files(
            board_id=args.files_board_id,
            max_file_bytes=args.max_file_bytes,
        ),
    }

    if args.source == "all":
        selected = list(sources.keys())
    else:
        selected = [args.source]

    total_stats = {"processed": 0, "errors": 0, "skipped": 0}

    for source_name in selected:
        logger.info(f"Processing {source_name}...")
        fetch_fn = sources[source_name]

        stats = embed_and_store(
            fetch_fn(),
            embedding_client,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )

        for key in total_stats:
            total_stats[key] += stats[key]

        logger.info(f"{source_name}: {stats}")

    logger.info(f"Total: {total_stats}")


if __name__ == "__main__":
    main()
