"""
transform.py — Map JSON payloads to typed rows
"""
import json
from typing import Any, Dict, List, Tuple

ItemRow = Dict[str, Any]
PropRow = Tuple[str, str, str | None, Any | None, float | None, Dict[str, Any]]
AssigneeRow = Tuple[str, str]

def parse_item_payload(p: Dict[str, Any]) -> Tuple[ItemRow, List[PropRow], List[AssigneeRow]]:
    monday_id = str(p.get("id") or p.get("item_id") or "")
    if not monday_id:
        return {}, [], []

    name = p.get("name")
    board_id = str((p.get("board") or {}).get("id") or p.get("board_id") or "") or None
    group_id = str((p.get("group") or {}).get("id") or p.get("group_id") or "") or None
    created_at = p.get("created_at")
    updated_at = p.get("updated_at")

    # --- Base item row (for monday.items)
    item_row: ItemRow = {
        "monday_item_id": monday_id,
        "board_id": board_id,
        "name": name,
        "group_id": group_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "raw_json": json.dumps(p, ensure_ascii=False),
    }

    # --- Properties (extract from column_values OR top-level keys)
    properties: List[PropRow] = []
    columns = p.get("column_values") or []

    # Fallback: if no column_values, map top-level fields
    if not columns:
        for k, v in p.items():
            if k not in {"id", "item_id", "board_id", "group_id", "name", "created_at", "updated_at", "raw_json"}:
                properties.append((monday_id, k, str(v)[:255], None, None, json.dumps({k: v})))
    else:
        for col in columns:
            col_id = str(col.get("id") or col.get("column_id") or "")
            if not col_id:
                continue
            parsed = col.get("parsed") or {}
            text_val = (
                col.get("raw_text")
                or parsed.get("text")
                or col.get("text")
                or ""
            ).strip() or None
            # Extract numeric value from parsed.number or by parsing the text
            num_val = parsed.get("number")
            if num_val is None and text_val:
                try:
                    num_val = float(text_val)
                except (ValueError, TypeError):
                    num_val = None
            properties.append((
                monday_id,
                col_id,
                text_val,
                None,
                num_val,
                json.dumps(col),
            ))

    # --- Assignees (support both assignees[] and creator_id)
    assignees: List[AssigneeRow] = []
    if "assignees" in p:
        for a in p["assignees"]:
            uid = str(a.get("id") or "").strip()
            if uid:
                assignees.append((monday_id, uid))
    elif "creator_id" in p:
        assignees.append((monday_id, str(p["creator_id"])))

    return item_row, properties, assignees
