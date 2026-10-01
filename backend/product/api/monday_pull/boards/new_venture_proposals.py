# monday_pull/boards/new_venture_proposals/pull.py

import argparse
from pathlib import Path
from dotenv import load_dotenv

from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id

# Column behavior for this board
_OVERRIDES_RAW = {
    # Files (attachments)
    "Idea Files": "file",
    "POC Files": "file",
    "POC Results": "file",

    # Dates
    "Next Presentation Date": "date",

    # Formula
    "Report Out Deadline": "formula",

    # Long text (free text)
    "Biz-summary": "long_text",
    "Business Summary": "long_text",
    "Main Customer": "long_text",
    "Comments": "long_text",

    # People
    "Lead/CEO": "people",
    "Tech Lead/CTO": "people",

    # Status-like (labels mapped via settings_str)
    "Stage/Status": "status",
    "Idea Proposal (IP)": "status",
    "PoC Proposal": "status",
    "PoC Results": "status",
    "CMBU Proposal": "status",
    "Seed Results": "status",
    "Location": "status",
    "Vertical": "status",

    # Links
    "Link": "link",
    "Links": "link",
}

# Normalize to {"type": "..."} form
OVERRIDES = {k: ({"type": v} if isinstance(v, str) else v) for k, v in _OVERRIDES_RAW.items()}

# Exclude noisy display-only columns
EXCLUDES: list[str] = [
    "Status",
    "Subitems",
    "Last Updated"
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

    board_id = args.board_id or get_board_id("new_venture_proposals")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure new_venture_proposals in board_config."
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
