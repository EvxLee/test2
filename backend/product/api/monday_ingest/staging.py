"""
staging.py — DDL + run tracking + staging inserts
"""
import json
from typing import Any, List
from uuid import UUID


def ensure_staging(cur) -> None:
    """
    Create schemas/tables if missing.
    """
    cur.execute("CREATE SCHEMA IF NOT EXISTS monday_staging;")

    # Run tracking table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday_staging.ingestion_runs (
            run_id UUID PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            finished_at TIMESTAMPTZ NULL,
            summary_jsonb JSONB
        );
    """)

    # Raw JSON item storage
    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday_staging.items_json (
            run_id UUID REFERENCES monday_staging.ingestion_runs(run_id) ON DELETE CASCADE,
            item_id TEXT NOT NULL,
            payload_jsonb JSONB NOT NULL,
            PRIMARY KEY (run_id, item_id)
        );
    """)

    # Raw JSON file storage (asset_id keyed)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS monday_staging.files_json (
            run_id  UUID REFERENCES monday_staging.ingestion_runs(run_id) ON DELETE CASCADE,
            item_id TEXT NOT NULL,
            file_id TEXT NOT NULL,
            payload_jsonb JSONB NOT NULL,
            PRIMARY KEY (run_id, item_id, file_id)
        );
    """)


def start_run(cur, run_id: UUID) -> None:
    """
    Insert (run_id, status='running', started_at=now()).
    """
    cur.execute(
        """
        INSERT INTO monday_staging.ingestion_runs (run_id, status, started_at)
        VALUES (%s, 'running', NOW())
        ON CONFLICT (run_id) DO NOTHING;
        """,
        (str(run_id),),
    )


def finish_run(cur, run_id: UUID, status: str, summary_counts: Any) -> None:
    """
    Update the run row: status, finished_at=now(), summary_jsonb=summary_counts.
    """
    summary_json = json.dumps(summary_counts or {}, ensure_ascii=False)
    cur.execute(
        """
        UPDATE monday_staging.ingestion_runs
           SET status = %s,
               finished_at = NOW(),
               summary_jsonb = %s
         WHERE run_id = %s;
        """,
        (status, summary_json, str(run_id)),
    )


def stage_items(cur, run_id: UUID, items: List[dict], board_id: str) -> int:
    """
    Stage both top-level items AND their subitems into monday_staging.items_json.
    """
    print(
        "DEBUG stage_items: got",
        len(items),
        "items. Example keys:",
        list(items[0].keys()) if items else "NO ITEMS",
        flush=True,
    )

    if not items:
        return 0

    rows: list[tuple[str, str, str]] = []

    for it in items:
        raw_id = it.get("id") or it.get("item_id") or it.get("uuid") or it.get("itemId")
        if not raw_id:
            continue
        parent_id = str(raw_id)

        parent_payload = dict(it)
        parent_payload["board"] = {"id": board_id}

        parent_json = json.dumps(parent_payload, ensure_ascii=False)
        rows.append((str(run_id), parent_id, parent_json))

        subitems = it.get("subitems") or []
        if subitems:
            print(
                f"DEBUG stage_items: parent {parent_id} has {len(subitems)} subitems",
                flush=True,
            )

        for sub in subitems:
            sub_raw_id = sub.get("id") or sub.get("item_id") or sub.get("uuid") or sub.get("itemId")
            if not sub_raw_id:
                continue
            sub_id = str(sub_raw_id)

            sub_payload = dict(sub)
            sub_payload["parent_item_id"] = parent_id
            sub_payload["board"] = {"id": board_id}

            sub_json = json.dumps(sub_payload, ensure_ascii=False)
            rows.append((str(run_id), sub_id, sub_json))

    if not rows:
        return 0

    cur.executemany(
        """
        INSERT INTO monday_staging.items_json (run_id, item_id, payload_jsonb)
        VALUES (%s, %s, %s::jsonb)
        ON CONFLICT (run_id, item_id) DO NOTHING;
        """,
        rows,
    )
    return len(rows)


def stage_files(cur, run_id: UUID, files: List[dict]) -> int:
    """
    Stage files into monday_staging.files_json.
    Each file has: asset_id, item_id, column_id, file_name, public_url
    """
    if not files:
        return 0

    print(
        f"DEBUG stage_files: got {len(files)} files",
        flush=True,
    )

    rows: list[tuple[str, str, str, str]] = []

    for f in files:
        asset_id = f.get("asset_id")
        item_id = f.get("item_id")
        if not asset_id or not item_id:
            continue

        file_json = json.dumps(f, ensure_ascii=False)
        # Primary key: (run_id, item_id, file_id) where file_id is asset_id
        rows.append((str(run_id), str(item_id), str(asset_id), file_json))

    if not rows:
        return 0

    cur.executemany(
        """
        INSERT INTO monday_staging.files_json (run_id, item_id, file_id, payload_jsonb)
        VALUES (%s, %s, %s, %s::jsonb)
        ON CONFLICT (run_id, item_id, file_id) DO NOTHING;
        """,
        rows,
    )
    return len(rows)
