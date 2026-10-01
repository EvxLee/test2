# GCED Cycle 4 Board

import argparse
from pathlib import Path
from dotenv import load_dotenv

from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id

_OVERRIDES_RAW = {
    # Status
    "Startup Source": "status",
    "GCED Scrub": "status",
    "Team Decision": "status",
    "Startup Type": "status",
    "Track": "status",
    "Partner Status Update": "status",

    # Links
    "Hubspot Link": "link",
    "SwitchPitch Link": "link",

    # People / Team
    "People": "people",
    "Team": "team",

    # Dates
    "Due Date": "date",

    # Text / Notes
    "Pre-CAP Meeting Notes": "long_text",
    "Pitch Deck Rec": "text",
}

# Normalize to {"type": "..."} form
OVERRIDES = {k: ({"type": v} if isinstance(v, str) else v) for k, v in _OVERRIDES_RAW.items()}

# Exclude noisy display-only/system columns
EXCLUDES: list[str] = [
    "Status",
    "Subitems",
    "subitems",
    "Last Updated",
]

def _mask(s: str) -> str:
    """Mask an ID for logs"""
    s = str(s)
    return ("*" * max(0, len(s) - 4)) + s[-4:]


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Export GCED Cycle 4 board.")
    ap.add_argument(
        "--out",
        default=str(Path(__file__).parent / "out"),
        help="Output directory (default: boards/gced/out)",
    )
    ap.add_argument(
        "--board-id",
        default=None,
        help="Optional override of the board id (takes precedence over .env)",
    )
    args = ap.parse_args()

    # Use a Cycle 4–specific env var
    board_id = args.board_id or get_board_id("gced_mftf25_cycle4")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure gced_mftf25_cycle4 in board_config."
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
