# Incubation Startups Health Board

import argparse
from pathlib import Path
from dotenv import load_dotenv

from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id


# Column behavior for this board
# (map Monday columns to explicit types the core understands)
_OVERRIDES_RAW = {
    # Long text
    "Comment": "long_text",
    "Meeting Notes": "long_text",   # present on some groups/views

    # People
    "Lead": "people",
    "Who can edit": "people",

    # Status-like (labels mapped via settings_str)
    "Stage": "status",
    "Priority": "status",
    "CMBU": "status",
    "CAP Status": "status",
    "Area": "status",
    "Fund is Interested": "status",   # yes/no style labels
    "Pre-CAP Cycle": "status",        # e.g., “GC1-2”, “GC3 Cycle 1”
    "Pre-CCAP Cycle": "status",       # some boards spell it this way
    "Marketing": "checkbox",          # appears as a green checkmark in UI

    # Dates
    "Date": "date",

    # Plain text fallbacks
    "Item": "text",
}

# Normalize to {"type": "..."} form
OVERRIDES = {k: ({"type": v} if isinstance(v, str) else v) for k, v in _OVERRIDES_RAW.items()}

# Columns to drop from the normalized payload (keep board tidy)
EXCLUDES: list[str] = [
    "Item",  # item name already promoted elsewhere by engine
]


def _mask(s: str) -> str:
    s = str(s)
    return ("*" * max(0, len(s) - 4)) + s[-4:]


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Export Startups Health board.")
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

    board_id = args.board_id or get_board_id("incubation_health")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure incubation_health in board_config."
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
