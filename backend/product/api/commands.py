import click
import json
import uuid
import sys
from datetime import datetime
from flask.cli import AppGroup
from database.db import SessionLocal
from display.core.db import fetch_all as db_fetch_all, get_conn
from boards_registry import BOARD_REGISTRY

from monday_ingest.clients import fetch_live_bundle
from monday_ingest.staging import ensure_staging, start_run, stage_items, stage_files
from monday_ingest.load import ensure_finals, load_boards, load_items_bundle, load_files
from monday_ingest.transform import parse_item_payload

from db.core_mapping import map_monday_to_core
from chat.embed_documents import (
    embed_and_store,
    fetch_projects,
    fetch_organizations,
    fetch_pitchbook_deals,
    fetch_pitchbook_companies,
    fetch_monday_items,
    fetch_contracts,
    fetch_documents,
    fetch_files,
)
from chat.llm_client import get_embedding_client

monday_cli = AppGroup('monday')

@monday_cli.command('pull')
@click.option('--board', '-b', multiple=True, help='Board key from registry (e.g. gced_cycle4) or raw ID. If not provided, pulls all registered boards.')
@click.option('--handle-deletes', default='soft', type=click.Choice(['soft', 'hard']), help='How to handle deleted items.')
@click.option('--dry-run', is_flag=True, help='Run without committing changes.')
def pull_monday(board, handle_deletes, dry_run):
    """Pull data from Monday.com and ingest into Atlas."""

    # Determine board IDs to pull
    board_ids = []
    if not board:
        # Pull all from registry
        print(f"Fetching all {len(BOARD_REGISTRY)} boards from registry...")
        for key, (_, board_id) in BOARD_REGISTRY.items():
            if board_id:
                board_ids.append(board_id)
            else:
                print(f"WARNING: No board ID for board {key}", file=sys.stderr)
    else:
        # Resolve provided keys or IDs
        for b in board:
            if b in BOARD_REGISTRY:
                _, board_id = BOARD_REGISTRY[b]
                if board_id:
                    board_ids.append(board_id)
                else:
                    print(f"WARNING: No board ID for board {b}", file=sys.stderr)
            else:
                # Assume raw ID
                board_ids.append(b)

    if not board_ids:
        print("No valid board IDs found to process.")
        return

    print(f"Starting ingest for {len(board_ids)} boards: {board_ids}")

    db = SessionLocal()
    conn = db.bind.raw_connection()
    cur = conn.cursor()
    run_id = uuid.uuid4()

    try:
        # Setup
        try:
            ensure_staging(cur)
            ensure_finals(cur)
            conn.commit()
        except NotImplementedError:
            pass

        try:
            start_run(cur, run_id)
            conn.commit()
        except NotImplementedError:
            pass

        for bid in board_ids:
            print(f"Processing board {bid}...")
            try:
                # Fetch
                try:
                    bundle = fetch_live_bundle(bid)
                except NotImplementedError:
                    print(f"  - Fetch failed (NotImplemented), skipping.")
                    continue
                except Exception as e:
                    print(f"  - Fetch failed: {e}")
                    continue

                items_payload = bundle.get("items") or []
                subitems_payload = bundle.get("subitems") or []
                files_payload = bundle.get("files") or []
                all_items_payload = list(items_payload) + list(subitems_payload)

                print(f"  - Fetched {len(items_payload)} items, {len(subitems_payload)} subitems, {len(files_payload)} files.")

                # Stage items
                staged = 0
                try:
                    staged = stage_items(cur, run_id, all_items_payload, bid)
                    conn.commit()
                    print(f"  - Staged {staged} items.")
                except NotImplementedError:
                    pass

                # Stage files
                staged_files = 0
                try:
                    staged_files = stage_files(cur, run_id, files_payload)
                    conn.commit()
                    print(f"  - Staged {staged_files} files.")
                except Exception as e:
                    print(f"  - WARNING: Failed to stage files: {e}")

                # Load board record first (required by FK on monday.items)
                board_payload = bundle.get("board") or {"id": bid}
                load_boards(cur, board_payload)
                conn.commit()

                # Load items
                changes = load_items_bundle(
                    cur,
                    run_id,
                    bid,
                    all_items_payload,
                    parse_item_payload,
                    handle_deletes=handle_deletes
                ) or {"ins": 0, "upd": 0, "del": 0, "name_upd": 0}

                print(f"  - Load items results: {changes}")

                # Load item properties
                all_properties = []
                for item in all_items_payload:
                    try:
                        _, props, _ = parse_item_payload(item)
                        all_properties.extend(props)
                    except Exception:
                        pass
                if all_properties:
                    cur.executemany("""
                        INSERT INTO monday.item_properties
                            (monday_item_id, column_id, value_text, value_date, value_number, raw_json)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (monday_item_id, column_id) DO UPDATE
                            SET value_text = EXCLUDED.value_text,
                                value_date = EXCLUDED.value_date,
                                value_number = EXCLUDED.value_number,
                                raw_json = EXCLUDED.raw_json
                    """, all_properties)
                    conn.commit()
                    print(f"  - Loaded {len(all_properties)} item properties.")

                # Load files (with item metadata for enrichment)
                file_changes = {}
                try:
                    file_changes = load_files(cur, bid, files_payload, items_payload) or {"ins": 0, "upd": 0}
                    print(f"  - Load files results: {file_changes}")
                except Exception as e:
                    print(f"  - WARNING: Failed to load files: {e}")

                if not dry_run:
                    conn.commit()
                else:
                    conn.rollback()
                    print("  - Dry run: Rolled back changes.")

            except Exception as e:
                conn.rollback()
                print(f"ERROR processing board {bid}: {e}", file=sys.stderr)

    finally:
        cur.close()
        conn.close()
        db.close()


@monday_cli.command('map')
@click.option('--board', '-b', multiple=True, help='Board ID(s) to map. If not provided, maps all known boards.')
@click.option('--no-embed', is_flag=True, help='Skip embedding generation after mapping.')
def map_monday(board, no_embed):
    """Map ingested Monday data into core Atlas tables, then regenerate embeddings."""
    db = SessionLocal()
    conn = db.bind.raw_connection()
    try:
        board_ids = list(board) if board else None
        map_monday_to_core(conn, board_ids=board_ids)
        print("Mapping complete.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR during mapping: {e}", file=sys.stderr)
        return
    finally:
        conn.close()
        db.close()

    if not no_embed:
        _run_embed()


@monday_cli.command('embed')
@click.option('--source', default='all',
              type=click.Choice([
                  'projects',
                  'organizations',
                  'pitchbook',
                  'pitchbook_companies',
                  'monday_items',
                  'contracts',
                  'documents',
                  'files',
                  'all',
              ]),
              help='Data source to embed (default: all).')
@click.option('--no-incremental', 'no_incremental', is_flag=True, help='Force full re-embed, ignoring last run timestamp.')
def embed_monday(source, no_incremental):
    """Regenerate embeddings for core Atlas data."""
    _run_embed(source=source, incremental=not no_incremental)


def _get_last_run(source_type: str) -> datetime | None:
    rows = db_fetch_all(
        "SELECT last_run_at FROM llm.embedding_runs WHERE source_type = %s",
        (source_type,)
    )
    return rows[0]["last_run_at"] if rows else None


def _record_run(source_type: str, chunks_processed: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO llm.embedding_runs (source_type, last_run_at, chunks_processed)
                VALUES (%s, now(), %s)
                ON CONFLICT (source_type) DO UPDATE
                    SET last_run_at = now(),
                        chunks_processed = EXCLUDED.chunks_processed
            """, (source_type, chunks_processed))


def _run_embed(source: str = 'all', incremental: bool = True) -> None:
    """Shared embedding logic used by both 'map' and 'embed' commands.

    First live run after deployment must use --no-incremental to seed timestamps.
    """
    try:
        embedding_client = get_embedding_client()
    except Exception as e:
        print(f"ERROR: Could not initialise embedding client: {e}", file=sys.stderr)
        return

    sources = {
        'projects': (fetch_projects, True),
        'organizations': (fetch_organizations, True),
        'pitchbook': (fetch_pitchbook_deals, False),
        'pitchbook_companies': (fetch_pitchbook_companies, True),
        'monday_items': (fetch_monday_items, True),
        'contracts': (fetch_contracts, True),
        'documents': (fetch_documents, True),
        'files': (fetch_files, True),
    }
    selected = list(sources.keys()) if source == 'all' else [source]

    total = {"processed": 0, "errors": 0, "skipped": 0}
    for name in selected:
        fetch_fn, supports_since = sources[name]
        since = _get_last_run(name) if incremental and supports_since else None
        if since:
            print(f"[EMBED] {name}: incremental since {since.isoformat()}", flush=True)
        else:
            print(f"[EMBED] {name}: full scan", flush=True)
        docs = fetch_fn(since=since) if supports_since else fetch_fn()
        stats = embed_and_store(docs, embedding_client)
        _record_run(name, stats["processed"])
        for k in total:
            total[k] += stats[k]
        print(f"[EMBED] {name}: {stats}", flush=True)

    print(f"[EMBED] Complete: {total}", flush=True)
