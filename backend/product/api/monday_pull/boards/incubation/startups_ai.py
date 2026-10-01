# Incubation Startups AI Board

import argparse
from pathlib import Path
from dotenv import load_dotenv

from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id


# Column behavior for this board (seen in screenshots: Item, Comment,
# Fund isInterested, Marketing, CMBU, Lead, Status, Priority, Step, Date,
# Area, Pre-CAP Meeting Notes)
_OVERRIDES_RAW = {
    # Long text
    "Comment": "long_text",
    "Pre-CAP Meeting Notes": "long_text",

    # People
    "Lead": "people",

    # Status-like (labels mapped via settings_str)
    "Status": "status",
    "Priority": "status",
    "Step": "status",
    "CMBU": "status",
    "Area": "status",
    "Fund isInterested": "status",   # often a Yes/No style status

    # Checkboxes / booleans
    "Marketing": "checkbox",         # shows as a green check in UI

    # Dates
    "Date": "date",

    # Files (present on some views/tabs)
    "SW": "file",

    # Plain text fallback
    "Item": "text",
}

# Normalize to {"type": "..."} form
OVERRIDES = {k: ({"type": v} if isinstance(v, str) else v) for k, v in _OVERRIDES_RAW.items()}

# Drop from payload if your downstream already promotes item name
EXCLUDES: list[str] = ["Item"]


def _mask(s: str) -> str:
    s = str(s)
    return ("*" * max(0, len(s) - 4)) + s[-4:]


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Export Startups AI board.")
    ap.add_argument(
        "--out",
        default=str(Path(__file__).parent / "out"),
        help="Output directory (default: boards/incubation/out)",
    )
    ap.add_argument(
        "--board-id",
        default=None,
        help="Optional override of the board id (takes precedence over .env)",
    )
    args = ap.parse_args()

    board_id = args.board_id or get_board_id("incubation_ai")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure incubation_ai in board_config."
        )

    config = {
        "board_id": str(board_id),
        "overrides": OVERRIDES,
        "excludes": EXCLUDES,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = pull_board(config["board_id"], config)
    write_json(payload, str(out_dir / "dump.json"), unique=True)

    print(f"Exported board {_mask(config['board_id'])} → {out_dir}")


if __name__ == "__main__":
    main()
