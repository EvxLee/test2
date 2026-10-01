#!/usr/bin/env python3
"""
monday_ingest/ingest_monday_files.py — File ingestion script for Monday.com boards.

Fetches board data from Monday.com, loads file metadata into monday.files,
and uploads the file bytes to DO Spaces (sets spaces_key on each row).

Usage:
    # Ingest all configured file boards from master_dashboard.board_config
    python ingest_monday_files.py

    # Ingest a specific board by ID
    python ingest_monday_files.py <board_id>

Boards with file attachments are configured via master_dashboard.board_config.
"""
import sys
import os
import uuid

# Ensure the api/ root is on the path regardless of where this script is invoked from.
_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_DIR)
os.chdir(_API_DIR)

from files.spaces import upload_monday_files
from board_config_db import get_board_ids_by_mapper_type
from monday_ingest.clients import fetch_live_bundle, get_file_board_ids
from monday_ingest.staging import ensure_staging, start_run, stage_items, stage_files
from monday_ingest.load import ensure_finals, load_boards, load_items_bundle, load_files
from monday_ingest.transform import parse_item_payload
from database.db import SessionLocal


def ingest_board(board_id: str) -> bool:
    """Ingest a single board: metadata → items → file metadata → Spaces upload."""
    print(f'\n{"="*60}')
    print(f'Starting ingestion for board: {board_id}')
    print(f'{"="*60}\n')

    db = SessionLocal()
    conn = db.bind.raw_connection()
    cur = conn.cursor()
    run_id = uuid.uuid4()

    success = False
    try:
        # Setup tables
        print('Setting up database tables...')
        ensure_staging(cur)
        ensure_finals(cur)
        conn.commit()
        print('Tables ready\n')

        # Start run tracking
        start_run(cur, run_id)
        conn.commit()

        # Fetch data from Monday.com
        print('Fetching data from Monday.com...')
        bundle = fetch_live_bundle(board_id)

        board_payload = bundle.get('board', {})
        items = bundle.get('items', [])
        files = bundle.get('files', [])

        board_name = board_payload.get('name', 'Unknown')
        print(f'Board: {board_name}')
        print(f'Items: {len(items)}')
        print(f'Files: {len(files)}\n')

        if not files:
            print('No files found on this board')
            return True

        # Step 1: Load board metadata
        print('Step 1/4: Loading board metadata...')
        load_boards(cur, board_payload)
        conn.commit()
        print(f'Board "{board_name}" loaded\n')

        # Step 2: Load items
        print('Step 2/4: Loading items...')
        item_changes = load_items_bundle(
            cur, run_id, board_id, items,
            parse_item_payload, handle_deletes='soft'
        )
        conn.commit()
        print(f'Items: {item_changes}\n')

        # Step 3: Load file metadata into monday.files
        print('Step 3/4: Loading file metadata...')
        file_changes = load_files(cur, board_id, files)
        conn.commit()
        print(f'File metadata: {file_changes}\n')

        # Step 4: Upload file bytes to DO Spaces
        print('Step 4/4: Uploading files to DO Spaces...')
        spaces_result = upload_monday_files(cur, conn, board_id, files)
        print(f'Spaces: {spaces_result}\n')

        # Step 5: Embed files for the AI Locate board
        if board_id in get_board_ids_by_mapper_type("ai_locate_file", "file_metadata"):
            print('Step 5/5: Generating embeddings for AI Locate board...')
            try:
                from chat.embed_documents import fetch_files, embed_and_store
                from chat.llm_client import get_embedding_client
                embedding_client = get_embedding_client()
                stats = embed_and_store(fetch_files(board_id=board_id), embedding_client)
                print(f'Embeddings: {stats}\n')
            except Exception as embed_err:
                print(f'Warning: embedding step failed (search may be stale): {embed_err}\n')

        # Verify
        print('Verifying data...')
        cur.execute("SELECT COUNT(*) FROM monday.files WHERE board_id = %s", (board_id,))
        file_count = cur.fetchone()[0]
        print(f'Files in database: {file_count}')

        if file_count > 0:
            cur.execute(
                """
                SELECT file_name, spaces_key IS NOT NULL AS in_spaces
                FROM monday.files
                WHERE board_id = %s
                LIMIT 3
                """,
                (board_id,),
            )
            print('\nSample files:')
            for fname, in_spaces in cur.fetchall():
                status = 'in Spaces' if in_spaces else 'metadata only'
                print(f'  - {fname} ({status})')

        success = True
        print(f'\n{"="*60}')
        print('INGESTION SUCCESSFUL!')
        print(f'{"="*60}\n')

    except Exception as e:
        print(f'\n{"="*60}')
        print('ERROR during ingestion:')
        print(f'{"="*60}')
        print(f'{e}\n')
        import traceback
        traceback.print_exc()
        print('\nRolling back transaction...')
        conn.rollback()

    finally:
        cur.close()
        conn.close()
        db.close()

    return success


if __name__ == '__main__':
    if len(sys.argv) > 1:
        board_ids = [sys.argv[1]]
    else:
        board_ids = get_file_board_ids()
        if not board_ids:
            print(
                'No file board IDs configured. '
                f'Set one or more of: {", ".join(FILE_BOARD_ENV_VARS)}'
            )
            sys.exit(1)

    all_success = True
    for bid in board_ids:
        ok = ingest_board(bid)
        all_success = all_success and ok

    sys.exit(0 if all_success else 1)
