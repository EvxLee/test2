from pathlib import Path

CANDS = ["utf-16","utf-16le","utf-16be","utf-32","utf-32le","utf-32be","utf-8-sig"]

def fix(p: Path):
    b = p.read_bytes()
    src = None
    for enc in CANDS:
        try:
            s = b.decode(enc)
            src = enc
            break
        except Exception:
            pass
    if src is None:
        # last resort: strip NULs then UTF-8
        s = b.replace(b"\x00", b"").decode("utf-8")
        src = "strip+utf8"
    p.write_text(s, encoding="utf-8", newline="\n")
    print(f"Re-encoded {p} from {src} -> utf-8")

for path in (Path("/app/product/__init__.py"), Path("/app/product/db/__init__.py")):
    if path.exists():
        fix(path)
    else:
        print(f"{path} does not exist (ok if namespace package).")
