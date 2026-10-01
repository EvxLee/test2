# Incubation Startups Cleantech Board

import argparse
from pathlib import Path
from dotenv import load_dotenv

from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id


_OVERRIDES_RAW = {
    "Comment": "long_text",
    "Meeting Notes": "long_text",

    "Lead": "people",

    "Stage": "status",
    "Priority": "status",
    "CMBU": "status",

    "Date": "date",
    "Pre-Cap": "date",

    "SW": "file",

    "Item": "text",
    "Marketing Fund": "text",
    "Is Interested": "text",
    "Area": "text",
    "Dependent On": "text",
}

OVERRIDES = {k: ({"type": v} if isinstance(v, str) else v) for k, v in _OVERRIDES_RAW.items()}


EXCLUDES: list[str] = [
    "Item",
    "Dependent On",
]

def _mask(s: str) -> str: 
    s = str(s)
    return ("*" * max(0, len(s) - 4)) + s[-4:]

def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Export Startups Incubation board.")
    ap.add_argument(
        "--out",
        default=str(Path(__file__).parent / "out"),
        help="Output directory (default: boards/incubation/out)"
    )
    ap.add_argument(
        "--board-id",
        default=None,
        help="Optional override of the board id (takes precedence over .env)",
    )
    args = ap.parse_args()

    board_id = args.board_id or get_board_id("incubation_cleantech")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure incubation_cleantech in board_config."
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
