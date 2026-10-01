"""Claude-backed formatting for document search results."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_ANSWER_CHUNKS = 6
MAX_ANSWER_CHUNKS_CAP = 10
DEFAULT_MIN_SCORE = 0.70


def _min_score() -> float:
    raw = os.getenv("ATLAS_DOC_SEARCH_MIN_SCORE") or os.getenv("ATLAS_RAG_MIN_SCORE")
    if not raw:
        return DEFAULT_MIN_SCORE
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_MIN_SCORE


def clamp_answer_chunks(value: Any) -> int:
    """Return a bounded chunk count for LLM answer formatting."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_MAX_ANSWER_CHUNKS
    return max(1, min(parsed, MAX_ANSWER_CHUNKS_CAP))


def normalize_answer_style(value: Any) -> str:
    style = str(value or "summary").strip().lower()
    return style if style in {"summary", "direct", "bullets"} else "summary"


def _score(result: Dict[str, Any]) -> float:
    for key in ("score", "similarity"):
        value = result.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _citation_for(index: int, result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "index": index,
        "file_name": result.get("file_name"),
        "file_type": result.get("file_type"),
        "document_id": result.get("document_id"),
        "source_type": result.get("source_type"),
        "source_id": result.get("source_id"),
        "page": result.get("page") or result.get("page_number"),
        "page_number": result.get("page_number") or result.get("page"),
        "section_title": result.get("section_title"),
        "score": result.get("score"),
        "similarity": result.get("similarity"),
        "snippet": result.get("snippet"),
        "spaces_key": result.get("spaces_key"),
    }


def _context_block(index: int, result: Dict[str, Any]) -> str:
    text = (result.get("chunk_text") or result.get("snippet") or "").strip()
    if len(text) > 1600:
        text = text[:1600].rstrip() + "..."

    source = result.get("file_name") or result.get("section_title") or result.get("source_type") or "Unknown source"
    page = result.get("page") or result.get("page_number") or "unknown"
    section = result.get("section_title") or "unknown"
    document_id = result.get("document_id") or "unknown"

    return (
        f"[{index}] Source: {source}\n"
        f"Page: {page}\n"
        f"Section: {section}\n"
        f"Document ID: {document_id}\n"
        f"Text:\n{text}"
    )


def build_document_answer_prompt(
    query: str,
    results: List[Dict[str, Any]],
    *,
    answer_style: str,
) -> str:
    style_instructions = {
        "summary": "Write a concise summary answer in 1-3 short paragraphs.",
        "direct": "Answer directly in the first sentence, then add only essential supporting detail.",
        "bullets": "Use concise bullets. Keep each bullet grounded in the provided context.",
    }
    context = "\n\n---\n\n".join(
        _context_block(index, result)
        for index, result in enumerate(results, start=1)
    )
    return f"""You are formatting Atlas document search results into a grounded answer.

Use only the provided document context. Do not use outside knowledge. If the context does not contain enough information, say that the retrieved context does not contain enough information.

User query:
{query}

Formatting requirement:
{style_instructions.get(answer_style, style_instructions["summary"])}

Citation requirement:
Mention the most relevant source names and page numbers when available. Use bracket references like [1] or [2] to connect claims to the provided context.

Document context:
{context}
"""


def format_document_search_answer(
    *,
    query: str,
    results: List[Dict[str, Any]],
    llm_client: Optional[Any] = None,
    llm_client_factory: Optional[Any] = None,
    answer_style: str = "summary",
    max_answer_chunks: int = DEFAULT_MAX_ANSWER_CHUNKS,
) -> Dict[str, Any]:
    """Generate an optional grounded answer for document search results."""
    selected = results[:clamp_answer_chunks(max_answer_chunks)]
    citations = [_citation_for(index, result) for index, result in enumerate(selected, start=1)]

    if not selected:
        return {
            "answer": "No relevant Atlas document context was found for this query.",
            "citations": [],
            "answer_source": "none",
            "grounding_status": "empty",
            "confidence": "low",
            "warning": "No relevant retrieved context was available, so no generated answer was produced.",
        }

    max_score = max(_score(result) for result in selected)
    if max_score < _min_score():
        return {
            "answer": "I found possible matching documents, but not enough reliable context to answer confidently.",
            "citations": citations,
            "answer_source": "none",
            "grounding_status": "weak",
            "confidence": "low",
            "warning": "Retrieved context was below the configured grounding threshold.",
        }

    prompt = build_document_answer_prompt(
        query=query,
        results=selected,
        answer_style=normalize_answer_style(answer_style),
    )
    try:
        if llm_client is None:
            if not callable(llm_client_factory):
                raise RuntimeError("No Claude client is configured for document answer formatting")
            llm_client = llm_client_factory()
        response = llm_client.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1200,
        )
        answer = (response.get("content") or "").strip()
        if not answer:
            raise RuntimeError("Claude returned an empty answer")
        return {
            "answer": answer,
            "citations": citations,
            "answer_source": "atlas_context",
            "grounding_status": "grounded",
            "confidence": "high",
            "warning": None,
        }
    except Exception as exc:
        logger.warning("Document answer formatting failed: %s", exc)
        return {
            "answer": None,
            "citations": citations,
            "answer_source": "atlas_context",
            "grounding_status": "grounded",
            "confidence": "medium",
            "warning": f"Retrieved results are available, but Claude formatting failed: {exc}",
        }
