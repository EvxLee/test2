from __future__ import annotations

import io
import re

import pandas as pd
from flask import Blueprint, request, Response
from rapidfuzz import fuzz, process

from database.db import SessionLocal
from database.models import PartnerAuditLog
from display.core.db import fetch_all
from extensions import limiter
from auth import require_role

bp = Blueprint("duplicate_check", __name__)

_FUZZY_THRESHOLD = 80  # minimum similarity score to flag as name duplicate


def _client_ip() -> str:
    """Return the best-guess client IP, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.remote_addr or "")[:45]


def _normalize_url(url: str | None) -> str | None:
    """Strip protocol and www prefix for domain comparison."""
    if not url or str(url).strip().lower() in ("nan", "none", ""):
        return None
    url = str(url).strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    return url or None


@bp.route("/atlas/partners/check-duplicates", methods=["POST"])
@limiter.limit("10 per hour")
@require_role("external-partner")
def check_duplicates():
    if "file" not in request.files:
        return {
            "error": "No file uploaded. Send a CSV as multipart field 'file'."
        }, 400

    file = request.files["file"]

    if not file.filename or not file.filename.lower().endswith(".csv"):
        return {"error": "File must be a CSV."}, 400

    try:
        df = pd.read_csv(io.BytesIO(file.read()))
    except Exception:
        return {"error": "Could not parse file as CSV."}, 400

    # Accept PitchBook 'Website' column or legacy 'domain_name'
    if "Website" in df.columns:
        website_col = "Website"
    elif "domain_name" in df.columns:
        website_col = "domain_name"
    else:
        return {"error": "CSV must contain a 'Website' column."}, 400

    has_company_col = "Companies" in df.columns

    # Normalize websites
    df["_website_norm"] = df[website_col].apply(_normalize_url)
    websites_to_check = df["_website_norm"].dropna().unique().tolist()

    # Normalize company names if present
    if has_company_col:
        df["_company_norm"] = df["Companies"].astype(str).str.strip()
        df.loc[
            df["_company_norm"].isin(["", "nan", "None"]), "_company_norm"
        ] = None

    # Query dp.pitchbook_companies for website and company name data
    db_websites: set[str] = set()
    db_company_names: list[str] = []

    try:
        if websites_to_check:
            rows = fetch_all(
                "SELECT website FROM dp.pitchbook_companies"
                " WHERE website IS NOT NULL"
            )
            db_websites = {
                norm
                for row in rows
                if (norm := _normalize_url(row["website"])) is not None
            }

        if has_company_col:
            rows = fetch_all(
                "SELECT company_name FROM dp.pitchbook_companies"
                " WHERE company_name IS NOT NULL"
            )
            db_company_names = [row["company_name"] for row in rows]
    except Exception:
        pass  # dp schema unavailable (local dev) — return no matches

    # Website exact match
    df["is_website_duplicate"] = df["_website_norm"].apply(
        lambda w: w in db_websites if w is not None else False
    )

    # Company name fuzzy match
    if has_company_col:
        def _is_name_duplicate(name: str | None) -> bool:
            if not name or not db_company_names:
                return False
            result = process.extractOne(
                name, db_company_names, scorer=fuzz.WRatio
            )
            return result is not None and result[1] >= _FUZZY_THRESHOLD

        df["is_name_duplicate"] = df["_company_norm"].apply(_is_name_duplicate)

    # Drop internal columns
    drop_cols = ["_website_norm"] + (["_company_norm"] if has_company_col else [])
    df.drop(columns=drop_cols, inplace=True, errors="ignore")

    # Compute duplicate count
    if has_company_col:
        duplicate_count = int(
            (df["is_website_duplicate"] | df["is_name_duplicate"]).sum()
        )
    else:
        duplicate_count = int(df["is_website_duplicate"].sum())

    # Write audit log row
    try:
        session = SessionLocal()
        try:
            log_entry = PartnerAuditLog(
                ip_address=_client_ip(),
                row_count=len(df),
                duplicate_count=duplicate_count,
            )
            session.add(log_entry)
            session.commit()
        finally:
            session.close()
    except Exception:
        pass  # Audit failure must never block the response

    # Return the original CSV with the added columns
    out = io.StringIO()
    df.to_csv(out, index=False)
    return Response(
        out.getvalue(),
        status=200,
        mimetype="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="duplicates_result.csv"'
        },
    )
