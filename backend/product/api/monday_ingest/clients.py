"""
clients.py — Monday data sources
"""

import os
import json
from typing import Any, Dict, Optional, List
from monday_pull.core.engine import pull_board
from psycopg import Connection
from board_config_db import get_board_ids_by_mapper_type, get_file_board_ids_from_config

# Config the team can use
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")
MONDAY_EXPORT_DIR = os.getenv("MONDAY_EXPORT_DIR", "/app/exports/monday")

# Boards that carry file attachments requiring DO Spaces storage
FILE_BOARD_ENV_VARS = [
    "MONDAY_BOARD_CONTRACT_STATUS_2_ID",
    "MONDAY_BOARD_AI_LOCATE_FILE_ID",
]


def get_file_board_ids() -> list[str]:
    """Resolve configured file-storage board IDs from board_config."""
    return get_file_board_ids_from_config()


# Pre-CAP board env-var names (centralized so core_mapping can import)
PRECAP_BOARD_ENV_VARS = [
    # 2024 cohort
    "MONDAY_BOARD_PRECAP_2024_CYCLE5_ID",
    "MONDAY_BOARD_PRECAP_2024_CYCLE6_ID",
    "MONDAY_BOARD_PRECAP_2024_CYCLE7_ID",
    # 2025 cohort
    "MONDAY_BOARD_PRECAP_2025_CYCLE1_ID",
    "MONDAY_BOARD_PRECAP_2025_CYCLE2_ID",
    "MONDAY_BOARD_PRECAP_2025_CYCLE3_ID",
    "MONDAY_BOARD_PRECAP_2025_CYCLE4_ID",
    "MONDAY_BOARD_PRECAP_2025_CYCLE5_ID",
    "MONDAY_BOARD_PRECAP_2025_CYCLE6_ID",
    "MONDAY_BOARD_PRECAP_2025_CYCLE7_ID",
    # 2026 cohort
    "MONDAY_BOARD_PRECAP_2026_CYCLE1_ID",
    "MONDAY_BOARD_PRECAP_2026_CYCLE2_ID",
    "MONDAY_BOARD_PRECAP_2026_CYCLE3_ID",
    "MONDAY_BOARD_PRECAP_2026_CYCLE4_ID",
    "MONDAY_BOARD_PRECAP_2026_CYCLE5_ID",
    "MONDAY_BOARD_PRECAP_2026_CYCLE6_ID",
    "MONDAY_BOARD_PRECAP_2026_CYCLE7_ID",
]


def get_precap_board_ids() -> set[str]:
    """Resolve configured Pre-CAP board IDs from board_config."""
    return get_board_ids_by_mapper_type("gced")

def _attach_column_values_to_items(
    items: List[Dict[str, Any]],
    column_values: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Take a flat items list and a flat column_values list and return items where
    each item has item["column_values"] = [ ... ] attached.

    Expects each column_values entry to have an "item_id" (or "itemId") field.
    """
    # Build map: item_id -> [col_val, col_val, ...]
    by_item: Dict[str, List[Dict[str, Any]]] = {}
    for cv in column_values:
        item_id = cv.get("item_id") or cv.get("itemId")
        if item_id is None:
            continue
        key = str(item_id)
        by_item.setdefault(key, []).append(cv)

    hydrated: List[Dict[str, Any]] = []
    for item in items:
        iid = str(item.get("id"))
        new_item = dict(item)
        new_item["column_values"] = by_item.get(iid, [])
        hydrated.append(new_item)

    return hydrated

def _extract_item_id(item: dict) -> str | None:
    """
    Normalize the different item id keys used by monday_pull.
    """
    return (
        item.get("id")
        or item.get("item_id")
        or item.get("monday_id")
        or item.get("pulse_id")
        or item.get("pulseId")
    )

def _attach_column_values(bundle: dict) -> dict:
    """
    Convert top-level column_values[] list into per-item column_values[] arrays.
    Mutates bundle["items"] and bundle["subitems"] in-place.
    """
    items_by_id: dict[str, dict] = {}

    # I made it so that we index both items and subitems by id
    # subitems must be included so that reviewer score column_values are not silently dropped,
    # this is what caused average_score to be null.
    for item in bundle.get("items", []) + bundle.get("subitems", []):
        iid = _extract_item_id(item)
        if iid is None:
            continue
        items_by_id[str(iid)] = item

    # Ensure each item has column_values list
    for it in items_by_id.values():
        it.setdefault("column_values", [])

    # Attach each column_value to the right item
    for cv in bundle.get("column_values", []) or bundle.get("columnValues", []) or []:
        cv_item_id = cv.get("item_id") or cv.get("itemId") or cv.get("id")
        if cv_item_id is None:
            continue
        key = str(cv_item_id)
        if key in items_by_id:
            items_by_id[key]["column_values"].append(cv)

    return bundle

def _normalize_bundle(board_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    board_info = payload.get("board", {"id": board_id, "name": payload.get("name")})
    items = payload.get("items", []) or []
    subitems = payload.get("subitems", []) or []
    files = payload.get("files", []) or []
    columns = payload.get("columns", []) or []
    groups = payload.get("groups", []) or []
    label_maps = payload.get("label_maps", {}) or {}
    item_links = payload.get("item_links", []) or []

    if items and any("column_values" in itm for itm in items):
        return {
            "board": board_info,
            "items": items,
            "subitems": subitems,
            "files": files,
            "columns": columns,
            "groups": groups,
            "label_maps": label_maps,
            "item_links": item_links,
        }

    column_values = (
        payload.get("column_values")
        or payload.get("columnValues")
        or []
    )
    if column_values:
        items = _attach_column_values_to_items(items, column_values)

    return {
        "board": board_info,
        "items": items,
        "subitems": subitems,
        "files": files,
        "columns": columns,
        "groups": groups,
        "label_maps": label_maps,
        "item_links": item_links,
    }


def fetch_live_bundle(
    board_id: str,
    include: Optional[dict] = None,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return a dict
    """
    if not board_id:
        raise ValueError("board_id is required")

    cfg = {"board_id": str(board_id)}
    print("DEBUG fetch_live_bundle() called for board:", board_id, "cfg:", cfg, flush=True)

    try:
        payload = pull_board(board_id, cfg)

        print(
            "DEBUG fetch_live_bundle: raw payload keys:",
            list(payload.keys()),
            flush=True,
        )
        items = payload.get("items") or []
        colvals = payload.get("column_values") or payload.get("columnValues") or []
        print(
            "DEBUG fetch_live_bundle: items_len =",
            len(items),
            "column_values_len =",
            len(colvals),
            flush=True,
        )
        if colvals:
            from pprint import pformat
            print(
                "DEBUG fetch_live_bundle: sample column_value:",
                pformat(colvals[0])[:1000],
                flush=True,
            )
        payload = _attach_column_values(payload)

        items_after = payload.get("items") or []
        if items_after:
            from pprint import pformat
            print(
                "DEBUG fetch_live_bundle: first item after _attach_column_values:",
                pformat(items_after[0])[:1000],
                flush=True,
            )
        else:
            print("DEBUG fetch_live_bundle: NO items_after", flush=True)

    except Exception as e:
        print("DEBUG fetch_live_bundle exception:", repr(e), flush=True)
        raise RuntimeError(f"Failed to pull Monday board {board_id}: {e}")

    return _normalize_bundle(str(board_id), payload)


def read_export_bundle(board_id: str) -> Dict[str, Any]:
    """
    Read previously exported dump from: {MONDAY_EXPORT_DIR}/{board_id}/dump.json
    and return the same dict shape as fetch_live_bundle (items with column_values attached).
    """
    if not board_id:
        raise ValueError("board_id is required")

    dump_path = os.path.join(MONDAY_EXPORT_DIR, str(board_id), "dump.json")

    if not os.path.exists(dump_path):
        raise FileNotFoundError(f"Exported dump not found at {dump_path}")

    try:
        with open(dump_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
            payload = _attach_column_values(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in dump file {dump_path}: {e}")

    return _normalize_bundle(str(board_id), payload)


def hydrate_monday_from_staging(conn: Connection) -> None:
    """
    Wrapper over monday.hydrate_from_staging().

    Assumes monday_staging.items_json was populated with bundles in the shape
    produced by fetch_live_bundle/read_export_bundle (items with column_values nested).
    """
    with conn.cursor() as cur:
        cur.execute("SELECT monday.hydrate_from_staging();")
    conn.commit()
