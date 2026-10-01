import os
from typing import Any

from display.core.db import fetch_all, get_conn


BOARD_CONFIG_COLUMNS = {
    "board_key",
    "label",
    "category",
    "year",
    "display_order",
    "is_active",
    "monday_board_id",
    "env_var_name",
    "mapper_type",
}


def _resolved_board_id(row: dict[str, Any]) -> str | None:
    board_id = row.get("monday_board_id")
    if board_id:
        return str(board_id).strip() or None
    env_var_name = row.get("env_var_name")
    if env_var_name:
        return os.getenv(str(env_var_name), "").strip() or None
    return None


def _serialize_board(row: dict[str, Any]) -> dict[str, Any]:
    board_id = _resolved_board_id(row)
    return {
        "board_key": row["board_key"],
        "key": row["board_key"],
        "label": row["label"],
        "category": row["category"],
        "year": row["year"],
        "display_order": row["display_order"],
        "displayOrder": row["display_order"],
        "board_id": board_id,
        "boardId": board_id,
        "monday_board_id": row.get("monday_board_id"),
        "env_var_name": row.get("env_var_name"),
        "mapper_type": row.get("mapper_type"),
        "is_active": row.get("is_active", True),
    }


def get_board_id(board_key: str) -> str | None:
    """Return the Monday board ID for a given board_key.

    Looks up monday_board_id from DB first.
    Falls back to the env_var_name value if monday_board_id is NULL.
    Returns None if the board is not found or inactive.
    """
    rows = fetch_all(
        """
        SELECT monday_board_id, env_var_name
        FROM master_dashboard.board_config
        WHERE board_key = %s AND is_active = TRUE
        """,
        (board_key,),
    )
    if not rows:
        return None

    row = rows[0]
    return _resolved_board_id(row)


def get_all_boards() -> list[dict]:
    """Return all active boards with their resolved board IDs."""
    rows = fetch_all(
        """
        SELECT board_key, label, category, year, display_order, is_active,
               monday_board_id, env_var_name, mapper_type
        FROM master_dashboard.board_config
        WHERE is_active = TRUE
        ORDER BY display_order
        """,
    )
    return [_serialize_board(row) for row in rows]


def get_boards_by_mapper_type(*mapper_types: str) -> list[dict]:
    """Return active boards whose mapper_type is in the provided set."""
    wanted = {m for m in mapper_types if m}
    return [b for b in get_all_boards() if b["mapper_type"] in wanted and b["board_id"]]


def get_board_ids_by_mapper_type(*mapper_types: str) -> set[str]:
    return {b["board_id"] for b in get_boards_by_mapper_type(*mapper_types) if b["board_id"]}


def get_board_ids_by_category(*categories: str) -> set[str]:
    wanted = {c for c in categories if c}
    return {
        b["board_id"]
        for b in get_all_boards()
        if b["category"] in wanted and b["board_id"]
    }


def get_board_ids_by_keys(*board_keys: str) -> set[str]:
    wanted = {k for k in board_keys if k}
    return {
        b["board_id"]
        for b in get_all_boards()
        if b["board_key"] in wanted and b["board_id"]
    }


def get_file_board_ids_from_config() -> list[str]:
    board_ids = get_board_ids_by_mapper_type("file_metadata", "ai_locate_file")
    # Contract Status 2 is both a contract mapper and a file board.
    board_ids |= get_board_ids_by_keys("contract_status_2")
    return sorted(board_ids)


def get_cycle_board_map() -> dict[str, str]:
    """Return legacy cycle_id -> board_id mapping for cycle endpoints."""
    result: dict[str, str] = {}
    for board in get_all_boards():
        env_var = board.get("env_var_name") or ""
        # GCED startup cycle mappings should prefer the runtime env var over
        # board_config.monday_board_id because board_config can contain stale
        # historical board ids from older seed data.
        board_id = os.getenv(env_var, "").strip() or board["board_id"]
        if not board_id:
            continue
        if env_var.startswith("MONDAY_BOARD_GCED_MFTF25_CYCLE") and env_var.endswith("_ID"):
            cycle = env_var.removeprefix("MONDAY_BOARD_GCED_MFTF25_CYCLE").removesuffix("_ID")
            if cycle.isdigit():
                result[f"gced_cycle{cycle}"] = board_id
    return result


def upsert_board_config(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {k: payload.get(k) for k in BOARD_CONFIG_COLUMNS if k in payload}
    if not allowed.get("board_key"):
        raise ValueError("board_key is required")
    required = ["label", "category"]
    missing = [k for k in required if not allowed.get(k)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    cols = list(allowed.keys())
    placeholders = ["%s"] * len(cols)
    update_cols = [c for c in cols if c != "board_key"]
    assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    if assignments:
        assignments += ", updated_at = now()"
    else:
        assignments = "updated_at = now()"

    sql = f"""
        INSERT INTO master_dashboard.board_config ({', '.join(cols)})
        VALUES ({', '.join(placeholders)})
        ON CONFLICT (board_key) DO UPDATE SET {assignments}
        RETURNING board_key, label, category, year, display_order, is_active,
                  monday_board_id, env_var_name, mapper_type
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(allowed[c] for c in cols))
        row = cur.fetchone()
    return _serialize_board(dict(zip([
        "board_key", "label", "category", "year", "display_order", "is_active",
        "monday_board_id", "env_var_name", "mapper_type",
    ], row)))


def update_board_config(board_key: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    updates = {k: payload[k] for k in BOARD_CONFIG_COLUMNS - {"board_key"} if k in payload}
    if not updates:
        raise ValueError("No supported fields to update")

    assignments = ", ".join(f"{k} = %s" for k in updates)
    sql = f"""
        UPDATE master_dashboard.board_config
        SET {assignments}, updated_at = now()
        WHERE board_key = %s
        RETURNING board_key, label, category, year, display_order, is_active,
                  monday_board_id, env_var_name, mapper_type
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (*updates.values(), board_key))
        row = cur.fetchone()
    if not row:
        return None
    return _serialize_board(dict(zip([
        "board_key", "label", "category", "year", "display_order", "is_active",
        "monday_board_id", "env_var_name", "mapper_type",
    ], row)))
