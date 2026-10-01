import csv, io, json
from flask import request, Response, redirect
from flask_restx import Resource, fields
from . import ns
try:
    from product.api.auth import _require_auth as require_auth
except Exception:
    def require_auth():
        return None  # no-op fallback

from .core.db import fetch_all, fetch_one, quote_ident
from .core.cursor import encode_cursor, decode_cursor
from .core.filtering import build_search_clause, build_filters, build_sort
from .core.redact import sanitize_row
from .core.attachments import get_attachments, get_links
from .core.util import (
    table_exists, default_safe_columns, pick_searchable_columns,
    ensure_sort_keys, project_column_sql
)

def parse_list(name: str):
    v = request.args.get(name)
    if not v:
        return []
    return [t.strip() for t in v.split(",") if t.strip()]

def bool_onoff(name: str, default_on=True) -> bool:
    v = (request.args.get(name) or "").lower()
    if v == "on": return True
    if v == "off": return False
    return default_on

def parse_repeatable(name: str):
    return request.args.getlist(name)

def next_cursor_from_rows(rows, sort_keys):
    if not rows:
        return None
    last = rows[-1]
    keyvals = [last.get(col) for (col, _) in sort_keys]
    return encode_cursor({"last_key": keyvals})

def build_where(schema, table, q, filters, searchable_cols, allowed_cols):
    clauses, params = [], []
    sq, sp = build_search_clause(q, searchable_cols)
    if sq:
        clauses.append(sq); params += sp
    fq, fp = build_filters(filters, allowed_cols)
    if fq:
        clauses.append(fq); params += fp
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
    where_sql = ("WHERE " + cursor_clause) if not where_sql else (where_sql + " AND " + cursor_clause)

    cursor_params = []
    for i in range(len(sort_pairs)):
        # add equality values for prefix, then ith comparator value
        cursor_params += last_key[:i] + [last_key[i]]
    return where_sql, params + cursor_params

def build_order_by(sort_pairs):
    return "ORDER BY " + ", ".join(f"{quote_ident(c)} {d}" for c, d in sort_pairs)

def expand_includes(schema, table, rows, includes, redact_on, safe_cols_set):
    if not rows:
        return rows
    want_att = "attachments" in includes
    want_links = "links" in includes
    if not want_att and not want_links:
        return rows
    out = []
    for r in rows:
        rr = dict(r)  # copy
        rid = str(rr.get("id") or rr.get("uuid") or rr.get("pk") or rr.get("gid") or "")
        if want_att:
            rr["_attachments"] = get_attachments(schema, table, rid)
        if want_links:
            # normalize to {rel, href, label}
            rr["_links"] = [{"rel": x["rel"], "href": x["href"], "label": x["label"]} for x in get_links(schema, table, rid)]
        out.append(rr)
    # sanitize (again) in case nested text exists in columns we keep
    return [sanitize_row(r, redact_on, safe_cols_set | {"_attachments","_links"}) for r in out]

def _stage_sort_key(stage: str) -> tuple[int, str]:
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
        by_stage[stage]["startups"].append({
            "startup_name": r.get("startup_name"),
        })

    stages = list(by_stage.values())
    stages.sort(key=lambda row: _stage_sort_key(row.get("stage") or ""))
    for stage_row in stages:
        stage_row["startups"].sort(key=lambda row: (row.get("startup_name") or "").lower())
    return stages

def _fetch_project_partner_startups_by_project_id(project_id: str):
    if not table_exists("master_dashboard", "project_partner_startups"):
        return []
    return fetch_all(
        """
        SELECT stage, startup_name
        FROM master_dashboard.project_partner_startups
        WHERE project_id = %s
        ORDER BY stage, startup_name;
        """,
        (project_id,),
    )

def _fetch_project_partner_startups_by_monday_item_id(monday_item_id: str):
    if not table_exists("master_dashboard", "project_partner_startups"):
        return None, []

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
        return None, []
    return project, _fetch_project_partner_startups_by_project_id(str(project["id"]))

@ns.route("/data/<string:schema>/<string:table>")
class ListRecords(Resource):
    def get(self, schema: str, table: str):
        if (auth := require_auth()): return auth

        if not table_exists(schema, table):
            return {"error": {"message": f"{schema}.{table} not found"}}, 404

        # columns projection
        req_cols = parse_list("columns")
        safe_cols = default_safe_columns(schema, table)
        if req_cols:
            # Only allow requesting a subset of safe columns
            safe_cols = [c for c in req_cols if c in set(default_safe_columns(schema, table))]

        allowed_cols = default_safe_columns(schema, table)
        searchable_cols = pick_searchable_columns(schema, table)
        include = set(parse_list("include"))
        redact_on = bool_onoff("redact", default_on=True)
        q = request.args.get("q") or ""
        filters = parse_repeatable("filter")
        sort_pairs = ensure_sort_keys(schema, table, build_sort(request.args.get("sort") or "", allowed_cols))
        limit = min(int(request.args.get("limit") or 50), 500)
        cursor = request.args.get("cursor")

        select_cols_sql = project_column_sql(schema, table, safe_cols)
        from_sql = f'FROM {quote_ident(schema)}.{quote_ident(table)}'
        where_sql, params = build_where(schema, table, q, filters, searchable_cols, allowed_cols)
        where_sql, params = apply_cursor(sort_pairs, cursor, where_sql, params)
        order_sql = build_order_by(sort_pairs)
        sql = f"SELECT {select_cols_sql} {from_sql} {where_sql} {order_sql} LIMIT %s"
        rows = fetch_all(sql, tuple(params + [limit]))

        # sanitize
        sset = set(safe_cols)
        rows = [sanitize_row(r, redact_on, sset) for r in rows]
        # includes
        rows = expand_includes(schema, table, rows, include, redact_on, sset)

        # CSV export?
        fmt = (request.args.get("format") or "json").lower()
        next_cur = next_cursor_from_rows(rows, sort_pairs)
        meta = {
            "schema": schema, "table": table,
            "columns": safe_cols,
            "count": len(rows),
            "next_cursor": next_cur
        }

        if fmt == "csv":
            # stream as CSV
            def gen():
                buf = io.StringIO()
                w = csv.DictWriter(buf, fieldnames=safe_cols, extrasaction="ignore")
                w.writeheader()
                yield buf.getvalue(); buf.seek(0); buf.truncate(0)
                for r in rows:
                    w.writerow({k: r.get(k) for k in safe_cols})
                    yield buf.getvalue(); buf.seek(0); buf.truncate(0)
            headers = {
                "X-Next-Cursor": next_cur or "",
                "Content-Disposition": f'attachment; filename="{schema}_{table}.csv"'
            }
            return Response(gen(), mimetype="text/csv", headers=headers)

        return {
            **meta,
            "rows": rows
        }, 200

@ns.route("/data/<string:schema>/<string:table>/<string:rid>")
class GetRecord(Resource):
    def get(self, schema: str, table: str, rid: str):
        if (auth := require_auth()): return auth
        if not table_exists(schema, table):
            return {"error": {"message": f"{schema}.{table} not found"}}, 404

        include = set(parse_list("include"))
        redact_on = bool_onoff("redact", default_on=True)
        safe_cols = default_safe_columns(schema, table)
        # id column guess (prefer 'id', else first column)
        cols = safe_cols or [c for c,_ in []]
        idcol = "id" if "id" in cols else cols[0]
        sql = f"""
          SELECT {project_column_sql(schema, table, safe_cols)}
          FROM {quote_ident(schema)}.{quote_ident(table)}
          WHERE {quote_ident(idcol)}=%s
          LIMIT 1
        """
        row = fetch_one(sql, (rid,))
        if not row:
            return {"error": {"message": f"{schema}.{table} id={rid} not found"}}, 404

        sset = set(safe_cols)
        row = sanitize_row(row, redact_on, sset)
        if "attachments" in include or "links" in include:
            row = expand_includes(schema, table, [row], include, redact_on, sset)[0]
        if schema == "master_dashboard" and table == "projects":
            partner_rows = _fetch_project_partner_startups_by_project_id(rid)
            row["partner_startup_stages"] = _build_partner_startup_stages(partner_rows)
            row["total_partners"] = len(partner_rows)
        return row, 200

@ns.route("/map/<string:schema>/<string:table>")
class MapFeed(Resource):
    def get(self, schema: str, table: str):
        if (auth := require_auth()): return auth
        if not table_exists(schema, table):
            return {"error": {"message": f"{schema}.{table} not found"}}, 404

        geom_col = request.args.get("geom") or "geom"
        properties = parse_list("properties")
        redact_on = bool_onoff("redact", default_on=True)
        filters = parse_repeatable("filter")
        q = request.args.get("q") or ""
        limit = min(int(request.args.get("limit") or 200), 1000)
        cursor = request.args.get("cursor")
        allowed_cols = default_safe_columns(schema, table)
        searchable_cols = pick_searchable_columns(schema, table)
        sort_pairs = ensure_sort_keys(schema, table, build_sort(request.args.get("sort") or "", allowed_cols))

        cols_types = dict(default_safe_columns(schema, table) and fetch_all("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
        """, (schema, table)))
        cols = {c for c,_ in fetch_all("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
        """, (schema, table))}

        has_geom = geom_col in cols
        has_latlng = ("lat" in cols) and ("lng" in cols)

        if not (has_geom or has_latlng):
            return {"type":"FeatureCollection","features":[],"next_cursor":None}, 200

        select_props = [c for c in properties if c in allowed_cols][:30]
        prop_sql = ", ".join(quote_ident(c) for c in select_props) if select_props else ""
        prop_list = select_props

        where_sql, params = build_where(schema, table, q, filters, searchable_cols, allowed_cols)

        # bbox
        bbox = request.args.get("bbox")
        if bbox:
            try:
                minLon, minLat, maxLon, maxLat = [float(x) for x in bbox.split(",")]
                if has_geom:
                    # PostGIS required
                    where_sql = (where_sql + " AND " if where_sql else "WHERE ") + \
                        f"ST_Intersects({quote_ident(geom_col)}, ST_MakeEnvelope(%s,%s,%s,%s, 4326))"
                    params += [minLon, minLat, maxLon, maxLat]
                elif has_latlng:
                    where_sql = (where_sql + " AND " if where_sql else "WHERE ") + \
                        "(%s <= lng AND lng <= %s AND %s <= lat AND lat <= %s)"
                    params += [minLon, maxLon, minLat, maxLat]
            except Exception:
                pass

        where_sql, params = apply_cursor(sort_pairs, cursor, where_sql, params)
        order_sql = build_order_by(sort_pairs)

        # Build SELECT
        if has_geom:
            geom_sel = f"ST_AsGeoJSON({quote_ident(geom_col)}) AS gj"
        else:
            geom_sel = "to_jsonb(json_build_object('type','Point','coordinates', ARRAY[lng,lat]))::text AS gj"

        cols_sql = ", ".join(filter(None, [geom_sel] + [quote_ident(c) for c in prop_list] + ["id"]))
        sql = f"""
            SELECT {cols_sql}
            FROM {quote_ident(schema)}.{quote_ident(table)}
            {where_sql} {order_sql}
            LIMIT %s
        """
        rows = fetch_all(sql, tuple(params + [limit]))

        features = []
        for r in rows:
            props = {k: r[k] for k in prop_list if k in r}
            props = {k: (props[k] if not isinstance(props[k], str) or not redact_on else props[k]) for k in props}  # basic
            props = sanitize_row(props, redact_on, set(prop_list))
            gid = f"{table}:{r.get('id')}" if r.get("id") is not None else None
            features.append({
                "type": "Feature",
                "id": gid,
                "geometry": json.loads(r["gj"]) if isinstance(r["gj"], str) else r["gj"],
                "properties": props
            })

        return {"type": "FeatureCollection", "features": features, "next_cursor": next_cursor_from_rows(rows, sort_pairs)}, 200


@ns.route("/data/<string:schema>/<string:table>/<string:rid>/attachments")
class RowAttachments(Resource):
    def get(self, schema: str, table: str, rid: str):
        if (auth := require_auth()): return auth
        return get_attachments(schema, table, rid), 200

@ns.route("/data/<string:schema>/<string:table>/<string:rid>/links")
class RowLinks(Resource):
    def get(self, schema: str, table: str, rid: str):
        if (auth := require_auth()): return auth
        return get_links(schema, table, rid), 200

@ns.route("/incubation/projects/<string:monday_item_id>/partners")
class IncubationProjectPartners(Resource):
    def get(self, monday_item_id: str):
        if (auth := require_auth()): return auth

        if not monday_item_id.isdigit():
            return {"error": {"message": "monday_item_id must be a numeric value"}}, 400

        if not table_exists("master_dashboard", "project_partner_startups"):
            return {"error": {"message": "Partner startups table not found"}}, 404

        project, rows = _fetch_project_partner_startups_by_monday_item_id(monday_item_id)

        return {
            "monday_item_id": monday_item_id,
            "project_id": str(project["id"]) if project else None,
            "partner_startup_stages": _build_partner_startup_stages(rows),
            "total_partners": len(rows),
        }, 200


@ns.route("/attachments/<int:att_id>/redirect")
class AttachmentRedirect(Resource):
    def get(self, att_id: int):
        """Return a redirect to a fresh file URL.

        For Monday file attachments the stored URL is a pre-signed S3 URL
        that expires after 1 hour.  When asset_id is present we fetch a
        fresh URL from the Monday API before redirecting.
        """
        if (auth := require_auth()): return auth
        row = fetch_one(
            "SELECT id, asset_id, url, source "
            "FROM master_dashboard.core_attachments WHERE id = %s",
            (att_id,),
        )
        if not row:
            return {"error": "attachment not found"}, 404

        url = row["url"]
        if row.get("asset_id") and row.get("source") == "monday":
            try:
                from monday_pull.core.assets import fetch_assets
                assets = fetch_assets([str(row["asset_id"])])
                asset = assets.get(str(row["asset_id"]))
                if asset:
                    fresh = asset.get("public_url") or asset.get("url")
                    if fresh:
                        url = fresh
            except Exception:
                pass  # fall back to cached URL

        return redirect(url, code=302)


@ns.route("/_health")
class DisplayHealth:
    def get(self):
        return {"ok": True}, 200
