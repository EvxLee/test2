from typing import List, Set, Tuple
from .db import fetch_all, quote_ident
from .redact import DROP_COLUMNS

def table_exists(schema: str, table: str) -> bool:
    row = fetch_all("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema=%s AND table_name=%s
        LIMIT 1
    """, (schema, table))
    return bool(row)

def get_columns(schema: str, table: str) -> List[Tuple[str, str]]:
    rows = fetch_all("""
      SELECT column_name, data_type
      FROM information_schema.columns
      WHERE table_schema=%s AND table_name=%s
      ORDER BY ordinal_position
    """, (schema, table))
    return [(r["column_name"], r["data_type"]) for r in rows]

def default_safe_columns(schema: str, table: str) -> List[str]:
    cols = get_columns(schema, table)
    safe = [c for c, t in cols if c not in DROP_COLUMNS]
    return safe

def pick_searchable_columns(schema: str, table: str) -> List[str]:
    cols = get_columns(schema, table)
    textlikes = {"character varying", "text", "character", "citext"}
    out = [c for (c, t) in cols if t in textlikes and c not in DROP_COLUMNS]
    return out[:8]

def ensure_sort_keys(schema: str, table: str, requested: List[Tuple[str,str]]) -> List[Tuple[str,str]]:
    cols = {c for c, _ in get_columns(schema, table)}
    out = list(requested)
    if "updated_at" not in [c for c,_ in requested] and "updated_at" in cols:
        out = [("updated_at", "DESC")] + out
    if "id" in cols and "id" not in [c for c,_ in out]:
        out.append(("id","ASC"))
    if not out:
        if "id" in cols: out = [("id","ASC")]
        else: out = [(list(cols)[0], "ASC")]
    return out

def project_column_sql(schema: str, table: str, columns: List[str]) -> str:
    if not columns:
        return "*"
    return ", ".join(quote_ident(c) for c in columns)
