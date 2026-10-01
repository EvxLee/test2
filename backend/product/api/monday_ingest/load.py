"""
load.py — Final tables & upsert loaders
"""
import json
from uuid import UUID
from typing import Callable, Dict, Any, List, Union, Tuple
from psycopg import Cursor

def ensure_finals(cur) -> None:
    cur.execute("CREATE SCHEMA IF NOT EXISTS monday;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday.boards (
            monday_board_id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMPTZ NULL,
            updated_at TIMESTAMPTZ NULL,
            as_of TIMESTAMPTZ DEFAULT NOW(),
            raw_json JSONB
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday.items (
            monday_item_id TEXT PRIMARY KEY,
            board_id TEXT REFERENCES monday.boards(monday_board_id),
            name TEXT,
            group_id TEXT,
            created_at TIMESTAMPTZ NULL,
            updated_at TIMESTAMPTZ NULL,
            is_active BOOLEAN DEFAULT TRUE,
            deactivated_at TIMESTAMPTZ NULL,
            as_of TIMESTAMPTZ DEFAULT NOW(),
            raw_json JSONB
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday.item_properties (
            monday_item_id TEXT REFERENCES monday.items(monday_item_id),
            column_id TEXT,
            value_text TEXT,
            value_date TIMESTAMPTZ NULL,
            value_number DOUBLE PRECISION NULL,
            raw_json JSONB,
            PRIMARY KEY (monday_item_id, column_id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday.item_assignees (
            monday_item_id TEXT REFERENCES monday.items(monday_item_id),
            monday_user_id TEXT,
            PRIMARY KEY (monday_item_id, monday_user_id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday.files (
            monday_file_id TEXT PRIMARY KEY,
            asset_id TEXT,
            item_id TEXT,
            column_id TEXT,
            board_id TEXT,
            file_name TEXT,
            public_url TEXT,
            spaces_key TEXT,
            category TEXT,
            owner_name TEXT,
            summary TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)


def load_boards(cur, board_payload: Dict[str, Any]) -> None:
    """
    Upsert the single board payload for this ingest.
    Conflict target: monday_board_id.
    Freshness guard: only update if incoming updated_at is newer (or null logic).
    """
    if not board_payload:
        return

    board_id = str(board_payload.get("id") or board_payload.get("board_id"))
    name = board_payload.get("name")
    created_at = board_payload.get("created_at")
    updated_at = board_payload.get("updated_at")
    raw_json = json.dumps(board_payload)

    # Insert or update if fresher
    cur.execute(
        """
        INSERT INTO monday.boards (monday_board_id, name, created_at, updated_at, as_of, raw_json)
        VALUES (%s, %s, %s, %s, NOW(), %s)
        ON CONFLICT (monday_board_id) DO UPDATE
        SET name = EXCLUDED.name,
            created_at = COALESCE(EXCLUDED.created_at, monday.boards.created_at),
            updated_at = CASE
                            WHEN monday.boards.updated_at IS NULL 
                                 OR EXCLUDED.updated_at > monday.boards.updated_at 
                            THEN EXCLUDED.updated_at
                            ELSE monday.boards.updated_at
                         END,
            as_of = NOW(),
            raw_json = EXCLUDED.raw_json;
        """,
        (board_id, name, created_at, updated_at, raw_json)
    )

RecordLike = Union[Dict[str, Any], Tuple[Any, ...], List[Any]]

def load_items_bundle(
    cur: Cursor,
    run_id,
    board_id: str,
    items_payload: List[RecordLike],
    parse_item_payload: Callable[[Dict[str, Any]], Dict[str, Any]],
    handle_deletes: str = "soft",
) -> Dict[str, int]:
    """
    Upsert items for one board and return counts:
      {"ins": n, "upd": n, "del": n, "name_upd": k}

    Accepts either:
      - dict records with keys: monday_item_id, board_id?, name, raw_json
      - tuples/lists: (id, board_id, name, raw_json) OR (id, name, raw_json)
    """

    def _coerce_jsonb(v: Any) -> Any:
        # Allow dict/str/json already; leave as-is and let Postgres cast text->jsonb
        if isinstance(v, (dict, list)):
            return json.dumps(v)  # send as text; Postgres casts to jsonb
        return v

    def _to_record(x: RecordLike) -> Dict[str, Any]:
        # First try parse_item_payload if x looks like a Monday raw item (dict with many keys)
        rec = None
        try:
            if isinstance(x, dict) and ("id" in x or "monday_item_id" in x or "item_id" in x):
                result = parse_item_payload(x)
                # parse_item_payload returns (item_row, properties, assignees) tuple
                rec = result[0] if isinstance(result, tuple) else result
        except Exception:
            rec = None

        if rec is None:
            if isinstance(x, dict):
                mid = x.get("monday_item_id") or x.get("id") or x.get("item_id")
                nm  = x.get("name")
                bid = x.get("board_id") or board_id
                rj  = x.get("raw_json")
                if mid is None:
                    raise ValueError(f"Missing monday_item_id in dict record: {x}")
                return {
                    "monday_item_id": str(mid),
                    "board_id": str(bid) if bid is not None else str(board_id),
                    "name": "(untitled)" if nm is None or str(nm).strip() == "" else str(nm),
                    "raw_json": _coerce_jsonb(rj),
                }

            if isinstance(x, (tuple, list)):
                if len(x) >= 4:
                    mid, bid, nm, rj = x[0], x[1], x[2], x[3]
                elif len(x) == 3:
                    mid, nm, rj = x[0], x[1], x[2]
                    bid = board_id
                else:
                    raise ValueError(f"Tuple/list record must have 3 or 4 values, got {len(x)}: {x}")
                if mid is None:
                    raise ValueError(f"Missing monday_item_id in tuple/list: {x}")
                return {
                    "monday_item_id": str(mid),
                    "board_id": str(bid) if bid is not None else str(board_id),
                    "name": "(untitled)" if nm is None or str(nm).strip() == "" else str(nm),
                    "raw_json": _coerce_jsonb(rj),
                }

            # Unknown type
            raise TypeError(f"Unsupported record type: {type(x).__name__}: {x}")

        # rec came from parse_item_payload
        mid = rec.get("monday_item_id") or rec.get("id")
        nm  = rec.get("name")
        bid = rec.get("board_id") or board_id
        rj  = rec.get("raw_json")
        if mid is None:
            raise ValueError(f"parse_item_payload result missing monday_item_id: {rec}")
        return {
            "monday_item_id": str(mid),
            "board_id": str(bid) if bid is not None else str(board_id),
            "name": "(untitled)" if nm is None or str(nm).strip() == "" else str(nm),
            "raw_json": _coerce_jsonb(rj),
        }

    # Build normalized rows (handle dicts/tuples robustly)
    rows: List[Tuple[str, str, str, Any]] = []
    for i, raw in enumerate(items_payload or []):
        try:
            rec = _to_record(raw)
            rows.append((rec["monday_item_id"], rec["board_id"], rec["name"], rec["raw_json"]))
        except Exception as e:
            # Skip bad record but keep ingesting the rest; you can log if desired
            # print(f"Skip item idx={i}: {e}")
            continue

    if not rows:
        return {"ins": 0, "upd": 0, "del": 0, "name_upd": 0}

    # Temp incoming table
    cur.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _items_incoming (
            monday_item_id text,
            board_id       text,
            name           text,
            raw_json       jsonb
        ) ON COMMIT DROP;
    """)
    cur.execute("TRUNCATE _items_incoming;")

    # Bulk insert incoming via executemany (psycopg3-friendly)
    cur.executemany(
        "INSERT INTO _items_incoming (monday_item_id, board_id, name, raw_json) VALUES (%s, %s, %s, %s)",
        rows,
    )

    # INSERT new rows; count inserts
    cur.execute("""
        WITH ins AS (
            INSERT INTO monday.items AS t (monday_id, board_id, name, raw_json)
            SELECT i.monday_item_id, i.board_id, i.name, i.raw_json
            FROM _items_incoming i
            ON CONFLICT (monday_id) DO NOTHING
            RETURNING 1
        )
        SELECT COUNT(*) FROM ins;
    """)
    (ins_count,) = cur.fetchone()

    # UPDATE changed rows only; count updates and name changes
    cur.execute("""
        WITH upd AS (
            UPDATE monday.items t
            SET
                board_id = i.board_id,
                name     = i.name,
                raw_json = i.raw_json
            FROM _items_incoming i
            WHERE t.monday_id = i.monday_item_id
              AND (
                    t.board_id IS DISTINCT FROM i.board_id
                 OR t.name     IS DISTINCT FROM i.name
                 OR t.raw_json IS DISTINCT FROM i.raw_json
              )
            RETURNING
                t.monday_id,
                i.name AS new_name,
                t.name AS updated_name
        )
        SELECT
            COUNT(*)::int AS upd,
            SUM( (updated_name IS DISTINCT FROM new_name)::int )::int AS name_upd
        FROM upd;
    """)
    upd_count, name_upd = cur.fetchone()

    # Deletions for this board
    if (handle_deletes or "soft").lower() == "hard":
        cur.execute("""
            WITH gone AS (
                DELETE FROM monday.items t
                WHERE t.board_id = %s
                  AND NOT EXISTS (
                      SELECT 1 FROM _items_incoming i
                      WHERE i.monday_item_id = t.monday_id
                        AND i.board_id = t.board_id
                  )
                RETURNING 1
            )
            SELECT COUNT(*) FROM gone;
        """, (str(board_id),))
    else:
        # Soft delete if columns present; otherwise no-op deletions
        try:
            cur.execute("""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='monday' AND table_name='items'
                      AND column_name='is_deleted'
                  ) THEN
                    ALTER TABLE monday.items
                      ADD COLUMN IF NOT EXISTS is_deleted boolean DEFAULT FALSE,
                      ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
                  END IF;
                END $$;
            """)
            cur.execute("""
                WITH gone AS (
                    UPDATE monday.items t
                    SET is_deleted = TRUE, deleted_at = NOW()
                    WHERE t.board_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM _items_incoming i
                          WHERE i.monday_item_id = t.monday_id
                            AND i.board_id = t.board_id
                      )
                    RETURNING 1
                )
                SELECT COUNT(*) FROM gone;
            """, (str(board_id),))
        except Exception:
            cur.execute("SELECT 0;")
    (del_count,) = cur.fetchone()

    return {
        "ins": int(ins_count or 0),
        "upd": int(upd_count or 0),
        "del": int(del_count or 0),
        "name_upd": int(name_upd or 0),
    }


def load_files(cur: Cursor, board_id: str, files_payload: List[Dict[str, Any]], items_payload: List[Dict[str, Any]] = None) -> Dict[str, int]:
    """
    Upsert files for one board into monday.files table.
    Returns counts: {"ins": n, "upd": n}

    Each file has: asset_id, item_id, column_id, file_name, public_url
    If items_payload is provided, enriches files with category, owner, and summary from item metadata.
    """
    if not files_payload:
        return {"ins": 0, "upd": 0}

    print(f"DEBUG load_files: loading {len(files_payload)} files for board {board_id}", flush=True)

    # Build item metadata map if items provided
    item_metadata = {}
    if items_payload:
        for item in items_payload:
            item_id = item.get('item_id') or item.get('id')
            if not item_id:
                continue

            category = item.get('group_title', 'Uncategorized')
            owner = None
            summary = None

            # Extract owner and summary from column_values
            for cv in item.get('column_values', []):
                col_title = cv.get('column_title', '')
                col_type = cv.get('type')

                if col_title == 'Owner' and col_type == 'people':
                    parsed = cv.get('parsed', {})
                    owner = parsed.get('text', 'Unknown')
                elif col_title == 'Summary' and col_type == 'text':
                    parsed = cv.get('parsed', {})
                    summary = parsed.get('text', 'No summary available')

            item_metadata[str(item_id)] = {
                'category': category,
                'owner': owner or 'Unknown',
                'summary': summary or 'No summary available'
            }

    rows: List[Tuple[str, str, str, str, str, str, str, str, str, str]] = []
    for f in files_payload:
        asset_id = f.get("asset_id")
        item_id = f.get("item_id")
        if not asset_id:
            continue

        # Use asset_id as the primary key (monday_file_id)
        file_id = str(asset_id)
        column_id = f.get("column_id") or ""
        file_name = f.get("file_name") or ""
        public_url = f.get("public_url") or ""

        # Get metadata from item if available
        meta = item_metadata.get(str(item_id), {})
        category = meta.get('category', 'Uncategorized')
        owner = meta.get('owner', 'Unknown')
        summary = meta.get('summary', 'No summary available')

        rows.append((
            file_id,
            str(asset_id),
            str(item_id) if item_id else "",
            column_id,
            str(board_id),
            file_name,
            public_url,
            category,
            owner,
            summary,
        ))

    if not rows:
        return {"ins": 0, "upd": 0}

    # Create temp table for incoming files
    cur.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _files_incoming (
            monday_file_id  text,
            asset_id        text,
            item_id         text,
            column_id       text,
            board_id        text,
            file_name       text,
            public_url      text,
            category        text,
            owner_name      text,
            summary         text
        ) ON COMMIT DROP;
    """)
    cur.execute("TRUNCATE _files_incoming;")

    # Insert all incoming files
    cur.executemany(
        """
        INSERT INTO _files_incoming
            (monday_file_id, asset_id, item_id, column_id, board_id, file_name, public_url, category, owner_name, summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """,
        rows
    )

    # Upsert into monday.files
    cur.execute("""
        WITH upserted AS (
            INSERT INTO monday.files
                (monday_file_id, asset_id, item_id, column_id, board_id, file_name, public_url, category, owner_name, summary, updated_at)
            SELECT
                monday_file_id, asset_id, item_id, column_id, board_id, file_name, public_url, category, owner_name, summary, NOW()
            FROM _files_incoming
            ON CONFLICT (monday_file_id) DO UPDATE
            SET asset_id   = EXCLUDED.asset_id,
                item_id    = EXCLUDED.item_id,
                column_id  = EXCLUDED.column_id,
                board_id   = EXCLUDED.board_id,
                file_name  = EXCLUDED.file_name,
                public_url = EXCLUDED.public_url,
                category   = EXCLUDED.category,
                owner_name = EXCLUDED.owner_name,
                summary    = EXCLUDED.summary,
                updated_at = NOW()
            RETURNING
                CASE WHEN monday.files.created_at = NOW() THEN 'ins' ELSE 'upd' END as op
        )
        SELECT
            COUNT(*) FILTER (WHERE op = 'ins') as ins_count,
            COUNT(*) FILTER (WHERE op = 'upd') as upd_count
        FROM upserted;
    """)

    result = cur.fetchone()
    ins_count = result[0] if result else 0
    upd_count = result[1] if result else 0

    print(f"DEBUG load_files: inserted={ins_count}, updated={upd_count}", flush=True)

    return {
        "ins": int(ins_count or 0),
        "upd": int(upd_count or 0),
    }
