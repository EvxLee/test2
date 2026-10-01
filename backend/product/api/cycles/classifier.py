import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from chat.llm_client import get_llm_client
from cycles.categories import SUBCATEGORIES, KNOWN_VERTICALS

logger = logging.getLogger(__name__)


def classify_startup(description: str, vertical: str) -> str:
    subcategories = SUBCATEGORIES.get(vertical, [])
    if not subcategories:
        return "Other"

    options = "\n".join(f"- {s}" for s in subcategories)

    prompt = f"""You are classifying a startup into exactly one sub-category.

Vertical: {vertical}

Available sub-categories:
{options}

Startup description:
{description}

Reply with only the sub-category name, exactly as written above. If none fit, reply with "Other"."""

    client = get_llm_client()
    try:
        response = client.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=64,
        )
    except Exception:
        # Graceful degradation: a single LLM failure must not abort the batch.
        logger.exception(
            "classify_startup LLM invocation failed for vertical=%s; defaulting to 'Other'",
            vertical,
        )
        return "Other"

    result = (response.get("content", "") or "").strip()

    # Validate the result is one of the known sub-categories
    if result in subcategories:
        return result
    return "Other"


def aggregate_results(classified_startups: list[dict]) -> dict:
    result: dict = {}

    for startup in classified_startups:
        vertical = startup.get("vertical") or "Unknown"
        sub_category = startup.get("sub_category") or "Other"

        if vertical not in result:
            result[vertical] = {"total": 0, "sub_categories": {}}

        result[vertical]["total"] += 1
        sub_cats = result[vertical]["sub_categories"]
        sub_cats[sub_category] = sub_cats.get(sub_category, 0) + 1

    return result


def classify_cycle(startups: list[dict]) -> dict:
    eligible = [
        s for s in startups
        if s.get("vertical") in KNOWN_VERTICALS and s.get("description")
    ]

    if not eligible:
        return aggregate_results([])

    max_workers = int(os.getenv("CYCLE_CLASSIFIER_MAX_WORKERS", min(16, len(eligible))))

    classified = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            (
                s.get("company_name"),
                s["vertical"],
                executor.submit(classify_startup, s["description"], s["vertical"]),
            )
            for s in eligible
        ]

        for company_name, vertical, future in futures:
            try:
                sub_category = future.result(timeout=60)
            except FuturesTimeoutError:
                logger.warning(
                    "classify_startup timed out for company=%s; skipping", company_name
                )
                continue
            except Exception:
                logger.exception(
                    "classify_startup failed for company=%s; skipping", company_name
                )
                continue

            classified.append({
                "company_name": company_name,
                "vertical": vertical,
                "sub_category": sub_category,
            })

    return aggregate_results(classified)
