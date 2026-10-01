import argparse
from pathlib import Path
from dotenv import load_dotenv

from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json
from board_config_db import get_board_id

_OVERRIDES_RAW = {
    # Core fields
    "Project name": "text",
    "Stage": "status",
    "Vertical": "status",
    "Status": "status",

    # Business Theme (large text)
    "Business Theme": "long_text",

    # Timeline (usually a timeline or text)
    "Timeline": "long_text",

    # Main Customer
    "Main Customer": "text",

    # Monthly Activities
    "Monthly Activities": "long_text",

    # Files, if any
    "Files": "file",
}

OVERRIDES = {
    k: ({"type": v} if isinstance(v, str) else v)
    for k, v in _OVERRIDES_RAW.items()
}

EXCLUDES: list[str] = [
    "Subitems",
    "Last Updated",
    "Person",
    "Link to Item",
]

def _mask(s: str) -> str:
    s = str(s)
    return ("*" * max(0, len(s) - 4)) + s[-4:]


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Export regional board metadata.")
    ap.add_argument("--out",
                    default=str(Path(__file__).parent / "out"),
                    help="Output directory (default: ./out)")
    ap.add_argument("--board-id",
                    default=None,
                    help="Override board ID (otherwise taken from .env)")
    args = ap.parse_args()

    board_id = args.board_id or get_board_id("korean")
    if not board_id:
        raise SystemExit(
            "Missing board id. Provide --board-id or configure korean in board_config."
        )

    config = {
        "board_id": str(board_id),
        "overrides": OVERRIDES,
        "excludes": EXCLUDES,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[KOREAN] Pulling board {_mask(board_id)}...")

    payload = pull_board(config["board_id"], config)
    write_json(payload, str(out_dir / "dump.json"), unique=True)

    print(f"[KOREAN] Exported board {_mask(board_id)} → {out_dir}")


if __name__ == "__main__":
    main()
