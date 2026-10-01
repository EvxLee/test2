from flask import Blueprint, jsonify
from .queries import get_startups_for_cycle
from .classifier import classify_cycle
from .summary import generate_cycle_summary
from .cache import get_cached_summary, write_cached_summary
from .exceptions import LLMGenerationError

bp = Blueprint("cycles", __name__)


@bp.route("/cycles/<string:cycle_id>/summary", methods=["GET"])
def get_cycle_summary(cycle_id):
    # 0. Require bearer auth (same pattern used by other protected routes)
    from app import _require_auth
    if (auth := _require_auth()):
        return auth

    # 1. Fetch startups from DB
    try:
        startups = get_startups_for_cycle(cycle_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    # 2. Edge case: empty cycle
    if not startups:
        return jsonify({"error": f"No startups found for cycle '{cycle_id}'."}), 422

    # 2b. Cache hit — serve without classification or LLM
    cached = get_cached_summary(cycle_id)
    if cached is not None:
        return jsonify(cached)

    # 3. Classify and aggregate
    aggregated = classify_cycle(startups)

    # 4. Edge case: no classifiable startups
    if not aggregated:
        return jsonify({
            "error": f"No classifiable startups for cycle '{cycle_id}'. "
                     "All entries may be missing PitchBook descriptions."
        }), 422

    # 5. Generate narrative summary (graceful fallback on LLM failure)
    try:
        summary_text = generate_cycle_summary(cycle_id, aggregated)
    except LLMGenerationError:
        return jsonify({"error": "Summary generation failed, try again later"}), 503

    # 6. Build payload and cache it
    total = sum(v["total"] for v in aggregated.values())
    payload = {
        "cycle_id": cycle_id,
        "summary": summary_text,
        "verticals": aggregated,
        "total_startups": total,
    }

    try:
        write_cached_summary(cycle_id, payload)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "[WARN] failed to write cache for cycle_id=%s", cycle_id, exc_info=True
        )

    return jsonify(payload)