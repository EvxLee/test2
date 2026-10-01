# backend/product/api/display/core/db.py
import os
from contextlib import contextmanager
import psycopg
from psycopg import sql as psycopg_sql
from psycopg.rows import dict_row

def _normalize_dsn(dsn: str) -> str:
    if not dsn:
        return dsn
    s = dsn.strip()
    if s.startswith("postgres://"):
        s = "postgresql://" + s[len("postgres://"):]
    if s.startswith("postgresql+psycopg://"):
        s = "postgresql://" + s[len("postgresql+psycopg://"):]
    if s.startswith("postgresql+psycopg2://"):
        s = "postgresql://" + s[len("postgresql+psycopg2://"):]
    if s.startswith("postgresql+asyncpg://"):
        s = "postgresql://" + s[len("postgresql+asyncpg://"):]
    return s

_raw = os.getenv("ATLAS_PG_DSN") or os.getenv("DATABASE_URL") or "postgresql://atlas:changeme@db:5432/atlas"
PG_DSN = _normalize_dsn(_raw)

@contextmanager
def get_conn():
    conn = psycopg.connect(PG_DSN, autocommit=True)
    try:
        yield conn
    finally:
        try: conn.close()
        except Exception: pass

def fetch_all(sql: str, params: tuple = ()):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def fetch_one(sql: str, params: tuple = ()):
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchone()

def stream_copy(sql: str, params: tuple = ()):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        for row in cur:
            yield row

def quote_ident(ident: str) -> str:
    if not ident:
        raise ValueError("empty identifier")
    return psycopg_sql.Identifier(ident).as_string(None)
