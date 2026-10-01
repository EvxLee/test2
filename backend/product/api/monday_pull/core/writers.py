
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import json
import datetime
import os

def _ensure_dir(path: str | os.PathLike) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_json(payload, path: str, *, pretty: bool = True, unique: bool = False) -> str:
    out_path = Path(path)

    if unique:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_path.with_name(f"{out_path.stem}_{ts}{out_path.suffix}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        if pretty:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        else:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), default=str)
    return str(out_path)


def write_json_parts(
    payload: Dict[str, Any],
    out_dir: str,
    *,
    keys: Optional[Iterable[str]] = None,
    pretty: bool = True,
) -> Dict[str, str]:
    """
    Split the payload into multiple JSON files (one per top-level key).
    Example outputs:
      out_dir/board.json, items.json, files.json, etc.
    """
    out_paths: Dict[str, str] = {}
    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    use_keys = list(keys) if keys is not None else list(payload.keys())
    for k in use_keys:
        if k not in payload:
            continue
        path = out_dir_p / f"{k}.json"
        write_json(payload[k], str(path), pretty=pretty)
        out_paths[str(k)] = str(path)

    return out_paths