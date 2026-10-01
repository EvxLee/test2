from typing import List, Dict
from .db import fetch_all

def get_attachments(owner_schema: str, owner_table: str, owner_id: str) -> List[Dict]:
    sql = """
      SELECT id, name, mime, url, size_bytes AS size, source, created_at
      FROM core_attachments
      WHERE owner_schema=%s AND owner_table=%s AND owner_id=%s
      ORDER BY created_at DESC, id DESC
      LIMIT 500
    """
    return fetch_all(sql, (owner_schema, owner_table, str(owner_id)))

def get_links(owner_schema: str, owner_table: str, owner_id: str) -> List[Dict]:
    sql = """
      SELECT id, rel, href, COALESCE(label, rel) AS label, created_at
      FROM core_links
      WHERE owner_schema=%s AND owner_table=%s AND owner_id=%s
      ORDER BY created_at DESC, id DESC
      LIMIT 200
    """
    return fetch_all(sql, (owner_schema, owner_table, str(owner_id)))
