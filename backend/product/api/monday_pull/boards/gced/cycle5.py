# GCED Cycle 5 Board

import argparse
from pathlib import Path
from dotenv import load_dotenv

from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id

# Column behavior for this board
_OVERRIDES_RAW = {
    # Status-like (labels mapped via settings_str)
    "Startup Source": "status",
    "GCED Scrub": "status",
    "Team Decision": "status",
    "Startup Type": "status",
    "Track": "status",

    # Links
    "Hubspot Link": "link",
    "SwitchPink": "link",
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

    board_id = args.board_id or get_board_id("gced_mftf25_cycle5")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure gced_mftf25_cycle5 in board_config."
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
