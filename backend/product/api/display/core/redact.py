import re
from typing import Dict, Any

EMAIL_RX = re.compile(r'([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})')
PHONE_RX = re.compile(r'(\+?\d{1,2}[\s-]?)?(\(?\d{3}\)?)[\s-]?(\d{3})[\s-]?(\d{4})')
KEY_RX   = re.compile(r'\b(sk-[a-zA-Z0-9]{4,}|sk-proj-[a-zA-Z0-9\-]{8,}|AIza[0-9A-Za-z\-_]{10,}|ghp_[A-Za-z0-9]{20,})\b')
BEARER_RX= re.compile(r'\bBearer\s+([A-Za-z0-9\-\._~\+\/]+=*)\b', re.IGNORECASE)
URL_SECRET_RX = re.compile(r'((https?|s3|gs):\/\/[^?\s]+)\?[^#\s]*')

DROP_COLUMNS = {
    "raw_json","webhook_body","api_response","_token","_secret","password",
    "access_key","refresh_token","ip_address","audit_blob","debug_payload",
    "internal_notes",
}

def mask_text(s: str) -> str:
    if not s or not isinstance(s, str):
        return s
    s = EMAIL_RX.sub(lambda m: m.group(1)[:1] + "****@" + m.group(2), s)
    s = PHONE_RX.sub(lambda m: (m.group(1) or "+X ") + "███-███-" + m.group(4), s)
    s = KEY_RX.sub(lambda m: m.group(0).split("-")[0] + "-****", s)
    s = BEARER_RX.sub("Bearer ****", s)
    s = URL_SECRET_RX.sub(r'\1', s)
    s = re.sub(r'<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>', '', s, flags=re.I|re.S)
    return s

def sanitize_row(row: Dict[str, Any], redact_on: bool, safe_cols: set) -> Dict[str, Any]:
    if not row:
        return row
    out = {}
    for k, v in row.items():
        if k not in safe_cols:
            if k.startswith("_"):
                out[k] = v
            continue
        if not redact_on:
            out[k] = v
            continue
        if isinstance(v, str):
            out[k] = mask_text(v)
        else:
            out[k] = v
    return out
