import datetime as _dt
import decimal as _dec
import json, base64, zlib

def _cursor_json_default(o):
    if isinstance(o, (_dt.datetime, _dt.date, _dt.time)):
        # keep tz info if present
        return o.isoformat()
    if isinstance(o, _dec.Decimal):
        # safe for cursors; alternatively: str(o)
        return float(o)
    return str(o)

def encode_cursor(obj):
    raw = json.dumps(
        obj,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_cursor_json_default,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw)).decode("ascii")

def decode_cursor(s):
    raw = zlib.decompress(base64.urlsafe_b64decode(s.encode("ascii")))
    return json.loads(raw.decode("utf-8"))
