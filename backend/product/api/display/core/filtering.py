import re
from typing import List, Tuple, Dict, Any
from .db import quote_ident

OPS = {
    "eq": "=",
    "neq": "!=",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
    "like": "LIKE",
    "ilike": "ILIKE",
    "in": "IN",
    "notin": "NOT IN",
    "isnull": "IS NULL",
    "notnull": "IS NOT NULL",
    "contains": "@>",
}

FILTER_RX_TRIPLE = re.compile(r"^([^:]+):([^:]+):(.+)$")
FILTER_RX_EQ     = re.compile(r"^([^=]+)=(.+)$")

def parse_filter_item(item: str) -> Tuple[str, str, str]:
    item = item.strip()
    m = FILTER_RX_TRIPLE.match(item)
    if m:
        return m.group(1), m.group(2).lower(), m.group(3)
    m = FILTER_RX_EQ.match(item)
    if m:
        return m.group(1), "eq", m.group(2)
    raise ValueError(f"Bad filter: {item}")

def build_search_clause(q: str, searchable_cols: List[str]) -> Tuple[str, List[Any]]:
    if not q or not searchable_cols:
        return "", []
    clauses, params = [], []
    for c in searchable_cols:
        clauses.append(f"{quote_ident(c)} ILIKE %s")
        params.append(f"%{q}%")
    return "(" + " OR ".join(clauses) + ")", params

def build_filters(filter_items: List[str], allowed_cols: List[str]) -> Tuple[str, List[Any]]:
    if not filter_items:
        return "", []
    clauses, params = [], []
    allowed = set(allowed_cols)
    for it in filter_items:
        col, op, val = parse_filter_item(it)
        if col not in allowed:
            continue
        if op not in OPS:
            continue
        sqlop = OPS[op]
        col_sql = quote_ident(col)

        if op in ("isnull", "notnull"):
            clauses.append(f"{col_sql} {sqlop}")
        elif op in ("in", "notin"):
            vals = [v.strip() for v in val.split(",")]
            placeholders = ",".join(["%s"] * len(vals))
            clauses.append(f"{col_sql} {sqlop} ({placeholders})")
            params.extend(vals)
        elif op == "contains":
            clauses.append(f"{col_sql} {sqlop} %s")
            params.append(val)
        else:
            clauses.append(f"{col_sql} {sqlop} %s")
            params.append(val)
    if not clauses:
        return "", []
    return "(" + " AND ".join(clauses) + ")", params

def build_sort(sort_csv: str, existing_cols: List[str]) -> List[Tuple[str, str]]:
    if not sort_csv:
        return []
    out = []
    cols = set(existing_cols)
    for token in [t.strip() for t in sort_csv.split(",") if t.strip()]:
        if token.startswith("-"):
            col, direction = token[1:], "DESC"
        else:
            col, direction = token, "ASC"
        if col in cols:
            out.append((col, direction))
    return out
