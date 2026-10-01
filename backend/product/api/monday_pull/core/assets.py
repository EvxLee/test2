import json
from .client import gql

def collect_asset_ids_from_value(value_json: str) -> list[str]:
    out: list[str] = []
    if not value_json:
        return out
    try:
        v = json.loads(value_json)
    except Exception:
        return out
    # Files column: {"files":[{"assetId":"12345", ...}]}
    for f in v.get("files", []):
        aid = f.get("assetId") or f.get("id")
        if aid:
            out.append(str(aid))
    return out

def fetch_assets(asset_ids: list[str]) -> dict[str, dict]:
    # If empty, don't call GraphQL at all (avoids non-null constraint)
    if not asset_ids:
        return {}

    assets_map: dict[str, dict] = {}
    q = """
    query ($ids: [ID!]!) {
      assets(ids: $ids) {
        id
        name
        public_url
        url
      }
    }
    """
    CHUNK = 50
    for i in range(0, len(asset_ids), CHUNK):
        ids = [str(x) for x in asset_ids[i:i+CHUNK]]
        data = gql(q, {"ids": ids})["assets"]
        for a in data:
            assets_map[str(a["id"])] = a
    return assets_map
