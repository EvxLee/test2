import json
from typing import Dict, Any
from .assets import collect_asset_ids_from_value


def _coerce_jsonish(v):
    """
    If v is a JSON string like '{"url":"...","text":"..."}', parse it.
    If v is a plain string (e.g., 'https://...'), leave it as-is.
    If v is None or already a dict/list, return as-is.
    """
    if isinstance(v, str):
        s = v.strip()
        if s and (s.startswith('{') or s.startswith('[')):
            try:
                return json.loads(s)
            except Exception:
                return v  # fall back to original string
    return v


def build_label_maps(columns: list[dict]) -> dict[str, dict[str, str]]:
    # Pull human labels out of settings_str for status/dropdown
    out: dict[str, dict[str, str]] = {}
    for c in columns:
        settings_str = c.get("settings_str")
        if not settings_str:
            continue
        try:
            settings = json.loads(settings_str)
        except Exception:
            settings = {}
        labels = settings.get("labels") or {}
        if isinstance(labels, dict) and labels:
            out[c["id"]] = {str(k): v for k, v in labels.items()}
    return out


def decode_value(
    col: dict,
    label_maps: dict[str, dict[str, str]],
    overrides: dict[str, dict] | None = None
) -> dict:
    """Return a consistent dict: {type, raw_text, raw_value, parsed:{...}}"""
    overrides = overrides or {}
    raw_text = col.get("text")
    raw_val  = col.get("value")
    ctype    = col.get("type")
    title_or_id = col.get("title") or col.get("id")

    # Apply overrides by id or title
    for key, spec in overrides.items():
        if key == col.get("id") or key == col.get("title"):
            ctype = spec.get("type", ctype)

    parsed: Dict[str, Any] = {"text": raw_text}

    # SAFELY coerce raw_val which may be JSON string / dict / plain string / None
    v = _coerce_jsonish(raw_val)
    vdict = v if isinstance(v, dict) else {}

    if ctype in ("status", "color"):
        idx = None
        if isinstance(vdict, dict):
            idx = vdict.get("index")
        idx_str = str(idx) if idx is not None else None
        label = label_maps.get(col.get("id", ""), {}).get(idx_str) if idx_str is not None else None
        parsed |= {"index": idx_str, "label": label}

    elif ctype == "dropdown":
        ids = []
        if isinstance(vdict, dict):
            ids = vdict.get("ids", []) or []
        idxs = [str(i) for i in ids]
        parsed |= {
            "indexes": idxs,
            "labels": [label_maps.get(col.get("id", ""), {}).get(i) for i in idxs],
        }

    elif ctype == "link":
        # v can be dict({'url','text'}), JSON string, plain URL string, or None
        url_val = None
        text_val = None
        if isinstance(v, dict):
            url_val = v.get("url")
            text_val = v.get("text") or raw_text
        elif isinstance(v, str):
            # Treat plain string as URL; keep column display text as label if available
            url_val = v or None
            text_val = raw_text or None
        # If v is None/other, leave both as None
        parsed |= {"url": url_val, "text": text_val}

    elif ctype in ("people", "team"):
        persons = []
        if isinstance(vdict, dict):
            persons = vdict.get("personsAndTeams", []) or []
        parsed |= {"personsAndTeams": persons}

    elif ctype in ("connect_boards", "board_relation", "link_to_item"):
        linked_raw = []
        board_ids = None
        display_value = col.get("display_value")            # from BoardRelationValue fragment
        named_linked = col.get("linked_items") or []        # [{id, name}] from fragment
        if isinstance(vdict, dict):
            linked_raw = vdict.get("linkedPulseIds", []) or []
            board_ids = vdict.get("boardIds")
        linked = [{"linked_item_id": str(x.get("linkedPulseId"))} for x in linked_raw if isinstance(x, dict)]
        # Merge names from inline fragment when available
        if named_linked:
            id_to_name = {str(x.get("id")): x.get("name") for x in named_linked if isinstance(x, dict)}
            linked = [
                {"linked_item_id": lnk["linked_item_id"],
                 "name": id_to_name.get(lnk["linked_item_id"])}
                for lnk in linked
            ]
        parsed |= {"linked_items": linked, "boardIds": board_ids, "display_value": display_value}

    elif ctype == "file":
        parsed |= {"asset_ids": collect_asset_ids_from_value(raw_val or "")}

    elif ctype == "date":
        date_val = None
        time_val = None
        if isinstance(vdict, dict):
            date_val = vdict.get("date")
            time_val = vdict.get("time")
        parsed |= {"date": date_val, "time": time_val}

    elif ctype == "numbers":
        num_val = None
        if isinstance(vdict, dict):
            num_val = vdict.get("number")
        parsed |= {"number": num_val}

    elif ctype in ("long_text", "text", "email", "phone"):
        pass

    elif ctype == "json_text":
        try:
            parsed |= {"json": json.loads(raw_text or "{}")}
        except Exception:
            parsed |= {"json": None}

    return {"type": ctype, "raw_text": raw_text, "raw_value": raw_val, "parsed": parsed, "title": title_or_id}
