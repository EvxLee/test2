"""
Atlas retrieval eval runner - Precision@K and Recall@K baseline.

Requires a live database and Bedrock credentials. Do not run in CI.

Usage:
    docker exec -w /backend/product/api backend-backend-1 python tests/evals/eval_runner.py
    docker exec -w /backend/product/api backend-backend-1 python tests/evals/eval_runner.py --k 10
    docker exec -w /backend/product/api backend-backend-1 python tests/evals/eval_runner.py --source-type project
    docker exec -w /backend/product/api backend-backend-1 python tests/evals/eval_runner.py --mode semantic_tool
    docker exec -w /backend/product/api backend-backend-1 python tests/evals/eval_runner.py --mode hybrid
    docker exec -w /backend/product/api backend-backend-1 python tests/evals/eval_runner.py --mode hybrid --rerank
    docker exec -w /backend/product/api backend-backend-1 python tests/evals/eval_runner.py --save-baseline

Bootstrapping labels (first-time setup):
    Run with empty expected_source_ids, review printed results, then curate
    the correct source_id UUIDs from source data before adding them to
    queries.json.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup - makes `chat.*` importable regardless of working directory
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent

# Docker mounts the app at /app/api; outside Docker it's at backend/product/api
_DOCKER_API = Path("/app/api")
_LOCAL_API = _HERE.parents[1]  # backend/product/api/tests/evals -> backend/product/api
_PRODUCT_API = _DOCKER_API if _DOCKER_API.exists() else _LOCAL_API
if str(_PRODUCT_API) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_API))

# Load .env from backend/ if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(_HERE.parents[3] / ".env")  # backend/product/api/tests/evals -> backend/
except ImportError:
    pass

from chat.llm_client import get_embedding_client, get_llm_client  # noqa: E402
from chat.tools import RAGTools  # noqa: E402

# ---------------------------------------------------------------------------
# File paths and constants
# ---------------------------------------------------------------------------

QUERIES_FILE = _HERE / "queries.json"

MODES = ("semantic_raw", "semantic_tool", "hybrid")
LABEL_WARNING = (
    "Label hygiene: expected_source_ids should be curated from source data, "
    "not copied blindly from a previous retriever run."
)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def load_queries(source_type_filter: str | None = None) -> list[dict]:
    """Load queries.json, optionally filtered to one source_type."""
    with open(QUERIES_FILE) as f:
        queries = json.load(f)
    if source_type_filter:
        queries = [q for q in queries if q.get("source_type") == source_type_filter]
    return queries


def normalize_artifacts(artifacts: list[dict]) -> list[dict]:
    """Normalize retrieval outputs from all modes to a common shape."""
    normalized = []
    for artifact in artifacts:
        source_id = artifact.get("source_id")
        similarity = artifact.get("similarity")
        score = artifact.get("score", similarity)
        fusion_score = artifact.get("fusion_score")

        normalized.append({
            "source_id": str(source_id) if source_id is not None else None,
            "similarity": _round_number(similarity),
            "score": _round_number(score),
            "fusion_score": _round_number(fusion_score),
            "file_name": artifact.get("file_name"),
            "chunk_text": artifact.get("chunk_text") or artifact.get("snippet"),
        })
    return normalized


def unique_source_ids(artifacts: list[dict]) -> list[str]:
    """Return ordered unique source_ids, preserving first ranked occurrence."""
    seen = set()
    ids = []
    for artifact in artifacts:
        source_id = artifact.get("source_id")
        if source_id is None or source_id in seen:
            continue
        seen.add(source_id)
        ids.append(source_id)
    return ids


def metrics_at_k(
    retrieved_ids: list[str],
    expected_ids: list[str],
    k: int,
) -> tuple[float | None, float | None]:
    """
    Compute source-level Precision@K and Recall@K.

    Returns (None, None) for unlabeled queries so they are excluded from
    aggregate means.
    """
    expected = {str(source_id) for source_id in expected_ids if source_id}
    if not expected:
        return None, None

    top_k = retrieved_ids[:k]
    hits = {rid for rid in top_k if rid in expected}
    precision = len(hits) / k
    recall = len(hits) / len(expected)
    return precision, recall


def retrieve(
    tools: RAGTools,
    *,
    mode: str,
    query: str,
    source_type: str | None,
    k: int,
    rerank: bool,
) -> list[dict]:
    """Run the selected retrieval mode and return normalized artifacts."""
    if mode == "semantic_raw":
        rows = tools._semantic_search_rows(
            query=query,
            source_type=source_type,
            limit=k,
            similarity_threshold=None,
        )
        return normalize_artifacts(list(rows))

    if mode == "semantic_tool":
        result = tools.semantic_search(query=query, source_type=source_type, limit=k)
        return normalize_artifacts(result.artifacts or [])

    if mode == "hybrid":
        result = tools.hybrid_document_search(
            query=query,
            source_type=source_type,
            limit=k,
            rerank=rerank,
        )
        return normalize_artifacts(result.artifacts or [])

    raise ValueError(f"Unknown eval mode: {mode}")


def _round_number(value: Any) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return value


# ---------------------------------------------------------------------------
# Main eval loop
# ---------------------------------------------------------------------------

def run_eval(
    k: int = 5,
    source_type: str | None = None,
    save_baseline: bool = False,
    mode: str = "semantic_raw",
    rerank: bool = False,
) -> None:
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")

    queries = load_queries(source_type)
    if not queries:
        print("No queries found. Check queries.json or your --source-type filter.")
        return

    precision_label = f"Precision@{k}"
    recall_label = f"Recall@{k}"
    print(f"Loaded {len(queries)} queries. Running {precision_label} / {recall_label}.")
    print(f"Mode: {mode}" + (", rerank: on" if mode == "hybrid" and rerank else ""))
    print(f"{LABEL_WARNING}\n")
    print("=" * 60)

    embedding_client = get_embedding_client()
    llm_client = get_llm_client() if mode == "hybrid" and rerank else None
    tools = RAGTools(embedding_client=embedding_client, llm_client=llm_client)

    precision_scores: list[float] = []
    recall_scores: list[float] = []
    rows: list[dict] = []

    for q in queries:
        qid = q["id"]
        query_text = q["query"]
        q_source_type = q.get("source_type")
        expected = [str(source_id) for source_id in q.get("expected_source_ids", []) if source_id]

        artifacts = retrieve(
            tools,
            mode=mode,
            query=query_text,
            source_type=q_source_type,
            k=k,
            rerank=rerank,
        )
        retrieved_ids = unique_source_ids(artifacts)

        precision, recall = metrics_at_k(retrieved_ids, expected, k)
        status = (
            "UNLABELED"
            if precision is None
            else f"{precision_label}={precision:.2f}, {recall_label}={recall:.2f}"
        )

        print(f"[{qid}] {query_text}")
        print(f"  source_type : {q_source_type or 'any'}")
        print(f"  mode        : {mode}")
        print(f"  retrieved   : {retrieved_ids}")
        print(f"  expected    : {expected}")
        print(f"  result      : {status}")
        print()

        rows.append({
            "id": qid,
            "query": query_text,
            "source_type": q_source_type,
            "mode": mode,
            "retrieved_source_ids": retrieved_ids,
            "expected_source_ids": expected,
            "artifacts": artifacts,
            "p_at_k": precision,
            "r_at_k": recall,
        })
        if precision is not None:
            precision_scores.append(precision)
        if recall is not None:
            recall_scores.append(recall)

    labeled = len(precision_scores)
    mean_p = sum(precision_scores) / labeled if labeled else 0.0
    mean_r = sum(recall_scores) / labeled if labeled else 0.0

    print("=" * 60)
    print(f"Labeled queries : {labeled} / {len(queries)}")
    print(f"Mean {precision_label}  : {mean_p:.4f}")
    print(f"Mean {recall_label}     : {mean_r:.4f}")
    print("=" * 60)

    if labeled == 0:
        print(
            "\nNo labeled queries yet. Run once to see retrieved source_ids, "
            "then curate expected_source_ids in queries.json from source data."
        )

    if save_baseline:
        baseline_file, baseline_json_file = _baseline_paths(mode=mode, rerank=rerank)
        _write_baseline(
            mean_p=mean_p,
            mean_r=mean_r,
            k=k,
            rows=rows,
            labeled=labeled,
            total=len(queries),
            mode=mode,
            rerank=rerank,
            baseline_file=baseline_file,
            baseline_json_file=baseline_json_file,
        )
        print(f"\nBaseline saved to {baseline_file}")
        print(f"Diagnostics saved to {baseline_json_file}")


# ---------------------------------------------------------------------------
# Baseline writer
# ---------------------------------------------------------------------------

def _write_baseline(
    mean_p: float,
    mean_r: float,
    k: int,
    rows: list[dict],
    labeled: int,
    total: int,
    mode: str,
    rerank: bool,
    baseline_file: Path,
    baseline_json_file: Path,
) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Eval Baseline - Precision@{k} / Recall@{k}",
        "",
        f"**Date:** {timestamp}",
        f"**Mode:** {mode}",
        f"**Rerank:** {'on' if rerank else 'off'}",
        f"**Labeled queries:** {labeled} / {total}",
        f"**Mean Precision@{k}: {mean_p:.4f}**",
        f"**Mean Recall@{k}: {mean_r:.4f}**",
        "",
        f"> {LABEL_WARNING}",
        "",
        "## Per-Query Results",
        "",
        f"| ID | Query | Source Type | Mode | Retrieved Source IDs | Expected Source IDs | P@{k} | R@{k} |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        precision = f"{r['p_at_k']:.2f}" if r["p_at_k"] is not None else "unlabeled"
        recall = f"{r['r_at_k']:.2f}" if r["r_at_k"] is not None else "unlabeled"
        retrieved = "<br>".join(r["retrieved_source_ids"]) or "-"
        expected = "<br>".join(r["expected_source_ids"]) or "-"
        lines.append(
            "| "
            f"{_md_cell(r['id'])} | "
            f"{_md_cell(r['query'])} | "
            f"{_md_cell(r.get('source_type') or 'any')} | "
            f"{_md_cell(r['mode'])} | "
            f"{retrieved} | "
            f"{expected} | "
            f"{precision} | "
            f"{recall} |"
        )
    lines.append("")
    baseline_file.write_text("\n".join(lines))

    payload = {
        "date": timestamp,
        "mode": mode,
        "rerank": rerank,
        "k": k,
        "labeled_queries": labeled,
        "total_queries": total,
        "mean_precision_at_k": mean_p,
        "mean_recall_at_k": mean_r,
        "label_warning": LABEL_WARNING,
        "rows": rows,
    }
    baseline_json_file.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _baseline_paths(*, mode: str, rerank: bool) -> tuple[Path, Path]:
    suffix = f"{mode}_rerank" if mode == "hybrid" and rerank else mode
    return _HERE / f"BASELINE.{suffix}.md", _HERE / f"BASELINE.{suffix}.json"


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Atlas retrieval eval runner - Precision@K and Recall@K"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Top-K unique source IDs to evaluate (default: 5)",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        default=None,
        choices=[
            "project",
            "organization",
            "pitchbook_deal",
            "pitchbook_company",
            "monday_item",
            "contract",
            "document",
            "file",
        ],
        help="Only run queries matching this source_type",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="semantic_raw",
        choices=MODES,
        help=(
            "Retrieval path to evaluate: semantic_raw calls the private vector "
            "helper, semantic_tool calls RAGTools.semantic_search, hybrid calls "
            "RAGTools.hybrid_document_search (default: semantic_raw)"
        ),
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Enable LLM reranking for --mode hybrid. Ignored by other modes.",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help=(
            "Write results to mode-specific files, e.g. BASELINE.semantic_raw.md "
            "and BASELINE.semantic_raw.json"
        ),
    )
    args = parser.parse_args()

    run_eval(
        k=args.k,
        source_type=args.source_type,
        save_baseline=args.save_baseline,
        mode=args.mode,
        rerank=args.rerank,
    )
