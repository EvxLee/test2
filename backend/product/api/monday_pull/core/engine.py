from typing import Dict, Any, List
from .client import gql
from .decoders import build_label_maps, decode_value
from .assets import fetch_assets

ITEM_FRAGMENT = """
id
name
group { id title }
created_at
updated_at
creator { id }
column_values {
  id text value type
  ... on BoardRelationValue {
    display_value
    linked_items { id name }
  }
}
subitems {
  id
  name
  created_at
  updated_at
  creator { id }
  column_values {
    id text value type
    ... on BoardRelationValue {
      display_value
      linked_items { id name }
    }
  }
}
"""

def get_schema(board_id: str) -> tuple[list[dict], list[dict], str]:
    """
    Fetch columns, groups, and board name for a single board id.
    Raises a clear error if the board isn't found / accessible.
    """
    query = """
    query ($board_id: [ID!]) {
      boards(ids: $board_id) {
        id
        name
        columns { id title type settings_str }
        groups  { id title }
      }
    }
    """
    data = gql(query, {"board_id": [str(board_id)]})
    boards = data.get("boards") or []
    if not boards:
        raise ValueError(
            f"No board returned for id={board_id}. "
            "Check the ID and that your API token has access to this board."
        )
    b = boards[0]
    return b["columns"], b["groups"], b["name"]

def iter_items(board_id: str):
    cursor = None
    q = f"""
    query($board_id:[ID!], $cursor: String) {{
      boards(ids: $board_id) {{
        items_page(limit:100, cursor:$cursor) {{
          items {{ {ITEM_FRAGMENT} }}
          cursor
        }}
      }}
    }}
    """
    while True:
        data = gql(q, {"board_id": [str(board_id)], "cursor": cursor})
        boards = data.get("boards") or []
        if not boards:
            break
        page = boards[0].get("items_page") or {}
        for it in page.get("items", []):
            yield it
        cursor = page.get("cursor")
        if not cursor:
            break

def pull_board(board_id: str, config: dict) -> dict:
    excludes = set(config.get("excludes", []))
    overrides = config.get("overrides", {})

    columns, groups, board_name = get_schema(board_id)
    label_maps = build_label_maps(columns)
    column_title_map = {col["id"]: col["title"] for col in columns}

    items_out, subitems_out, column_values_out, links_out = [], [], [], []
    file_asset_ids: List[str] = []

    def record_column_values(item_id: str, cvs: list[dict]):
        nonlocal file_asset_ids
        for cv in cvs:
            title = column_title_map.get(cv["id"], cv["id"])
            if (title in excludes) or (cv["id"] in excludes):
                continue
            dec = decode_value(cv | {"title": title}, label_maps, overrides)
            column_values_out.append({
                "item_id": item_id,
                "column_id": cv["id"],
                "title": title,
                "column_title": title,
                **dec
            })
            if dec["type"] == "file":
                file_asset_ids.extend(dec["parsed"].get("asset_ids") or [])
            if dec["type"] in ("connect_boards","board_relation","link_to_item"):
                for l in dec["parsed"].get("linked_items", []):
                    links_out.append({
                        "item_id": item_id,
                        "column_id": cv["id"],
                        "linked_item_id": l["linked_item_id"],
                    })

    for it in iter_items(board_id):
        items_out.append({
            "item_id": str(it["id"]),
            "name": it["name"],
            "group_id": it["group"]["id"] if it.get("group") else None,
            "group_title": it["group"]["title"] if it.get("group") else None,
            "parent_item_id": None,
            "created_at": it.get("created_at"),
            "updated_at": it.get("updated_at"),
            "creator_id": (it.get("creator") or {}).get("id"),
        })
        record_column_values(str(it["id"]), it.get("column_values", []))

        for si in it.get("subitems", []):
            subitems_out.append({
                "item_id": str(si["id"]),
                "name": si["name"],
                "group_id": None,
                "group_title": None,
                "parent_item_id": str(it["id"]),
                "created_at": si.get("created_at"),
                "updated_at": si.get("updated_at"),
                "creator_id": (si.get("creator") or {}).get("id"),
            })
            record_column_values(str(si["id"]), si.get("column_values", []))

    assets = fetch_assets(sorted(set(file_asset_ids)))
    files_out = []
    for cv in column_values_out:
        if cv["type"] == "file":
            for aid in (cv["parsed"].get("asset_ids") or []):
                a = assets.get(str(aid))
                if a:
                    files_out.append({
                        "asset_id": str(a["id"]),
                        "item_id": cv["item_id"],
                        "column_id": cv["column_id"],
                        "file_name": a.get("name"),
                        "public_url": a.get("public_url") or a.get("url"),
                    })

    return {
        "board": {"id": str(board_id), "name": board_name},
        "columns": columns,
        "groups": groups,
        "label_maps": label_maps,
        "items": items_out,
        "subitems": subitems_out,
        "column_values": column_values_out,
        "files": files_out,
        "item_links": links_out,
    }
