from __future__ import annotations
import os
from typing import Any, Callable
try:
    from psycopg import Connection
except Exception:
    Connection = Any  # type: ignore[misc, assignment]

try:
    from board_config_db import (
        get_all_boards,
        get_board_ids_by_mapper_type,
        get_cycle_board_map,
    )
except Exception:
    get_all_boards = None  # type: ignore[assignment]
    get_board_ids_by_mapper_type = None  # type: ignore[assignment]
    get_cycle_board_map = None  # type: ignore[assignment]

def _config_board_ids(*mapper_types: str) -> set[str]:
    if get_board_ids_by_mapper_type is None:
        return set()
    try:
        return get_board_ids_by_mapper_type(*mapper_types)
    except Exception as e:
        print(f"WARNING: failed to load board_config mapper types {mapper_types}: {e}", flush=True)
        return set()


def _env_board_ids(*env_names: str) -> set[str]:
    board_ids: set[str] = set()
    for name in env_names:
        value = os.getenv(name, "").strip().strip('"')
        if value:
            board_ids.add(value)
    return board_ids


def _gced_mftf_board_ids() -> set[str]:
    env_names = [
        *(f"MONDAY_BOARD_GCED_MFTF25_CYCLE{i}_ID" for i in range(1, 8)),
        *(f"MONDAY_BOARD_GCED_MFTF26_CYCLE{i}_ID" for i in range(1, 8)),
    ]
    board_ids = _env_board_ids(*env_names)
    if get_all_boards is not None:
        try:
            for board in get_all_boards():
                env_var = str(board.get("env_var_name") or "")
                if not env_var.startswith(("MONDAY_BOARD_GCED_MFTF25_CYCLE", "MONDAY_BOARD_GCED_MFTF26_CYCLE")):
                    continue
                board_id = str(board.get("board_id") or "").strip()
                if board_id:
                    board_ids.add(board_id)
        except Exception as e:
            print(f"WARNING: failed to load GCED MFTF board_config rows: {e}", flush=True)
    return board_ids


def _canonical_vertical_name(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    normalized = raw.lower().replace(" ", "")
    if normalized in {"ai"}:
        return "AI"
    if normalized in {"cleantech", "clean-tech", "cleantechnology"}:
        return "CleanTech"
    if normalized in {"healthcare", "healthtech", "health-tech"}:
        return "HealthTech"
    return raw


def _canonical_location_row(value: str | None) -> dict[str, str] | None:
    raw = (value or "").strip()
    if not raw:
        return None
    normalized = " ".join(raw.lower().split())
    if normalized == "example city":
        return {
            "display_name": "Example City",
            "city": "Example City",
            "state_region": "Example State",
            "country": "United States",
        }
    if normalized == "example region":
        return {
            "display_name": "Example Region",
            "city": "",
            "state_region": "Example Region",
            "country": "United States",
        }
    return {
        "display_name": raw,
        "city": "",
        "state_region": raw,
        "country": "United States",
    }


def _ensure_project_reference_rows(cur) -> None:
    santa_clara = _canonical_location_row("Example City")
    west_virginia = _canonical_location_row("Example Region")

    cur.execute(
        """
        INSERT INTO master_dashboard.verticals (vertical_name)
        VALUES ('AI'), ('CleanTech'), ('HealthTech')
        ON CONFLICT (vertical_name) DO NOTHING;
        """
    )

    cur.execute(
        """
        INSERT INTO master_dashboard.locations (display_name, city, state_region, country)
        VALUES
            (%s, %s, %s, %s),
            (%s, NULLIF(%s, ''), %s, %s)
        ON CONFLICT (display_name) DO UPDATE
        SET city         = COALESCE(master_dashboard.locations.city, EXCLUDED.city),
            state_region = COALESCE(master_dashboard.locations.state_region, EXCLUDED.state_region),
            country      = COALESCE(master_dashboard.locations.country, EXCLUDED.country),
            updated_at   = NOW();
        """,
        (
            santa_clara["display_name"],
            santa_clara["city"],
            santa_clara["state_region"],
            santa_clara["country"],
            west_virginia["display_name"],
            west_virginia["city"],
            west_virginia["state_region"],
            west_virginia["country"],
        ),
    )


# ---------------------------------------------------------------------------
# Incubation Projects — stage-to-column mapping
# Update placeholder column IDs once confirmed for Stages 2, 4, 5.
# ---------------------------------------------------------------------------
_INCUBATION_PROJECT_STAGE_COLUMNS: dict[str, dict] = {
    "Stage 2": {
        "column_id":    "board_relation_mkn379fk",
        "column_title": "Stage 2 (Idea) Startups",
    },
    "Stage 3": {
        "column_id":    "connect_boards__1",
        "column_title": "Stage 3 (POC) Startups",
    },
    "Stage 4": {
        "column_id":    "board_relation_mkm12tn4",
        "column_title": "Stage 4 (Business Plan) Startups",
    },
    "Stage 5": {
        "column_id":    "board_relation_mkm1sz",
        "column_title": "Stage 5 (Seed) Startups",
    },
    "Stage 6": {
        "column_id":    "board_relation_mkqa4ttv",
        "column_title": "Stage 6 (SpinOff) Startups",
    },
}


def _extract_startup_names_from_relation_column(column_value: dict) -> list[dict]:
    """
    Extract startup rows from a Monday board_relation column value dict.

    Priority order:
      1. linked_items with names  (requires BoardRelationValue fragment in engine)
      2. display_value            (comma/semicolon-separated fallback)
      3. text                     (last resort)

    Returns list of dicts: {startup_monday_item_id, startup_name, source_display_value}
    """
    rows: list[dict] = []

    # Priority 1: linked_items with names
    linked_items = column_value.get("linked_items") or []
    if linked_items:
        seen: set[str] = set()
        for item in linked_items:
            startup_id = item.get("id")
            startup_name = (item.get("name") or "").strip()
            if not startup_name or startup_name.lower() in seen:
                continue
            seen.add(startup_name.lower())
            rows.append({
                "startup_monday_item_id": int(startup_id) if startup_id else None,
                "startup_name": startup_name,
                "source_display_value": column_value.get("display_value") or "",
            })
        if rows:
            return rows

    # Priority 2: display_value
    display = (column_value.get("display_value") or "").strip()
    if display and display.upper() != "N/A":
        seen = set()
        for part in display.replace(";", ",").split(","):
            name = part.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            rows.append({
                "startup_monday_item_id": None,
                "startup_name": name,
                "source_display_value": display,
            })
        if rows:
            return rows

    # Priority 3: text field
    text = (column_value.get("text") or "").strip()
    if text and text.upper() != "N/A":
        seen = set()
        for part in text.replace(";", ",").split(","):
            name = part.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            rows.append({
                "startup_monday_item_id": None,
                "startup_name": name,
                "source_display_value": text,
            })

    return rows

def _backfill_items_board_id_from_raw(conn: Connection) -> None:
    """
    Fill monday.items.board_id using the raw_json payload, if possible.

    We look for:
      - raw_json->'board'->>'id'
      - raw_json->>'boardId'
    and write that into monday.items.board_id where it's currently NULL/empty.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM monday.items
            WHERE board_id IS NOT NULL AND board_id <> ''
        """)
        before = cur.fetchone()[0]
        print(f"[DEBUG] _backfill_items_board_id_from_raw: items with board_id BEFORE = {before}")

        cur.execute("""
            UPDATE monday.items mi
            SET board_id = COALESCE(
                (mi.raw_json->'board'->>'id'),
                (mi.raw_json->>'boardId')
            )
            WHERE (mi.board_id IS NULL OR mi.board_id = '')
              AND (
                mi.raw_json->'board'->>'id' IS NOT NULL
                OR mi.raw_json->>'boardId' IS NOT NULL
              );
        """)

        cur.execute("""
            SELECT COUNT(*)
            FROM monday.items
            WHERE board_id IS NOT NULL AND board_id <> ''
        """)
        after = cur.fetchone()[0]
        print(f"[DEBUG] _backfill_items_board_id_from_raw: items with board_id AFTER = {after}")

def map_monday_to_core(conn: Connection, board_ids: list[str] | None = None) -> None:
    """
    Main mapping entrypoint.

    - Uses master_dashboard.board_config to know which Monday boards map to which core tables.
    - If `board_ids` is provided, only those boards are processed (if registered).
    - Otherwise, all known boards (NVP, Contract Status, GCED MFTF25, Incubation) are processed.
    - IMPORTANT: GCED boards DO NOT populate master_dashboard.projects.
      NVP, Contract Status, Incubation, Incubation Projects, and PJT IT boards
      run the projects pipeline.
    """
    # Ensure we always operate in the right schemas
    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")
        _ensure_project_reference_rows(cur)

    print("=== MAP_MONDAY_TO_CORE STARTED ===", flush=True)

    # --- Resolve board IDs from master_dashboard.board_config ---
    nvp_ids = _config_board_ids("new_venture_proposals")
    cs_ids = _config_board_ids("contract_status")
    korean_ids = _config_board_ids("korean")
    pjt_it_ids = _config_board_ids("pjt_it")

    GCED_BOARD_IDS = _gced_mftf_board_ids()

    INCUBATION_BOARD_IDS = _config_board_ids("incubation")

    incubation_projects_ids = _config_board_ids("incubation_projects")
    ai_locate_file_ids = _config_board_ids("ai_locate_file", "file_metadata")

    # All boards that populate master_dashboard.projects
    PROJECT_BOARD_IDS = (
        nvp_ids
        | cs_ids
        | pjt_it_ids
        | incubation_projects_ids
        | INCUBATION_BOARD_IDS
    )

    # --- Register mappers per board ---
    board_mappers: dict[str, list[tuple[str, Callable[[Connection, str], None]]]] = {}

    def _register(board: str | None, label: str, fn: Callable[[Connection, str], None]) -> None:
        """Attach a mapper function to a specific Monday board."""
        if not board:
            return
        b = str(board)
        mappers = board_mappers.setdefault(b, [])
        if any(existing_label == label for existing_label, _ in mappers):
            return
        mappers.append((label, fn))

    # NVP -> projects + NVP-specific mapping
    for bid in nvp_ids:
        _register(bid, "nvp", _map_nvp)

    # Regional board -> board-specific table only (NO projects pipeline)
    for bid in korean_ids:
        _register(bid, "korean", _map_korean)

    # Contract Status -> projects + contract status mapping
    for bid in cs_ids:
        _register(bid, "contract_status", _map_contract_status)

    # GCED boards -> GCED-specific tables only (NO projects pipeline)
    for gced_bid in GCED_BOARD_IDS:
        _register(gced_bid, "gced_mftf25", _map_gced_mftf25)
        _register(gced_bid, "gced_reviews", _map_gced_reviews)

    # Incubation boards -> projects + incubation-specific mapping
    for inc_bid in INCUBATION_BOARD_IDS:
        _register(inc_bid, "incubation", _map_incubation)

    # Duplicate Project boards -> canonical full project mapper
    for bid in pjt_it_ids:
        _register(bid, "pjt_it", _map_pjt_it)

    # Incubation Projects board is operationally a duplicate of PJT Board IT.
    for bid in incubation_projects_ids:
        _register(bid, "pjt_it", _map_pjt_it)

    # AI Locate a File board -> file metadata only (no projects pipeline)
    for bid in ai_locate_file_ids:
        _register(bid, "ai_locate_file", _map_ai_locate_file)

    # --- Decide which boards to process for this call ---
    if board_ids:
        bids = [str(b) for b in board_ids]
    else:
        bids = list(board_mappers.keys())

    print(
        "[DEBUG] map_monday_to_core: board_ids to process = "
        f"{bids}",
        flush=True,
    )
    print(
        "[DEBUG] map_monday_to_core: configured boards -> "
        f"NVP={list(nvp_ids)}, CS={list(cs_ids)}, GCED={list(GCED_BOARD_IDS)}",
        flush=True,
    )

    # --- Decide whether to run the projects pipeline at all ---
    # Only if this ingest includes at least one "project" board (NVP / CS)
    has_project_boards = any(b in PROJECT_BOARD_IDS for b in bids)

    # Boards that create project rows — CS boards are intentionally excluded.
    # Contract items must NOT become project rows; they reference projects by name.
    CS_BOARD_IDS = set(cs_ids)
    PROJECT_SOURCE_BOARD_IDS = PROJECT_BOARD_IDS - CS_BOARD_IDS

    if has_project_boards:
        # This will prepare the raw projects/people tables from Monday data.
        project_source_board_ids_for_call = (
            PROJECT_SOURCE_BOARD_IDS & set(bids)
            if board_ids
            else PROJECT_SOURCE_BOARD_IDS
        )
        print("[MAP] _upsert_projects_people_raw START", flush=True)
        _upsert_projects_people_raw(conn, project_source_board_ids_for_call)
        conn.commit()
    else:
        print(
            "[DEBUG] map_monday_to_core: "
            "no NVP/ContractStatus boards in this call; "
            "skipping _upsert_projects_people_raw",
            flush=True,
        )

    # --- Run per-board mappers (NVP / CS / GCED) ---
    for bid in bids:
        mappers = board_mappers.get(bid)
        if not mappers:
            print(
                f"[DEBUG] map_monday_to_core: no registered mapper "
                f"for board {bid}, skipping",
                flush=True,
            )
            continue

        for label, fn in mappers:
            print(
                f"[DEBUG] map_monday_to_core: running _map_{label} "
                f"for board {bid}",
                flush=True,
            )
            fn(conn, bid)

    # --- Backfill projects only if we actually had NVP/CS boards ---
    if has_project_boards:
        print("[MAP] _backfill_projects_from_raw START", flush=True)
        _backfill_projects_from_raw(conn)

        # Re-run contract→project linking now that projects are fully backfilled
        print("[MAP] _link_contract_status_to_projects (post-backfill) START", flush=True)
        with conn.cursor() as cur:
            cur.execute("SET search_path TO master_dashboard;")
            _link_contract_status_to_projects(cur)

        print("[MAP] _backfill_project_source_board START", flush=True)
        _backfill_project_source_board(conn)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM master_dashboard.projects
                WHERE source_board IS NOT NULL
                  AND source_board <> ''
                """
            )
            sb_count = cur.fetchone()[0]
            print(
                "[DEBUG] map_monday_to_core: projects with source_board AFTER = "
                f"{sb_count}",
                flush=True,
            )

            cur.execute("SELECT COUNT(*) FROM master_dashboard.core_attachments;")
            att_count = cur.fetchone()[0]
            print(
                "[DEBUG] map_monday_to_core: core_attachments count AFTER = "
                f"{att_count}",
                flush=True,
            )

        conn.commit()
    else:
        # Still commit any GCED-specific changes
        conn.commit()
        print(
            "[DEBUG] map_monday_to_core: project backfill skipped "
            "(no NVP/CS boards in this call)",
            flush=True,
        )

    # Invalidate the summary cache for any GCED cycles whose board was re-ingested.
    try:
        from cycles.queries import cycle_id_for_board_id as _resolve_cycle_id
    except ImportError:
        def _resolve_cycle_id(board_id: str) -> str | None:  # type: ignore[misc]
            if get_cycle_board_map is None:
                return None
            reverse = {bid: cid for cid, bid in get_cycle_board_map().items()}
            return reverse.get(board_id)

    cycle_ids = [cid for cid in (_resolve_cycle_id(b) for b in bids) if cid]
    if cycle_ids:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM cycles.summary_cache WHERE cycle_id = ANY(%s);",
                (cycle_ids,),
            )
        conn.commit()

    print("=== MAP_MONDAY_TO_CORE END ===", flush=True)


def _upsert_projects_people_raw(conn: Connection, project_source_board_ids: set[str]) -> None:
    """
    Seed master_dashboard.projects with one row per Monday item, but ONLY for
    boards that are genuine project sources (NVP, Incubation, PJT IT, Incubation
    Projects).  Contract Status board items must NOT become project rows — those
    items are contracts that reference projects, not projects themselves.
    """
    print("[MAP] _upsert_projects_people_raw START", flush=True)
    board_id_list = list(project_source_board_ids)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO master_dashboard.projects (
                project_code,
                name,
                source_board,
                source_item_id,
                is_ongoing,
                created_at
            )
            SELECT
                CASE
                    WHEN existing_same_source.project_code IS NOT NULL
                        THEN existing_same_source.project_code
                    WHEN existing_code.id IS NULL
                        THEN mi.monday_id::text
                    ELSE mi.board_id::text || ':' || mi.monday_id::text
                END                                          AS project_code,
                COALESCE(NULLIF(mi.name, ''), '(untitled)') AS name,
                mi.board_id::text                           AS source_board,
                mi.monday_id::text                          AS source_item_id,
                TRUE,
                NOW()
            FROM monday.items mi
            LEFT JOIN master_dashboard.projects existing_same_source
              ON existing_same_source.source_board = mi.board_id::text
             AND existing_same_source.source_item_id = mi.monday_id::text
            LEFT JOIN master_dashboard.projects existing_code
              ON existing_code.project_code = mi.monday_id::text
             AND NOT (
                 existing_code.source_board = mi.board_id::text
                 AND existing_code.source_item_id = mi.monday_id::text
             )
            WHERE mi.board_id::text = ANY(%s)
            ON CONFLICT (source_board, source_item_id) DO UPDATE
            SET name           = EXCLUDED.name,
                project_code   = EXCLUDED.project_code,
                is_ongoing     = EXCLUDED.is_ongoing,
                updated_at     = NOW();
        """, (board_id_list,))

        cur.execute("""
            INSERT INTO master_dashboard.people (full_name, email)
            SELECT DISTINCT
                'User ' || ma.monday_user_id,
                ma.monday_user_id || '@monday.local'
            FROM monday.item_assignees ma
            ON CONFLICT (email) DO NOTHING;
        """)

        cur.execute("""
            INSERT INTO master_dashboard.project_owners (project_id, person_id)
            SELECT
                p.id,
                pe.id
            FROM monday.item_assignees ma
            JOIN monday.items mi
              ON mi.monday_id::text = ma.monday_item_id::text
            JOIN master_dashboard.projects p
              ON p.source_item_id = ma.monday_item_id::text
             AND p.source_board = mi.board_id::text
             AND mi.board_id::text = ANY(%s)
            JOIN master_dashboard.people pe
              ON pe.email = ma.monday_user_id || '@monday.local'
            ON CONFLICT DO NOTHING;
        """, (board_id_list,))

        cur.execute("""
            WITH latest_norm AS (
              SELECT inorm.item_id,
                     inorm.board_id,
                     ROW_NUMBER() OVER (PARTITION BY inorm.item_id ORDER BY inorm.run_id DESC) AS rn
              FROM monday_staging.items_norm inorm
            ),
            src AS (
              SELECT
                -- Choose the best available board id
                COALESCE(
                  mi.board_id::text,
                  ln.board_id::text,
                  (mi.raw_json->'board'->>'id'),
                  (mi.raw_json->>'boardId')
                )                              AS source_board,
                mi.monday_id::text             AS source_item_id,
                COALESCE(mi.raw_json, '{}'::jsonb) AS payload_json
              FROM monday.items mi
              LEFT JOIN latest_norm ln
               ON ln.item_id::text = mi.monday_id::text
               AND ln.rn = 1
              WHERE mi.board_id::text = ANY(%s)
            )
            INSERT INTO master_dashboard.raw_records (source_board, source_item_id, payload_json, ingested_at)
            SELECT source_board, source_item_id, payload_json, NOW()
            FROM src
            WHERE source_board IS NOT NULL
            ON CONFLICT (source_board, source_item_id) DO UPDATE
            SET payload_json = EXCLUDED.payload_json,
                ingested_at  = EXCLUDED.ingested_at;
        """, (board_id_list,))

def _backfill_project_source_board(conn: Connection) -> None:
    """
    Ensure projects have source_board set wherever we can match them
    to monday.items. Safe to run every ingest (idempotent).
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE master_dashboard.projects p
            SET source_board = mi.board_id::text
            FROM monday.items mi
            WHERE
              (p.source_board IS NULL OR p.source_board = '')
              AND (
                -- match either by project_code <-> monday_id
                (p.project_code IS NOT NULL AND p.project_code = mi.monday_id::text)
                OR
                -- or by source_item_id <-> monday_id
                (p.source_item_id IS NOT NULL AND p.source_item_id = mi.monday_id::text)
              );
        """)
# New Venture Proposals → dashboard (temp table)
def _map_nvp(conn: Connection, board_id: str) -> None:
    """
    Map 'New Venture Proposals' Monday board into core tables.
    """

    print(f"[MAP] _map_nvp START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:

        cur.execute("SET search_path TO master_dashboard, monday;")

        # 1) Extract properties into temp table
        cur.execute("DROP TABLE IF EXISTS tmp_props_nvp;")
        cur.execute("""
            CREATE TEMP TABLE tmp_props_nvp ON COMMIT DROP AS
            SELECT
                %s::text             AS monday_board_id,
                it.monday_id::text   AS monday_item_id,
                it.name              AS monday_item_name,

                MAX(ip.value_text)  FILTER (WHERE ip.raw_json->>'title' = 'Stage/Status')
                    AS stage_label,
                MAX(
                  CASE
                      WHEN LOWER(ip.value_text) LIKE '%%health%%' THEN 'HealthTech'
                      WHEN LOWER(ip.value_text) IN ('ai', 'AI') THEN 'AI'
                      WHEN LOWER(ip.value_text) LIKE '%%clean%%' THEN 'CleanTech'
                      ELSE NULL
                  END
              ) FILTER (WHERE LOWER(ip.raw_json->>'title') = 'vertical') AS vertical_label,

                MAX(ip.value_text)  FILTER (WHERE ip.raw_json->>'title' = 'Location')
                    AS location_label,

                MAX(ip.value_date)  FILTER (WHERE ip.raw_json->>'title' = 'Start Date')
                    AS start_date,
                MAX(ip.value_date)  FILTER (WHERE ip.raw_json->>'title' = 'End Date')
                    AS end_date,
                MAX(ip.value_date)  FILTER (WHERE ip.raw_json->>'title' = 'Next Presentation Date')
                    AS next_presentation_date,

                -- DESCRIPTION FIELDS
                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' IN ('Biz-summary','Business Summary')
                ) AS biz_summary,

                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' = 'Main Customer'
                ) AS main_customer,

                -- Links
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Link')
                    AS link_single,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Links')
                    AS link_multi,

                -- NEW: Owner / Lead
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Lead/CEO')
                    AS lead_ceo_raw

            FROM monday.items it
            JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            GROUP BY it.monday_id, it.name;
        """, (board_id,))

        # Count rows
        cur.execute("SELECT COUNT(*) FROM tmp_props_nvp;")
        print("[DEBUG] tmp_props_nvp row count =", cur.fetchone()[0])

        # 2) Ensure monday.items has correct board_id
        cur.execute("""
            UPDATE monday.items it
            SET board_id = p.monday_board_id
            FROM tmp_props_nvp p
            WHERE it.monday_id::text = p.monday_item_id
              AND (it.board_id IS NULL OR it.board_id = '');
        """)

        # 3) Map columns into master_dashboard.projects

        # project.source_board set
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET source_board = p.monday_board_id,
                updated_at   = NOW()
            FROM tmp_props_nvp p
            WHERE pr.source_item_id = p.monday_item_id
              AND (pr.source_board IS NULL OR pr.source_board = '');
        """)

        # Vertical
        cur.execute("""
            UPDATE tmp_props_nvp
            SET vertical_label = NULL
            WHERE vertical_label NOT IN ('AI', 'CleanTech', 'HealthTech');
        """)

        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET vertical_id = v.id,
                updated_at  = NOW()
            FROM tmp_props_nvp p
            JOIN master_dashboard.verticals v
              ON v.vertical_name = p.vertical_label
            WHERE pr.source_item_id = p.monday_item_id
              AND COALESCE(p.vertical_label,'') <> '';
        """)

        # Location
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET location_id = l.id,
                updated_at  = NOW()
            FROM tmp_props_nvp p
            JOIN master_dashboard.locations l
              ON l.display_name = p.location_label
            WHERE pr.source_item_id = p.monday_item_id
              AND COALESCE(p.location_label,'') <> '';
        """)

        # Start/End Dates
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET
              start_date = COALESCE(p.start_date, pr.start_date),
              end_date   = COALESCE(p.end_date, pr.end_date),
              updated_at = NOW()
            FROM tmp_props_nvp p
            WHERE pr.source_item_id = p.monday_item_id
              AND (p.start_date IS NOT NULL OR p.end_date IS NOT NULL);
        """)

        # 4) New: Map stage_name & status_category

        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET stage_name = p.stage_label,
                status_category =
                    CASE
                        WHEN LOWER(p.stage_label) LIKE '%%archive%'  THEN 'Archived'
                        WHEN LOWER(p.stage_label) LIKE '%%hold%'     THEN 'On Hold'
                        WHEN LOWER(p.stage_label) LIKE '%%closed%'   THEN 'Archived'
                        WHEN LOWER(p.stage_label) LIKE '%%reject%'   THEN 'Archived'
                        ELSE 'Ongoing'
                    END,
                updated_at = NOW()
            FROM tmp_props_nvp p
            WHERE pr.source_item_id = p.monday_item_id;
        """)

        # 5) New: Map owner (Lead/CEO)
        cur.execute("""
            INSERT INTO master_dashboard.people (full_name)
            SELECT DISTINCT p.lead_ceo_raw
            FROM tmp_props_nvp p
            WHERE COALESCE(p.lead_ceo_raw,'') <> ''
            ON CONFLICT (full_name) DO NOTHING;
        """)

        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET owner_id = pe.id,
                company_name = pr.company_name,
                updated_at = NOW()
            FROM tmp_props_nvp p
            JOIN master_dashboard.people pe
              ON pe.full_name = p.lead_ceo_raw
            WHERE pr.source_item_id = p.monday_item_id
              AND COALESCE(p.lead_ceo_raw,'') <> '';
        """)

        # Create project_owners link
        cur.execute("""
            INSERT INTO master_dashboard.project_owners (
              project_id,
              person_id,
              role,
              source_board,
              source_item_id
            )
            SELECT
              pr.id,
              pe.id,
              'Lead/CEO',
              p.monday_board_id,
              p.monday_item_id
            FROM tmp_props_nvp p
            JOIN master_dashboard.projects pr
              ON pr.source_item_id = p.monday_item_id
            JOIN master_dashboard.people pe
              ON pe.full_name = p.lead_ceo_raw
            WHERE COALESCE(p.lead_ceo_raw, '') <> ''
            ON CONFLICT (project_id, person_id) DO UPDATE
            SET role = EXCLUDED.role,
                source_board = EXCLUDED.source_board,
                source_item_id = EXCLUDED.source_item_id;
        """)

        # 6) Map summary (description)
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET description = CONCAT_WS(
                E'\n\n',
                NULLIF(p.biz_summary,''),
                CASE WHEN COALESCE(p.main_customer,'') <> ''
                     THEN 'Main customer: ' || p.main_customer
                     ELSE NULL END
            ),
            company_name = COALESCE(pr.company_name, p.main_customer),
            updated_at = NOW()
            FROM tmp_props_nvp p
            WHERE pr.source_item_id = p.monday_item_id;
        """)

        # 7) Insert organization and org roles (customer)
        cur.execute("""
            INSERT INTO master_dashboard.organizations (org_name)
            SELECT DISTINCT p.main_customer
            FROM tmp_props_nvp p
            WHERE COALESCE(p.main_customer,'') <> ''
            ON CONFLICT DO NOTHING;
        """)

        cur.execute("""
            INSERT INTO master_dashboard.project_org_roles (
                project_id, org_id, role, external_program, external_key
            )
            SELECT DISTINCT
              pr.id,
              o.id,
              'customer',
              'NVP',
              p.monday_item_id
            FROM tmp_props_nvp p
            JOIN master_dashboard.projects pr
              ON pr.source_item_id = p.monday_item_id
            JOIN master_dashboard.organizations o
              ON o.org_name = p.main_customer
            WHERE COALESCE(p.main_customer,'') <> ''
            ON CONFLICT (project_id, org_id, role) DO NOTHING;
        """)

        # 8) Map attachments
        cur.execute("""
            INSERT INTO master_dashboard.core_attachments (
              owner_schema, owner_table, owner_id, name, url, source
            )
            SELECT DISTINCT
              'master_dashboard','projects', pr.id::text,
              COALESCE(NULLIF(ip.raw_json->>'title',''),'file'),
              ip.value_text,
              'monday'
            FROM monday.item_properties ip
            JOIN monday.items it
              ON it.monday_id::text = ip.monday_item_id::text
            JOIN master_dashboard.projects pr
              ON pr.source_item_id = it.monday_id::text
            WHERE ip.raw_json->>'title' IN ('Idea Files','POC Files','POC Results')
              AND ip.value_text ~ '^https?://'
              AND pr.source_board = %s
            ON CONFLICT DO NOTHING;
        """, (board_id,))

    print(f"[MAP] _map_nvp END for board_id={board_id}", flush=True)



# PJT Board IT → master_dashboard.projects
def _map_pjt_it_legacy_partial(conn: Connection, board_id: str) -> None:
    """
    Map 'PJT Board IT' Monday board (1000000001) into master_dashboard.projects.

    Column titles are matched flexibly to handle common Monday naming variants.
    After first ingest, verify actual titles via:
      SELECT DISTINCT raw_json->>'title' FROM monday.item_properties ip
      JOIN monday.items it ON it.monday_id::text = ip.monday_item_id::text
      WHERE it.board_id = '1000000001';
    """
    print(f"[MAP] _map_pjt_it START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")

        # 1) Pivot column values into a temp table scoped to this board
        cur.execute("DROP TABLE IF EXISTS tmp_props_pjt_it;")
        cur.execute("""
            CREATE TEMP TABLE tmp_props_pjt_it ON COMMIT DROP AS
            SELECT
                %s::text           AS monday_board_id,
                it.monday_id::text AS monday_item_id,
                it.name            AS monday_item_name,

                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' IN ('Stage', 'Status', 'Stage/Status')
                ) AS stage_label,

                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' IN (
                        'Owner', 'Person', 'Lead', 'Assigned To', 'Lead/CEO'
                    )
                ) AS owner_name,

                MAX(ip.value_date) FILTER (
                    WHERE ip.raw_json->>'title' IN ('Start Date', 'Start')
                ) AS start_date,

                MAX(ip.value_date) FILTER (
                    WHERE ip.raw_json->>'title' IN ('Due Date', 'End Date', 'End')
                ) AS end_date,

                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' IN (
                        'Description', 'Notes', 'Summary', 'Biz-summary', 'Business Summary'
                    )
                ) AS description,

                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' = 'Priority'
                ) AS priority

            FROM monday.items it
            JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            WHERE it.board_id::text = %s
            GROUP BY it.monday_id, it.name;
        """, (board_id, board_id))

        cur.execute("SELECT COUNT(*) FROM tmp_props_pjt_it;")
        print("[DEBUG] tmp_props_pjt_it row count =", cur.fetchone()[0])

        # 2) Stamp source_board on any matching projects that don't have it yet
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET source_board = p.monday_board_id,
                updated_at   = NOW()
            FROM tmp_props_pjt_it p
            WHERE pr.source_item_id = p.monday_item_id
              AND (pr.source_board IS NULL OR pr.source_board = '');
        """)

        # 3) Map stage → stage_name + status_category
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET stage_name = p.stage_label,
                status_category =
                    CASE
                        WHEN LOWER(p.stage_label) LIKE '%%archive%%'  THEN 'Archived'
                        WHEN LOWER(p.stage_label) LIKE '%%hold%%'     THEN 'On Hold'
                        WHEN LOWER(p.stage_label) LIKE '%%closed%%'   THEN 'Archived'
                        WHEN LOWER(p.stage_label) LIKE '%%done%%'     THEN 'Archived'
                        WHEN LOWER(p.stage_label) LIKE '%%complete%%' THEN 'Archived'
                        ELSE 'Ongoing'
                    END,
                updated_at = NOW()
            FROM tmp_props_pjt_it p
            WHERE pr.source_item_id = p.monday_item_id
              AND COALESCE(p.stage_label, '') <> '';
        """)

        # 4) Map start / end dates (preserve existing if new value is NULL)
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET start_date = COALESCE(p.start_date, pr.start_date),
                end_date   = COALESCE(p.end_date,   pr.end_date),
                updated_at = NOW()
            FROM tmp_props_pjt_it p
            WHERE pr.source_item_id = p.monday_item_id
              AND (p.start_date IS NOT NULL OR p.end_date IS NOT NULL);
        """)

        # 5) Map description
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET description = p.description,
                updated_at  = NOW()
            FROM tmp_props_pjt_it p
            WHERE pr.source_item_id = p.monday_item_id
              AND COALESCE(p.description, '') <> '';
        """)

        # 6) Upsert owner into people, then link to project
        cur.execute("""
            INSERT INTO master_dashboard.people (full_name)
            SELECT DISTINCT p.owner_name
            FROM tmp_props_pjt_it p
            WHERE COALESCE(p.owner_name, '') <> ''
            ON CONFLICT (full_name) DO NOTHING;
        """)

        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET owner_id   = pe.id,
                updated_at = NOW()
            FROM tmp_props_pjt_it p
            JOIN master_dashboard.people pe ON pe.full_name = p.owner_name
            WHERE pr.source_item_id = p.monday_item_id
              AND COALESCE(p.owner_name, '') <> '';
        """)

        cur.execute("""
            INSERT INTO master_dashboard.project_owners (
                project_id, person_id, role, source_board, source_item_id
            )
            SELECT
                pr.id,
                pe.id,
                'Owner',
                p.monday_board_id,
                p.monday_item_id
            FROM tmp_props_pjt_it p
            JOIN master_dashboard.projects pr ON pr.source_item_id = p.monday_item_id
            JOIN master_dashboard.people pe   ON pe.full_name = p.owner_name
            WHERE COALESCE(p.owner_name, '') <> ''
            ON CONFLICT (project_id, person_id) DO UPDATE
                SET role           = EXCLUDED.role,
                    source_board   = EXCLUDED.source_board,
                    source_item_id = EXCLUDED.source_item_id;
        """)

    conn.commit()
    print(f"[MAP] _map_pjt_it END for board_id={board_id}", flush=True)


def _link_contract_status_to_projects(cur) -> None:
    """
    Link contract_status rows to projects by pjt_task name matching.

    Primary match: pjt_task == project.name (exact, case-insensitive).
    Fallback match: contract name CONTAINS project name (only when pjt_task didn't match).

    project_stage_id is NOT set here — CS2 stage values ("4", "5", "N/A") are raw
    Monday text and do not correspond to stage_types.stage_name. The budget-by-stage
    endpoint groups directly on cs.stage text.

    Safe to call multiple times — only updates rows where project_id IS NULL.
    """
    # Primary: pjt_task exact match
    cur.execute(
        """
        UPDATE master_dashboard.contract_status cs
        SET
          project_id = pr.id,
          updated_at = NOW()
        FROM master_dashboard.projects pr
        WHERE cs.project_id IS NULL
          AND pr.name IS NOT NULL
          AND cs.pjt_task IS NOT NULL
          AND LOWER(TRIM(cs.pjt_task)) = LOWER(TRIM(pr.name))
        """
    )
    # Fallback: contract name contains project name (only for still-unlinked rows)
    cur.execute(
        """
        UPDATE master_dashboard.contract_status cs
        SET
          project_id = pr.id,
          updated_at = NOW()
        FROM master_dashboard.projects pr
        WHERE cs.project_id IS NULL
          AND pr.name IS NOT NULL
          AND cs.contract IS NOT NULL
          AND LOWER(cs.contract) LIKE '%%' || LOWER(TRIM(pr.name)) || '%%'
        """
    )


# Contract Status (temp table)
def _map_contract_status(conn: Connection, board_id: str) -> None:
    """
    Map 'Contract Status' Monday board into contract_status + attachments.
    """
    print(f"[MAP] _map_contract_status START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")

        # Ensure columns exist (idempotent — safe on every run)
        cur.execute(
            """
            ALTER TABLE master_dashboard.contract_status
              ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES master_dashboard.projects(id),
              ADD COLUMN IF NOT EXISTS project_stage_id UUID REFERENCES master_dashboard.project_stages(id);
            CREATE INDEX IF NOT EXISTS ix_contract_status_project_id
              ON master_dashboard.contract_status (project_id);
            CREATE INDEX IF NOT EXISTS ix_contract_status_project_stage_id
              ON master_dashboard.contract_status (project_stage_id);
            """
        )

        # Sanity check
        cur.execute("SELECT COUNT(*) FROM monday.items;")
        total_items = cur.fetchone()[0]
        print(f"[DEBUG] _map_contract_status: total monday.items rows = {total_items}")

        # 1) Temp props – ONLY rows from this board
        cur.execute("DROP TABLE IF EXISTS tmp_props_cs;")
        cur.execute(
            """
            CREATE TEMP TABLE tmp_props_cs ON COMMIT DROP AS
            SELECT
                it.board_id::text      AS monday_board_id,
                it.monday_id::text     AS monday_item_id,
                it.name                AS monday_item_name,

                MAX(ip.value_text)   FILTER (WHERE ip.raw_json->>'title' = 'LMS')
                    AS lms_number,
                MAX(ip.value_number) FILTER (WHERE ip.raw_json->>'title' = 'Amount')
                    AS contract_amount,
                MAX(ip.value_text)   FILTER (WHERE ip.raw_json->>'title' = 'Category')
                    AS category,
                MAX(ip.value_text)   FILTER (WHERE ip.raw_json->>'title' = 'Team')
                    AS team,
                MAX(ip.value_text)   FILTER (WHERE ip.raw_json->>'title' = 'Project / Task')
                    AS pjt_task,
                MAX(ip.value_text)   FILTER (WHERE ip.raw_json->>'title' = 'Stage (PJT)')
                    AS stage,
                MAX(ip.value_text)   FILTER (WHERE ip.raw_json->>'title' = 'Owner')
                    AS owner,

                -- Period is a timeline column: raw_value stores {"from":"YYYY-MM-DD","to":"YYYY-MM-DD"}
                -- value_date is NULL for timeline columns so we parse raw_value directly
                MAX(
                    CASE WHEN ip.raw_json->>'raw_value' ~ '^[{]'
                         THEN (((ip.raw_json->>'raw_value')::jsonb)->>'from')::date END
                ) FILTER (WHERE ip.raw_json->>'title' = 'Period') AS start_date,
                MAX(
                    CASE WHEN ip.raw_json->>'raw_value' ~ '^[{]'
                         THEN (((ip.raw_json->>'raw_value')::jsonb)->>'to')::date END
                ) FILTER (WHERE ip.raw_json->>'title' = 'Period') AS end_date

            FROM monday.items it
            JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            WHERE it.board_id::text = %s
            GROUP BY it.board_id, it.monday_id, it.name;
            """,
            (board_id,),
        )

        cur.execute("SELECT COUNT(*) FROM tmp_props_cs;")
        tmp_count = cur.fetchone()[0]
        print(f"[DEBUG] _map_contract_status: tmp_props_cs row count = {tmp_count}")

        # 2) Update projects.source_board for any matching items
        cur.execute(
            """
            UPDATE master_dashboard.projects pr
            SET source_board = p.monday_board_id,
                updated_at   = NOW()
            FROM tmp_props_cs p
            WHERE pr.source_item_id = p.monday_item_id
              AND (pr.source_board IS NULL OR pr.source_board = '');
            """
        )

        # 3) Upsert into contract_status
        cur.execute(
            """
            INSERT INTO master_dashboard.contract_status AS cs (
              source,
              monday_board_id,
              monday_item_id,
              monday_item_name,
              contract,
              lms_number,
              contract_amount,
              start_date,
              end_date,
              category,
              team,
              pjt_task,
              stage,
              owner
            )
            SELECT
              'monday'                                        AS source,
              p.monday_board_id,
              p.monday_item_id,
              NULLIF(p.monday_item_name,''),
              COALESCE(NULLIF(p.monday_item_name,''), '(untitled)') AS contract,
              NULLIF(p.lms_number,''),
              p.contract_amount,
              p.start_date,
              p.end_date,
              NULLIF(p.category,''),
              NULLIF(p.team,''),
              NULLIF(p.pjt_task,''),
              NULLIF(p.stage,''),
              NULLIF(p.owner,'')
            FROM tmp_props_cs p
            ON CONFLICT ON CONSTRAINT contract_status_unique_source DO UPDATE
            SET monday_item_name = EXCLUDED.monday_item_name,
                contract         = EXCLUDED.contract,
                lms_number       = EXCLUDED.lms_number,
                contract_amount  = EXCLUDED.contract_amount,
                start_date       = EXCLUDED.start_date,
                end_date         = EXCLUDED.end_date,
                category         = EXCLUDED.category,
                team             = EXCLUDED.team,
                pjt_task         = EXCLUDED.pjt_task,
                stage            = EXCLUDED.stage,
                owner            = EXCLUDED.owner,
                updated_at       = NOW();
            """
        )
        # 3b) Link contracts to projects/stages (delegated to shared helper)
        cur.execute("SET search_path TO master_dashboard;")
        _link_contract_status_to_projects(cur)
        # 4) Attachments → core_attachments
        # File-type columns ("Contract", "Related Docs") store URLs in
        # monday.files.public_url (pre-signed S3, expires after 1 hour).
        # We store asset_id so fresh URLs can be fetched on demand.
        # On re-ingest the URL is refreshed via ON CONFLICT ... DO UPDATE.

        # 4a) File-type columns: join monday.files to get asset_id + public_url
        cur.execute(
            """
            INSERT INTO master_dashboard.core_attachments (
              owner_schema, owner_table, owner_id, name, url, asset_id, source
            )
            SELECT DISTINCT ON (mf.asset_id)
              'master_dashboard', 'contract_status', cs.id::text,
              COALESCE(NULLIF(ip.raw_json->>'title', ''), 'file'),
              mf.public_url,
              mf.asset_id,
              'monday'
            FROM monday.item_properties ip
            JOIN monday.items it
              ON it.monday_id::text = ip.monday_item_id::text
            JOIN monday.files mf
              ON mf.item_id    = it.monday_id::text
             AND mf.column_id  = ip.column_id
            JOIN tmp_props_cs p
              ON p.monday_item_id = it.monday_id::text
            JOIN master_dashboard.contract_status cs
              ON cs.source          = 'monday'
             AND cs.monday_board_id = p.monday_board_id
             AND cs.monday_item_id  = p.monday_item_id
            WHERE ip.raw_json->>'title' IN ('Contract','Related Docs','Files','File','Attachment')
              AND mf.public_url IS NOT NULL
              AND mf.asset_id   IS NOT NULL
            ON CONFLICT (asset_id) WHERE asset_id IS NOT NULL
            DO UPDATE SET
              url        = EXCLUDED.url,
              updated_at = NOW();
            """
        )

        # 4b) Link/url-type columns: URL lives in value_text (no asset_id)
        cur.execute(
            """
            INSERT INTO master_dashboard.core_attachments (
              owner_schema, owner_table, owner_id, name, url, source
            )
            SELECT DISTINCT
              'master_dashboard', 'contract_status', cs.id::text,
              COALESCE(NULLIF(ip.raw_json->>'title', ''), 'file'),
              ip.value_text,
              'monday'
            FROM monday.item_properties ip
            JOIN monday.items it
              ON it.monday_id::text = ip.monday_item_id::text
            JOIN tmp_props_cs p
              ON p.monday_item_id = it.monday_id::text
            JOIN master_dashboard.contract_status cs
              ON cs.source          = 'monday'
             AND cs.monday_board_id = p.monday_board_id
             AND cs.monday_item_id  = p.monday_item_id
            WHERE ip.raw_json->>'title' IN ('Contract','Related Docs','Files','File','Attachment')
              AND ip.value_text ~ '^https?://'
            ON CONFLICT DO NOTHING;
            """
        )

        cur.execute("SELECT COUNT(*) FROM master_dashboard.core_attachments;")
        att_count = cur.fetchone()[0]
        print(f"[DEBUG] _map_contract_status: total core_attachments AFTER = {att_count}")

        # 5) Populate files_hint with URLs from "Contract" and "Related Docs" file columns
        cur.execute(
            """
            UPDATE master_dashboard.contract_status cs
            SET files_hint = sub.urls,
                updated_at = NOW()
            FROM (
                SELECT
                    mf.item_id,
                    ARRAY_AGG(DISTINCT mf.public_url ORDER BY mf.public_url) AS urls
                FROM monday.files mf
                JOIN monday.item_properties ip
                  ON ip.monday_item_id = mf.item_id
                 AND ip.column_id      = mf.column_id
                WHERE ip.raw_json->>'title' IN ('Contract', 'Related Docs')
                  AND mf.public_url IS NOT NULL
                GROUP BY mf.item_id
            ) sub
            WHERE cs.monday_item_id  = sub.item_id
              AND cs.monday_board_id = %s;
            """,
            (board_id,),
        )

    print(f"[DEBUG] _map_contract_status: END for board_id={board_id}")


def _map_incubation(conn: Connection, board_id: str) -> None:
    """
    Map Incubation boards (AI, CleanTech, HealthTech) into master_dashboard.projects.

    These boards contain startup companies in the incubation program.
    """
    print(f"[MAP] _map_incubation START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")

        # 1) Extract properties into temp table
        cur.execute("DROP TABLE IF EXISTS tmp_props_incubation;")
        cur.execute("""
            CREATE TEMP TABLE tmp_props_incubation ON COMMIT DROP AS
            SELECT
                %s::text             AS monday_board_id,
                it.monday_id::text   AS monday_item_id,
                it.name              AS monday_item_name,
                it.raw_json->>'group_title' AS group_title,

                -- Stage/Status
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' IN ('Stage', 'Status', 'Stage/Status'))
                    AS stage_label,

                -- Vertical (from board name or explicit column)
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Vertical')
                    AS vertical_label,

                -- Location
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' IN ('Location', 'HQ Location', 'Country'))
                    AS location_label,

                -- Description fields
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' IN ('Description', 'Summary', 'Company Description', 'Biz-summary'))
                    AS description,

                -- Dates
                MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' IN ('Start Date', 'Founded'))
                    AS start_date,
                MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'End Date')
                    AS end_date,

                -- Links
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' IN ('Website', 'Link', 'URL'))
                    AS website,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'LinkedIn')
                    AS linkedin,

                -- Owner/Lead
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' IN ('Owner', 'Lead', 'Point of Contact', 'POC'))
                    AS owner_name

            FROM monday.items it
            LEFT JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            WHERE it.board_id::text = %s
            GROUP BY it.monday_id, it.name, it.raw_json->>'group_title';
        """, (board_id, board_id))

        cur.execute("SELECT COUNT(*) FROM tmp_props_incubation;")
        tmp_count = cur.fetchone()[0]
        print(f"[DEBUG] _map_incubation: tmp_props_incubation row count = {tmp_count}")

        # 2) Ensure monday.items has correct board_id
        cur.execute("""
            UPDATE monday.items it
            SET board_id = p.monday_board_id
            FROM tmp_props_incubation p
            WHERE it.monday_id::text = p.monday_item_id
              AND (it.board_id IS NULL OR it.board_id = '');
        """)

        # 3) Upsert into projects
        cur.execute("""
            INSERT INTO master_dashboard.projects (
                project_code,
                name,
                company_name,
                source_board,
                source_item_id,
                description,
                stage_name,
                status_category,
                start_date,
                end_date,
                is_ongoing,
                created_at
            )
            SELECT
                p.monday_item_id              AS project_code,
                p.monday_item_name            AS name,
                p.monday_item_name            AS company_name,  -- For incubation, name IS the company
                p.monday_board_id             AS source_board,
                p.monday_item_id              AS source_item_id,
                p.description,
                COALESCE(p.stage_label, p.group_title) AS stage_name,
                CASE
                    WHEN LOWER(COALESCE(p.stage_label, '')) LIKE '%archive%' THEN 'Archived'
                    WHEN LOWER(COALESCE(p.stage_label, '')) LIKE '%hold%' THEN 'On Hold'
                    WHEN LOWER(COALESCE(p.stage_label, '')) LIKE '%closed%' THEN 'Archived'
                    ELSE 'Ongoing'
                END AS status_category,
                p.start_date,
                p.end_date,
                TRUE AS is_ongoing,
                NOW()
            FROM tmp_props_incubation p
            ON CONFLICT (project_code) DO UPDATE
            SET name            = EXCLUDED.name,
                company_name    = EXCLUDED.company_name,
                source_board    = EXCLUDED.source_board,
                source_item_id  = EXCLUDED.source_item_id,
                description     = COALESCE(EXCLUDED.description, master_dashboard.projects.description),
                stage_name      = COALESCE(EXCLUDED.stage_name, master_dashboard.projects.stage_name),
                status_category = EXCLUDED.status_category,
                start_date      = COALESCE(EXCLUDED.start_date, master_dashboard.projects.start_date),
                end_date        = COALESCE(EXCLUDED.end_date, master_dashboard.projects.end_date),
                updated_at      = NOW();
        """)

        # 4) Determine vertical from board name
        # Board names like "[Incubation] Startups AI" -> vertical "AI"
        # First, get the board name and determine vertical
        cur.execute("""
            SELECT name FROM monday.boards WHERE monday_board_id = %s
        """, (board_id,))
        board_row = cur.fetchone()
        board_name = board_row[0] if board_row else ""

        # Determine vertical name from board name
        if "AI" in board_name.upper():
            vertical_name = _canonical_vertical_name("AI")
        elif "CLEAN" in board_name.upper() or "CLEANTECH" in board_name.upper():
            vertical_name = _canonical_vertical_name("Cleantech")
        elif "HEALTH" in board_name.upper():
            vertical_name = _canonical_vertical_name("Healthcare")
        else:
            vertical_name = "Other"

        print(f"[DEBUG] _map_incubation: board_name={board_name}, vertical={vertical_name}")

        # Ensure vertical exists
        cur.execute("""
            INSERT INTO master_dashboard.verticals (vertical_name)
            VALUES (%s)
            ON CONFLICT (vertical_name) DO NOTHING;
        """, (vertical_name,))

        # Get vertical ID
        cur.execute("""
            SELECT id FROM master_dashboard.verticals WHERE vertical_name = %s
        """, (vertical_name,))
        vertical_row = cur.fetchone()
        vertical_id = vertical_row[0] if vertical_row else None

        # Update projects with vertical and company_name
        if vertical_id:
            cur.execute("""
                UPDATE master_dashboard.projects pr
                SET vertical_id = %s,
                    company_name = pr.name,
                    updated_at = NOW()
                FROM tmp_props_incubation p
                WHERE pr.source_item_id = p.monday_item_id
                  AND pr.source_board = %s;
            """, (str(vertical_id), board_id))

        # 5) Create organization entries for each startup
        cur.execute("""
            INSERT INTO master_dashboard.organizations (org_name, org_type)
            SELECT DISTINCT
                p.monday_item_name,
                'Startup'
            FROM tmp_props_incubation p
            WHERE COALESCE(p.monday_item_name, '') <> ''
            ON CONFLICT (org_name) DO NOTHING;
        """)

        # 6) Link organizations to projects
        cur.execute("""
            INSERT INTO master_dashboard.project_org_roles (
                project_id, org_id, role, external_program, external_key
            )
            SELECT DISTINCT
                pr.id,
                o.id,
                'startup',
                'Incubation',
                p.monday_item_id
            FROM tmp_props_incubation p
            JOIN master_dashboard.projects pr
              ON pr.source_item_id = p.monday_item_id
            JOIN master_dashboard.organizations o
              ON o.org_name = p.monday_item_name
            WHERE COALESCE(p.monday_item_name, '') <> ''
            ON CONFLICT (project_id, org_id, role) DO NOTHING;
        """)

        # 7) Handle owner/lead if present
        cur.execute("""
            INSERT INTO master_dashboard.people (full_name)
            SELECT DISTINCT p.owner_name
            FROM tmp_props_incubation p
            WHERE COALESCE(p.owner_name, '') <> ''
            ON CONFLICT (full_name) DO NOTHING;
        """)

        cur.execute("""
            INSERT INTO master_dashboard.project_owners (
                project_id, person_id, role, source_board, source_item_id
            )
            SELECT
                pr.id,
                pe.id,
                'Owner',
                p.monday_board_id,
                p.monday_item_id
            FROM tmp_props_incubation p
            JOIN master_dashboard.projects pr
              ON pr.source_item_id = p.monday_item_id
            JOIN master_dashboard.people pe
              ON pe.full_name = p.owner_name
            WHERE COALESCE(p.owner_name, '') <> ''
            ON CONFLICT (project_id, person_id) DO UPDATE
            SET role = EXCLUDED.role,
                source_board = EXCLUDED.source_board,
                source_item_id = EXCLUDED.source_item_id;
        """)

        cur.execute("SELECT COUNT(*) FROM master_dashboard.projects WHERE source_board = %s;", (board_id,))
        proj_count = cur.fetchone()[0]
        print(f"[DEBUG] _map_incubation: projects for board {board_id} = {proj_count}")

    print(f"[MAP] _map_incubation END for board_id={board_id}", flush=True)


def _map_gced_mftf25(conn: Connection, board_id: str) -> None:
    """
    Map a GCED MFTF25 Monday board into master_dashboard.gced_mftf25_startups.

    This is board-agnostic: you can call it for cycle 4, cycle 5, etc.,
    as long as they share the same column structure.
    """
    print(f"[MAP] _map_gced_mftf25 START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")

        cur.execute("SELECT COUNT(*) FROM monday.items;")
        total_items = cur.fetchone()[0]
        print(f"[DEBUG] _map_gced_mftf25: total monday.items rows = {total_items}", flush=True)

        # 1) Temp table with one row per top-level Monday item on this board
        cur.execute("DROP TABLE IF EXISTS tmp_gced_mftf25;")
        cur.execute(
            """
            CREATE TEMP TABLE tmp_gced_mftf25 ON COMMIT DROP AS
            SELECT
                it.board_id::text  AS monday_board_id,
                it.monday_id::text AS monday_item_id,
                it.name            AS monday_item_name,

                -- Core ID + links
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Startup')
                    AS startup_name,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' IN ('Hubspot Link', 'Link'))
                    AS hubspot_link,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'SwitchPitch Link')
                    AS switchpitch_link,

                -- Metadata / classifications
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Startup Source')
                    AS startup_source,
                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' IN ('Track', 'Tracks')
                ) AS track_label,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Startup Type')
                    AS startup_type,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Venture')
                    AS venture,

                -- GCED process
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'GCED Scrub')
                    AS gced_scrub_label,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Team Decision')
                    AS team_decision,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Pitch Deck Rec')
                    AS pitch_deck_rec,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Partner Status Update')
                    AS sosa_status,

                -- Parent-level scores if present on the main item
                MAX(ip.value_number) FILTER (
                    WHERE ip.column_id = ANY(%s)
                ) AS overall_startup_strength,
                MAX(ip.value_number) FILTER (
                    WHERE ip.column_id = ANY(%s)
                ) AS collaboration_potential,

                -- Dates
                MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Due Date')
                    AS due_date,
                MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Last updated')
                    AS last_updated_date,

                -- Notes + people
                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' = 'Pre-CAP Meeting Notes'
                ) AS pre_cap_notes,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'People')
                    AS people_label,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Team')
                    AS team_label

            FROM monday.items it
            JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            WHERE it.board_id::text = %s
              AND it.raw_json->>'parent_item_id' IS NULL
              AND it.raw_json->>'parentItemId'   IS NULL
            GROUP BY it.board_id, it.monday_id, it.name;
            """,
            (_GCED_REVIEW_OVERALL_COL_IDS, _GCED_REVIEW_COLLAB_COL_IDS, board_id),
        )

        cur.execute("SELECT COUNT(*) FROM tmp_gced_mftf25;")
        tmp_count = cur.fetchone()[0]
        print(f"[DEBUG] _map_gced_mftf25: tmp_gced_mftf25 row count = {tmp_count}", flush=True)

        # 2) Upsert into gced_mftf25_startups
        cur.execute(
            """
            INSERT INTO master_dashboard.gced_mftf25_startups AS g (
              source,
              monday_board_id,
              monday_item_id,
              monday_item_name,
              startup_name,
              hubspot_link,
              switchpitch_link,
              startup_source,
              track,
              startup_type,
              venture,
              gced_scrub_label,
              team_decision,
              pitch_deck_rec,
              sosa_status,
              overall_startup_strength,
              collaboration_potential,
              due_date,
              last_updated_at,
              pre_cap_notes,
              people_label,
              team_label
            )
            SELECT
              'monday'                          AS source,
              p.monday_board_id,
              p.monday_item_id,
              NULLIF(p.monday_item_name, '')    AS monday_item_name,

              COALESCE(
                NULLIF(p.startup_name, ''),
                NULLIF(p.monday_item_name, '')
              )                                 AS startup_name,

              NULLIF(p.hubspot_link, '')        AS hubspot_link,
              NULLIF(p.switchpitch_link, '')    AS switchpitch_link,
              NULLIF(p.startup_source, '')      AS startup_source,
              NULLIF(p.track_label, '')         AS track,
              NULLIF(p.startup_type, '')        AS startup_type,
              NULLIF(p.venture, '')             AS venture,
              NULLIF(p.gced_scrub_label, '')    AS gced_scrub_label,
              NULLIF(p.team_decision, '')       AS team_decision,
              NULLIF(p.pitch_deck_rec, '')      AS pitch_deck_rec,
              NULLIF(p.sosa_status, '')         AS sosa_status,
              p.overall_startup_strength,
              p.collaboration_potential,
              p.due_date,
              CASE
                WHEN p.last_updated_date IS NOT NULL
                THEN p.last_updated_date::timestamptz
                ELSE NULL
              END                               AS last_updated_at,
              NULLIF(p.pre_cap_notes, '')       AS pre_cap_notes,
              NULLIF(p.people_label, '')        AS people_label,
              NULLIF(p.team_label, '')          AS team_label
            FROM tmp_gced_mftf25 p
            ON CONFLICT ON CONSTRAINT gced_mftf25_unique_source DO UPDATE
            SET monday_item_name          = EXCLUDED.monday_item_name,
                startup_name              = EXCLUDED.startup_name,
                hubspot_link              = EXCLUDED.hubspot_link,
                switchpitch_link          = EXCLUDED.switchpitch_link,
                startup_source            = EXCLUDED.startup_source,
                track                     = EXCLUDED.track,
                startup_type              = EXCLUDED.startup_type,
                venture                   = EXCLUDED.venture,
                gced_scrub_label          = EXCLUDED.gced_scrub_label,
                team_decision             = EXCLUDED.team_decision,
                pitch_deck_rec            = EXCLUDED.pitch_deck_rec,
                sosa_status               = EXCLUDED.sosa_status,
                overall_startup_strength  = EXCLUDED.overall_startup_strength,
                collaboration_potential   = EXCLUDED.collaboration_potential,
                due_date                  = EXCLUDED.due_date,
                last_updated_at           = EXCLUDED.last_updated_at,
                pre_cap_notes             = EXCLUDED.pre_cap_notes,
                people_label              = EXCLUDED.people_label,
                team_label                = EXCLUDED.team_label,
                updated_at                = NOW();
            """
        )

        # Remove stale subitems incorrectly stored as startups
        cur.execute(
            """
            DELETE FROM master_dashboard.gced_mftf25_startups g
            USING monday.items it
            WHERE g.monday_board_id = %s
              AND g.monday_item_id::text = it.monday_id::text
              AND it.board_id::text = %s
              AND COALESCE(
                    it.raw_json->>'parent_item_id',
                    it.raw_json->>'parentItemId'
                  ) IS NOT NULL;
            """,
            (board_id, board_id),
        )
        deleted = cur.rowcount
        if deleted:
            print(
                f"[DEBUG] _map_gced_mftf25: cleaned up {deleted} stale subitem rows",
                flush=True,
            )

    print(f"[DEBUG] _map_gced_mftf25: END for board_id={board_id}", flush=True)

_GCED_REVIEW_OVERALL_COL_IDS = ['numbers__1']
_GCED_REVIEW_COLLAB_COL_IDS  = ['numbers_1__1']

def _map_gced_reviews(conn: Connection, board_id: str) -> None:
    """
    Populate master_dashboard.gced_mftf25_reviews from reviewer subitems on a
    GCED board and backfill averaged reviewer scores onto
    master_dashboard.gced_mftf25_startups.

    Reviewer subitems are identified by having a parent_item_id in raw_json.
    Each reviewer subitem is expected to carry two numeric fields:
      - Overall Startup Strength (1-5)
      - Collaboration Potential (1-5)

    The reviews table stores one row per reviewer subitem.
    The startups table stores the averaged values across all reviewers for a
    startup, plus an optional combined average_score.
    """
    print(f"[MAP] _map_gced_reviews START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")

        cur.execute("DROP TABLE IF EXISTS tmp_gced_reviewer_rows;")

        # 1) Collect reviewer subitems for this board and extract the two separate numeric review columns.
        cur.execute(
            """
            CREATE TEMP TABLE tmp_gced_reviewer_rows ON COMMIT DROP AS
            SELECT
                it.monday_id::text AS reviewer_item_id,
                it.name            AS reviewer_name,
                COALESCE(
                    it.raw_json->>'parent_item_id',
                    it.raw_json->>'parentItemId'
                ) AS parent_item_id,
                MAX(ip.value_number) FILTER (
                    WHERE ip.column_id = ANY(%s)
                ) AS overall_startup_strength,
                MAX(ip.value_number) FILTER (
                    WHERE ip.column_id = ANY(%s)
                ) AS collaboration_potential
            FROM monday.items it
            LEFT JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            WHERE it.board_id::text = %s
              AND COALESCE(
                    it.raw_json->>'parent_item_id',
                    it.raw_json->>'parentItemId'
                  ) IS NOT NULL
            GROUP BY it.monday_id, it.name, it.raw_json;
            """,
            (_GCED_REVIEW_OVERALL_COL_IDS, _GCED_REVIEW_COLLAB_COL_IDS, board_id),
        )

        cur.execute("SELECT COUNT(*) FROM tmp_gced_reviewer_rows;")
        reviewer_cnt = cur.fetchone()[0]
        print(
            f"[DEBUG] _map_gced_reviews: reviewer subitems found = {reviewer_cnt}",
            flush=True,
        )

        # 2) Upsert each reviewer row into gced_mftf25_reviews, linking each subitem to its parent startup via monday_item_id.
        cur.execute(
            """
            INSERT INTO master_dashboard.gced_mftf25_reviews AS r (
                startup_id,
                monday_board_id,
                monday_item_id,
                monday_item_name,
                overall_startup_strength,
                collaboration_potential,
                source
            )
            SELECT
                g.id AS startup_id,
                %s   AS monday_board_id,
                rr.reviewer_item_id,
                rr.reviewer_name,
                rr.overall_startup_strength,
                rr.collaboration_potential,
                'monday'
            FROM tmp_gced_reviewer_rows rr
            JOIN master_dashboard.gced_mftf25_startups g
              ON g.monday_item_id  = rr.parent_item_id
             AND g.monday_board_id = %s
            WHERE rr.parent_item_id IS NOT NULL
            ON CONFLICT ON CONSTRAINT uq_gced_mftf25_reviews_source DO UPDATE
            SET monday_item_name          = EXCLUDED.monday_item_name,
                overall_startup_strength = EXCLUDED.overall_startup_strength,
                collaboration_potential  = EXCLUDED.collaboration_potential,
                startup_id               = EXCLUDED.startup_id,
                updated_at               = NOW();
            """,
            (board_id, board_id),
        )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM master_dashboard.gced_mftf25_reviews
            WHERE monday_board_id = %s;
            """,
            (board_id,),
        )
        reviews_cnt = cur.fetchone()[0]
        print(
            f"[DEBUG] _map_gced_reviews: total reviews for board = {reviews_cnt}",
            flush=True,
        )

        # 3) Clear existing averaged values for this board first so stale values do not survive when scores are removed or become NULL.
        cur.execute(
            """
            UPDATE master_dashboard.gced_mftf25_startups
            SET overall_startup_strength = NULL,
                collaboration_potential  = NULL,
                average_score            = NULL,
                updated_at               = NOW()
            WHERE monday_board_id = %s;
            """,
            (board_id,),
        )
        cleared_rows = cur.rowcount
        print(
            f"[DEBUG] _map_gced_reviews: cleared averaged score fields for {cleared_rows} startups",
            flush=True,
        )

        # 4) Recompute startup-level averages from the reviews table.
        cur.execute(
            """
            UPDATE master_dashboard.gced_mftf25_startups g
            SET overall_startup_strength = sub.avg_overall,
                collaboration_potential  = sub.avg_collab,
                average_score            = sub.avg_score,
                updated_at               = NOW()
            FROM (
                SELECT
                    startup_id,
                    AVG(overall_startup_strength)::numeric(4,2) AS avg_overall,
                    AVG(collaboration_potential)::numeric(4,2)  AS avg_collab,
                    (
                        (
                            COALESCE(AVG(overall_startup_strength), 0) +
                            COALESCE(AVG(collaboration_potential), 0)
                        ) /
                        NULLIF(
                            (CASE WHEN AVG(overall_startup_strength) IS NOT NULL THEN 1 ELSE 0 END) +
                            (CASE WHEN AVG(collaboration_potential)  IS NOT NULL THEN 1 ELSE 0 END),
                            0
                        )
                    )::numeric(4,2) AS avg_score
                FROM master_dashboard.gced_mftf25_reviews
                WHERE monday_board_id = %s
                GROUP BY startup_id
            ) sub
            WHERE g.id = sub.startup_id
              AND g.monday_board_id = %s;
            """,
            (board_id, board_id),
        )
        updated_rows = cur.rowcount
        print(
            f"[DEBUG] _map_gced_reviews: updated averaged review fields for {updated_rows} startups",
            flush=True,
        )

    conn.commit()
    print(f"[MAP] _map_gced_reviews END for board_id={board_id}", flush=True)


def _map_korean(conn: Connection, board_id: str) -> None:
    """
    Map the regional Monday board into master_dashboard.korean
    using NAME-BASED matching to existing projects.
    """

    print(f"[MAP] _map_korean START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")

        # 1) Extract regional board fields into temp table
        cur.execute("DROP TABLE IF EXISTS tmp_korean;")
        cur.execute(
            """
            CREATE TEMP TABLE tmp_korean ON COMMIT DROP AS
            SELECT
                %s::text           AS monday_board_id,
                it.monday_id::text AS monday_item_id,
                it.name            AS raw_item_name,

                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Project name')
                    AS project_name,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Stage')
                    AS stage_label,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Vertical')
                    AS raw_vertical,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Status')
                    AS status_label,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Business Theme')
                    AS business_theme,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Timeline')
                    AS timeline,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Main Customer')
                    AS main_customer,
                MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Monthly Activities')
                    AS monthly_activities
            FROM monday.items it
            JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            WHERE it.board_id::text = %s
            GROUP BY it.monday_id, it.name;
            """,
            (board_id, board_id),
        )

        cur.execute("SELECT COUNT(*) FROM tmp_korean;")
        print("[DEBUG] tmp_korean row count =", cur.fetchone()[0], flush=True)

        # 2) Normalize vertical (STRICT ALLOWED SET)
        cur.execute(
            """
            UPDATE tmp_korean
            SET raw_vertical = CASE
                WHEN LOWER(raw_vertical) IN ('health', 'healthtech') THEN 'HealthTech'
                WHEN LOWER(raw_vertical) = 'ai' THEN 'AI'
                WHEN LOWER(raw_vertical) IN ('cleantech', 'clean tech') THEN 'CleanTech'
                ELSE NULL
            END;
            """
        )

        # 3) Prepare normalized name for JOIN
        cur.execute(
            """
            ALTER TABLE tmp_korean
            ADD COLUMN norm_item_name TEXT,
            ADD COLUMN project_id UUID,
            ADD COLUMN vertical_id UUID;
            """
        )

        cur.execute(
            """
            UPDATE tmp_korean
            SET norm_item_name = LOWER(
                REGEXP_REPLACE(
                    COALESCE(project_name, raw_item_name),
                    '[^a-zA-Z0-9]+',
                    '',
                    'g'
                )
            );
            """
        )

        # 4) Name-based JOIN to projects (NVP must already exist)
        cur.execute(
            """
            UPDATE tmp_korean tk
            SET project_id = pr.id
            FROM master_dashboard.projects pr
            WHERE LOWER(
                REGEXP_REPLACE(pr.name, '[^a-zA-Z0-9]+', '', 'g')
            ) = tk.norm_item_name;
            """
        )

        cur.execute("SELECT COUNT(*) FROM tmp_korean WHERE project_id IS NULL;")
        missing = cur.fetchone()[0]
        if missing:
            print(
                f"[WARN] {missing} regional rows could not be matched to projects by name",
                flush=True,
            )

        # 5) Map vertical_id
        cur.execute(
            """
            UPDATE tmp_korean tk
            SET vertical_id = v.id
            FROM master_dashboard.verticals v
            WHERE v.vertical_name = tk.raw_vertical;
            """
        )

        # 6) UPSERT into korean
        cur.execute(
            """
            INSERT INTO master_dashboard.korean (
                project_id,
                vertical_id,
                project_name,
                stage,
                vertical,
                status,
                business_theme,
                timeline,
                main_customer,
                monthly_activities
            )
            SELECT
                tk.project_id,
                tk.vertical_id,
                COALESCE(tk.project_name, pr.name),
                tk.stage_label,
                tk.raw_vertical,
                tk.status_label,
                tk.business_theme,
                tk.timeline,
                tk.main_customer,
                tk.monthly_activities
            FROM tmp_korean tk
            JOIN master_dashboard.projects pr
              ON pr.id = tk.project_id
            WHERE tk.project_id IS NOT NULL
            ON CONFLICT (project_id) DO UPDATE
            SET
                vertical_id        = EXCLUDED.vertical_id,
                project_name       = EXCLUDED.project_name,
                stage              = EXCLUDED.stage,
                vertical           = EXCLUDED.vertical,
                status             = EXCLUDED.status,
                business_theme     = EXCLUDED.business_theme,
                timeline           = EXCLUDED.timeline,
                main_customer      = EXCLUDED.main_customer,
                monthly_activities = EXCLUDED.monthly_activities,
                updated_at         = NOW();
            """
        )

    print(f"[MAP] _map_korean END for board_id={board_id}", flush=True)

def _map_project_board_full(conn: Connection, board_id: str, mapper_name: str = "project_board") -> None:
    """
    Map 'Incubation Projects' Monday board into master_dashboard.projects and
    master_dashboard.project_partner_startups.

    Each item is an internal project — upserted directly into master_dashboard.projects
    so it can be linked to contract_status via project_id.

    Stage-relation columns (connect_boards__1 etc.) link to partner startup items;
    those relationships are stored in project_partner_startups keyed by
    master_dashboard.projects.id.
    Archived projects (group_title ILIKE '%archive%') are excluded.
    """
    print(f"[MAP] _map_{mapper_name} START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")
        _ensure_project_reference_rows(cur)

        # Ensure the partner-startups table exists.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS master_dashboard.project_partner_startups (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id      UUID NOT NULL
                                REFERENCES master_dashboard.projects(id)
                                ON DELETE CASCADE,
                stage           TEXT NOT NULL,
                startup_name    TEXT NOT NULL,
                ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT uq_project_partner_startup
                    UNIQUE (project_id, stage, startup_name)
            );
        """)

        cur.execute(
            """
            SELECT COUNT(*)
            FROM master_dashboard.project_partner_startups pps
            JOIN master_dashboard.projects pr ON pr.id = pps.project_id
            WHERE pr.source_board = %s;
            """,
            (board_id,)
        )
        print(
            f"[DEBUG] _map_incubation_projects: rows BEFORE = {cur.fetchone()[0]}",
            flush=True,
        )

        # 1) Load active (non-archived) project items for this board
        cur.execute(
            """
            SELECT
                mi.monday_id::bigint        AS monday_item_id,
                mi.name                     AS project_name
            FROM monday.items mi
            WHERE mi.board_id::text = %s
              AND LOWER(COALESCE(mi.raw_json->>'group_title', '')) NOT LIKE '%%archive%%';
            """,
            (board_id,),
        )
        project_rows = cur.fetchall()
        print(
            f"[DEBUG] _map_incubation_projects: active projects = {len(project_rows)}",
            flush=True,
        )

        if not project_rows:
            print("[DEBUG] _map_incubation_projects: no active projects, skipping", flush=True)
            return

        project_ids = [str(r[0]) for r in project_rows]

        # 2) Upsert project items directly into master_dashboard.projects with all
        #    incubation milestone fields mapped from Monday column titles.
        id_placeholders = ",".join(["%s"] * len(project_ids))
        cur.execute(
            f"""
            WITH props AS (
                SELECT
                    it.monday_id::text AS monday_item_id,
                    it.name,
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'Item ID')
                        AS item_id_code,
                    COALESCE(
                        it.raw_json->>'group_title',
                        it.raw_json->>'groupTitle',
                        'No Cycle'
                    ) AS cycle_name,

                    -- Basic descriptive fields
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Biz-summary')
                        AS biz_summary,
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Main Customer')
                        AS main_customer,
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Comments')
                        AS comments,
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Links')
                        AS links,

                    -- Stage / status columns (use COALESCE: Monday status cols may store
                    -- their label in raw_json->>'text' when value_text is null)
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (
                        WHERE ip.raw_json->>'title' IN ('Atlas Project Stage', 'Project Stage (2026)')
                    )
                        AS atlas_project_stage,
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (
                        WHERE ip.raw_json->>'title' IN ('Project Stage', 'Project Stage (pre 2026)')
                    )
                        AS project_stage,
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (
                        WHERE ip.raw_json->>'title' IN ('Project Status', 'Status')
                    )
                        AS project_status,
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'Vertical')
                        AS vertical,
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'Location')
                        AS location,

                    -- People
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Lead/CEO')
                        AS lead_ceo,
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Tech Lead/CTO')
                        AS tech_lead,
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Team')
                        AS team,
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Notify')
                        AS notify,

                    -- Dates / deadlines
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Next Presentation Date')
                        AS next_presentation_date,
                    MAX(ip.value_text) FILTER (WHERE ip.raw_json->>'title' = 'Report Out Deadline')
                        AS report_out_deadline,

                    -- Idea Proposal (IP) milestone
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'Idea Proposal (IP)')
                        AS idea_proposal_status,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'IP Planned Date')
                        AS ip_planned_date,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'IP Actual Date')
                        AS ip_actual_date,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'IP Decision Date')
                        AS ip_decision_date,

                    -- PoC Proposal milestone
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'PoC Proposal')
                        AS poc_proposal_status,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'PoC Proposal Date Planned')
                        AS poc_proposal_date_planned,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Updated PoC Proposal Date Planned')
                        AS poc_proposal_date_updated,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'PoC Proposal Decision')
                        AS poc_proposal_decision_date,

                    -- PoC Results milestone
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'PoC Results')
                        AS poc_results_status,
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' IN ('POC Status', 'PoC Status'))
                        AS poc_status,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'PoC Results Planned Date')
                        AS poc_results_planned_date,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Updated PoC Report Date')
                        AS poc_results_date_updated,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'PoC Results Decision Date')
                        AS poc_results_decision_date,

                    -- CMBU Proposal milestone
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'CMBU Proposal')
                        AS cmbu_proposal_status,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'CMBU Proposal Planned Date')
                        AS cmbu_proposal_date_planned,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Updated CMBU Proposal Planned Date')
                        AS cmbu_proposal_date_updated,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'CMBU Proposal Decision Date')
                        AS cmbu_proposal_decision_date,

                    -- Seed Results milestone
                    MAX(COALESCE(ip.value_text, ip.raw_json->>'text')) FILTER (WHERE ip.raw_json->>'title' = 'Seed Results')
                        AS seed_results_status,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Seed Results Planned Date')
                        AS seed_results_planned_date,
                    MAX(ip.value_date) FILTER (WHERE ip.raw_json->>'title' = 'Updated Seed Results Planned Date')
                        AS seed_results_date_updated

                FROM monday.items it
                LEFT JOIN monday.item_properties ip
                    ON ip.monday_item_id::text = it.monday_id::text
                WHERE it.monday_id::text IN ({id_placeholders})
                GROUP BY it.monday_id, it.name,
                         it.raw_json->>'group_title', it.raw_json->>'groupTitle'
            )
            INSERT INTO master_dashboard.projects (
                project_code, name, company_name, source_board, source_item_id,
                description, stage_name,
                cycle_name, project_stage, project_status, atlas_project_stage, status_category,
                tech_lead, team, notify, links, report_out_deadline,
                next_presentation_date,
                idea_proposal_status, ip_planned_date, ip_actual_date, ip_decision_date,
                poc_proposal_status, poc_proposal_date_planned, poc_proposal_date_updated,
                poc_proposal_decision_date,
                poc_results_status, poc_status, poc_results_planned_date, poc_results_date_updated,
                poc_results_decision_date,
                cmbu_proposal_status, cmbu_proposal_date_planned, cmbu_proposal_date_updated,
                cmbu_proposal_decision_date,
                seed_results_status, seed_results_planned_date, seed_results_date_updated,
                is_ongoing, created_at
            )
            SELECT
                CASE
                    WHEN NULLIF(p.item_id_code, '') IS NULL THEN p.monday_item_id
                    WHEN EXISTS (
                        SELECT 1
                        FROM master_dashboard.projects existing
                        WHERE existing.project_code = p.item_id_code
                          AND NOT (
                              existing.source_board = %s::text
                              AND existing.source_item_id = p.monday_item_id
                          )
                    ) THEN p.monday_item_id
                    ELSE p.item_id_code
                END AS project_code,
                p.name,
                p.name AS company_name,
                %s::text AS source_board,
                p.monday_item_id AS source_item_id,
                CONCAT_WS(
                    E'\\n\\n',
                    NULLIF(p.biz_summary, ''),
                    NULLIF(p.comments, ''),
                    CASE WHEN COALESCE(p.main_customer, '') <> ''
                         THEN 'Main customer: ' || p.main_customer
                         ELSE NULL END
                ) AS description,
                COALESCE(
                    NULLIF(p.atlas_project_stage, ''),
                    NULLIF(p.project_stage, ''),
                    NULLIF(p.cycle_name, '')
                ) AS stage_name,
                p.cycle_name,
                p.project_stage,
                p.project_status,
                p.atlas_project_stage,
                CASE
                    WHEN LOWER(COALESCE(p.project_status, p.atlas_project_stage, p.project_stage, p.cycle_name, '')) LIKE '%%archive%%' THEN 'Archived'
                    WHEN LOWER(COALESCE(p.project_status, p.atlas_project_stage, p.project_stage, p.cycle_name, '')) LIKE '%%hold%%' THEN 'On Hold'
                    WHEN LOWER(COALESCE(p.project_status, p.atlas_project_stage, p.project_stage, p.cycle_name, '')) LIKE '%%closed%%' THEN 'Archived'
                    WHEN LOWER(COALESCE(p.project_status, p.atlas_project_stage, p.project_stage, p.cycle_name, '')) LIKE '%%done%%' THEN 'Archived'
                    WHEN LOWER(COALESCE(p.project_status, p.atlas_project_stage, p.project_stage, p.cycle_name, '')) LIKE '%%complete%%' THEN 'Archived'
                    ELSE 'Ongoing'
                END AS status_category,
                p.tech_lead,
                p.team,
                p.notify,
                p.links,
                p.report_out_deadline,
                p.next_presentation_date,
                p.idea_proposal_status,
                p.ip_planned_date,
                p.ip_actual_date,
                p.ip_decision_date,
                p.poc_proposal_status,
                p.poc_proposal_date_planned,
                p.poc_proposal_date_updated,
                p.poc_proposal_decision_date,
                p.poc_results_status,
                p.poc_status,
                p.poc_results_planned_date,
                p.poc_results_date_updated,
                p.poc_results_decision_date,
                p.cmbu_proposal_status,
                p.cmbu_proposal_date_planned,
                p.cmbu_proposal_date_updated,
                p.cmbu_proposal_decision_date,
                p.seed_results_status,
                p.seed_results_planned_date,
                p.seed_results_date_updated,
                TRUE AS is_ongoing,
                NOW()
            FROM props p
            ON CONFLICT (source_board, source_item_id) DO UPDATE
            SET name                        = EXCLUDED.name,
                company_name                = EXCLUDED.company_name,
                project_code                = EXCLUDED.project_code,
                source_board                = EXCLUDED.source_board,
                source_item_id              = EXCLUDED.source_item_id,
                description                 = COALESCE(EXCLUDED.description, master_dashboard.projects.description),
                stage_name                  = COALESCE(EXCLUDED.stage_name, master_dashboard.projects.stage_name),
                cycle_name                  = EXCLUDED.cycle_name,
                project_stage               = EXCLUDED.project_stage,
                project_status              = EXCLUDED.project_status,
                atlas_project_stage         = EXCLUDED.atlas_project_stage,
                status_category             = EXCLUDED.status_category,
                tech_lead                   = EXCLUDED.tech_lead,
                team                        = EXCLUDED.team,
                notify                      = EXCLUDED.notify,
                links                       = EXCLUDED.links,
                report_out_deadline         = EXCLUDED.report_out_deadline,
                next_presentation_date      = EXCLUDED.next_presentation_date,
                idea_proposal_status        = EXCLUDED.idea_proposal_status,
                ip_planned_date             = EXCLUDED.ip_planned_date,
                ip_actual_date              = EXCLUDED.ip_actual_date,
                ip_decision_date            = EXCLUDED.ip_decision_date,
                poc_proposal_status         = EXCLUDED.poc_proposal_status,
                poc_proposal_date_planned   = EXCLUDED.poc_proposal_date_planned,
                poc_proposal_date_updated   = EXCLUDED.poc_proposal_date_updated,
                poc_proposal_decision_date  = EXCLUDED.poc_proposal_decision_date,
                poc_results_status          = EXCLUDED.poc_results_status,
                poc_status                  = EXCLUDED.poc_status,
                poc_results_planned_date    = EXCLUDED.poc_results_planned_date,
                poc_results_date_updated    = EXCLUDED.poc_results_date_updated,
                poc_results_decision_date   = EXCLUDED.poc_results_decision_date,
                cmbu_proposal_status        = EXCLUDED.cmbu_proposal_status,
                cmbu_proposal_date_planned  = EXCLUDED.cmbu_proposal_date_planned,
                cmbu_proposal_date_updated  = EXCLUDED.cmbu_proposal_date_updated,
                cmbu_proposal_decision_date = EXCLUDED.cmbu_proposal_decision_date,
                seed_results_status         = EXCLUDED.seed_results_status,
                seed_results_planned_date   = EXCLUDED.seed_results_planned_date,
                seed_results_date_updated   = EXCLUDED.seed_results_date_updated,
                is_ongoing                  = EXCLUDED.is_ongoing,
                updated_at                  = NOW();
            """,
            project_ids + [board_id, board_id],
        )
        cur.execute(
            "SELECT COUNT(*) FROM master_dashboard.projects WHERE source_board = %s;",
            (board_id,),
        )
        print(
            f"[DEBUG] _map_incubation_projects: projects rows = {cur.fetchone()[0]}",
            flush=True,
        )

        # 2b) Resolve vertical_id by matching the extracted vertical text to
        #     master_dashboard.verticals.vertical_name.  Done as a separate UPDATE
        #     because vertical_id is a FK that cannot be inlined in the CTE above.
        id_placeholders_vt = ",".join(["%s"] * len(project_ids))
        cur.execute(
            f"""
            UPDATE master_dashboard.projects pr
            SET    vertical_id = v.id,
                   updated_at  = NOW()
            FROM (
                SELECT
                    it.monday_id::text AS monday_item_id,
                    CASE
                        WHEN LOWER(TRIM(MAX(COALESCE(ip.value_text, ip.raw_json->>'text'))
                            FILTER (WHERE ip.raw_json->>'title' = 'Vertical'))) IN ('healthcare', 'healthtech')
                            THEN 'HealthTech'
                        WHEN LOWER(TRIM(MAX(COALESCE(ip.value_text, ip.raw_json->>'text'))
                            FILTER (WHERE ip.raw_json->>'title' = 'Vertical'))) IN ('cleantech', 'clean tech', 'clean-tech')
                            THEN 'CleanTech'
                        WHEN LOWER(TRIM(MAX(COALESCE(ip.value_text, ip.raw_json->>'text'))
                            FILTER (WHERE ip.raw_json->>'title' = 'Vertical'))) = 'ai'
                            THEN 'AI'
                        ELSE NULLIF(TRIM(MAX(COALESCE(ip.value_text, ip.raw_json->>'text'))
                            FILTER (WHERE ip.raw_json->>'title' = 'Vertical')), '')
                    END AS vertical
                FROM monday.items it
                LEFT JOIN monday.item_properties ip
                    ON ip.monday_item_id::text = it.monday_id::text
                WHERE it.monday_id::text IN ({id_placeholders_vt})
                GROUP BY it.monday_id
            ) props
            JOIN master_dashboard.verticals v
                ON LOWER(TRIM(v.vertical_name)) = LOWER(TRIM(props.vertical))
            WHERE pr.source_item_id = props.monday_item_id
              AND pr.source_board   = %s
              AND COALESCE(props.vertical, '') <> '';
            """,
            project_ids + [board_id],
        )
        print(
            f"[DEBUG] _map_incubation_projects: vertical_id rows updated = {cur.rowcount}",
            flush=True,
        )

        # 2c) Resolve location_id by matching extracted location text to
        #     master_dashboard.locations.display_name.
        id_placeholders_loc = ",".join(["%s"] * len(project_ids))
        cur.execute(
            f"""
            UPDATE master_dashboard.projects pr
            SET    location_id = loc.id,
                   updated_at  = NOW()
            FROM (
                SELECT
                    it.monday_id::text AS monday_item_id,
                    CASE
                        WHEN LOWER(TRIM(MAX(COALESCE(ip.value_text, ip.raw_json->>'text'))
                            FILTER (WHERE ip.raw_json->>'title' = 'Location'))) = 'example city'
                            THEN 'Example City'
                        WHEN LOWER(TRIM(MAX(COALESCE(ip.value_text, ip.raw_json->>'text'))
                            FILTER (WHERE ip.raw_json->>'title' = 'Location'))) = 'example region'
                            THEN 'Example Region'
                        ELSE NULLIF(TRIM(MAX(COALESCE(ip.value_text, ip.raw_json->>'text'))
                            FILTER (WHERE ip.raw_json->>'title' = 'Location')), '')
                    END AS location
                FROM monday.items it
                LEFT JOIN monday.item_properties ip
                    ON ip.monday_item_id::text = it.monday_id::text
                WHERE it.monday_id::text IN ({id_placeholders_loc})
                GROUP BY it.monday_id
            ) props
            JOIN master_dashboard.locations loc
                ON LOWER(TRIM(loc.display_name)) = LOWER(TRIM(props.location))
            WHERE pr.source_item_id = props.monday_item_id
              AND pr.source_board   = %s
              AND COALESCE(props.location, '') <> '';
            """,
            project_ids + [board_id],
        )
        print(
            f"[DEBUG] _map_incubation_projects: location_id rows updated = {cur.rowcount}",
            flush=True,
        )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM master_dashboard.projects pr
            WHERE pr.source_board = %s
              AND pr.source_item_id = ANY(%s)
              AND (pr.vertical_id IS NULL OR pr.location_id IS NULL);
            """,
            (board_id, project_ids),
        )
        unresolved_count = cur.fetchone()[0]
        print(
            f"[DEBUG] _map_incubation_projects: unresolved vertical/location rows = {unresolved_count}",
            flush=True,
        )

        # 2d) Resolve owner_id from Lead/CEO people column.
        #     Upsert the person into master_dashboard.people by full_name, then
        #     link projects.owner_id.
        id_placeholders_own = ",".join(["%s"] * len(project_ids))
        cur.execute(
            f"""
            WITH lead_names AS (
                SELECT
                    it.monday_id::text AS monday_item_id,
                    MAX(ip.value_text)
                        FILTER (WHERE ip.raw_json->>'title' = 'Lead/CEO') AS lead_ceo
                FROM monday.items it
                LEFT JOIN monday.item_properties ip
                    ON ip.monday_item_id::text = it.monday_id::text
                WHERE it.monday_id::text IN ({id_placeholders_own})
                GROUP BY it.monday_id
            )
            INSERT INTO master_dashboard.people (full_name)
            SELECT DISTINCT lead_ceo
            FROM lead_names
            WHERE COALESCE(lead_ceo, '') <> ''
            ON CONFLICT (full_name) DO NOTHING;
            """,
            project_ids,
        )

        cur.execute(
            f"""
            UPDATE master_dashboard.projects pr
            SET    owner_id   = pe.id,
                   updated_at = NOW()
            FROM (
                SELECT
                    it.monday_id::text AS monday_item_id,
                    MAX(ip.value_text)
                        FILTER (WHERE ip.raw_json->>'title' = 'Lead/CEO') AS lead_ceo
                FROM monday.items it
                LEFT JOIN monday.item_properties ip
                    ON ip.monday_item_id::text = it.monday_id::text
                WHERE it.monday_id::text IN ({id_placeholders_own})
                GROUP BY it.monday_id
            ) props
            JOIN master_dashboard.people pe
                ON LOWER(TRIM(pe.full_name)) = LOWER(TRIM(props.lead_ceo))
            WHERE pr.source_item_id = props.monday_item_id
              AND pr.source_board   = %s
              AND COALESCE(props.lead_ceo, '') <> '';
            """,
            project_ids + [board_id],
        )
        print(
            f"[DEBUG] _map_incubation_projects: owner_id rows updated = {cur.rowcount}",
            flush=True,
        )

        cur.execute(
            f"""
            INSERT INTO master_dashboard.project_owners (
                project_id, person_id, role, source_board, source_item_id
            )
            SELECT
                pr.id,
                pe.id,
                'Owner',
                %s::text,
                props.monday_item_id
            FROM (
                SELECT
                    it.monday_id::text AS monday_item_id,
                    MAX(ip.value_text)
                        FILTER (WHERE ip.raw_json->>'title' = 'Lead/CEO') AS lead_ceo
                FROM monday.items it
                LEFT JOIN monday.item_properties ip
                    ON ip.monday_item_id::text = it.monday_id::text
                WHERE it.monday_id::text IN ({id_placeholders_own})
                GROUP BY it.monday_id
            ) props
            JOIN master_dashboard.projects pr
                ON pr.source_item_id = props.monday_item_id
               AND pr.source_board   = %s
            JOIN master_dashboard.people pe
                ON LOWER(TRIM(pe.full_name)) = LOWER(TRIM(props.lead_ceo))
            WHERE COALESCE(props.lead_ceo, '') <> ''
            ON CONFLICT (project_id, person_id) DO UPDATE
                SET role           = EXCLUDED.role,
                    source_board   = EXCLUDED.source_board,
                    source_item_id = EXCLUDED.source_item_id;
            """,
            [board_id] + project_ids + [board_id],
        )

        cur.execute(
            """
            SELECT id::text, source_item_id::text
            FROM master_dashboard.projects
            WHERE source_board = %s
              AND source_item_id = ANY(%s);
            """,
            (board_id, project_ids),
        )
        project_id_by_item_id = {
            str(source_item_id): str(project_id)
            for project_id, source_item_id in cur.fetchall()
            if source_item_id
        }

        # 3) Load stage-relation column properties for active projects
        stage_column_ids = [
            cfg["column_id"] for cfg in _INCUBATION_PROJECT_STAGE_COLUMNS.values()
        ]
        id_placeholders = ",".join(["%s"] * len(project_ids))
        col_placeholders = ",".join(["%s"] * len(stage_column_ids))

        cur.execute(
            f"""
            SELECT
                ip.monday_item_id::text AS monday_item_id,
                ip.column_id,
                ip.raw_json
            FROM monday.item_properties ip
            WHERE ip.monday_item_id::text IN ({id_placeholders})
              AND ip.column_id IN ({col_placeholders});
            """,
            project_ids + stage_column_ids,
        )
        prop_rows = cur.fetchall()

        # 3) Build partner rows using priority-order extractor
        col_id_to_stage = {
            cfg["column_id"]: stage
            for stage, cfg in _INCUBATION_PROJECT_STAGE_COLUMNS.items()
        }
        partner_rows: list[tuple] = []
        for item_id_str, column_id, raw_json in prop_rows:
            stage = col_id_to_stage.get(column_id)
            if not stage:
                continue
            project_id = project_id_by_item_id.get(item_id_str)
            if not project_id:
                continue

            parsed = (raw_json or {}).get("parsed", {}) if isinstance(raw_json, dict) else {}
            column_value = {
                "linked_items": [
                    {"id": lnk.get("linked_item_id"), "name": lnk.get("name")}
                    for lnk in (parsed.get("linked_items") or [])
                ],
                "display_value": parsed.get("display_value"),
                "text": raw_json.get("raw_text") if isinstance(raw_json, dict) else None,
            }

            startups = _extract_startup_names_from_relation_column(column_value)

            for s in startups:
                partner_rows.append((
                    project_id,
                    stage,
                    s["startup_name"],
                ))

        print(
            f"[DEBUG] _map_incubation_projects: partner rows extracted = {len(partner_rows)}",
            flush=True,
        )

        # 4) Full refresh: delete existing rows, then insert fresh
        cur.execute(
            """
            DELETE FROM master_dashboard.project_partner_startups pps
            USING master_dashboard.projects pr
            WHERE pr.id = pps.project_id
              AND pr.source_board = %s;
            """,
            (board_id,),
        )

        if partner_rows:
            cur.executemany(
                """
                INSERT INTO master_dashboard.project_partner_startups (
                    project_id, stage, startup_name, ingested_at, updated_at
                ) VALUES (%s, %s, %s, NOW(), NOW())
                ON CONFLICT (project_id, stage, startup_name) DO UPDATE SET
                    ingested_at = EXCLUDED.ingested_at,
                    updated_at  = NOW();
                """,
                partner_rows,
            )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM master_dashboard.project_partner_startups pps
            JOIN master_dashboard.projects pr ON pr.id = pps.project_id
            WHERE pr.source_board = %s;
            """,
            (board_id,)
        )
        print(
            f"[DEBUG] _map_incubation_projects: rows AFTER = {cur.fetchone()[0]}",
            flush=True,
        )

    print(f"[MAP] _map_{mapper_name} END for board_id={board_id}", flush=True)


def _map_pjt_it(conn: Connection, board_id: str) -> None:
    """
    Canonical mapper for duplicate Project boards, including PJT Board IT and
    Incubation Projects. Populates full Project Tab fields plus partner startups.
    """
    _map_project_board_full(conn, board_id, mapper_name="pjt_it")
    conn.commit()


def _map_incubation_projects(conn: Connection, board_id: str) -> None:
    """Compatibility alias for older imports/tests; project boards use _map_pjt_it."""
    _map_pjt_it(conn, board_id)


def _map_ai_locate_file(conn: Connection, board_id: str) -> None:
    """
    Map 'AI - Locate a File' Monday board into monday.files metadata.

    Populates owner_name (from 'Owner' people column) and category
    (from group title) on monday.files rows belonging to this board,
    so the master_dashboard.documents view returns enriched results.
    """
    print(f"[MAP] _map_ai_locate_file START for board_id={board_id}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO master_dashboard, monday;")

        # Build a temp table with per-item owner and category derived from
        # the Monday 'Owner' people column and the item's group title.
        cur.execute("DROP TABLE IF EXISTS tmp_ai_locate_file;")
        cur.execute(
            """
            CREATE TEMP TABLE tmp_ai_locate_file ON COMMIT DROP AS
            SELECT
                it.monday_id::text  AS item_id,
                COALESCE(
                    it.raw_json->>'group_title',
                    it.raw_json->>'groupTitle'
                )                   AS category,
                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' IN ('Owner', 'Person')
                )                   AS owner_name,
                MAX(ip.value_text) FILTER (
                    WHERE ip.raw_json->>'title' IN (
                        'Description', 'Summary', 'Notes', 'Details'
                    )
                )                   AS summary
            FROM monday.items it
            LEFT JOIN monday.item_properties ip
              ON ip.monday_item_id::text = it.monday_id::text
            WHERE it.board_id::text = %s
            GROUP BY it.monday_id, it.raw_json;
            """,
            (board_id,),
        )

        cur.execute("SELECT COUNT(*) FROM tmp_ai_locate_file;")
        tmp_count = cur.fetchone()[0]
        print(f"[DEBUG] _map_ai_locate_file: tmp rows = {tmp_count}", flush=True)

        cur.execute(
            """
            UPDATE monday.files f
            SET
                owner_name = COALESCE(NULLIF(t.owner_name, ''), f.owner_name),
                category   = COALESCE(NULLIF(t.category, ''), f.category),
                summary    = COALESCE(NULLIF(t.summary, ''), f.summary),
                updated_at = NOW()
            FROM tmp_ai_locate_file t
            WHERE f.item_id::text = t.item_id
              AND f.board_id::text = %s;
            """,
            (board_id,),
        )

        cur.execute(
            "SELECT COUNT(*) FROM monday.files WHERE board_id::text = %s;",
            (board_id,),
        )
        file_count = cur.fetchone()[0]
        print(
            f"[DEBUG] _map_ai_locate_file: updated metadata on {file_count} files",
            flush=True,
        )

    print(f"[MAP] _map_ai_locate_file END for board_id={board_id}", flush=True)


def _backfill_projects_from_raw(conn: Connection) -> None:
    """
    Generic enrichment for projects using monday_staging / raw_records payloads.

    - Links raw_records.project_id to projects.id.
    - Derives verticals from group_title (e.g., 'HealthTech', 'CleanTech').
    - Fills projects.vertical_id when missing.
    - Fills projects.start_date from created_at when missing.
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE master_dashboard.raw_records rr
            SET project_id = p.id
            FROM master_dashboard.projects p
            WHERE rr.project_id IS NULL
              AND rr.source_board   = p.source_board
              AND rr.source_item_id = p.source_item_id;
        """)

        # Note: Verticals (AI, CleanTech, HealthTech) are mapped from the "Vertical"
        # column in _map_nvp, not from group_title. Group titles like "All Proposals"
        # are Monday board groupings, not actual verticals.

        # Only fill projects.vertical_id where missing if group_title is a valid vertical
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET vertical_id = v.id,
                updated_at  = NOW()
            FROM master_dashboard.raw_records rr
            JOIN master_dashboard.verticals v
              ON v.vertical_name = rr.payload_json->>'group_title'
            WHERE rr.project_id = pr.id
              AND pr.vertical_id IS NULL
              AND rr.payload_json->>'group_title' IN ('AI', 'CleanTech', 'HealthTech');
        """)

        # 4) Fill projects.start_date from created_at when missing
        cur.execute("""
            UPDATE master_dashboard.projects pr
            SET start_date = COALESCE(
                               pr.start_date,
                               (rr.payload_json->>'created_at')::timestamptz::date
                             ),
                updated_at = NOW()
            FROM master_dashboard.raw_records rr
            WHERE rr.project_id = pr.id
              AND pr.start_date IS NULL
              AND rr.payload_json->>'created_at' IS NOT NULL;
        """)
