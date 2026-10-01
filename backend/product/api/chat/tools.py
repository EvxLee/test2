"""
RAG Tools for the LLM agent.

These tools allow the agent to:
1. Perform semantic search on document embeddings
2. Query structured data (projects, companies, deals)
3. Filter and aggregate data
"""

import logging
import json
import os
import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from display.core.db import fetch_all, fetch_one, get_conn
from .metadata_ranker import rerank_with_metadata

logger = logging.getLogger(__name__)

_STRONG_KEYWORD_SCORE_THRESHOLD = 0.8
ATLAS_RETRIEVAL_SOURCE_TYPES = [
    "project",
    "organization",
    "pitchbook_deal",
    "pitchbook_company",
    "monday_item",
    "contract",
    "document",
    "file",
]
_HYBRID_SOURCE_TYPES = {"file", "document"}
_DOCUMENT_SUMMARY_CONTEXT_CHARS = int(os.getenv("ATLAS_DOCUMENT_SUMMARY_CONTEXT_CHARS", "32000"))
_DOCUMENT_SUMMARY_GROUP_CHARS = int(os.getenv("ATLAS_DOCUMENT_SUMMARY_GROUP_CHARS", "12000"))


def _tokenize_query(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 1 and token not in {"the", "a", "an", "and", "or", "of", "for", "to", "on", "in"}
    ]


def _metadata_text(row: Dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    return " ".join(
        str(value)
        for value in [
            row.get("file_name"),
            row.get("category"),
            row.get("owner"),
            metadata.get("file_name"),
            metadata.get("category"),
            metadata.get("owner"),
            metadata.get("owner_name"),
        ]
        if value
    ).lower()


def _filename_rank_boost(query: str, row: Dict[str, Any]) -> Tuple[float, str]:
    tokens = _tokenize_query(query)
    if not tokens:
        return 0.0, "semantic_match"

    name = str(row.get("file_name") or "").lower()
    metadata_text = _metadata_text(row)
    name_tokens = set(_tokenize_query(name))
    metadata_tokens = set(_tokenize_query(metadata_text))
    if not name_tokens and not metadata_tokens:
        return 0.0, "semantic_match"

    filename_hits = sum(1 for token in tokens if token in name_tokens)
    metadata_hits = sum(1 for token in tokens if token in metadata_tokens)
    filename_coverage = filename_hits / len(tokens)
    metadata_coverage = metadata_hits / len(tokens)

    boost = 0.0
    reason = "semantic_match"
    if filename_coverage:
        boost += 0.08 * filename_coverage
        reason = "filename_match"
    if metadata_coverage:
        boost += 0.03 * metadata_coverage
        if reason == "semantic_match":
            reason = "metadata_match"

    normalized_name = " ".join(_tokenize_query(name))
    normalized_query = " ".join(tokens)
    if normalized_query and normalized_query in normalized_name:
        boost += 0.08
        reason = "title_match"
    elif len(tokens) > 1 and filename_coverage >= 0.95:
        boost += 0.05
        reason = "filename_match"

    return round(boost, 6), reason


@dataclass
class ToolResult:
    """Standard tool result format."""
    content: str
    artifacts: Optional[List[Dict]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Tool definitions for the LLM
TOOL_DEFINITIONS = [
    {
        "name": "get_cycle_startup_count",
        "description": (
            "Return the authoritative startup count for a GCED cycle from structured Atlas SQL data. "
            "Use before atlas_retrieve for questions like 'how many startups were in cycle 5'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cycle_id": {
                    "type": "string",
                    "description": "Canonical cycle id such as gced_cycle5. Optional if cycle_number is provided."
                },
                "cycle_number": {
                    "type": "integer",
                    "description": "Cycle number, e.g. 5 for gced_cycle5."
                },
                "year": {
                    "type": "integer",
                    "description": "Optional year mentioned by the user. Used for display only unless cycle data is year-scoped."
                },
            },
        },
    },
    {
        "name": "get_cycle_startups",
        "description": (
            "List startups for a GCED cycle from structured Atlas SQL data. "
            "Use before atlas_retrieve for cycle startup list questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cycle_id": {
                    "type": "string",
                    "description": "Canonical cycle id such as gced_cycle5. Optional if cycle_number is provided."
                },
                "cycle_number": {
                    "type": "integer",
                    "description": "Cycle number, e.g. 5 for gced_cycle5."
                },
                "year": {
                    "type": "integer",
                    "description": "Optional year mentioned by the user. Used for display only unless cycle data is year-scoped."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum startups to return in the formatted content.",
                    "default": 25,
                },
            },
        },
    },
    {
        "name": "get_project_counts",
        "description": "Count Atlas projects from structured SQL, optionally grouped by stage, vertical, owner, or status.",
        "parameters": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "enum": ["stage", "vertical", "owner", "status"]},
                "stage": {"type": "string"},
                "vertical": {"type": "string"},
                "owner": {"type": "string"},
                "status": {"type": "string"},
                "is_ongoing": {"type": "boolean"},
            },
        },
    },
    {
        "name": "get_contract_metrics",
        "description": "Count contracts and sum contract amounts from structured SQL, optionally grouped by status, stage, owner, team, or category.",
        "parameters": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "enum": ["status", "stage", "owner", "team", "category"]},
                "status": {"type": "string"},
                "stage": {"type": "string"},
                "owner": {"type": "string"},
                "team": {"type": "string"},
                "category": {"type": "string"},
            },
        },
    },
    {
        "name": "get_startup_counts",
        "description": "Count GCED startups from structured SQL, optionally by cycle, vertical, team decision, status, or source.",
        "parameters": {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "string"},
                "cycle_number": {"type": "integer"},
                "group_by": {"type": "string", "enum": ["cycle", "vertical", "decision", "status", "source"]},
                "vertical": {"type": "string"},
                "decision": {"type": "string"},
                "status": {"type": "string"},
                "source": {"type": "string"},
                "year": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_pitchbook_counts",
        "description": "Count PitchBook companies or deals from structured SQL with common filters.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "enum": ["company", "deal"]},
                "group_by": {"type": "string", "enum": ["industry", "country", "region", "deal_type", "year", "vertical"]},
                "industry": {"type": "string"},
                "country": {"type": "string"},
                "region": {"type": "string"},
                "deal_type": {"type": "string"},
                "company_name": {"type": "string"},
                "year": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_monday_counts",
        "description": "Count Monday boards or items from structured SQL, optionally filtered by board id/name and active status.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "enum": ["board", "item"]},
                "board_id": {"type": "string"},
                "board_name": {"type": "string"},
                "active_only": {"type": "boolean"},
                "group_by": {"type": "string", "enum": ["board", "active"]},
            },
        },
    },
    {
        "name": "get_file_counts",
        "description": "Count Monday files from structured SQL, optionally grouped by board, category, owner, or file type.",
        "parameters": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string"},
                "board_name": {"type": "string"},
                "category": {"type": "string"},
                "owner": {"type": "string"},
                "file_type": {"type": "string"},
                "group_by": {"type": "string", "enum": ["board", "category", "owner", "type"]},
            },
        },
    },
    {
        "name": "atlas_retrieve",
        "description": (
            "Retrieve grounded Atlas context from internal embeddings and files. Use structured tools "
            "first for counts, totals, filters, lists, and cycle questions. Use atlas_retrieve for semantic "
            "questions about Atlas data and for document/file questions where chunks and file metadata are needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's natural-language retrieval query"
                },
                "source_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ATLAS_RETRIEVAL_SOURCE_TYPES,
                    },
                    "description": "Optional source-type filters. Use ['file'] for full-text file retrieval."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of retrieval results (default 8)",
                    "default": 8
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "semantic", "hybrid"],
                    "description": "Retrieval mode. Use auto unless the caller explicitly needs semantic or hybrid.",
                    "default": "auto"
                },
                "file_type": {
                    "type": "string",
                    "description": "Optional file extension filter for file/document retrieval, such as pdf, docx, or pptx"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "semantic_search",
        "description": "Backward-compatible Atlas semantic search. Prefer atlas_retrieve for new calls, especially document/file questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query in natural language"
                },
                "source_type": {
                    "type": "string",
                    "enum": ATLAS_RETRIEVAL_SOURCE_TYPES,
                    "description": "Optional filter by source type"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_project_details",
        "description": "Get detailed information about a specific project by name or code. Use when user asks about a specific project like 'Tell me about Project X' or 'What is ExampleCo?'",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "The project name or code to look up"
                }
            },
            "required": ["project_name"]
        }
    },
    {
        "name": "get_company_details",
        "description": "Get detailed information about a company/organization. Use when user asks about a specific company or startup.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The company or organization name"
                }
            },
            "required": ["company_name"]
        }
    },
    {
        "name": "filter_projects_by_stage",
        "description": "Find projects at a specific stage (e.g., Seed, Series A, POC, Incubation). Use when user asks 'What projects are in Stage X?' or 'List all Seed stage projects'",
        "parameters": {
            "type": "object",
            "properties": {
                "stage": {
                    "type": "string",
                    "description": "The stage to filter by"
                }
            },
            "required": ["stage"]
        }
    },
    {
        "name": "filter_projects_by_vertical",
        "description": "Find projects in a specific vertical/industry (e.g., AI, CleanTech, HealthTech). Use when user asks about projects in a specific domain.",
        "parameters": {
            "type": "object",
            "properties": {
                "vertical": {
                    "type": "string",
                    "description": "The vertical/industry to filter by"
                }
            },
            "required": ["vertical"]
        }
    },
    {
        "name": "search_by_keyword",
        "description": "Search projects and companies by keyword in their descriptions. Use for broad topic searches.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "The keyword to search for"
                }
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "list_projects",
        "description": "List all projects with optional filters. Use when user wants to see available projects or browse the portfolio.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)",
                    "default": 20
                },
                "vertical": {
                    "type": "string",
                    "description": "Optional vertical filter"
                },
                "is_ongoing": {
                    "type": "boolean",
                    "description": "Filter by ongoing status"
                }
            }
        }
    },
    {
        "name": "compare_companies",
        "description": "Compare multiple companies or projects. Use when user asks to compare competitors or similar startups.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of company names to compare"
                }
            },
            "required": ["company_names"]
        }
    },
    {
        "name": "get_pitchbook_deals",
        "description": "Search PitchBook deal data for market intelligence and competitor analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Optional company name filter"
                },
                "industry": {
                    "type": "string",
                    "description": "Optional industry filter"
                },
                "limit": {
                    "type": "integer",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for current information, general knowledge, market trends, technology explanations, or news. Use this when the question requires up-to-date information not available in internal data, or when asked about general topics. DO NOT use for questions about specific internal projects or companies - use internal tools instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific and use relevant keywords."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default 5, max 10)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
]


class RAGTools:
    """Collection of RAG tools for the LLM agent."""

    def __init__(self, embedding_client=None, llm_client=None):
        """
        Initialize RAG tools.

        Args:
            embedding_client: Optional embedding client for semantic search
            llm_client: Optional LLM client for reranking
        """
        self.embedding_client = embedding_client
        self.llm_client = llm_client

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            ToolResult with content and optional artifacts
        """
        tool_map = {
            "get_cycle_startup_count": self.get_cycle_startup_count,
            "get_cycle_startups": self.get_cycle_startups,
            "get_project_counts": self.get_project_counts,
            "get_contract_metrics": self.get_contract_metrics,
            "get_startup_counts": self.get_startup_counts,
            "get_pitchbook_counts": self.get_pitchbook_counts,
            "get_monday_counts": self.get_monday_counts,
            "get_file_counts": self.get_file_counts,
            "atlas_retrieve": self.atlas_retrieve,
            "summarize_document": self.summarize_document,
            "semantic_search": self.semantic_search,
            "get_project_details": self.get_project_details,
            "get_company_details": self.get_company_details,
            "filter_projects_by_stage": self.filter_projects_by_stage,
            "filter_projects_by_vertical": self.filter_projects_by_vertical,
            "search_by_keyword": self.search_by_keyword,
            "list_projects": self.list_projects,
            "compare_companies": self.compare_companies,
            "get_pitchbook_deals": self.get_pitchbook_deals,
            "web_search": self.web_search,
        }

        tool_fn = tool_map.get(tool_name)
        if not tool_fn:
            return ToolResult(content=f"Unknown tool: {tool_name}")

        try:
            return tool_fn(**arguments)
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return ToolResult(content=f"Error executing {tool_name}: {str(e)}")

    def _cycle_id_from_args(
        self,
        cycle_id: Optional[str] = None,
        cycle_number: Optional[int] = None,
    ) -> Optional[str]:
        if cycle_id:
            normalized = str(cycle_id).strip().lower().replace(" ", "_")
            if normalized.isdigit():
                return f"gced_cycle{normalized}"
            if normalized.startswith("cycle"):
                digits = "".join(ch for ch in normalized if ch.isdigit())
                return f"gced_cycle{digits}" if digits else normalized
            return normalized
        if cycle_number is not None:
            return f"gced_cycle{int(cycle_number)}"
        return None

    def _cycle_number_from_id(self, cycle_id: Optional[str]) -> Optional[int]:
        if not cycle_id:
            return None
        digits = "".join(ch for ch in str(cycle_id) if ch.isdigit())
        return int(digits) if digits else None

    def _cycle_board_candidates(
        self,
        *,
        cycle_id: Optional[str] = None,
        cycle_number: Optional[int] = None,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        resolved_cycle_id = self._cycle_id_from_args(cycle_id, cycle_number)
        cycle_num = cycle_number or self._cycle_number_from_id(resolved_cycle_id)
        candidates: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def add(board_id: Optional[str], source: str, priority: int) -> None:
            board_id = str(board_id or "").strip().strip('"')
            if not board_id or board_id in seen:
                return
            seen.add(board_id)
            candidates.append({"board_id": board_id, "source": source, "priority": priority})

        if cycle_num:
            if year:
                suffix = str(int(year))[-2:]
                env_name = f"MONDAY_BOARD_GCED_MFTF{suffix}_CYCLE{cycle_num}_ID"
                add(os.getenv(env_name), env_name, 100)
            else:
                for suffix in ("25", "26"):
                    env_name = f"MONDAY_BOARD_GCED_MFTF{suffix}_CYCLE{cycle_num}_ID"
                    add(os.getenv(env_name), env_name, 100)

        if cycle_num and year:
            try:
                from board_config_db import get_all_boards
                for board in get_all_boards():
                    label = (board.get("label") or "").lower()
                    key = (board.get("board_key") or "").lower()
                    env_var = (board.get("env_var_name") or "").lower()
                    if "precap" in key or "precap" in env_var or "pre-cap" in label:
                        continue
                    if "gced_mftf" not in key and "monday_board_gced" not in env_var:
                        continue
                    if year:
                        suffix = str(int(year))[-2:]
                        if f"mftf{suffix}" not in key and f"mftf{suffix}" not in env_var:
                            continue
                    if (
                        f"cycle {cycle_num}" in label
                        or f"cycle{cycle_num}" in key
                        or f"cycle{cycle_num}" in env_var
                    ):
                        add(board.get("board_id"), f"board_config:{board.get('board_key')}", 90)
            except Exception:
                pass

        if resolved_cycle_id:
            try:
                from cycles.queries import board_id_for_cycle
                add(board_id_for_cycle(resolved_cycle_id), f"legacy:{resolved_cycle_id}", 50)
            except Exception:
                pass

        candidates.sort(key=lambda item: item["priority"], reverse=True)
        return candidates

    def _count_startups_for_board(self, board_id: str) -> int:
        row = fetch_one(
            """
            SELECT COUNT(*)::int AS count
            FROM master_dashboard.gced_mftf25_startups
            WHERE monday_board_id = %s
            """,
            (board_id,),
        )
        return int((row or {}).get("count") or 0)

    def _resolve_cycle_board_for_startups(
        self,
        *,
        cycle_id: Optional[str] = None,
        cycle_number: Optional[int] = None,
        year: Optional[int] = None,
    ) -> tuple[Optional[str], Optional[str], Optional[str], int, List[Dict[str, Any]]]:
        resolved_cycle_id = self._cycle_id_from_args(cycle_id, cycle_number)
        candidates = self._cycle_board_candidates(
            cycle_id=resolved_cycle_id,
            cycle_number=cycle_number,
            year=year,
        )
        scored = []
        for candidate in candidates:
            count = self._count_startups_for_board(candidate["board_id"])
            scored.append({**candidate, "count": count})

        if not scored:
            return resolved_cycle_id, None, None, 0, []

        # Prefer boards with data. If all candidates are empty, keep the
        # highest-priority configured board so the artifact is debuggable.
        selected = max(scored, key=lambda item: (item["count"] > 0, item["priority"], item["count"]))
        return resolved_cycle_id, selected["board_id"], selected["source"], selected["count"], scored

    def _fetch_cycle_startups(
        self,
        *,
        board_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                id,
                source,
                monday_board_id,
                monday_item_id,
                monday_item_name,
                startup_name,
                hubspot_link,
                switchpitch_link,
                startup_source,
                track,
                startup_type,
                venture,
                gced_scrub_label,
                team_decision,
                pitch_deck_rec,
                sosa_status,
                average_score,
                due_date,
                last_updated_at,
                pre_cap_notes,
                people_label,
                team_label,
                created_at,
                updated_at,
                overall_startup_strength,
                collaboration_potential
            FROM master_dashboard.gced_mftf25_startups
            WHERE monday_board_id = %s
            ORDER BY startup_name NULLS LAST, monday_item_name NULLS LAST
        """
        params: List[Any] = [board_id]
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        return list(fetch_all(sql, tuple(params)))

    def _structured_metadata(
        self,
        *,
        artifact_count: int,
        direct_response: str,
        status: str = "grounded",
    ) -> Dict[str, Any]:
        return {
            "retrieval_attempted": True,
            "retrieval_artifact_count": artifact_count,
            "max_score": 1.0 if artifact_count else None,
            "grounding_status": status,
            "answer_source": "atlas_structured" if artifact_count else "none",
            "confidence": "high" if artifact_count else "low",
            "direct_response": direct_response,
        }

    def _structured_result(
        self,
        *,
        title: str,
        rows: List[Dict[str, Any]],
        artifact: Dict[str, Any],
        empty_message: str,
    ) -> ToolResult:
        if not rows:
            return ToolResult(
                content=empty_message,
                artifacts=[],
                metadata=self._structured_metadata(
                    artifact_count=0,
                    direct_response=empty_message,
                    status="empty",
                ),
            )

        lines = [title]
        for row in rows:
            label = row.get("label")
            if label is None:
                label = row.get("group_value")
            if label is None:
                label = "All"
            count = row.get("count") or row.get("total") or 0
            amount = row.get("total_amount")
            if amount is not None:
                lines.append(f"- {label}: {count} records, total amount {amount}")
            else:
                lines.append(f"- {label}: {count}")

        response = "\n".join(lines)
        artifact["rows"] = rows
        return ToolResult(
            content=response,
            artifacts=[artifact],
            metadata=self._structured_metadata(artifact_count=1, direct_response=response),
        )

    def _add_ilike_filter(
        self,
        clauses: List[str],
        params: List[Any],
        column_sql: str,
        value: Optional[str],
    ) -> None:
        if value:
            clauses.append(f"{column_sql} ILIKE %s")
            params.append(f"%{value}%")

    def get_cycle_startup_count(
        self,
        cycle_id: Optional[str] = None,
        cycle_number: Optional[int] = None,
        year: Optional[int] = None,
    ) -> ToolResult:
        resolved_cycle_id = self._cycle_id_from_args(cycle_id, cycle_number)
        if not resolved_cycle_id:
            response = "No GCED cycle was specified, so I could not query the structured Atlas cycle data."
            return ToolResult(
                content=response,
                artifacts=[],
                metadata=self._structured_metadata(artifact_count=0, direct_response=response, status="empty"),
            )

        resolved_cycle_id, board_id, board_source, total, candidates = self._resolve_cycle_board_for_startups(
            cycle_id=resolved_cycle_id,
            year=year,
        )
        if not board_id:
            response = (
                f"No configured Atlas board mapping was found for {resolved_cycle_id}"
                + (f" in {year}" if year else "")
                + ", "
                "so I cannot provide an authoritative startup count from structured data."
            )
            return ToolResult(
                content=response,
                artifacts=[],
                metadata=self._structured_metadata(artifact_count=0, direct_response=response, status="empty"),
            )

        sample_startups = self._fetch_cycle_startups(board_id=board_id, limit=10)
        cycle_label = resolved_cycle_id.replace("gced_cycle", "Cycle ")
        year_part = f" in {year}" if year else ""
        response = f"{cycle_label}{year_part} had {total} startups in the structured Atlas database."
        artifact = {
            "source_type": "cycle_summary",
            "cycle_id": resolved_cycle_id,
            "cycle_number": int(resolved_cycle_id.replace("gced_cycle", "")),
            "year": year,
            "board_id": board_id,
            "board_source": board_source,
            "candidate_boards": candidates,
            "total_startups": total,
            "sample_startups": sample_startups,
        }
        return ToolResult(
            content=response,
            artifacts=[artifact],
            metadata=self._structured_metadata(artifact_count=1, direct_response=response),
        )

    def get_cycle_startups(
        self,
        cycle_id: Optional[str] = None,
        cycle_number: Optional[int] = None,
        year: Optional[int] = None,
        limit: int = 25,
    ) -> ToolResult:
        resolved_cycle_id = self._cycle_id_from_args(cycle_id, cycle_number)
        if not resolved_cycle_id:
            response = "No GCED cycle was specified, so I could not query the structured Atlas cycle data."
            return ToolResult(
                content=response,
                artifacts=[],
                metadata=self._structured_metadata(artifact_count=0, direct_response=response, status="empty"),
            )

        resolved_cycle_id, board_id, board_source, total, candidates = self._resolve_cycle_board_for_startups(
            cycle_id=resolved_cycle_id,
            year=year,
        )
        if not board_id:
            response = (
                f"No configured Atlas board mapping was found for {resolved_cycle_id}"
                + (f" in {year}" if year else "")
                + ", "
                "so I cannot list startups from structured data."
            )
            return ToolResult(
                content=response,
                artifacts=[],
                metadata=self._structured_metadata(artifact_count=0, direct_response=response, status="empty"),
            )

        limit = max(1, min(int(limit or 25), 100))
        startups = self._fetch_cycle_startups(board_id=board_id, limit=limit)
        cycle_label = resolved_cycle_id.replace("gced_cycle", "Cycle ")
        year_part = f" in {year}" if year else ""
        listed = startups[:limit]
        names = "\n".join(
            f"- {s.get('startup_name') or s.get('monday_item_name') or 'Unknown'}"
            + (f" ({s.get('track')})" if s.get("track") else "")
            + (f" - {s.get('team_decision')}" if s.get("team_decision") else "")
            for s in listed
        )
        response = f"{cycle_label}{year_part} had {total} startups in the structured Atlas database."
        if names:
            response += f"\n\n{names}"
        artifact = {
            "source_type": "cycle_startups",
            "cycle_id": resolved_cycle_id,
            "cycle_number": int(resolved_cycle_id.replace("gced_cycle", "")),
            "year": year,
            "board_id": board_id,
            "board_source": board_source,
            "candidate_boards": candidates,
            "total_startups": total,
            "startups": listed,
        }
        return ToolResult(
            content=response,
            artifacts=[artifact],
            metadata=self._structured_metadata(artifact_count=1, direct_response=response),
        )

    def get_project_counts(
        self,
        group_by: Optional[str] = None,
        stage: Optional[str] = None,
        vertical: Optional[str] = None,
        owner: Optional[str] = None,
        status: Optional[str] = None,
        is_ongoing: Optional[bool] = None,
    ) -> ToolResult:
        group_map = {
            "stage": "COALESCE(p.stage_name, 'Unknown')",
            "vertical": "COALESCE(v.vertical_name, 'Unknown')",
            "owner": "COALESCE(pe.full_name, 'Unknown')",
            "status": "COALESCE(p.status_category, 'Unknown')",
        }
        group_expr = group_map.get(group_by or "")
        select_group = f"{group_expr} AS label," if group_expr else "'All projects' AS label,"
        sql = f"""
            SELECT {select_group} COUNT(DISTINCT p.id)::int AS count
            FROM master_dashboard.projects p
            LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
            LEFT JOIN master_dashboard.project_owners po ON po.project_id = p.id
            LEFT JOIN master_dashboard.people pe ON pe.id = COALESCE(po.person_id, p.owner_id)
            WHERE 1=1
        """
        clauses: List[str] = []
        params: List[Any] = []
        self._add_ilike_filter(clauses, params, "p.stage_name", stage)
        self._add_ilike_filter(clauses, params, "v.vertical_name", vertical)
        self._add_ilike_filter(clauses, params, "pe.full_name", owner)
        self._add_ilike_filter(clauses, params, "p.status_category", status)
        if is_ongoing is not None:
            clauses.append("p.is_ongoing = %s")
            params.append(is_ongoing)
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        if group_expr:
            sql += " GROUP BY label ORDER BY count DESC, label"
        rows = fetch_all(sql, tuple(params))
        return self._structured_result(
            title="Structured Atlas project counts:",
            rows=list(rows),
            artifact={"source_type": "project_counts", "group_by": group_by, "filters": {
                "stage": stage, "vertical": vertical, "owner": owner, "status": status, "is_ongoing": is_ongoing,
            }},
            empty_message="No projects matched those structured Atlas filters.",
        )

    def get_contract_metrics(
        self,
        group_by: Optional[str] = None,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        owner: Optional[str] = None,
        team: Optional[str] = None,
        category: Optional[str] = None,
    ) -> ToolResult:
        group_map = {
            "status": "COALESCE(cs.status_label, 'Unknown')",
            "stage": "COALESCE(cs.stage, 'Unknown')",
            "owner": "COALESCE(cs.owner, 'Unknown')",
            "team": "COALESCE(cs.team, 'Unknown')",
            "category": "COALESCE(cs.category, 'Unknown')",
        }
        group_expr = group_map.get(group_by or "")
        select_group = f"{group_expr} AS label," if group_expr else "'All contracts' AS label,"
        sql = f"""
            SELECT
                {select_group}
                COUNT(DISTINCT cs.id)::int AS count,
                COALESCE(SUM(cs.contract_amount), 0)::numeric AS total_amount
            FROM master_dashboard.contract_status cs
            WHERE 1=1
        """
        clauses: List[str] = []
        params: List[Any] = []
        self._add_ilike_filter(clauses, params, "cs.status_label", status)
        self._add_ilike_filter(clauses, params, "cs.stage", stage)
        self._add_ilike_filter(clauses, params, "cs.owner", owner)
        self._add_ilike_filter(clauses, params, "cs.team", team)
        self._add_ilike_filter(clauses, params, "cs.category", category)
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        if group_expr:
            sql += " GROUP BY label ORDER BY count DESC, label"
        rows = fetch_all(sql, tuple(params))
        return self._structured_result(
            title="Structured Atlas contract metrics:",
            rows=list(rows),
            artifact={"source_type": "contract_metrics", "group_by": group_by, "filters": {
                "status": status, "stage": stage, "owner": owner, "team": team, "category": category,
            }},
            empty_message="No contracts matched those structured Atlas filters.",
        )

    def get_startup_counts(
        self,
        cycle_id: Optional[str] = None,
        cycle_number: Optional[int] = None,
        group_by: Optional[str] = None,
        vertical: Optional[str] = None,
        decision: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        year: Optional[int] = None,
    ) -> ToolResult:
        resolved_cycle_id = self._cycle_id_from_args(cycle_id, cycle_number)
        board_id = None
        if resolved_cycle_id:
            resolved_cycle_id, board_id, board_source, _total, candidates = self._resolve_cycle_board_for_startups(
                cycle_id=resolved_cycle_id,
                cycle_number=cycle_number,
                year=year,
            )
            if not board_id:
                response = (
                    f"No configured Atlas board mapping was found for {resolved_cycle_id}"
                    + (f" in {year}" if year else "")
                    + "."
                )
                return ToolResult(
                    content=response,
                    artifacts=[],
                    metadata=self._structured_metadata(artifact_count=0, direct_response=response, status="empty"),
                )

        group_map = {
            "cycle": "COALESCE(g.monday_board_id, 'Unknown')",
            "vertical": "COALESCE(g.track, 'Unknown')",
            "decision": "COALESCE(g.team_decision, 'Unknown')",
            "status": "COALESCE(g.sosa_status, 'Unknown')",
            "source": "COALESCE(g.startup_source, 'Unknown')",
        }
        group_expr = group_map.get(group_by or "")
        select_group = f"{group_expr} AS label," if group_expr else "'All startups' AS label,"
        sql = f"""
            SELECT {select_group} COUNT(DISTINCT g.id)::int AS count
            FROM master_dashboard.gced_mftf25_startups g
            WHERE 1=1
        """
        clauses: List[str] = []
        params: List[Any] = []
        if board_id:
            clauses.append("g.monday_board_id = %s")
            params.append(board_id)
        self._add_ilike_filter(clauses, params, "g.track", vertical)
        self._add_ilike_filter(clauses, params, "g.team_decision", decision)
        self._add_ilike_filter(clauses, params, "g.sosa_status", status)
        self._add_ilike_filter(clauses, params, "g.startup_source", source)
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        if group_expr:
            sql += " GROUP BY label ORDER BY count DESC, label"
        rows = fetch_all(sql, tuple(params))
        return self._structured_result(
            title="Structured Atlas startup counts:",
            rows=list(rows),
            artifact={
                "source_type": "startup_counts",
                "cycle_id": resolved_cycle_id,
                "year": year,
                "board_id": board_id,
                "board_source": board_source if resolved_cycle_id else None,
                "candidate_boards": candidates if resolved_cycle_id else None,
                "group_by": group_by,
            },
            empty_message="No startups matched those structured Atlas filters.",
        )

    def get_pitchbook_counts(
        self,
        entity: str = "company",
        group_by: Optional[str] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        deal_type: Optional[str] = None,
        company_name: Optional[str] = None,
        year: Optional[int] = None,
    ) -> ToolResult:
        entity = (entity or "company").lower()
        if entity == "deal":
            group_map = {
                "industry": "COALESCE(primary_industry_sector, 'Unknown')",
                "country": "COALESCE(company_country_region, 'Unknown')",
                "region": "COALESCE(hq_global_region, 'Unknown')",
                "deal_type": "COALESCE(deal_type, 'Unknown')",
                "year": "COALESCE(EXTRACT(YEAR FROM deal_date)::text, 'Unknown')",
                "vertical": "COALESCE(verticals, 'Unknown')",
            }
            group_expr = group_map.get(group_by or "")
            select_group = f"{group_expr} AS label," if group_expr else "'All PitchBook deals' AS label,"
            sql = f"SELECT {select_group} COUNT(DISTINCT deal_id)::int AS count FROM dp.pitchbook_deals WHERE 1=1"
            clauses: List[str] = []
            params: List[Any] = []
            self._add_ilike_filter(clauses, params, "primary_industry_sector", industry)
            self._add_ilike_filter(clauses, params, "company_country_region", country)
            self._add_ilike_filter(clauses, params, "hq_global_region", region)
            self._add_ilike_filter(clauses, params, "deal_type", deal_type)
            self._add_ilike_filter(clauses, params, "startups", company_name)
            if year:
                clauses.append("EXTRACT(YEAR FROM deal_date) = %s")
                params.append(year)
        else:
            group_map = {
                "industry": "COALESCE(primary_industry_sector, 'Unknown')",
                "country": "COALESCE(hq_country_region, 'Unknown')",
                "region": "COALESCE(hq_global_region, 'Unknown')",
                "year": "COALESCE(year_founded::text, 'Unknown')",
                "vertical": "COALESCE(verticals, 'Unknown')",
            }
            group_expr = group_map.get(group_by or "")
            select_group = f"{group_expr} AS label," if group_expr else "'All PitchBook companies' AS label,"
            sql = f"SELECT {select_group} COUNT(DISTINCT company_id)::int AS count FROM dp.pitchbook_companies WHERE 1=1"
            clauses = []
            params = []
            self._add_ilike_filter(clauses, params, "primary_industry_sector", industry)
            self._add_ilike_filter(clauses, params, "hq_country_region", country)
            self._add_ilike_filter(clauses, params, "hq_global_region", region)
            self._add_ilike_filter(clauses, params, "company_name", company_name)
            if year:
                clauses.append("year_founded = %s")
                params.append(year)
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        if group_expr:
            sql += " GROUP BY label ORDER BY count DESC, label"
        rows = fetch_all(sql, tuple(params))
        return self._structured_result(
            title=f"Structured PitchBook {entity} counts:",
            rows=list(rows),
            artifact={"source_type": f"pitchbook_{entity}_counts", "entity": entity, "group_by": group_by},
            empty_message=f"No PitchBook {entity} records matched those filters.",
        )

    def get_monday_counts(
        self,
        entity: str = "item",
        board_id: Optional[str] = None,
        board_name: Optional[str] = None,
        active_only: Optional[bool] = None,
        group_by: Optional[str] = None,
    ) -> ToolResult:
        entity = (entity or "item").lower()
        if entity == "board":
            rows = fetch_all("SELECT 'All Monday boards' AS label, COUNT(*)::int AS count FROM monday.boards", ())
            return self._structured_result(
                title="Structured Monday board counts:",
                rows=list(rows),
                artifact={"source_type": "monday_board_counts"},
                empty_message="No Monday boards were found.",
            )

        group_expr = "COALESCE(b.name, i.board_id, 'Unknown')" if group_by == "board" else "'All Monday items'"
        sql = f"""
            SELECT {group_expr} AS label, COUNT(DISTINCT i.monday_id)::int AS count
            FROM monday.items i
            LEFT JOIN monday.boards b ON b.monday_board_id = i.board_id
            WHERE 1=1
        """
        clauses: List[str] = []
        params: List[Any] = []
        if board_id:
            clauses.append("i.board_id = %s")
            params.append(board_id)
        self._add_ilike_filter(clauses, params, "b.name", board_name)
        if active_only is not None:
            clauses.append("i.is_active = %s")
            params.append(active_only)
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        if group_by == "board":
            sql += " GROUP BY label ORDER BY count DESC, label"
        rows = fetch_all(sql, tuple(params))
        return self._structured_result(
            title="Structured Monday item counts:",
            rows=list(rows),
            artifact={"source_type": "monday_item_counts", "group_by": group_by, "board_id": board_id, "board_name": board_name},
            empty_message="No Monday items matched those filters.",
        )

    def get_file_counts(
        self,
        board_id: Optional[str] = None,
        board_name: Optional[str] = None,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        file_type: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> ToolResult:
        group_map = {
            "board": "COALESCE(b.name, f.board_id, 'Unknown')",
            "category": "COALESCE(f.category, 'Unknown')",
            "owner": "COALESCE(f.owner_name, 'Unknown')",
            "type": "COALESCE(LOWER(NULLIF(split_part(f.file_name, '.', array_length(string_to_array(f.file_name, '.'), 1)), '')), 'unknown')",
        }
        group_expr = group_map.get(group_by or "")
        select_group = f"{group_expr} AS label," if group_expr else "'All files' AS label,"
        sql = f"""
            SELECT {select_group} COUNT(DISTINCT f.monday_file_id)::int AS count
            FROM monday.files f
            LEFT JOIN monday.boards b ON b.monday_board_id = f.board_id
            WHERE 1=1
        """
        clauses: List[str] = []
        params: List[Any] = []
        if board_id:
            clauses.append("f.board_id = %s")
            params.append(board_id)
        self._add_ilike_filter(clauses, params, "b.name", board_name)
        self._add_ilike_filter(clauses, params, "f.category", category)
        self._add_ilike_filter(clauses, params, "f.owner_name", owner)
        if file_type:
            clauses.append("LOWER(f.file_name) LIKE %s")
            params.append(f"%.{file_type.lower().lstrip('.')}")
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        if group_expr:
            sql += " GROUP BY label ORDER BY count DESC, label"
        rows = fetch_all(sql, tuple(params))
        return self._structured_result(
            title="Structured Atlas file counts:",
            rows=list(rows),
            artifact={"source_type": "file_counts", "group_by": group_by, "filters": {
                "board_id": board_id, "board_name": board_name, "category": category, "owner": owner, "file_type": file_type,
            }},
            empty_message="No files matched those structured Atlas filters.",
        )

    def _semantic_search_rows(
        self,
        *,
        query: str,
        source_type: Optional[str],
        source_types: Optional[List[str]] = None,
        limit: int = 5,
        similarity_threshold: float | None = 0.6,
        file_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_client.embed(query)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        sql = """
            SELECT
                dc.id,
                dc.document_id,
                d.source_type,
                d.source_id,
                d.file_name,
                d.spaces_key,
                d.file_type,
                d.category,
                d.owner,
                d.created_at,
                dc.chunk_text,
                dc.page_number,
                dc.section_title,
                dc.metadata,
                1 - (dc.embedding <=> %s::vector) AS similarity
            FROM llm.document_chunks dc
            JOIN llm.documents d ON d.id = dc.document_id
            WHERE dc.embedding IS NOT NULL
        """
        params: List[Any] = [embedding_str]

        if source_type:
            sql += " AND d.source_type = %s"
            params.append(source_type)

        if source_types:
            sql += " AND d.source_type = ANY(%s)"
            params.append(source_types)

        if file_type:
            sql += " AND d.file_type = %s"
            params.append(file_type.lower())

        sql += " ORDER BY dc.embedding <=> %s::vector LIMIT %s"
        params.extend([embedding_str, limit])

        rows = fetch_all(sql, tuple(params))
        if similarity_threshold is None:
            return list(rows)
        return [r for r in rows if r["similarity"] >= similarity_threshold]

    def _keyword_search_file_rows(
        self,
        *,
        query: str,
        source_type: Optional[str],
        source_types: Optional[List[str]] = None,
        limit: int = 5,
        file_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Keyword search for file-like documents.

        Uses Postgres FTS on chunk_text and boosts exact-ish filename matches
        via ILIKE + trigram similarity when available.
        """
        pattern = f"%{query}%"

        # 1) Filename matches (fast with trigram index)
        sql_file_name = """
            SELECT
                dc.id,
                dc.document_id,
                d.source_type,
                d.source_id,
                d.file_name,
                d.spaces_key,
                d.file_type,
                d.category,
                d.owner,
                d.created_at,
                dc.chunk_text,
                dc.page_number,
                dc.section_title,
                dc.metadata,
                similarity(COALESCE(d.file_name, ''), %s) AS keyword_score,
                'file_name' AS keyword_match_type
            FROM llm.documents d
            JOIN llm.document_chunks dc ON dc.document_id = d.id
            WHERE COALESCE(d.file_name, '') ILIKE %s
        """
        params_file_name: List[Any] = [query, pattern]
        if source_type:
            sql_file_name += " AND d.source_type = %s"
            params_file_name.append(source_type)
        if source_types:
            sql_file_name += " AND d.source_type = ANY(%s)"
            params_file_name.append(source_types)
        if file_type:
            sql_file_name += " AND LOWER(d.file_type) = %s"
            params_file_name.append(file_type.lower())
        sql_file_name += """
            ORDER BY keyword_score DESC NULLS LAST, dc.page_number NULLS FIRST
            LIMIT %s
        """
        params_file_name.append(max(1, limit // 2))

        # 2) Full-text matches in chunk_text
        # Build an OR-based tsquery so chunks that match any query term are found,
        # not just those containing every term. This is critical for table chunks
        # (e.g. a Metro City Rates table has "rate" and "city" but not "hotel" or
        # "business"), where AND semantics would return zero rows.
        _fts_terms = [w.strip(".,!?;:'\"()") for w in query.split() if len(w.strip(".,!?;:'\"()")) > 2]
        _or_query = " OR ".join(_fts_terms[:15]) if _fts_terms else query

        sql_fts = """
            SELECT
                dc.id,
                dc.document_id,
                d.source_type,
                d.source_id,
                d.file_name,
                d.spaces_key,
                d.file_type,
                d.category,
                d.owner,
                d.created_at,
                ts_headline(
                    'english',
                    dc.chunk_text,
                    websearch_to_tsquery('english', %s),
                    'StartSel=<em>,StopSel=</em>,MaxFragments=2,MaxWords=30,MinWords=10,FragmentDelimiter= … '
                ) AS chunk_text,
                dc.page_number,
                dc.section_title,
                dc.metadata,
                ts_rank_cd(
                    to_tsvector('english', COALESCE(dc.chunk_text, '')),
                    websearch_to_tsquery('english', %s)
                ) AS keyword_score,
                'chunk_fts' AS keyword_match_type
            FROM llm.document_chunks dc
            JOIN llm.documents d ON d.id = dc.document_id
            WHERE
                to_tsvector('english', COALESCE(dc.chunk_text, '')) @@ websearch_to_tsquery('english', %s)
        """
        params_fts: List[Any] = [_or_query, _or_query, _or_query]
        if source_type:
            sql_fts += " AND d.source_type = %s"
            params_fts.append(source_type)
        if source_types:
            sql_fts += " AND d.source_type = ANY(%s)"
            params_fts.append(source_types)
        if file_type:
            sql_fts += " AND LOWER(d.file_type) = %s"
            params_fts.append(file_type.lower())
        sql_fts += " ORDER BY keyword_score DESC NULLS LAST LIMIT %s"
        params_fts.append(max(1, limit))

        try:
            rows_file_name = fetch_all(sql_file_name, tuple(params_file_name))
        except Exception:
            # If pg_trgm isn't installed in a given environment, fallback gracefully.
            rows_file_name = fetch_all(
                sql_file_name.replace("similarity(COALESCE(d.file_name, ''), %s)", "0.0").replace(
                    "ORDER BY keyword_score DESC NULLS LAST,",
                    "ORDER BY",
                ),
                tuple(params_file_name),
            )

        rows_fts = fetch_all(sql_fts, tuple(params_fts))
        return list(rows_file_name) + list(rows_fts)

    def _rrf_fuse(
        self,
        *,
        query: str,
        semantic_rows: List[Dict[str, Any]],
        keyword_rows: List[Dict[str, Any]],
        limit: int,
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal rank fusion (RRF) at the document level.

        Dedupes by document_id and keeps the best chunk as the representative snippet.
        """
        matched_rows: Dict[str, List[Dict[str, Any]]] = {}

        def _add_score(
            scores: Dict[str, float],
            best_row: Dict[str, Dict[str, Any]],
            *,
            rows: List[Dict[str, Any]],
            weight: float,
        ):
            for rank, row in enumerate(rows, start=1):
                doc_id = str(row.get("document_id"))
                matched_rows.setdefault(doc_id, []).append(row)
                scores[doc_id] = scores.get(doc_id, 0.0) + weight * (1.0 / (k + rank))
                # pick best representative row per doc by max score contribution, break ties by presence of page/snippet
                prev = best_row.get(doc_id)
                if prev is None:
                    best_row[doc_id] = row
                else:
                    prev_page = prev.get("page_number")
                    row_page = row.get("page_number")
                    if (prev_page is None and row_page is not None) or (len(str(row.get("chunk_text") or "")) > len(str(prev.get("chunk_text") or ""))):
                        best_row[doc_id] = row

        scores: Dict[str, float] = {}
        best_row: Dict[str, Dict[str, Any]] = {}
        _add_score(scores, best_row, rows=semantic_rows, weight=1.0)
        _add_score(scores, best_row, rows=keyword_rows, weight=1.0)

        # Build fused results
        fused = []
        for doc_id, score in scores.items():
            row = dict(best_row[doc_id])
            unique_chunks = {str(r.get("id")) for r in matched_rows.get(doc_id, []) if r.get("id") is not None}
            spread_boost = min(0.05, max(0, len(unique_chunks) - 1) * 0.01)
            metadata_boost, rank_reason = _filename_rank_boost(query, row)
            document_score = score + spread_boost + metadata_boost
            row["fusion_score"] = round(score, 6)
            row["document_score"] = round(document_score, 6)
            row["matched_chunk_count"] = len(unique_chunks) or len(matched_rows.get(doc_id, [])) or 1
            row["rank_reason"] = rank_reason
            fused.append(row)

        fused.sort(key=lambda r: r.get("document_score", r.get("fusion_score", 0.0)), reverse=True)
        return fused[:limit]

    def _llm_rerank(
        self,
        *,
        query: str,
        rows: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        if not self.llm_client or not rows:
            return rows

        candidates = rows[:top_n]
        payload = [
            {
                "id": str(r.get("id")),
                "document_id": str(r.get("document_id")),
                "file_name": r.get("file_name"),
                "page": r.get("page_number"),
                "snippet": (r.get("chunk_text") or "")[:800],
            }
            for r in candidates
        ]

        system = (
            "You are a reranking model. "
            "Given a user query and candidate document snippets, reorder candidates by relevance. "
            "Return ONLY valid JSON with this schema: {\"ordered_ids\": [\"<id>\", ...]} "
            "Use only the provided candidate ids; do not invent ids."
        )
        user = f"Query: {query}\n\nCandidates JSON:\n{json.dumps(payload, ensure_ascii=False)}"

        resp = self.llm_client.invoke(
            messages=[{"role": "user", "content": user}],
            system=system,
            temperature=0.0,
            max_tokens=800,
        )

        ordered: List[str] = []
        try:
            data = json.loads(resp.get("content", "") or "{}")
            ordered = [str(x) for x in data.get("ordered_ids", []) if x]
        except Exception:
            return rows

        by_id = {str(r.get("id")): r for r in candidates}
        reranked = [by_id[i] for i in ordered if i in by_id]
        # Append anything the model omitted, preserving previous order
        seen = set(ordered)
        reranked.extend([r for r in candidates if str(r.get("id")) not in seen])
        reranked.extend(rows[len(candidates):])
        return reranked

    def _normalize_artifact(self, row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        file_name = row.get("file_name") or metadata.get("file_name")
        file_type = row.get("file_type") or metadata.get("file_type")
        spaces_key = row.get("spaces_key") or metadata.get("spaces_key")
        created_at = row.get("created_at")
        upload_date = created_at.date().isoformat() if created_at is not None else metadata.get("upload_date")
        similarity = row.get("similarity")
        score_base = (
            row.get("document_score")
            or row.get("fusion_score")
            or row.get("keyword_score")
            or similarity
        )

        artifact = {
            "id": str(row.get("id")) if row.get("id") is not None else None,
            "document_id": str(row.get("document_id")) if row.get("document_id") is not None else None,
            "source_type": row.get("source_type"),
            "source_id": str(row.get("source_id")) if row.get("source_id") is not None else None,
            "file_name": file_name,
            "file_type": file_type,
            "spaces_key": spaces_key,
            "upload_date": upload_date,
            "category": row.get("category") or metadata.get("category"),
            "owner": row.get("owner") or metadata.get("owner") or metadata.get("owner_name"),
            "chunk_text": row.get("chunk_text"),
            "snippet": row.get("chunk_text"),
            "page_number": row.get("page_number"),
            "page": row.get("page_number"),
            "section_title": row.get("section_title"),
            "metadata": metadata,
            "similarity": round(float(score_base), 3) if score_base is not None else None,
            "keyword_score": float(row.get("keyword_score")) if row.get("keyword_score") is not None else None,
            "fusion_score": row.get("fusion_score"),
            "document_score": row.get("document_score"),
            "matched_chunk_count": row.get("matched_chunk_count"),
            "rank_reason": row.get("rank_reason"),
            "created_at": created_at,
        }
        return artifact

    def _normalize_and_rank(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = [self._normalize_artifact(row) for row in rows]
        results = rerank_with_metadata(results)
        for result in results:
            result.pop("created_at", None)
            if result.get("score") is None:
                result["score"] = result.get("fusion_score") or result.get("similarity")
        return results

    def _retrieval_metadata(self, results: List[Dict[str, Any]], *, status: str | None = None) -> Dict[str, Any]:
        scores = [
            float(score)
            for result in results
            for score in [result.get("score") or result.get("similarity") or result.get("fusion_score")]
            if score is not None
        ]
        artifact_count = len(results)
        max_score = max(scores) if scores else None
        return {
            "retrieval_attempted": True,
            "retrieval_artifact_count": artifact_count,
            "max_score": round(max_score, 4) if max_score is not None else None,
            "grounding_status": status or ("grounded" if artifact_count else "empty"),
        }

    def _format_retrieval_content(self, results: List[Dict[str, Any]]) -> str:
        formatted_results = []
        for result in results:
            location_parts = []
            if result.get("page_number") is not None:
                location_parts.append(f"page {result['page_number']}")
            if result.get("section_title"):
                location_parts.append(f"section {result['section_title']}")
            location = f" [{', '.join(location_parts)}]" if location_parts else ""

            meta_parts = [p for p in [
                result.get("source_type"),
                result.get("file_type", "").upper() if result.get("file_type") else None,
                result.get("file_name"),
                result.get("category"),
                f"uploaded {result['upload_date']}" if result.get("upload_date") else None,
                f"owner: {result['owner']}" if result.get("owner") else None,
            ] if p]
            meta_header = " - ".join(meta_parts)
            score = result.get("score") or result.get("fusion_score") or result.get("similarity")
            formatted_results.append(
                f"[{meta_header}] (score: {score}){location}\n{result.get('chunk_text') or ''}"
            )
        return "\n\n".join(formatted_results) or "No results found."

    def retrieve_context(
        self,
        *,
        query: str,
        source_types: Optional[List[str]] = None,
        limit: int = 8,
        mode: str = "auto",
        file_type: Optional[str] = None,
        rerank: bool = False,
    ) -> ToolResult:
        """Shared Atlas retrieval service used by chat and document search."""
        if not self.embedding_client:
            return ToolResult(
                content="Atlas retrieval is unavailable: embedding client not configured.",
                artifacts=[],
                metadata=self._retrieval_metadata([], status="empty"),
            )

        selected_sources = [s for s in (source_types or []) if s]
        selected_sources = [s for s in selected_sources if s in ATLAS_RETRIEVAL_SOURCE_TYPES]
        if source_types and not selected_sources:
            return ToolResult(
                content="No valid Atlas source types requested.",
                artifacts=[],
                metadata=self._retrieval_metadata([], status="empty"),
            )

        limit = max(1, min(int(limit or 8), 100))
        mode = (mode or "auto").lower()
        if mode not in {"auto", "semantic", "hybrid"}:
            mode = "auto"

        use_hybrid = mode == "hybrid" or (
            mode == "auto" and (not selected_sources or any(s in _HYBRID_SOURCE_TYPES for s in selected_sources))
        )

        try:
            if use_hybrid:
                semantic_rows = self._semantic_search_rows(
                    query=query,
                    source_type=None,
                    source_types=selected_sources or None,
                    limit=max(limit, 25),
                    similarity_threshold=None,
                    file_type=file_type,
                )
                keyword_rows = self._keyword_search_file_rows(
                    query=query,
                    source_type=None,
                    source_types=selected_sources or None,
                    limit=max(limit, 25),
                    file_type=file_type,
                )
                rows = self._rrf_fuse(
                    query=query,
                    semantic_rows=semantic_rows,
                    keyword_rows=keyword_rows,
                    limit=limit,
                )
                if rerank:
                    rows = self._llm_rerank(query=query, rows=rows, top_n=min(15, max(limit, 5)))
            else:
                rows = self._semantic_search_rows(
                    query=query,
                    source_type=None,
                    source_types=selected_sources or None,
                    limit=limit,
                    similarity_threshold=0.7,
                    file_type=file_type,
                )

            if not rows:
                return ToolResult(
                    content="No relevant Atlas context found.",
                    artifacts=[],
                    metadata=self._retrieval_metadata([], status="empty"),
                )

            results = self._normalize_and_rank(rows)
            return ToolResult(
                content=self._format_retrieval_content(results),
                artifacts=results,
                metadata=self._retrieval_metadata(results),
            )
        except Exception as e:
            logger.error(f"Atlas retrieval error: {e}")
            return ToolResult(
                content=f"Atlas retrieval encountered an error: {str(e)}",
                artifacts=[],
                metadata=self._retrieval_metadata([], status="empty"),
            )

    def atlas_retrieve(
        self,
        query: str,
        source_types: Optional[List[str]] = None,
        limit: int = 8,
        mode: str = "auto",
        file_type: Optional[str] = None,
    ) -> ToolResult:
        return self.retrieve_context(
            query=query,
            source_types=source_types,
            limit=limit,
            mode=mode,
            file_type=file_type,
            rerank=False,
        )

    def get_document_context(self, document_id: str, max_chunks: Optional[int] = None) -> ToolResult:
        """Fetch normalized chunks for one document in stable reading order."""
        if not document_id:
            return ToolResult(
                content="No document id was provided.",
                artifacts=[],
                metadata=self._retrieval_metadata([], status="empty"),
            )

        sql = """
            SELECT
                dc.id,
                dc.document_id,
                d.source_type,
                d.source_id,
                d.file_name,
                d.spaces_key,
                d.file_type,
                d.category,
                d.owner,
                d.created_at,
                dc.chunk_text,
                dc.page_number,
                dc.section_title,
                dc.metadata,
                1.0 AS document_score
            FROM llm.document_chunks dc
            JOIN llm.documents d ON d.id = dc.document_id
            WHERE dc.document_id = %s
            ORDER BY dc.page_number NULLS LAST, dc.id
        """
        params: List[Any] = [document_id]
        if max_chunks is not None:
            sql += " LIMIT %s"
            params.append(max(1, int(max_chunks)))

        rows = fetch_all(sql, tuple(params))
        results = [self._normalize_artifact(row) for row in rows]
        for result in results:
            result.pop("created_at", None)
            result["score"] = result.get("document_score") or result.get("score") or 1.0

        return ToolResult(
            content=self._format_retrieval_content(results),
            artifacts=results,
            metadata=self._retrieval_metadata(results, status="grounded" if results else "empty"),
        )

    def _document_summary_context(self, chunks: List[Dict[str, Any]], *, max_chars: int) -> str:
        blocks = []
        used = 0
        for chunk in chunks:
            text = (chunk.get("chunk_text") or chunk.get("snippet") or "").strip()
            if not text:
                continue
            source = chunk.get("file_name") or "Unknown file"
            page = chunk.get("page_number") or chunk.get("page") or "unknown"
            section = chunk.get("section_title") or "unknown"
            block = f"Source: {source}\nPage: {page}\nSection: {section}\nText:\n{text}"
            if used + len(block) > max_chars:
                remaining = max_chars - used
                if remaining > 1000:
                    blocks.append(block[:remaining].rstrip())
                break
            blocks.append(block)
            used += len(block)
        return "\n\n---\n\n".join(blocks)

    def _summarize_context_once(
        self,
        *,
        query: str,
        file_name: str,
        context: str,
        alternatives: List[str],
        max_tokens: int = 1400,
    ) -> str:
        if not self.llm_client:
            raise RuntimeError("No LLM client is configured for document summaries")
        alternatives_text = ", ".join(alternatives[:3]) if alternatives else "None"
        prompt = f"""Summarize the selected Atlas document using only the full-document context below.

User request:
{query}

Selected document:
{file_name}

Close alternative matches:
{alternatives_text}

Instructions:
- Summarize the selected document, not the search snippets.
- Cite the selected file name and page numbers when available.
- If close alternatives are listed, mention them briefly after the summary as possible related files.
- Do not say the retrieved context is insufficient when the document context contains policy content.

Document context:
{context}
"""
        response = self.llm_client.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        answer = (response.get("content") or "").strip()
        if not answer:
            raise RuntimeError("LLM returned an empty document summary")
        return answer

    def _summarize_large_document(
        self,
        *,
        query: str,
        file_name: str,
        chunks: List[Dict[str, Any]],
        alternatives: List[str],
    ) -> str:
        groups: List[List[Dict[str, Any]]] = []
        current: List[Dict[str, Any]] = []
        current_chars = 0
        for chunk in chunks:
            text_len = len(chunk.get("chunk_text") or chunk.get("snippet") or "")
            if current and current_chars + text_len > _DOCUMENT_SUMMARY_GROUP_CHARS:
                groups.append(current)
                current = []
                current_chars = 0
            current.append(chunk)
            current_chars += text_len
        if current:
            groups.append(current)

        partials = []
        for index, group in enumerate(groups, start=1):
            context = self._document_summary_context(group, max_chars=_DOCUMENT_SUMMARY_GROUP_CHARS)
            partials.append(
                self._summarize_context_once(
                    query=f"{query}\nSummarize part {index} of {len(groups)}.",
                    file_name=file_name,
                    context=context,
                    alternatives=[],
                    max_tokens=900,
                )
            )

        combined = "\n\n---\n\n".join(
            f"Part {index} summary:\n{summary}"
            for index, summary in enumerate(partials, start=1)
        )
        return self._summarize_context_once(
            query=query,
            file_name=file_name,
            context=combined,
            alternatives=alternatives,
            max_tokens=1400,
        )

    def summarize_document(
        self,
        query: str,
        source_types: Optional[List[str]] = None,
        limit: int = 5,
        mode: str = "hybrid",
        file_type: Optional[str] = None,
    ) -> ToolResult:
        """Select the best matching file, load its full chunks, and summarize it."""
        search = self.retrieve_context(
            query=query,
            source_types=source_types or ["file"],
            limit=max(2, min(int(limit or 5), 10)),
            mode=mode or "hybrid",
            file_type=file_type,
            rerank=False,
        )
        matches = search.artifacts or []
        if not matches:
            return ToolResult(
                content="No relevant Atlas document was found to summarize.",
                artifacts=[],
                metadata={
                    **(search.metadata or {}),
                    "answer_source": "none",
                    "confidence": "low",
                    "direct_response": "No relevant Atlas document was found to summarize.",
                },
            )

        selected = matches[0]
        document_id = selected.get("document_id")
        document = self.get_document_context(str(document_id)) if document_id else ToolResult(content="", artifacts=[])
        chunks = document.artifacts or []
        if not chunks:
            return ToolResult(
                content="I found a matching document, but no full-document chunks were available to summarize.",
                artifacts=matches,
                metadata={
                    "retrieval_attempted": True,
                    "retrieval_artifact_count": len(matches),
                    "max_score": self._retrieval_metadata(matches).get("max_score"),
                    "grounding_status": "weak",
                    "answer_source": "none",
                    "confidence": "low",
                    "direct_response": "I found a matching document, but no full-document chunks were available to summarize.",
                },
            )

        file_name = selected.get("file_name") or chunks[0].get("file_name") or "selected document"
        alternatives = [
            str(match.get("file_name"))
            for match in matches[1:]
            if match.get("file_name") and match.get("file_name") != file_name
        ]

        try:
            raw_context = self._document_summary_context(chunks, max_chars=_DOCUMENT_SUMMARY_CONTEXT_CHARS + 1)
            if len(raw_context) <= _DOCUMENT_SUMMARY_CONTEXT_CHARS:
                answer = self._summarize_context_once(
                    query=query,
                    file_name=file_name,
                    context=raw_context,
                    alternatives=alternatives,
                )
            else:
                answer = self._summarize_large_document(
                    query=query,
                    file_name=file_name,
                    chunks=chunks,
                    alternatives=alternatives,
                )
        except Exception as exc:
            logger.warning("Document summary failed: %s", exc)
            return ToolResult(
                content=document.content,
                artifacts=chunks,
                metadata={
                    "retrieval_attempted": True,
                    "retrieval_artifact_count": len(chunks),
                    "max_score": self._retrieval_metadata(matches).get("max_score"),
                    "grounding_status": "grounded",
                    "answer_source": "atlas_context",
                    "confidence": "medium",
                    "warning": f"Document summary generation failed: {exc}",
                },
            )

        summary_artifact = {
            **selected,
            "summary_document_id": document_id,
            "full_document_chunk_count": len(chunks),
            "alternative_file_names": alternatives[:3],
        }
        return ToolResult(
            content=answer,
            artifacts=[summary_artifact],
            metadata={
                "retrieval_attempted": True,
                "retrieval_artifact_count": 1,
                "max_score": self._retrieval_metadata(matches).get("max_score"),
                "grounding_status": "grounded",
                "answer_source": "atlas_context",
                "confidence": "high",
                "direct_response": answer,
            },
        )

    def hybrid_document_search(
        self,
        *,
        query: str,
        source_type: Optional[str],
        limit: int,
        rerank: bool = True,
        rerank_top_n: int = 15,
        file_type: Optional[str] = None,
    ) -> ToolResult:
        return self.retrieve_context(
            query=query,
            source_types=[source_type] if source_type else None,
            limit=limit,
            mode="hybrid",
            file_type=file_type,
            rerank=rerank,
        )

    def semantic_search(
        self,
        query: str,
        source_type: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 5
    ) -> ToolResult:
        """Perform semantic search on document embeddings."""
        mode = "hybrid" if source_type in _HYBRID_SOURCE_TYPES else "semantic"
        return self.retrieve_context(
            query=query,
            source_types=[source_type] if source_type else None,
            limit=limit,
            mode=mode,
            file_type=file_type,
            rerank=False,
        )

    def get_project_details(self, project_name: str) -> ToolResult:
        """Get detailed information about a specific project."""
        sql = """
            SELECT
                p.id, p.project_code, p.name, p.company_name, p.description,
                p.stage_name, p.status_category, p.is_ongoing,
                p.start_date, p.end_date,
                v.vertical_name,
                l.display_name AS location, l.country, l.city,
                ps.summary_text AS summary
            FROM master_dashboard.projects p
            LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
            LEFT JOIN master_dashboard.locations l ON p.location_id = l.id
            LEFT JOIN master_dashboard.project_summaries ps
                ON ps.project_id = p.id AND ps.lang = 'en'
            WHERE
                LOWER(p.name) LIKE LOWER(%s)
                OR LOWER(p.project_code) LIKE LOWER(%s)
                OR LOWER(p.company_name) LIKE LOWER(%s)
            LIMIT 1
        """
        pattern = f"%{project_name}%"
        row = fetch_one(sql, (pattern, pattern, pattern))

        if not row:
            return ToolResult(content=f"No project found matching '{project_name}'.")

        # Get owners
        owners_sql = """
            SELECT ppl.full_name, po.role
            FROM master_dashboard.project_owners po
            JOIN master_dashboard.people ppl ON ppl.id = po.person_id
            WHERE po.project_id = %s
        """
        owners = fetch_all(owners_sql, (row["id"],))

        # Get organizations
        orgs_sql = """
            SELECT org.org_name, por.role
            FROM master_dashboard.project_org_roles por
            JOIN master_dashboard.organizations org ON org.id = por.org_id
            WHERE por.project_id = %s
        """
        orgs = fetch_all(orgs_sql, (row["id"],))

        # Format response
        content = f"""
Project: {row['name']}
Code: {row.get('project_code', 'N/A')}
Company: {row.get('company_name', 'N/A')}
Vertical: {row.get('vertical_name', 'N/A')}
Stage: {row.get('stage_name', 'N/A')}
Status: {row.get('status_category', 'N/A')}
Location: {row.get('location', 'N/A')}
Ongoing: {'Yes' if row.get('is_ongoing') else 'No'}
Start Date: {row.get('start_date', 'N/A')}
End Date: {row.get('end_date', 'N/A')}

Description:
{row.get('description') or row.get('summary') or 'No description available.'}

Owners: {', '.join(o['full_name'] for o in owners) if owners else 'N/A'}

Organizations: {', '.join(f"{o['org_name']} ({o['role']})" for o in orgs) if orgs else 'N/A'}
""".strip()

        return ToolResult(content=content, artifacts=[dict(row)])

    def get_company_details(self, company_name: str) -> ToolResult:
        """Get detailed information about a company/organization."""
        pattern = f"%{company_name}%"

        # First try projects table (startups are stored as projects)
        project_sql = """
            SELECT
                p.id, p.name, p.company_name, p.description,
                p.stage_name, p.status_category, p.is_ongoing,
                v.vertical_name
            FROM master_dashboard.projects p
            LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
            WHERE LOWER(p.name) LIKE LOWER(%s)
               OR LOWER(p.company_name) LIKE LOWER(%s)
            LIMIT 1
        """
        project = fetch_one(project_sql, (pattern, pattern))

        if project:
            content = f"""
Company: {project.get('name', company_name)}
Vertical: {project.get('vertical_name', 'N/A')}
Stage: {project.get('stage_name', 'N/A')}
Status: {project.get('status_category', 'N/A')}
Ongoing: {'Yes' if project.get('is_ongoing') else 'No'}
"""
            if project.get('description'):
                content += f"\nDescription:\n{project['description']}"

            return ToolResult(content=content.strip(), artifacts=[dict(project)])

        # Try organizations table
        org_sql = """
            SELECT id, org_name, org_type, website, country
            FROM master_dashboard.organizations
            WHERE LOWER(org_name) LIKE LOWER(%s)
            LIMIT 1
        """
        org = fetch_one(org_sql, (pattern,))

        if org:
            # Get associated projects
            projects_sql = """
                SELECT p.name, p.stage_name, por.role
                FROM master_dashboard.project_org_roles por
                JOIN master_dashboard.projects p ON p.id = por.project_id
                WHERE por.org_id = %s
            """
            projects = fetch_all(projects_sql, (org["id"],))

            content = f"""
Organization: {org['org_name']}
Type: {org.get('org_type', 'N/A')}
Website: {org.get('website', 'N/A')}
Country: {org.get('country', 'N/A')}

Associated Projects:
{chr(10).join(f"- {p['name']} ({p['role']}, {p.get('stage_name', 'N/A')})" for p in projects) if projects else 'None found'}
""".strip()

            return ToolResult(content=content, artifacts=[dict(org)])

        # Try PitchBook data
        pb_sql = """
            SELECT *
            FROM dp.pitchbook_deals
            WHERE LOWER(startups) LIKE LOWER(%s)
            LIMIT 1
        """
        pb = fetch_one(pb_sql, (pattern,))

        if pb:
            content = f"""
Company (PitchBook): {pb.get('startups', company_name)}
Deal Size: {pb.get('deal_size', 'N/A')}
Deal Type: {pb.get('deal_type', 'N/A')}
Stage: {pb.get('stage', 'N/A')}
Industry: {pb.get('primary_industry_sector', 'N/A')}
Location: {pb.get('company_hq_location', 'N/A')}
Investors: {pb.get('investors', 'N/A')}
""".strip()
            return ToolResult(content=content, artifacts=[dict(pb)])

        return ToolResult(content=f"No company found matching '{company_name}'.")

    def filter_projects_by_stage(self, stage: str) -> ToolResult:
        """Find projects at a specific stage."""
        sql = """
            SELECT p.name, p.company_name, p.stage_name, v.vertical_name
            FROM master_dashboard.projects p
            LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
            WHERE LOWER(p.stage_name) LIKE LOWER(%s)
            ORDER BY p.name
            LIMIT 50
        """
        pattern = f"%{stage}%"
        rows = fetch_all(sql, (pattern,))

        if not rows:
            return ToolResult(content=f"No projects found at stage '{stage}'.")

        content = f"Projects at stage '{stage}':\n\n"
        content += "\n".join(
            f"- {r['name']} ({r.get('company_name', 'N/A')}) - {r.get('vertical_name', 'N/A')}"
            for r in rows
        )

        return ToolResult(content=content, artifacts=list(rows))

    def filter_projects_by_vertical(self, vertical: str) -> ToolResult:
        """Find projects in a specific vertical."""
        sql = """
            SELECT p.name, p.company_name, p.stage_name, v.vertical_name
            FROM master_dashboard.projects p
            LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
            WHERE LOWER(v.vertical_name) LIKE LOWER(%s)
            ORDER BY p.name
            LIMIT 50
        """
        pattern = f"%{vertical}%"
        rows = fetch_all(sql, (pattern,))

        if not rows:
            return ToolResult(content=f"No projects found in vertical '{vertical}'.")

        content = f"Projects in {vertical}:\n\n"
        content += "\n".join(
            f"- {r['name']} ({r.get('company_name', 'N/A')}) - Stage: {r.get('stage_name', 'N/A')}"
            for r in rows
        )

        return ToolResult(content=content, artifacts=list(rows))

    def search_by_keyword(self, keyword: str) -> ToolResult:
        """Search projects by keyword in descriptions."""
        sql = """
            SELECT
                p.name, p.company_name, p.description, p.stage_name,
                v.vertical_name
            FROM master_dashboard.projects p
            LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
            WHERE
                LOWER(p.description) LIKE LOWER(%s)
                OR LOWER(p.name) LIKE LOWER(%s)
                OR LOWER(p.company_name) LIKE LOWER(%s)
            ORDER BY p.name
            LIMIT 20
        """
        pattern = f"%{keyword}%"
        rows = fetch_all(sql, (pattern, pattern, pattern))

        if not rows:
            return ToolResult(content=f"No results found for keyword '{keyword}'.")

        content = f"Search results for '{keyword}':\n\n"
        for r in rows:
            desc = (r.get('description') or '')[:200]
            content += f"- {r['name']} ({r.get('company_name', 'N/A')})\n"
            content += f"  Vertical: {r.get('vertical_name', 'N/A')}, Stage: {r.get('stage_name', 'N/A')}\n"
            if desc:
                content += f"  {desc}...\n"
            content += "\n"

        return ToolResult(content=content.strip(), artifacts=list(rows))

    def list_projects(
        self,
        limit: int = 20,
        vertical: Optional[str] = None,
        is_ongoing: Optional[bool] = None
    ) -> ToolResult:
        """List projects with optional filters."""
        sql = """
            SELECT
                p.name, p.company_name, p.stage_name, p.is_ongoing,
                v.vertical_name
            FROM master_dashboard.projects p
            LEFT JOIN master_dashboard.verticals v ON p.vertical_id = v.id
            WHERE 1=1
        """
        params = []

        if vertical:
            sql += " AND LOWER(v.vertical_name) LIKE LOWER(%s)"
            params.append(f"%{vertical}%")

        if is_ongoing is not None:
            sql += " AND p.is_ongoing = %s"
            params.append(is_ongoing)

        sql += " ORDER BY p.name LIMIT %s"
        params.append(limit)

        rows = fetch_all(sql, tuple(params))

        if not rows:
            return ToolResult(content="No projects found matching the criteria.")

        content = "Projects:\n\n"
        content += "\n".join(
            f"- {r['name']} ({r.get('company_name', 'N/A')}) - "
            f"{r.get('vertical_name', 'N/A')}, {r.get('stage_name', 'N/A')}"
            + (" [Ongoing]" if r.get('is_ongoing') else "")
            for r in rows
        )

        return ToolResult(content=content, artifacts=list(rows))

    def compare_companies(self, company_names: List[str]) -> ToolResult:
        """Compare multiple companies."""
        results = []

        for name in company_names:
            result = self.get_company_details(name)
            results.append(f"=== {name} ===\n{result.content}")

        if not results:
            return ToolResult(content="No companies found for comparison.")

        content = "Company Comparison:\n\n" + "\n\n".join(results)
        return ToolResult(content=content)

    def get_pitchbook_deals(
        self,
        company_name: Optional[str] = None,
        industry: Optional[str] = None,
        limit: int = 10
    ) -> ToolResult:
        """Search PitchBook deal data."""
        sql = """
            SELECT
                startups, deal_size, deal_type, deal_date,
                primary_industry_sector, company_hq_location,
                investors, pre_money_valuation
            FROM dp.pitchbook_deals
            WHERE 1=1
        """
        params = []

        if company_name:
            sql += " AND LOWER(startups) LIKE LOWER(%s)"
            params.append(f"%{company_name}%")

        if industry:
            sql += " AND LOWER(primary_industry_sector) LIKE LOWER(%s)"
            params.append(f"%{industry}%")

        sql += " ORDER BY deal_date DESC NULLS LAST LIMIT %s"
        params.append(limit)

        rows = fetch_all(sql, tuple(params))

        if not rows:
            return ToolResult(content="No PitchBook deals found matching the criteria.")

        content = "PitchBook Deals:\n\n"
        for r in rows:
            content += f"- {r.get('startups', 'N/A')}\n"
            content += f"  Deal: {r.get('deal_type', 'N/A')} - ${r.get('deal_size', 'N/A')}\n"
            content += f"  Industry: {r.get('primary_industry_sector', 'N/A')}\n"
            content += f"  Location: {r.get('company_hq_location', 'N/A')}\n"
            content += f"  Investors: {r.get('investors', 'N/A')}\n\n"

        return ToolResult(content=content.strip(), artifacts=list(rows))

    def web_search(
        self,
        query: str,
        max_results: int = 5
    ) -> ToolResult:
        """
        Search the web using DDGS metasearch.

        Args:
            query: Search query string
            max_results: Maximum number of results (capped at 10)

        Returns:
            ToolResult with formatted search results
        """
        # Cap max_results to reasonable limit
        max_results = min(max_results, 10)

        try:
            from ddgs import DDGS

            # Initialize DDGS and perform search
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results
                ))

            if not results:
                return ToolResult(
                    content=f"No web search results found for '{query}'.",
                    artifacts=[]
                )

            # Format results for Claude
            content_parts = [f"Web search results for '{query}':\n"]
            artifacts = []

            for idx, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                url = result.get('href', result.get('link', ''))
                snippet = result.get('body', result.get('description', 'No description'))

                # Format each result
                content_parts.append(f"\n{idx}. {title}")
                content_parts.append(f"   URL: {url}")
                content_parts.append(f"   {snippet}")

                # Store structured data
                artifacts.append({
                    'title': title,
                    'url': url,
                    'snippet': snippet,
                    'rank': idx
                })

            content = '\n'.join(content_parts)
            return ToolResult(
                content=content,
                artifacts=artifacts,
                metadata={
                    "retrieval_attempted": False,
                    "retrieval_artifact_count": len(artifacts),
                    "max_score": None,
                    "grounding_status": "external",
                },
            )

        except Exception as e:
            logger.error(f"Web search error for query '{query}': {e}")

            # Provide helpful error message
            error_msg = f"Web search failed for '{query}'. "
            error_str = str(e).lower()

            if 'timeout' in error_str:
                error_msg += "The search request timed out. Please try a simpler query."
            elif 'ratelimit' in error_str or 'rate limit' in error_str:
                error_msg += "Rate limit reached. Please try again in a few moments."
            elif 'network' in error_str or 'connection' in error_str:
                error_msg += "Network connection issue. Please check connectivity."
            else:
                error_msg += f"Error: {str(e)}"

            return ToolResult(content=error_msg, artifacts=[])
