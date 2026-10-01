from sqlalchemy import text

from database.db import SessionLocal
from board_config_db import get_cycle_board_map

VALID_CYCLE_IDS = [f"gced_cycle{i}" for i in range(1, 8)]

STARTUPS_QUERY = text("""
    SELECT
        g.startup_name,
        p.description,
        g.track AS vertical
    FROM
        master_dashboard.gced_mftf25_startups g
    LEFT JOIN
        dp.pitchbook_companies p ON g.startup_name = p.company_name
    WHERE
        g.monday_board_id = :board_id
""")


def board_id_for_cycle(cycle_id: str) -> str | None:
    if cycle_id not in VALID_CYCLE_IDS:
        return None
    return get_cycle_board_map().get(cycle_id)


def cycle_id_for_board_id(board_id: str) -> str | None:
    reverse = {bid: cid for cid, bid in get_cycle_board_map().items()}
    return reverse.get(board_id)


def get_startups_for_cycle(cycle_id: str) -> list[dict]:
    if cycle_id not in VALID_CYCLE_IDS:
        valid = list(VALID_CYCLE_IDS)
        raise ValueError(f"Invalid cycle_id '{cycle_id}'. Must be one of: {valid}")

    board_id = board_id_for_cycle(cycle_id)

    if not board_id:
        raise ValueError(f"No active board_config entry found for cycle_id '{cycle_id}'.")

    with SessionLocal() as session:
        rows = session.execute(STARTUPS_QUERY, {"board_id": board_id}).fetchall()

    return [
        {
            "company_name": row.startup_name,
            "description": row.description,  # None if no PitchBook data
            "vertical": row.vertical,
        }
        for row in rows
    ]
