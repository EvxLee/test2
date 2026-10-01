import os
import sys
import io
import traceback
import hashlib
import json
import csv
import threading
import pandas as pd
import math
import logging
from flask_cors import CORS
from extensions import limiter

from flask import Flask, request, jsonify, Response, make_response, current_app
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask_restx import Api, Namespace, Resource, fields

# --- Your existing ORM imports (kept as-is for current endpoints) ---
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session
from database.db import SessionLocal
from database.models import StartupCompany, Location, Country, Track

# --- Monday pull / ingest modules (kept as-is) ---
from monday_pull.core.engine import pull_board
from monday_pull.core.writers import write_json

from monday_ingest.clients import fetch_live_bundle, read_export_bundle, get_file_board_ids
from monday_ingest.staging import ensure_staging, start_run, finish_run, stage_items, stage_files
from monday_ingest.transform import parse_item_payload
from monday_ingest.load import ensure_finals, load_boards, load_items_bundle, load_files

from display.core.db import fetch_all, fetch_one, quote_ident, get_conn
from display.core.cursor import encode_cursor, decode_cursor
from display.core.filtering import build_search_clause, build_filters, build_sort
from display.core.redact import sanitize_row
from display.core.attachments import get_attachments, get_links
from display.core.util import (
    table_exists,
    default_safe_columns,
    pick_searchable_columns,
    ensure_sort_keys,
    project_column_sql,
)

from pitchbook.helpers import (
    cast_boolean,
    cast_int,
    cast_decimal,
    cast_date,
    cast_text,
    find_header_idx,
    normalize_headers,
)

# Chat/LLM module
try:
    from chat.routes import register_chat_routes
    CHAT_ENABLED = True
except ImportError as e:
    CHAT_ENABLED = False
    print(f"[WARN] Chat module not available: {e}")

sys.path.append('/app')

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'csv'}


def output_json(data, code, headers=None):
    dumped = json.dumps(data, default=str)
    resp = make_response(dumped + "\n", code)
    resp.headers.extend(headers or {})
    return resp


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256_file(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return None


def _mask(s: str) -> str:
    s = str(s or "")
    return ("*" * max(0, len(s) - 4)) + s[-4:]


def _require_auth():
    auth = request.headers.get("Authorization", "")
    parts = auth.strip().split()
    token = parts[1].strip() if len(
        parts) == 2 and parts[0].lower() == "bearer" else ""
    expected = os.getenv("INGEST_API_TOKEN", "")
    if not expected or token != expected:
        return (
            {"error": {"type": "auth_error", "message": "Unauthorized"}},
            401,
            {"WWW-Authenticate": 'Bearer realm="atlas-ingest"'}
        )
    return None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _parse_list(name: str):
    v = request.args.get(name)
    if not v:
        return []
    return [t.strip() for t in v.split(",") if t.strip()]


def _parse_repeatable(name: str):
    return request.args.getlist(name)


def _bool_onoff(name: str, default_on=True) -> bool:
    v = (request.args.get(name) or "").lower()
    if v == "on":
        return True
    if v == "off":
        return False
    return default_on


def _next_cursor_from_rows(rows, sort_keys):
    if not rows:
        return None
    last = rows[-1]
    keyvals = [last.get(col) for (col, _) in sort_keys]
    return encode_cursor({"last_key": keyvals})


def _require_auth_wrapped():
    return _require_auth()


def build_where(schema, table, q, filters, searchable_cols, allowed_cols):
    clauses, params = [], []
    sq, sp = build_search_clause(q, searchable_cols)
    if sq:
        clauses.append(sq)
        params += sp
    fq, fp = build_filters(filters, allowed_cols)
    if fq:
        clauses.append(fq)
        params += fp
    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params


def apply_cursor(sort_pairs, cursor, where_sql, params):
    if not cursor:
        return where_sql, params
    payload = decode_cursor(cursor)
    last_key = payload.get("last_key")
    if not last_key or len(last_key) != len(sort_pairs):
        return where_sql, params
    comps = []
    for i in range(len(sort_pairs)):
        prefix_eq = []
        for j in range(i):
            colj, _ = sort_pairs[j]
            prefix_eq.append(f"{quote_ident(colj)} = %s")
        coli, diri = sort_pairs[i]
        op = ">" if diri.upper() == "ASC" else "<"
        ith = f"{quote_ident(coli)} {op} %s"
        parts = []
        if prefix_eq:
            parts.append("(" + " AND ".join(prefix_eq) + f" AND {ith})")
        else:
            parts.append(ith)
        comps.append("(" + " AND ".join(parts) + ")")
    cursor_clause = "(" + " OR ".join(comps) + ")"
    where_sql = (
        "WHERE " + cursor_clause) if not where_sql else (where_sql + " AND " + cursor_clause)

    cursor_params = []
    for i in range(len(sort_pairs)):
        cursor_params += last_key[:i] + [last_key[i]]
    return where_sql, params + cursor_params


def _expand_includes_list(schema, table, rows, includes, redact_on, safe_cols_set):
    """Inline attachments/links for a list of rows and re-sanitize."""
    if not rows:
        return rows
    want_att = "attachments" in includes
    want_links = "links" in includes
    if not (want_att or want_links):
        return rows

    out = []
    for r in rows:
        rr = dict(r)
        rid = str(rr.get("id") or rr.get("uuid")
                  or rr.get("pk") or rr.get("gid") or "")
        if want_att:
            rr["_attachments"] = get_attachments(schema, table, rid)
        if want_links:
            rr["_links"] = [
                {"rel": x["rel"], "href": x["href"], "label": x["label"]}
                for x in get_links(schema, table, rid)
            ]
        out.append(sanitize_row(rr, redact_on, safe_cols_set |
                   {"_attachments", "_links"}))
    return out


def _expand_includes_single(schema, table, row, includes, redact_on, safe_cols_set):
    """Inline attachments/links for a single row and re-sanitize."""
    rr = dict(row)
    rid = str(rr.get("id") or rr.get("uuid")
              or rr.get("pk") or rr.get("gid") or "")
    if "attachments" in includes:
        rr["_attachments"] = get_attachments(schema, table, rid)
    if "links" in includes:
        rr["_links"] = [
            {"rel": x["rel"], "href": x["href"], "label": x["label"]}
            for x in get_links(schema, table, rid)
        ]
    return sanitize_row(rr, redact_on, safe_cols_set | {"_attachments", "_links"})


# PitchBook per-column type mapping: db_column -> caster
TYPE_MAP_PITCHBOOK = {
    "contains_cross_border": cast_boolean,
    "add_on": cast_boolean,

    "total_patent_documents": cast_int,
    "total_patent_families": cast_int,
    "active_patent_documents": cast_int,
    "pending_patent_documents": cast_int,
    "current_employees": cast_int,
    "year_founded": cast_int,
    "fiscal_year": cast_int,
    "deal_no": cast_int,
    "investors_count": cast_int,
    "new_investors_count": cast_int,
    "follow_on_investors_count": cast_int,

    "revenue": cast_decimal,
    "net_income": cast_decimal,
    "ebitda": cast_decimal,
    "valuation_ebitda": cast_decimal,
    "valuation_net_income": cast_decimal,
    "valuation_revenue": cast_decimal,
    "deal_size_ebitda": cast_decimal,
    "deal_size_net_income": cast_decimal,
    "deal_size_revenue": cast_decimal,
    "ebitda_margin_pct": cast_decimal,
    "deal_size": cast_decimal,
    "pre_money_valuation": cast_decimal,
    "post_valuation": cast_decimal,
    "percent_acquired": cast_decimal,
    "raised_to_date": cast_decimal,
    "total_invested_equity": cast_decimal,

    "announced_date": cast_date,
    "deal_date": cast_date,
}

# Per-column type mapping for dp.pitchbook_companies (company-profile format)
TYPE_MAP_PITCHBOOK_COMPANIES = {
    "employees":           cast_int,
    "year_founded":        cast_int,
    "revenue":             cast_decimal,
    "total_raised":        cast_decimal,
    "last_financing_size": cast_decimal,
    "opportunity_score":   cast_decimal,
    "last_financing_date": cast_date,
    "last_updated_date":   cast_date,
}


def _clean_db_value(v):
    # Normalize pandas/NumPy NaNs and infinities to None before sending to Postgres
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    return v


def create_app():
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    CORS(
        app,
        resources={
            r"/atlas/display/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/atlas/files/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/atlas/chat/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/atlas/monday/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/atlas/boards/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/atlas/pitchbook/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/atlas/partners/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/atlas/document-search": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/mondayboard/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            r"/cycles/*": {"origins": ["http://localhost:5173", "https://atlas-develop.example.com"]},
            # Health check and status endpoints - allow all origins
            r"/v1/*": {"origins": "*"},
        },
        supports_credentials=True,
    )
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    limiter.init_app(app)

    from auth import get_jwt_roles

    @app.before_request
    def block_external_partner_non_partner_routes():
        if request.method == "OPTIONS":
            return None
        auth = request.headers.get("Authorization", "")
        parts = auth.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        roles = get_jwt_roles(parts[1])
        if "external-partner" in roles and not request.path.startswith("/atlas/partners/"):
            return {"error": {"type": "auth_error", "message": "Forbidden"}}, 403
        return None

    authorizations = {
        "bearer": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Use: Bearer <INGEST_API_TOKEN>",
        }
    }

    api = Api(
        app,
        version="1.0",
        title="Atlas API",
        description="Atlas endpoints",
        authorizations=authorizations,
        security='bearer',
    )

    api.representations['application/json'] = output_json

    ns = Namespace("atlas", description="Atlas resources")
    api.add_namespace(ns)

    from commands import monday_cli
    app.cli.add_command(monday_cli)
    # Register chat routes if available
    if CHAT_ENABLED:
        register_chat_routes(ns)
        print("[INFO] Chat routes registered")

    # Register partner duplicate-check routes
    from duplicate_check.routes import bp as duplicate_check_bp
    app.register_blueprint(duplicate_check_bp)
    from cycles.routes import bp as cycles_bp
    app.register_blueprint(cycles_bp)

    startup_model = ns.model("Startup", {
        "company_id": fields.Integer,
        "domain_name": fields.String,
        "short_description": fields.String,
        "employees": fields.Integer,
        "founded": fields.Integer,
        "revenue_range": fields.String,
        "track_name": fields.String,
        "city": fields.String,
        "state_region": fields.String,
        "country_code": fields.String,
        "country_name": fields.String,
    })

    page_meta = ns.model("PageMeta", {
        "page": fields.Integer,
        "per_page": fields.Integer,
        "total_items": fields.Integer,
        "total_pages": fields.Integer,
    })

    page_response = ns.model("PageResponse", {
        "meta": fields.Nested(page_meta),
        "data": fields.List(fields.Nested(startup_model)),
    })

    def get_db() -> Session:
        return SessionLocal()

    @ns.route("/startups")
    class StartupList(Resource):
        @ns.doc(
            description="Get a paginated list of startup companies from the database.",
            params={
                "page": "Page number (1-based)",
                "per_page": "Items per page (max 200)",
                "q": "Free-text search in domain/description",
                "track": "Track name (exact)",
                "country": "Country code",
                "state": "State/Region (exact)",
                "city": "City (exact)",
            },
            responses={200: "OK", 400: "Bad Request", 500: "Server Error"},
        )
        @ns.marshal_with(page_response)
        def get(self):
            page = max(int(request.args.get("page", 1)), 1)
            per_page = min(max(int(request.args.get("per_page", 10)), 1), 200)

            q = request.args.get("q")
            track = request.args.get("track")
            country = request.args.get("country")
            state = request.args.get("state")
            city = request.args.get("city")

            db = get_db()
            try:
                base = (
                    select(
                        StartupCompany.company_id,
                        StartupCompany.domain_name,
                        StartupCompany.short_description,
                        StartupCompany.employees,
                        StartupCompany.founded,
                        StartupCompany.revenue_range,
                        Track.track_name,
                        Location.city,
                        Location.state_region,
                        Country.code.label("country_code"),
                        Country.name.label("country_name"),
                    )
                    .select_from(StartupCompany)
                    .join(Location, Location.location_id == StartupCompany.location_id, isouter=True)
                    .join(Country, Country.code == Location.country_code, isouter=True)
                    .join(Track, Track.track_id == StartupCompany.track, isouter=True)
                )

                filters = []
                if q:
                    like = f"%{q}%"
                    filters.append(or_(
                        StartupCompany.domain_name.ilike(like),
                        StartupCompany.short_description.ilike(like),
                        StartupCompany.description.ilike(like),
                    ))
                if track:
                    filters.append(Track.track_name == track)
                if country:
                    filters.append(Country.code == country.upper())
                if state:
                    filters.append(Location.state_region == state)
                if city:
                    filters.append(Location.city == city)

                if filters:
                    base = base.where(and_(*filters))

                total_items = db.execute(
                    select(func.count()).select_from(base.subquery())).scalar_one()
                total_pages = (total_items + per_page -
                               1) // per_page if total_items else 0
                if total_pages and page > total_pages:
                    page = total_pages
                offset = (page - 1) * per_page if total_items else 0

                page_stmt = base.order_by(StartupCompany.company_id.asc()).offset(
                    offset).limit(per_page)
                rows = db.execute(page_stmt).all()

                data = [{
                    "company_id": r.company_id,
                    "domain_name": r.domain_name,
                    "short_description": r.short_description,
                    "employees": r.employees,
                    "founded": r.founded,
                    "revenue_range": r.revenue_range,
                    "track_name": r.track_name,
                    "city": r.city,
                    "state_region": r.state_region,
                    "country_code": r.country_code,
                    "country_name": r.country_name,
                } for r in rows]

                return {
                    "meta": {
                        "page": page,
                        "per_page": per_page,
                        "total_items": total_items,
                        "total_pages": total_pages,
                    },
                    "data": data,
                }, 200

            except Exception as e:
                db.rollback()
                return {"error": str(e)}, 500
            finally:
                db.close()

    upload = ns.parser()
    upload.add_argument("file", location="files",
                        type=FileStorage, required=True)

    @ns.route("/ingest/csv")
    class IngestCSV(Resource):
        @ns.expect(upload)
        @ns.doc(description="Upload a consolidated CSV and ingest rows into the DB.")
        def post(self):
            from ingest.ingest_service import upsert_company_from_row
            args = upload.parse_args()
            file = args.get("file")
            if not file:
                return {"error": "No file provided"}, 400

            import pandas as pd
            filename = secure_filename(file.filename or "upload.csv")
            content = file.read()
            current_app.logger.info(
                "CSV ingest: start filename=%s size_bytes=%s", filename, len(content))
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")

            processed = 0
            errors = 0
            error_samples = []

            db = get_db()
            try:
                batch = 0
                for idx, row in df.iterrows():
                    try:
                        upsert_company_from_row(db, row.to_dict())
                        batch += 1
                        processed += 1
                        if batch >= 100:
                            db.commit()
                            batch = 0
                    except Exception as e:
                        db.rollback()
                        errors += 1
                        if len(error_samples) < 10:
                            error_samples.append(
                                {"row": int(idx), "error": str(e)})

                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
                    errors += 1
                    if len(error_samples) < 10:
                        error_samples.append({"row": "final", "error": str(e)})

            finally:
                db.close()

            return {"status": "ok", "rows_processed": processed, "errors": errors, "columns": list(df.columns), "error_samples": error_samples}, 200

    @app.route("/")
    def index():
        return "This is the Atlas backend!"

    @app.route("/v1/status/")
    def status():
        """Health check endpoint for Kubernetes liveness/readiness probes."""
        return jsonify({"status": "ok"}), 200

    @app.route("/mondayboard/populate", methods=["POST"])
    def populate_board():
        try:
            from populate_newboard import populate_board_from_csv
            if 'file' not in request.files:
                return jsonify({"error": "No file part in the request"}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400

            if not allowed_file(file.filename):
                return jsonify({"error": "Only .csv files are allowed"}), 400

            board_name = request.form.get("board_name")
            workspace_name = request.form.get("workspace_name")

            if not board_name:
                return jsonify({"error": "Missing board_name in form data"}), 400
            if not workspace_name:
                return jsonify({"error": "Missing workspace_name in form data"}), 400

            filename = secure_filename(file.filename)
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(temp_path)

            populate_board_from_csv(temp_path, board_name, workspace_name)

            return jsonify({"message": f"{board_name} populated successfully in Workspace: {workspace_name}."}), 200

        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    from auth import require_role
    from board_config_db import get_all_boards, update_board_config, upsert_board_config
    from boards_registry import BOARD_REGISTRY

    storage_model = ns.model("ExportStorage", {
        "local_path": fields.String(required=False, description="Base output dir (default: /app/exports/monday)")
    })

    export_dl_req = ns.model("ExportDownloadRequest", {
        "board_ids": fields.List(fields.String, required=True, description="List of Monday board IDs to export"),
        "storage": fields.Nested(storage_model, required=False),
        "dedupe_on_checksum": fields.Boolean(required=False, description="Skip writing if dump is identical"),
    })

    artifact_model = ns.model("ExportArtifact", {
        "board_id": fields.String,
        "out_dir": fields.String,
        "dump_file": fields.String,
        "items": fields.Integer,
        "groups": fields.Integer,
        "columns": fields.Integer,
        "sha256": fields.String,
        "skipped": fields.Boolean,
        "message": fields.String,
    })

    export_dl_resp = ns.model("ExportDownloadResponse", {
        "boards_requested": fields.Integer,
        "boards_downloaded": fields.Integer,
        "artifacts": fields.List(fields.Nested(artifact_model)),
        "totals": fields.Raw,
    })

    @ns.route("/monday/boards")
    class MondayBoards(Resource):
        @ns.doc(description="List available Monday.com board keys.")
        def get(self):
            return {"boards": sorted(BOARD_REGISTRY.keys())}, 200

    @ns.route("/boards/config")
    class BoardsConfig(Resource):
        @ns.doc(description="Return all active board configurations from the database.")
        def get(self):
            return {"boards": get_all_boards()}, 200

        @require_role("admin")
        @ns.doc(description="Create or upsert a Monday board configuration. Requires admin role.")
        def post(self):
            try:
                board = upsert_board_config(request.get_json(force=True) or {})
                return {"board": board}, 201
            except ValueError as e:
                return {"error": str(e)}, 400

    @ns.route("/boards/config/<string:board_key>")
    class BoardConfig(Resource):
        @require_role("admin")
        @ns.doc(description="Update a Monday board configuration. Requires admin role.")
        def patch(self, board_key):
            try:
                board = update_board_config(board_key, request.get_json(force=True) or {})
            except ValueError as e:
                return {"error": str(e)}, 400
            if not board:
                return {"error": "Board config not found"}, 404
            return {"board": board}, 200

    @ns.route("/monday/export")
    class MondayExport(Resource):
        @ns.expect(export_dl_req, validate=True)
        @ns.marshal_with(export_dl_resp, code=200)
        @ns.doc(description="Export one or more Monday boards by raw board_id. Optional local storage base and checksum dedupe.")
        def post(self):
            data = request.get_json(force=True) or {}

            board_ids = data.get("board_ids") or []
            if not board_ids:
                return {"message": "board_ids is required and must be a non-empty list."}, 400

            storage = data.get("storage")
            if not isinstance(storage, dict):
                storage = {}

            local_path = storage.get("local_path")
            if not local_path or str(local_path).strip().lower() == "string":
                base_out = "/app/exports/monday"
            else:
                base_out = str(local_path)

            os.makedirs(base_out, exist_ok=True)

            dedupe = bool(data.get("dedupe_on_checksum", False))

            artifacts = []
            totals = {"items": 0, "groups": 0, "columns": 0}
            downloaded = 0

            for bid in board_ids:
                out_dir = os.path.join(base_out, str(bid))
                os.makedirs(out_dir, exist_ok=True)
                dump_path = os.path.join(out_dir, "dump.json")

                config = {"board_id": str(
                    bid), "overrides": {}, "excludes": []}
                payload = pull_board(config["board_id"], config)

                payload_bytes = json.dumps(payload, separators=(
                    ",", ":"), ensure_ascii=False).encode("utf-8")
                new_sha = _sha256_bytes(payload_bytes)
                old_sha = _sha256_file(dump_path)

                skipped = False
                if dedupe and old_sha == new_sha:
                    skipped = True
                    msg = f"Identical payload found for {bid}; skipped write."
                else:
                    write_json(payload, dump_path, unique=False)
                    msg = f"Exported board {bid} → {dump_path}"
                    downloaded += 1

                items = len(payload.get("items", []))
                groups = len(payload.get("groups", []))
                columns = len(payload.get("columns", []))

                if not skipped:
                    totals["items"] += items
                    totals["groups"] += groups
                    totals["columns"] += columns

                artifacts.append({
                    "board_id": str(bid),
                    "out_dir": out_dir,
                    "dump_file": dump_path,
                    "items": items,
                    "groups": groups,
                    "columns": columns,
                    "sha256": new_sha,
                    "skipped": skipped,
                    "message": msg,
                })

            return {
                "boards_requested": len(board_ids),
                "boards_downloaded": downloaded,
                "artifacts": artifacts,
                "totals": totals,
            }, 200

    @ns.route("/monday/ingest")
    class MondayIngest(Resource):
        ingest_req = ns.model(
            "MondayIngestRequest",
            {
                "source": fields.Nested(
                    ns.model(
                        "IngestSource",
                        {
                            "type": fields.String(
                                required=False,
                                description="Source type. Use 'live' to pull from Monday's API or 'run_id' to reuse a prior export.",
                                example="live",
                                enum=["live", "run_id"]
                            ),
                            "board_ids": fields.List(
                                fields.String,
                                required=True,
                                description="List of Monday board IDs to ingest. Typically only one board ID is required per call.",
                                example=["10000000004"]
                            ),
                            "download": fields.Nested(
                                ns.model(
                                    "DownloadOptions",
                                    {
                                        "board_ids": fields.List(
                                            fields.String,
                                            description="Explicit board IDs for the download request (overrides top-level board_ids)."
                                        ),
                                        "include": fields.List(
                                            fields.String,
                                            description="Optional related entities to include (e.g., 'updates', 'column_values')."
                                        ),
                                        "since": fields.String(
                                            description="Optional ISO 8601 timestamp to fetch only items updated after this time.",
                                            example="2025-10-01T00:00:00Z"
                                        )
                                    }
                                ),
                                description="Controls how the Monday board data is fetched."
                            ),
                        },
                    ),
                    description="Defines the ingestion source (live or prior run)."
                ),
                "options": fields.Nested(
                    ns.model(
                        "IngestOptions",
                        {
                            "handle_deletes": fields.String(
                                required=False,
                                description=(
                                    "How to handle items that no longer exist upstream. "
                                    "'soft' marks them deleted (default), 'hard' purges them."
                                ),
                                example="soft",
                                enum=["soft", "hard"]
                            ),
                            "dry_run": fields.Boolean(
                                required=False,
                                description="If true, validates the pipeline without committing changes.",
                                example=False
                            ),
                            "verbose": fields.Boolean(
                                required=False,
                                description="If true, enables detailed logging for debugging.",
                                example=True
                            )
                        },
                    ),
                    description="Optional behavioral flags for ingestion and load phases."
                ),
            },
        )

        @ns.expect(ingest_req, validate=True)
        @ns.doc(
            security='bearer',
            description="""Ingest data from Monday.com into Atlas. Pulls board data live or replays previous run; stages → loads → maps to core."""
        )
        def post(self):
            bearer = _require_auth()

            body = request.get_json(force=True) or {}
            source = body.get("source") or {}
            opts = body.get("options") or {}
            handle_deletes = (opts.get("handle_deletes") or "soft").lower()

            print("DEBUG /monday/ingest body:",
                  json.dumps(body, indent=2), flush=True)

            stype = (source.get("type") or "live").lower()
            if stype not in ("live", "run_id"):
                return {"error": {"type": "validation_error", "message": "source.type must be 'live' or 'run_id'"}}, 422

            dl = source.get("download") or {}
            board_ids = dl.get("board_ids") or source.get("board_ids")
            if not board_ids or not isinstance(board_ids, list):
                return {
                    "error": {
                        "type": "validation_error",
                        "message": "Provide source.board_ids as a non-empty list: ['<id1>','<id2>', ...]"
                    }
                }, 422
            board_ids = [str(b).strip() for b in board_ids if str(b).strip()]

            print("DEBUG ingest stype:", stype,
                  "board_ids:", board_ids, flush=True)

            db = SessionLocal()
            conn = db.bind.raw_connection()
            cur = conn.cursor()

            import uuid
            run_id = uuid.uuid4()

            def _compact(d: dict) -> dict:
                out = {}
                for k, v in d.items():
                    if v is None:
                        continue
                    if isinstance(v, dict) and not v:
                        continue
                    out[k] = v
                return out

            per_board = []
            totals = {
                "boards": 0,
                "items_staged": 0,
                "items_ins": 0,
                "items_upd": 0,
                "items_del": 0,
                "name_upd": 0,
            }

            try:
                try:
                    ensure_staging(cur)
                    ensure_finals(cur)
                    conn.commit()
                except NotImplementedError:
                    pass

                try:
                    start_run(cur, run_id)
                    conn.commit()
                except NotImplementedError:
                    pass

                for bid in board_ids:
                    board_result = {
                        "board_id": bid,
                        "staged_items": 0,
                        "summary": {"items": {"ins": 0, "upd": 0, "del": 0, "name_upd": 0}},
                        "status": "ok",
                    }
                    try:
                        print(
                            "DEBUG before fetch_live_bundle; using function from module:",
                            getattr(fetch_live_bundle, "__module__", None),
                            "for board:", bid,
                            flush=True,
                        )
                        if stype == "live":
                            try:
                                bundle = fetch_live_bundle(bid, include=dl.get(
                                    "include"), since=dl.get("since"))
                            except NotImplementedError:
                                bundle = {
                                    "board": {"id": bid, "name": None}, "items": [], "subitems": []}
                        else:
                            try:
                                bundle = read_export_bundle(bid)
                            except NotImplementedError:
                                bundle = {
                                    "board": {"id": bid, "name": None}, "items": [], "subitems": []}

                        board_payload = bundle.get("board") or {}
                        items_payload = bundle.get("items") or []
                        subitems_payload = bundle.get("subitems") or []
                        files_payload = bundle.get("files") or []

                        # Upsert the board into monday.boards BEFORE dealing with items
                        try:
                            load_boards(cur, board_payload)
                            conn.commit()
                            print(
                                f"[INGEST] Upserted board {board_payload.get('id') or bid} into monday.boards", flush=True)
                        except Exception as e:
                            # If this fails, better to fail the board than proceed and hit FK errors later
                            print(
                                f"[INGEST] ERROR upserting board {bid} into monday.boards: {e}", flush=True)
                            raise

                        print(
                            f"[DEBUG] ingest: for board {bid}, "
                            f"items_payload={len(items_payload)}, "
                            f"subitems_payload={len(subitems_payload)}",
                            flush=True,
                        )

                        # Combine parent items + subitems for staging so subitems land in monday_staging.items_json
                        all_items_payload = list(
                            items_payload) + list(subitems_payload)

                        print(
                            f"[DEBUG] ingest: for board {bid}, all_items_payload={len(all_items_payload)}",
                            flush=True,
                        )

                        try:
                            staged = stage_items(
                                cur, run_id, all_items_payload, bid)

                            if all_items_payload:
                                print(
                                    "DEBUG sample item before stage_items:",
                                    json.dumps(all_items_payload[0], indent=2)[
                                        :2000],
                                )

                            board_result["staged_items"] = int(staged or 0)
                            totals["items_staged"] += int(staged or 0)
                            conn.commit()
                        except NotImplementedError:
                            pass

                        # Stage files
                        try:
                            staged_files = stage_files(
                                cur, run_id, files_payload)
                            print(
                                f"[INGEST] Staged {staged_files} files for board {bid}", flush=True)
                            conn.commit()
                        except Exception as e:
                            print(
                                f"[INGEST] WARNING: Failed to stage files: {e}", flush=True)

                        try:
                            from api.monday_ingest.load import load_items_bundle as loader
                            from api.monday_ingest.transform import parse_item_payload as parser
                            changes = loader(
                                cur,
                                run_id,
                                bid,
                                items_payload,
                                parser,
                                handle_deletes=handle_deletes
                            ) or {"ins": 0, "upd": 0, "del": 0, "name_upd": 0}
                            board_result["summary"]["items"] = {
                                "ins": int(changes.get("ins", 0)),
                                "upd": int(changes.get("upd", 0)),
                                "del": int(changes.get("del", 0)),
                                "name_upd": int(changes.get("name_upd", 0)),
                            }
                            totals["items_ins"] += board_result["summary"]["items"]["ins"]
                            totals["items_upd"] += board_result["summary"]["items"]["upd"]
                            totals["items_del"] += board_result["summary"]["items"]["del"]
                            totals["name_upd"] += board_result["summary"]["items"]["name_upd"]
                            conn.commit()
                        except NotImplementedError:
                            pass

                        # Load files into final schema (with item metadata for enrichment)
                        try:
                            file_changes = load_files(cur, bid, files_payload, items_payload) or {
                                "ins": 0, "upd": 0}
                            print(
                                f"[INGEST] Loaded files for board {bid}: inserted={file_changes.get('ins', 0)}, updated={file_changes.get('upd', 0)}", flush=True)
                            conn.commit()
                        except Exception as e:
                            print(
                                f"[INGEST] WARNING: Failed to load files: {e}", flush=True)
                            traceback.print_exc()

                        # Upload files to DO Spaces (idempotent — skips already-uploaded keys)
                        try:
                            from files.spaces import upload_monday_files
                            upload_monday_files(cur, conn, bid, files_payload)
                        except Exception as e:
                            print(f"[INGEST] WARNING: Spaces upload step failed for board {bid}: {e}", flush=True)
                            traceback.print_exc()

                        # Embed files for the AI Locate board after Spaces upload sets spaces_key
                        from board_config_db import get_board_ids_by_mapper_type
                        _ai_boards = get_board_ids_by_mapper_type("ai_locate_file", "file_metadata")
                        if bid in _ai_boards:
                            try:
                                from chat.embed_documents import fetch_files, embed_and_store
                                from chat.llm_client import get_embedding_client
                                print(f"[INGEST] Generating embeddings for AI Locate board {bid}...", flush=True)
                                _embed_stats = embed_and_store(fetch_files(board_id=bid), get_embedding_client())
                                print(f"[INGEST] Embeddings done: {_embed_stats}", flush=True)
                            except Exception as e:
                                print(f"[INGEST] WARNING: Embedding step failed (search may be stale): {e}", flush=True)
                                traceback.print_exc()

                        totals["boards"] += 1

                    except Exception as e:
                        board_result["status"] = "error"
                        board_result["error"] = str(e)
                        conn.rollback()

                    per_board.append(_compact(board_result))

                try:
                    from db.core_mapping import map_monday_to_core
                    from db.hydrate import hydrate_monday_from_staging

                    print(
                        "\n\n================ INSTRUMENTED INGEST START ================", flush=True)
                    print("board_ids =", board_ids, flush=True)
                    print("About to enter HYDRATE + MAPPING loop...", flush=True)

                    for b in board_ids:
                        print(
                            f"\n=== [INGEST] START BOARD {b} ===", flush=True)

                        try:
                            print(
                                f"[INGEST] (1) Committing before hydrate for board {b}", flush=True)
                            conn.commit()

                            print(
                                f"[INGEST] (2) Calling hydrate_monday_from_staging() for board {b}", flush=True)
                            try:
                                hydrate_monday_from_staging(conn)
                                print(
                                    f"[INGEST] (3) hydrate OK for board {b}", flush=True)
                            except Exception as e:
                                print(
                                    f"\n******** HYDRATE ERROR for board {b} ********", flush=True)
                                traceback.print_exc()
                                print(
                                    "********************************************\n", flush=True)
                                raise  # ensure we STOP + see the error

                            print(
                                f"[INGEST] (4) Committing after hydrate for board {b}", flush=True)
                            conn.commit()

                            print(
                                f"[INGEST] (5) Calling map_monday_to_core() for board {b}", flush=True)
                            try:
                                map_monday_to_core(conn, board_ids=[str(b)])
                                print(
                                    f"[INGEST] (6) mapping OK for board {b}", flush=True)
                            except Exception as e:
                                print(
                                    f"\n******** MAPPING ERROR for board {b} ********", flush=True)
                                traceback.print_exc()
                                print(
                                    "********************************************\n", flush=True)
                                raise

                            print(
                                f"[INGEST] (7) Final commit after mapping for board {b}", flush=True)
                            conn.commit()

                        except Exception as e:
                            print(
                                f"\n=== [INGEST] ERROR in board {b}: {e} ===\n", flush=True)
                            traceback.print_exc()
                            conn.rollback()

                            updated = False
                            for br in per_board:
                                if br.get("board_id") == str(b):
                                    br["status"] = "error"
                                    br["error"] = str(e)
                                    updated = True
                                    break
                            if not updated:
                                per_board.append(
                                    {"board_id": str(b), "status": "error", "error": str(e)})

                except Exception:
                    traceback.print_exc()

                ok_cnt = sum(1 for b in per_board if b.get("status") == "ok")
                err_cnt = sum(1 for b in per_board if b.get(
                    "status") == "error")
                if err_cnt == 0:
                    overall_status = "ok"
                elif ok_cnt == 0:
                    overall_status = "error"
                else:
                    overall_status = "partial"

                overall_summary = {
                    "status": overall_status,
                    "totals": totals,
                    "per_board": per_board,
                    "handle_deletes": handle_deletes,
                }

                try:
                    finish_run(cur, run_id, "succeeded" if overall_status !=
                               "error" else "failed", overall_summary)
                    conn.commit()
                except NotImplementedError:
                    pass

                if overall_status != "error" and not opts.get("dry_run"):
                    def _background_embed():
                        try:
                            from commands import _run_embed
                            _run_embed()
                        except Exception as e:
                            print(f"[EMBED] Background embedding error: {e}", flush=True)
                    threading.Thread(target=_background_embed, daemon=True).start()
                    print("[EMBED] Background embedding thread started.", flush=True)

                return {
                    "status": overall_status,
                    "run_id": str(run_id),
                    "source_type": stype,
                    "boards_processed": len(board_ids),
                    "board_ids": board_ids,
                    "summary": overall_summary,
                    "message": f"Ingested {len(board_ids)} board(s): {', '.join(board_ids)}",
                }, 200 if overall_status != "error" else 207

            except Exception as e:
                conn.rollback()
                try:
                    finish_run(cur, run_id, "failed", {"error": str(e)})
                    conn.commit()
                except Exception:
                    pass
                return {"status": "error", "error": {"type": "internal", "message": str(e)}}, 500
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
                conn.close()
                db.close()

    @ns.route("/display/data")
    class DisplayData(Resource):
        @ns.doc(
            security='bearer',
            description="Unified read endpoint: list/single row with search, filters, sort, cursor, CSV export.",
            params={
                "schema":  "Required. DB schema name.",
                "table":   "Required. Table name.",
                "rid":     "If provided, returns a single row by this id.",
                "columns": "Comma-separated projection (subset of safe columns).",
                "q":       "Free-text search query.",
                "filter":  "Repeatable. col:op:value or col=value (eq).",
                "sort":    "col1:asc,col2:desc (or -col for desc if you implemented that).",
                "limit":   "Max rows (default 50; max 500). Ignored when rid is set.",
                "cursor":  "Opaque cursor for keyset pagination.",
                "include": "Comma-separated: attachments,links",
                "redact":  "on|off (default on).",
                "format":  "json|csv (default json)."
            }
        )
        def get(self):
            # Auth
            if (auth := _require_auth_wrapped()):
                return auth

            # Required params
            schema = (request.args.get("schema") or "").strip()
            table = (request.args.get("table") or "").strip()
            if not schema or not table:
                return {"error": {"message": "Missing required params: schema, table"}}, 400
            if not table_exists(schema, table):
                return {"error": {"message": f"{schema}.{table} not found"}}, 404

            # Common params
            rid = request.args.get("rid")
            fmt = (request.args.get("format") or "json").lower()
            include = set(_parse_list("include"))
            redact_on = _bool_onoff("redact", default_on=True)
            q = request.args.get("q") or ""
            filters = _parse_repeatable("filter")
            allowed = default_safe_columns(schema, table) or []
            req_cols = _parse_list("columns")
            if req_cols:
                safe_cols = [c for c in req_cols if c in set(allowed)]
                if not safe_cols:
                    return {"error": {"message": "None of the requested columns are allowed for this table."}}, 400
            else:
                safe_cols = allowed

            searchable = pick_searchable_columns(schema, table)

            sort_pairs = ensure_sort_keys(
                schema, table, build_sort(
                    request.args.get("sort") or "", allowed)
            )
            limit = 1 if rid else min(
                int(request.args.get("limit") or 50), 500)
            cursor = None if rid else (request.args.get("cursor") or None)

            where_sql, params = build_where(
                schema, table, q, filters, searchable, allowed)
            if not rid:
                where_sql, params = apply_cursor(
                    sort_pairs, cursor, where_sql, params)

            select_cols_sql = project_column_sql(schema, table, safe_cols)
            from_sql = f'FROM {quote_ident(schema)}.{quote_ident(table)}'

            if rid:
                idcol = "id" if "id" in safe_cols else (
                    safe_cols[0] if safe_cols else "id")
                sql = f"""
                    SELECT {select_cols_sql}
                    {from_sql}
                    WHERE {quote_ident(idcol)} = %s
                    LIMIT 1
                """
                row = fetch_one(sql, (rid,))
                if not row:
                    return {"error": {"message": f"{schema}.{table} id={rid} not found"}}, 404
                sset = set(safe_cols)
                row = sanitize_row(row, redact_on, sset)
                if "attachments" in include or "links" in include:
                    row = _expand_includes_single(
                        schema, table, row, include, redact_on, sset)
                return row, 200

            order_sql = "ORDER BY " + \
                ", ".join(f"{quote_ident(c)} {d}" for c, d in sort_pairs)
            sql = f"SELECT {select_cols_sql} {from_sql} {where_sql} {order_sql} LIMIT %s"
            rows = fetch_all(sql, tuple(params + [limit]))

            sset = set(safe_cols)
            rows = [sanitize_row(r, redact_on, sset) for r in rows]
            if "attachments" in include or "links" in include:
                rows = _expand_includes_list(
                    schema, table, rows, include, redact_on, sset)

            next_cur = _next_cursor_from_rows(rows, sort_pairs)

            if fmt == "csv":
                def gen():
                    buf = io.StringIO()
                    w = csv.DictWriter(
                        buf, fieldnames=safe_cols, extrasaction="ignore")
                    w.writeheader()
                    yield buf.getvalue()
                    buf.seek(0)
                    buf.truncate(0)
                    for r in rows:
                        w.writerow({k: r.get(k) for k in safe_cols})
                        yield buf.getvalue()
                        buf.seek(0)
                        buf.truncate(0)
                headers = {
                    "X-Next-Cursor": next_cur or "",
                    "Content-Disposition": f'attachment; filename="{schema}_{table}.csv"',
                }
                return Response(gen(), mimetype="text/csv", headers=headers)

            return {
                "schema": schema,
                "table": table,
                "columns": safe_cols,
                "count": len(rows),
                "next_cursor": next_cur,
                "rows": rows,
            }, 200

    @ns.route("/display/budget-by-stage")
    class BudgetByStage(Resource):
        @ns.doc(
            security="bearer",
            description="Aggregated contract spend per project and per stage (for project detail panel and reporting).",
            params={
                "project_id": "Optional. UUID of project; if omitted, returns all projects.",
            },
        )
        def get(self):
            if (auth := _require_auth_wrapped()):
                return auth
            project_id = (request.args.get("project_id") or "").strip() or None
            # Contract rows are not always linked to master_dashboard.projects yet.
            # When project_id is missing, fall back to the Monday "Project / Task"
            # text so the UI still gets grouped budget totals.
            project_name_expr = (
                "COALESCE("
                "NULLIF(TRIM(p.name), ''), "
                "CASE "
                "WHEN NULLIF(TRIM(cs.pjt_task), '') IS NULL OR UPPER(TRIM(cs.pjt_task)) = 'N/A' "
                "THEN NULL "
                "ELSE TRIM(cs.pjt_task) "
                "END"
                ")"
            )
            stage_expr = (
                "CASE "
                "WHEN NULLIF(TRIM(cs.stage), '') IS NULL OR UPPER(TRIM(cs.stage)) = 'N/A' "
                "THEN 'Unassigned' "
                "ELSE TRIM(cs.stage) "
                "END"
            )
            normalized_budget_sql = f"""
                WITH normalized AS (
                    SELECT
                        cs.project_id,
                        {project_name_expr} AS project_name,
                        {stage_expr} AS stage_name,
                        COALESCE(cs.contract_amount::numeric, 0) AS contract_amount
                    FROM master_dashboard.contract_status cs
                    LEFT JOIN master_dashboard.projects p ON p.id = cs.project_id
                )
                SELECT
                    COALESCE(project_id::text, 'pjt:' || md5(LOWER(project_name))) AS project_id,
                    project_name,
                    stage_name,
                    COALESCE(SUM(contract_amount), 0)::numeric(14,2) AS total_amount
                FROM normalized
            """
            if project_id:
                sql = f"""
                    {normalized_budget_sql}
                    WHERE project_name IS NOT NULL
                      AND (
                        project_id::text = %s
                        OR ('pjt:' || md5(LOWER(project_name))) = %s
                      )
                    GROUP BY project_id, project_name, stage_name
                    ORDER BY stage_name
                """
                rows = fetch_all(sql, (project_id, project_id))
            else:
                sql = f"""
                    {normalized_budget_sql}
                    WHERE project_name IS NOT NULL
                    GROUP BY project_id, project_name, stage_name
                    ORDER BY project_name, stage_name
                """
                rows = fetch_all(sql, ())
            out = [
                {
                    "project_id": str(r["project_id"]),
                    "project_name": r["project_name"],
                    "stage_name": r["stage_name"],
                    "total_amount": float(r["total_amount"]) if r["total_amount"] is not None else 0,
                }
                for r in rows
            ]
            return {"rows": out, "count": len(out)}, 200

    pitchbook_upload = ns.parser()
    pitchbook_upload.add_argument(
        "file",
        location="files",
        type=FileStorage,
        required=True,
    )

    @ns.route("/pitchbook/ingest")
    class IngestPitchbook(Resource):
        @ns.expect(pitchbook_upload)
        @ns.doc(
            description="Upload a PitchBook CSV/XLSX file and ingest into dp.pitchbook_deals (deal exports) or dp.pitchbook_companies (company-profile exports)."
        )
        def post(self):
            if (auth := _require_auth()):
                return auth

            from db.pitchbook_mapping import HEADER_MAP, HEADER_MAP_COMPANY
            from display.core.db import quote_ident

            args = pitchbook_upload.parse_args()
            file = args.get("file")

            if not file:
                return {"error": "No file provided"}, 400

            filename = getattr(file, "filename", "") or ""
            if not filename.lower().endswith((".csv", ".xlsx")):
                return {"error": "File must be CSV or XLSX"}, 400

            content = file.read()

            # 1) Load into DataFrame
            try:
                if filename.lower().endswith(".csv"):
                    df = pd.read_csv(io.BytesIO(content), dtype=str)
                    df = normalize_headers(df)

                    cols_norm = {str(c).strip().lower() for c in df.columns}
                    if "deal id" in cols_norm:
                        file_format = "deal"
                    elif "company id" in cols_norm:
                        file_format = "company_profile"
                    else:
                        return {"error": "Missing required 'Company ID' or 'Deal ID' column in file."}, 400

                    current_app.logger.info(
                        "PitchBook ingest: detected format=%s (csv) cols_sample=%s",
                        file_format,
                        list(df.columns)[:12],
                    )
                else:
                    raw = pd.read_excel(
                        io.BytesIO(content),
                        sheet_name="Data",
                        header=None,
                        dtype=str,
                        engine="openpyxl",
                    )

                    deal_header_idx = find_header_idx(raw, "Deal ID")
                    company_header_idx = find_header_idx(raw, "Company ID")

                    if deal_header_idx is not None:
                        file_format = "deal"
                        header_row_index = deal_header_idx
                    elif company_header_idx is not None:
                        file_format = "company_profile"
                        header_row_index = company_header_idx
                    else:
                        current_app.logger.warning(
                            "PitchBook ingest: could not find header row with Deal ID or Company ID (xlsx). filename=%s",
                            filename,
                        )
                        return {
                            "error": "Could not locate a header row containing 'Deal ID' or 'Company ID' in the PitchBook 'Data' sheet."
                        }, 400

                    df = raw.iloc[header_row_index + 1:].copy()
                    df.columns = raw.iloc[header_row_index].astype(
                        str).str.strip()
                    df = df.dropna(how="all")
                    df = normalize_headers(df)

                    current_app.logger.info(
                        "PitchBook ingest: detected format=%s (xlsx) header_row=%s cols_sample=%s",
                        file_format,
                        header_row_index,
                        list(df.columns)[:12],
                    )
            except Exception as e:
                return {"error": f"Could not read file: {e}"}, 400

            if df.empty:
                return {"error": "File is empty"}, 400

            rows_read = len(df)

            # Select the right column map, target table, and type map for the detected format
            if file_format == "company_profile":
                col_map = HEADER_MAP_COMPANY
                target_table = "dp.pitchbook_companies"
                type_map = TYPE_MAP_PITCHBOOK_COMPANIES
                id_col = "company_id"
                name_col = "company_name"
            else:
                col_map = HEADER_MAP
                target_table = "dp.pitchbook_deals"
                type_map = TYPE_MAP_PITCHBOOK
                id_col = "deal_id"
                name_col = "startups"
            current_app.logger.info(
                "PitchBook ingest routing: format=%s target_table=%s id_col=%s name_col=%s",
                file_format,
                target_table,
                id_col,
                name_col,
            )
            incoming_cols = list(df.columns)
            kept_cols = [c for c in incoming_cols if c in col_map]
            dropped_cols = [c for c in incoming_cols if c not in col_map]
            current_app.logger.info(
                "PitchBook ingest column mapping: incoming=%s kept=%s dropped=%s dropped_sample=%s",
                len(incoming_cols),
                len(kept_cols),
                len(dropped_cols),
                dropped_cols[:10],
            )
            # 2) Keep only headers we know how to map
            df = df[[col for col in df.columns if col in col_map]]

            if df.empty:
                return {
                    "error": "No recognized PitchBook columns found in file; "
                    "check that you're using the expected export template."
                }, 400

            # 3) Rename to DB column names
            df = df.rename(columns=col_map)

            # Validate that all columns are in the known allowlist
            allowed_cols = set(col_map.values())
            unexpected = set(df.columns) - allowed_cols
            if unexpected:
                return {
                    "error": f"Unexpected columns after mapping: {sorted(unexpected)}"
                }, 400

            if id_col not in df.columns:
                return {"error": f"Internal mapping error: '{id_col}' missing after rename"}, 500

            # Normalize primary ID and company name fields
            df[id_col] = df[id_col].apply(cast_text)

            if name_col in df.columns:
                df[name_col] = df[name_col].apply(cast_text)

            # Drop footer/empty rows: no primary ID or copyright footer line
            id_filter = (
                df[id_col].notna()
                & ~df[id_col].str.startswith("© PitchBook Data", na=False)
            )
            name_filter = df[name_col].notna(
            ) if name_col in df.columns else True
            before_filter = len(df)
            df = df[id_filter & name_filter]
            after_filter = len(df)

            current_app.logger.info(
                "PitchBook ingest row filter: before=%s after=%s dropped=%s",
                before_filter,
                after_filter,
                before_filter - after_filter,
            )

            if df.empty:
                return {
                    "status": "ok",
                    "rows_read": rows_read,
                    "rows_upserted": 0,
                    "rows_skipped": rows_read,
                    "error_samples": [f"All rows were missing {id_col} or Company name; nothing ingested."],
                }, 200

            # 4) Type casting per column (booleans/ints/decimals/dates)
            for col, caster in type_map.items():
                if col in df.columns:
                    df[col] = df[col].apply(caster)

            # Default remaining columns to text
            for col in df.columns:
                if col not in type_map:
                    df[col] = df[col].apply(cast_text)

            # 5) Build UPSERT statement (all identifiers quoted for safety)
            df = df.where(pd.notna(df), None)
            cols = df.columns.tolist()
            col_names = ", ".join(quote_ident(c) for c in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            update_set = ", ".join(
                f"{quote_ident(c)} = EXCLUDED.{quote_ident(c)}"
                for c in cols if c != id_col
            )

            tgt_schema, tgt_tbl = target_table.split(".", 1)
            sql = f"""
                INSERT INTO {quote_ident(tgt_schema)}.{quote_ident(tgt_tbl)} ({col_names})
                VALUES ({placeholders})
                ON CONFLICT ({quote_ident(id_col)}) DO UPDATE SET {update_set};
            """

            records = [
                tuple(_clean_db_value(row[c]) for c in cols)
                for _, row in df.iterrows()
            ]

            rows_upserted = 0
            error_samples = []

            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for idx, record in enumerate(records):
                            try:
                                cur.execute(sql, record)
                                rows_upserted += 1
                            except Exception as e:
                                # Capture a few failing rows for debugging
                                if len(error_samples) < 5:
                                    error_samples.append(
                                        f"row {idx}: {e} | record={record}"
                                    )
                    conn.commit()
            except Exception as e:
                # This would be a connection-level error, not per-row
                error_samples.append(f"connection error: {e}")

            rows_skipped = rows_read - rows_upserted
            status = "ok" if not error_samples else "error"
            http_code = 200 if status == "ok" else 500

            current_app.logger.info(
                "PitchBook ingest done: target_table=%s rows_read=%s rows_upserted=%s rows_skipped=%s errors=%s",
                target_table,
                rows_read,
                rows_upserted,
                rows_skipped,
                len(error_samples),
            )

            if status != "error":
                def _background_embed():
                    try:
                        from commands import _run_embed
                        _run_embed()
                    except Exception as e:
                        print(f"[EMBED] Background embedding error: {e}", flush=True)
                threading.Thread(target=_background_embed, daemon=True).start()
                print("[EMBED] Background embedding thread started.", flush=True)

            return {
                "status": status,
                "rows_read": rows_read,
                "rows_upserted": rows_upserted,
                "rows_skipped": rows_skipped,
                "error_samples": error_samples[:5],
            }, http_code

    @ns.route("/pitchbook/companies")
    class ListPitchbookCompanies(Resource):
        @ns.doc(
            description=(
                "List all ingested PitchBook company profiles, joined with "
                "Monday.com GCED pipeline data (track, decision, source, scores)."
            )
        )
        def get(self):
            if (auth := _require_auth()):
                return auth
            rows = fetch_all(
                """
                -- monday_enriched: one row per GCED startup, with the website URL
                -- extracted from item_properties so we can join on it below.
                WITH monday_enriched AS (
                    SELECT
                        g.monday_item_id,
                        g.startup_name,
                        g.track,
                        g.startup_source,
                        g.team_decision,
                        LOWER(TRIM(
                            MAX(CASE
                                WHEN ip.title ILIKE '%%website%%'
                                 AND ip.value_text IS NOT NULL
                                 AND TRIM(ip.value_text) <> ''
                                THEN ip.value_text
                            END)
                        )) AS monday_website
                    FROM master_dashboard.gced_mftf25_startups g
                    LEFT JOIN monday.item_properties ip
                        ON ip.monday_item_id = g.monday_item_id
                    GROUP BY
                        g.monday_item_id,
                        g.startup_name,
                        g.track,
                        g.startup_source,
                        g.team_decision
                )
                SELECT
                    pc.*,
                    me.track,
                    me.startup_source                                        AS source,
                    me.team_decision                                         AS decision,
                    MAX(CASE
                        WHEN ip.title ILIKE '%%gced cycle%%'
                          OR ip.title ILIKE '%%cycle%%year%%'
                        THEN ip.value_text END)                             AS gced_cycle_year,
                    MAX(CASE
                        WHEN ip.title ILIKE '%%cmbu%%'
                          AND ip.title ILIKE '%%pjt%%'
                        THEN ip.value_text END)                             AS cmbu_pjt,
                    MAX(CASE
                        WHEN ip.title ILIKE '%%score 1%%'
                          OR ip.title ILIKE '%%startup strength%%'
                        THEN ip.value_text END)                             AS score_1_startup_strength,
                    MAX(CASE
                        WHEN ip.title ILIKE '%%score 2%%'
                          OR ip.title ILIKE '%%collaboration%%'
                        THEN ip.value_text END)                             AS score_2_collaboration
                FROM dp.pitchbook_companies pc
                LEFT JOIN monday_enriched me
                    ON  -- Preferred: website match (when both sides have a URL)
                        (   me.monday_website IS NOT NULL
                        AND pc.website        IS NOT NULL
                        AND me.monday_website = LOWER(TRIM(pc.website))
                        )
                        -- Fallback: company name match
                        OR  LOWER(TRIM(me.startup_name)) = LOWER(TRIM(pc.company_name))
                LEFT JOIN monday.item_properties ip
                    ON ip.monday_item_id = me.monday_item_id
                GROUP BY
                    pc.company_id,
                    me.track, me.startup_source, me.team_decision, me.monday_item_id
                ORDER BY pc.company_name
                """
            )
            return rows, 200

    # ------------------------------------------------------------------
    # File download — returns a pre-signed DO Spaces URL
    # ------------------------------------------------------------------
    @ns.route("/files/<string:file_id>")
    class FileResource(Resource):
        @ns.doc(
            description="Return a pre-signed URL for a file stored in DO Spaces. "
                        "file_id is the monday_file_id (asset_id) from monday.files.",
            params={"expires": "URL lifetime in seconds (default 3600, max 86400)."},
        )
        def get(self, file_id):
            if (auth := _require_auth_wrapped()):
                return auth

            from files.spaces import presign

            expires = min(int(request.args.get("expires", 604800)), 604800)

            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT spaces_key, file_name FROM monday.files WHERE monday_file_id = %s",
                        (file_id,),
                    )
                    row = cur.fetchone()

            if not row:
                return {"error": "File not found"}, 404

            spaces_key, file_name = row
            if not spaces_key:
                return {"error": "File has not been uploaded to storage yet"}, 404

            url = presign(spaces_key, expires_in=expires)
            return {"url": url, "file_name": file_name, "key": spaces_key}, 200

    # ------------------------------------------------------------------
    # List files for a Monday board — with optional item_id filter
    # and embedded pre-signed URLs
    # ------------------------------------------------------------------
    @ns.route("/display/monday/boards/<string:board_id>/files")
    class BoardFiles(Resource):
        @ns.doc(
            description="List all files for a Monday board stored in DO Spaces. "
                        "Optionally filter to specific items with ?item_ids=id1,id2. "
                        "Files not yet uploaded to Spaces are included with available=false.",
            params={
                "item_ids": "Comma-separated Monday item IDs to filter results (optional).",
                "expires": "Presigned URL lifetime in seconds (default 604800 / 7 days, max 604800).",
            },
        )
        def get(self, board_id):
            if (auth := _require_auth_wrapped()):
                return auth

            from files.spaces import presign

            expires = min(int(request.args.get("expires", 604800)), 604800)

            # Optional item_ids filter — comma-separated list
            raw_item_ids = request.args.get("item_ids", "").strip()
            item_ids = [i.strip() for i in raw_item_ids.split(",") if i.strip()] if raw_item_ids else []

            with get_conn() as conn:
                with conn.cursor() as cur:
                    if item_ids:
                        cur.execute(
                            """
                            SELECT monday_file_id, file_name, category, owner_name, summary,
                                   spaces_key, item_id
                            FROM monday.files
                            WHERE board_id = %s AND item_id = ANY(%s)
                            ORDER BY item_id, created_at DESC
                            """,
                            (board_id, item_ids),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT monday_file_id, file_name, category, owner_name, summary,
                                   spaces_key, item_id
                            FROM monday.files
                            WHERE board_id = %s
                            ORDER BY item_id, created_at DESC
                            """,
                            (board_id,),
                        )
                    rows = cur.fetchall()

            files = []
            for file_id, file_name, category, owner_name, summary, spaces_key, item_id in rows:
                if spaces_key:
                    try:
                        download_url = presign(spaces_key, expires_in=expires)
                        available = True
                    except Exception:
                        download_url = None
                        available = False
                else:
                    download_url = None
                    available = False

                files.append({
                    "file_id": file_id,
                    "item_id": item_id,
                    "file_name": file_name,
                    "category": category,
                    "owner_name": owner_name,
                    "summary": summary,
                    "available": available,
                    "download_url": download_url,
                    "expires_in": expires if available else None,
                })

            return {"board_id": board_id, "count": len(files), "files": files}, 200

    # ------------------------------------------------------------------
    # Incubation project partner startups — per-stage lookup
    # ------------------------------------------------------------------
    @ns.route("/display/incubation/projects/<string:monday_item_id>/partners")
    class IncubationProjectPartners(Resource):
        @ns.doc(
            description="Return partner startups for an incubation project, grouped by stage.",
            params={"monday_item_id": "Monday item ID of the incubation project."},
        )
        def get(self, monday_item_id: str):
            if (auth := _require_auth_wrapped()):
                return auth

            if not monday_item_id.isdigit():
                return {"error": {"message": "monday_item_id must be a numeric value"}}, 400

            from display.core.util import table_exists
            from display.core.db import fetch_all, fetch_one

            def _stage_sort_key(stage: str):
                text = (stage or "").strip()
                digits = "".join(ch for ch in text if ch.isdigit())
                if digits:
                    return (int(digits), text.lower())
                return (999, text.lower())

            def _build_partner_startup_stages(rows):
                by_stage = {}
                for r in rows:
                    stage = r.get("stage") or "Unknown"
                    by_stage.setdefault(stage, {"stage": stage, "startups": []})
                    by_stage[stage]["startups"].append({"startup_name": r.get("startup_name")})
                stages = list(by_stage.values())
                stages.sort(key=lambda row: _stage_sort_key(row.get("stage") or ""))
                for stage_row in stages:
                    stage_row["startups"].sort(key=lambda row: (row.get("startup_name") or "").lower())
                return stages

            if not table_exists("master_dashboard", "project_partner_startups"):
                return {"error": {"message": "Partner startups table not found"}}, 404

            project = fetch_one(
                """
                SELECT id, source_item_id
                FROM master_dashboard.projects
                WHERE source_item_id = %s
                LIMIT 1;
                """,
                (monday_item_id,),
            )
            if not project:
                return {"error": {"message": "Project not found"}}, 404

            rows = fetch_all(
                """
                SELECT stage, startup_name
                FROM master_dashboard.project_partner_startups
                WHERE project_id = %s
                ORDER BY stage, startup_name;
                """,
                (str(project["id"]),),
            )

            return {
                "monday_item_id": monday_item_id,
                "project_id": str(project["id"]),
                "partner_startup_stages": _build_partner_startup_stages(rows),
                "total_partners": len(rows),
            }, 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(
        os.getenv("PORT_API", "8080")), debug=False)
