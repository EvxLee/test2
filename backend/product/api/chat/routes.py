"""
Flask routes for the chat endpoint.

This module provides the /atlas/chat endpoint for the RAG agent.
"""

import logging
import traceback

from flask import request, jsonify, Response
from flask_restx import Namespace, Resource, fields

from .agent import AtlasAgent
from .document_answer import (
    clamp_answer_chunks,
    format_document_search_answer,
    normalize_answer_style,
)
from .services import get_chat_services
from display.core.db import fetch_all
from cache import get_cache, make_cache_key

logger = logging.getLogger(__name__)


def get_agent() -> AtlasAgent:
    """Get or create the agent instance."""
    return get_chat_services().get_agent()

def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)

def keyword_search(query: str, limit: int = 10) -> list:
    try:
        rows = fetch_all("""
            SELECT
                dc.id,
                dc.document_id,
                dc.chunk_text,
                dc.page_number,
                dc.section_title,
                dc.metadata,
                d.source_type,
                d.source_id,
                d.file_name
            FROM llm.document_chunks dc
            JOIN llm.documents d ON d.id = dc.document_id
            WHERE
                dc.chunk_text ILIKE %s
                OR d.file_name ILIKE %s
            LIMIT %s
        """, (f"%{query}%", f"%{query}%", limit))
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Keyword search failed: {e}")
        return []
def rerank_results(query: str, results: list) -> list:
    if not results:
        return []
    if len(results) <= 3:
        return results  # no need to rerank tiny lists

    try:
        from .llm_client import get_llm_client
        import json

        llm = get_llm_client()

        # Build a simplified list to send to LLM
        simplified = [
            {
                "index": i,
                "text": r.get("chunk_text", "")[:300],
                "file": r.get("file_name") or r.get("source_type", ""),
            }
            for i, r in enumerate(results)
        ]

        prompt = f"""You are ranking search results by relevance to a user query.





User query: "{query}"

Here are the results (each has an index, file name, and text snippet):
{json.dumps(simplified, indent=2)}

Return ONLY a JSON array of the indices in order from most to least relevant.
Example: [2, 0, 4, 1, 3]
Return at most 5 indices. Return ONLY the array, nothing else."""

        response = llm.invoke(messages=[{"role": "user", "content": prompt}])
        content = response.get("content", "").strip()

        # Parse the LLM response
        indices = json.loads(content)
        reranked = [results[i] for i in indices if i < len(results)]

        # Add any results not included by LLM at the end
        included = set(indices)
        for i, r in enumerate(results):
            if i not in included:
                reranked.append(r)

        return reranked

    except Exception as e:
        logger.warning(f"Reranking failed, returning original order: {e}")
        return results  # safe fallback — return original if reranking fails

def apply_metadata_boost(results: list, filter_category: str = None, filter_source_type: str = None) -> list:
    """Feature 6: Filter and boost results using metadata."""
    import json
    from datetime import datetime, timezone

    filtered = []
    for item in results:
        # Parse metadata if it's a string
        meta = item.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        # --- FILTERING ---
        # Filter by category if provided
        if filter_category:
            item_category = meta.get("category", "")
            if not item_category or filter_category.lower() not in item_category.lower():
                continue  # skip this result

        # Filter by source type if provided
        if filter_source_type:
            if item.get("source_type") != filter_source_type:
                continue  # skip this result

        filtered.append(item)

    # --- RANKING BOOST ---
    # Score each result and sort
    def score(item):
        s = 0.0

        # Boost if it has a file name (more useful to users)
        meta = item.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        if meta.get("file_name") or item.get("file_name"):
            s += 0.2

        # Boost if it has a category
        if meta.get("category"):
            s += 0.1

        # Boost by recency using updated_at
        updated_at = item.get("updated_at")
        if updated_at:
            try:
                if isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(updated_at)
                age_days = (datetime.now(timezone.utc) - updated_at.replace(tzinfo=timezone.utc)).days
                # More recent = higher boost (max boost for today, 0 boost for 365+ days ago)
                recency_boost = max(0, 1 - age_days / 365) * 0.2
                s += recency_boost
            except Exception:
                pass

        # Boost files over other source types
        if item.get("source_type") == "file":
            s += 0.1

        return s

    # Sort by score descending, preserving original order for ties
    filtered.sort(key=score, reverse=True)
    return filtered

def register_chat_routes(ns: Namespace):
    """
    Register chat routes on the given namespace.

    Args:
        ns: Flask-RESTX namespace to register routes on
    """

    # Request/response models
    chat_message_model = ns.model("ChatMessage", {
        "role": fields.String(required=True, description="Message role: user, assistant, system"),
        "content": fields.String(required=True, description="Message content"),
    })

    chat_request_model = ns.model("ChatRequest", {
        "message": fields.String(required=True, description="The user's message"),
        "thread_id": fields.String(required=False, description="Optional thread ID for conversation tracking"),
        "conversation_history": fields.List(
            fields.Nested(chat_message_model),
            required=False,
            description="Optional previous messages for context"
        ),
    })

    chat_response_model = ns.model("ChatResponse", {
        "response": fields.String(description="The assistant's response"),
        "thread_id": fields.String(description="Thread ID for this conversation"),
        "artifacts": fields.List(fields.Raw, description="Any retrieved data artifacts"),
        "answer_source": fields.String(description="Source used for the answer: atlas_context, general_knowledge, web, or none"),
        "grounding_status": fields.String(description="Grounding status: grounded, empty, weak, not_required, or external"),
        "confidence": fields.String(description="Answer confidence: high, medium, or low"),
        "warning": fields.String(description="Optional warning when the answer is not grounded in Atlas context"),
        "retrieval_attempted": fields.Boolean(description="Whether Atlas retrieval was attempted"),
        "retrieval_artifact_count": fields.Integer(description="Number of retrieved Atlas artifacts"),
        "max_score": fields.Float(description="Maximum retrieval score used for grounding"),
    })

    error_model = ns.model("ChatError", {
        "error": fields.Nested(ns.model("ErrorDetail", {
            "type": fields.String,
            "message": fields.String,
        }))
    })

    document_search_request_model = ns.model("DocumentSearchRequest", {
        "query": fields.String(required=True, description="Semantic search query"),
        "source_type": fields.String(
            required=False,
            description="Filter by source type: project, organization, pitchbook_deal, pitchbook_company, monday_item, contract, document, file"
        ),
        "limit": fields.Integer(required=False, default=10, description="Max results (1-100, default 10)"),
        "mode": fields.String(
            required=False,
            description="Search mode: semantic or hybrid (default: hybrid for source_type=file, else semantic)"
        ),
        "rerank": fields.Boolean(
            required=False,
            default=False,
            description="If true, rerank top results with an LLM (hybrid mode only)."
        ),
        "file_type": fields.String(
            required=False,
            description="Filter by file type: pdf, docx, pptx, etc."
        ),
        "filter_category": fields.String(required=False, description="Filter results by category"),
        "format_response": fields.Boolean(
            required=False,
            default=False,
            description="If true, generate a Claude-formatted grounded answer from retrieved chunks."
        ),
        "answer_style": fields.String(
            required=False,
            default="summary",
            description="Formatted answer style: summary, direct, or bullets."
        ),
        "max_answer_chunks": fields.Integer(
            required=False,
            default=6,
            description="Maximum top-ranked chunks to send to Claude for answer formatting (1-10)."
        ),
    })

    document_search_response_model = ns.model("DocumentSearchResponse", {
        "query": fields.String(description="The search query"),
        "count": fields.Integer(description="Number of results returned"),
        "answer": fields.String(description="Optional Claude-formatted grounded answer"),
        "citations": fields.List(fields.Raw, description="Sources used by the formatted answer"),
        "answer_source": fields.String(description="Source used for the formatted answer"),
        "grounding_status": fields.String(description="Grounding status: grounded, empty, weak, or none"),
        "confidence": fields.String(description="Answer confidence: high, medium, or low"),
        "warning": fields.String(description="Optional warning when formatting is unavailable or weakly grounded"),
        "results": fields.List(fields.Raw, description="List of matching document chunks"),
    })

    @ns.route("/chat")
    class ChatEndpoint(Resource):
        @ns.expect(chat_request_model, validate=True)
        @ns.response(200, "Success", chat_response_model)
        @ns.response(400, "Bad Request", error_model)
        @ns.response(500, "Internal Error", error_model)
        @ns.doc(
            description="""
Chat with the Atlas AI assistant.

The assistant can:
- Find specific documents and project information
- Answer questions about startups and projects
- Compare companies and technologies
- Provide market intelligence
- Filter projects by stage, vertical, etc.

Example questions:
- "Show me the ExampleCo PoC Outcome report"
- "What projects are in the AI vertical?"
- "Compare SampleCo with similar startups"
- "List all Seed stage companies"
"""
        )
        def post(self):
            """Send a message to the Atlas AI assistant."""
            try:
                data = request.get_json(force=True) or {}

                message = data.get("message", "").strip()
                if not message:
                    return {
                        "error": {
                            "type": "validation_error",
                            "message": "Message is required"
                        }
                    }, 400

                thread_id = data.get("thread_id")
                conversation_history = data.get("conversation_history", [])

                # Get agent and process message
                agent = get_agent()
                result = agent.invoke(
                    user_message=message,
                    conversation_history=conversation_history,
                    thread_id=thread_id,
                )

                return {
                    "response": result.get("response", ""),
                    "thread_id": result.get("thread_id"),
                    "artifacts": result.get("artifacts", []),
                    "answer_source": result.get("answer_source"),
                    "grounding_status": result.get("grounding_status"),
                    "confidence": result.get("confidence"),
                    "warning": result.get("warning"),
                    "retrieval_attempted": result.get("retrieval_attempted"),
                    "retrieval_artifact_count": result.get("retrieval_artifact_count"),
                    "max_score": result.get("max_score"),
                }, 200

            except Exception as e:
                logger.error(f"Chat error: {e}")
                traceback.print_exc()
                return {
                    "error": {
                        "type": "internal_error",
                        "message": str(e)
                    }
                }, 500

    @ns.route("/chat/health")
    class ChatHealthEndpoint(Resource):
        @ns.doc(description="Check if the chat service is available")
        def get(self):
            """Health check for chat service."""
            try:
                # Try to initialize the agent (but don't invoke it)
                agent = get_agent()
                return {
                    "status": "ok",
                    "service": "chat",
                    "agent_initialized": agent is not None,
                }, 200
            except Exception as e:
                return {
                    "status": "error",
                    "service": "chat",
                    "error": str(e),
                }, 503

    @ns.route("/embed/status")
    class EmbedStatusEndpoint(Resource):
        @ns.doc(description="Check embedding pipeline status — chunk counts per source type and last updated timestamp.")
        def get(self):
            """Return embedding pipeline health."""
            try:
                rows = fetch_all("""
                    SELECT
                        d.source_type,
                        COUNT(*) AS total_chunks,
                        MAX(dc.updated_at) AS last_updated
                    FROM llm.document_chunks dc
                    JOIN llm.documents d ON d.id = dc.document_id
                    GROUP BY d.source_type
                    ORDER BY d.source_type
                """, ())
                return {
                    "status": "ok" if rows else "empty",
                    "sources": [
                        {
                            "source_type": r["source_type"],
                            "total_chunks": r["total_chunks"],
                            "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None,
                        }
                        for r in rows
                    ],
                }, 200
            except Exception as e:
                logger.error(f"Embed status error: {e}")
                return {"status": "error", "error": str(e)}, 500

    @ns.route("/chat/tools")
    class ChatToolsEndpoint(Resource):
        @ns.doc(description="List available tools for the chat agent")
        def get(self):
            """List available chat tools."""
            from .tools import TOOL_DEFINITIONS
            return {
                "tools": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                    }
                    for t in TOOL_DEFINITIONS
                ]
            }, 200

    @ns.route("/document-search")
    class DocumentSearchEndpoint(Resource):
        @ns.expect(document_search_request_model, validate=True)
        @ns.response(200, "Success", document_search_response_model)
        @ns.response(400, "Bad Request", error_model)
        @ns.response(500, "Internal Error", error_model)
        @ns.doc(description="Perform semantic search over document embeddings.")
        def post(self):
            """Search documents using semantic similarity."""
            try:
                from app import _require_auth
                if (auth := _require_auth()):
                    return auth
            except ImportError:
                pass

            try:
                data = request.get_json(force=True) or {}
                original_query = data.get("query", "").strip()
                if not original_query:
                    return {"error": {"type": "validation_error", "message": "query is required"}}, 400

                source_type = data.get("source_type")
                limit = max(1, min(int(data.get("limit", 10)), 100))
                mode = (data.get("mode") or "auto").strip().lower()
                rerank = bool(data.get("rerank", False))
                file_type = (data.get("file_type") or "").strip().lower() or None
                filter_category = data.get("filter_category")
                format_response = _as_bool(data.get("format_response"), False)
                answer_style = normalize_answer_style(data.get("answer_style"))
                max_answer_chunks = clamp_answer_chunks(data.get("max_answer_chunks"))

                _cache = get_cache()
                _cache_key = make_cache_key("docsearch", {
                    "query": original_query,
                    "source_type": source_type or "",
                    "limit": str(limit),
                    "mode": mode,
                    "rerank": str(rerank),
                    "file_type": file_type or "",
                    "filter_category": filter_category or "",
                    "format_response": str(format_response),
                    "answer_style": answer_style,
                    "max_answer_chunks": str(max_answer_chunks),
                })
                _cached = _cache.get(_cache_key)
                if _cached is not None:
                    return _cached, 200

                services = get_chat_services()
                rag = services.get_rag_tools()

                result = rag.retrieve_context(
                    query=original_query,
                    source_types=[source_type] if source_type else None,
                    limit=limit,
                    mode=mode,
                    file_type=file_type,
                    rerank=rerank,
                )
                artifacts = result.artifacts or []
                results = [
                    {
                        "file_name": a.get("file_name") or a.get("section_title") or "-",
                        "file_type": a.get("file_type"),
                        "spaces_key": a.get("spaces_key"),
                        "snippet": a.get("snippet") or a.get("chunk_text"),
                        "chunk_text": a.get("chunk_text"),
                        "page": a.get("page") or a.get("page_number"),
                        "page_number": a.get("page_number"),
                        "section_title": a.get("section_title"),
                        "document_id": a.get("document_id"),
                        "source_type": a.get("source_type"),
                        "source_id": a.get("source_id"),
                        "similarity": a.get("similarity"),
                        "score": a.get("score") or a.get("fusion_score") or a.get("similarity"),
                        "document_score": a.get("document_score"),
                        "matched_chunk_count": a.get("matched_chunk_count"),
                        "rank_reason": a.get("rank_reason"),
                        "metadata": a.get("metadata") or {},
                    }
                    for a in artifacts
                ]

                # Feature 6: Metadata filtering + boost
                results = apply_metadata_boost(
                    results=results,
                    filter_category=filter_category,
                    filter_source_type=source_type,
                )

                response = {
                    "query": original_query,
                    "count": len(results),
                    "results": results,
                }

                if format_response:
                    answer_payload = format_document_search_answer(
                        query=original_query,
                        results=results,
                        llm_client_factory=services.get_llm_client,
                        answer_style=answer_style,
                        max_answer_chunks=max_answer_chunks,
                    )
                    response.update(answer_payload)

                _cache.set(_cache_key, response)
                return response, 200

            except Exception as e:
                logger.error(f"Document search error: {e}")
                traceback.print_exc()
                return {"error": {"type": "internal_error", "message": str(e)}}, 500

    return ns
