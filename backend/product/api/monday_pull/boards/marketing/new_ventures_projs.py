# Marketing New Ventures Projects Board

import argparse
from pathlib import Path
from dotenv import load_dotenv
from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id

# source .venv/bin/activate, python -m product.api.monday_pull.boards.marketing.new_ventures_projs
# Column behavior for this board 
_OVERRIDES_RAW = {
    # People
    "Owner": "people",
    "Key Stakeholder": "people",

    # Status / labels
    "Status": "status",

    # Dates
    "Due Date": "date",
    "Live Date": "date",
    "Date": "date",
}

# Normalize to {"type": "..."} form
OVERRIDES = {k: ({"type": v} if isinstance(v, str) else v) for k, v in _OVERRIDES_RAW.items()}

# Exclude noisy display-only columns
EXCLUDES: list[str] = [
    "Subitems",
    "subitems"
]

def _mask(s: str) -> str:
    """Mask an ID for logs"""
    s = str(s)
    return ("*" * max(0, len(s) - 4)) + s[-4:]


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Export New Venture Proposals board.")
    ap.add_argument("--out", default=str(Path(__file__).parent / "out"),
                    help="Output directory (default: boards/new_venture_proposals/out)")
    ap.add_argument(
        "--board-id",
        default=None,
        help="Optional override of the board id (takes precedence over .env)",
    )
    args = ap.parse_args()

    board_id = args.board_id or get_board_id("projects")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure projects in board_config."
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
