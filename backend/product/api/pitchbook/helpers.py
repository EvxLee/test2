from decimal import Decimal
from datetime import datetime
import pandas as pd

NULL_TOKENS = {"", "na", "n/a", "none", "null", "nan"}

def _normalize_nullish(val):
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    if s == "":
        return None
    if s.lower() in NULL_TOKENS:
        return None
    return s


def cast_boolean(val):
    s = _normalize_nullish(val)
    if s is None:
        return None
    s = s.lower()
    if s in {"yes", "y", "1", "true"}:
        return True
    if s in {"no", "n", "0", "false"}:
        return False
    return None


def cast_int(val):
    s = _normalize_nullish(val)
    if s is None:
        return None
    try:
        return int(s.replace(",", ""))
    except Exception:
        return None


def cast_decimal(val):
    s = _normalize_nullish(val)
    if s is None:
        return None
    try:
        return Decimal(s.replace(",", ""))
    except Exception:
        return None


def cast_date(val):
    # Already parsed by pandas as datetime?
    if isinstance(val, datetime):
        return val.date()

    s = _normalize_nullish(val)
    if s is None:
        return None

    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def cast_text(val):
    s = _normalize_nullish(val)
    if s is None:
        return None
    return s

def norm_cell(val) -> str:
    """Normalize a cell value for safe header detection."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    return str(val).strip().lower()


def find_header_idx(raw: pd.DataFrame, needle: str) -> int | None:
    """
    Find first row index where any cell matches `needle`
    (case + whitespace insensitive).
    """
    target = needle.strip().lower()
    norm = raw.apply(lambda col: col.map(norm_cell))
    hits = norm.eq(target).any(axis=1)
    if hits.any():
        return int(hits[hits].index[0])
    return None


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from column headers."""
    df.columns = [str(c).strip() for c in df.columns]
    return df