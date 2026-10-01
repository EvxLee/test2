"""
Narrative summary generation for a classified cycle.
Takes aggregated vertical/sub-category counts and produces a human-readable
summary using the LLM client already used by classifier.py.
"""

import logging

from chat.llm_client import get_llm_client
from .exceptions import LLMGenerationError

logger = logging.getLogger(__name__)


def _build_prompt(cycle_id: str, aggregated: dict) -> str:
    """
    Build the prompt for the LLM to generate a cycle narrative summary.
    """
    # Format aggregated data into readable lines
    vertical_lines = []
    for vertical, data in aggregated.items():
        total = data["total"]
        sub_cats = data["sub_categories"]
        sub_cat_lines = "\n".join(
            f"    - {sub}: {count} startup{'s' if count != 1 else ''}"
            for sub, count in sorted(sub_cats.items(), key=lambda x: -x[1])
        )
        vertical_lines.append(
            f"  {vertical} ({total} startups total):\n{sub_cat_lines}"
        )

    vertical_block = "\n".join(vertical_lines)

    return f"""You are writing a quarterly report summary for the startup sourcing program.

Below is the aggregated startup data for {cycle_id}, broken down by vertical and sub-category.

{vertical_block}

Write a concise, professional 3-5 sentence narrative summary suitable for an executive report. 
Cover:
- The overall size of the cohort and which verticals are represented
- The dominant sub-categories and what they signal about market trends
- Any notable patterns or concentrations worth highlighting

Do not use bullet points. Write in flowing prose."""


def generate_cycle_summary(cycle_id: str, aggregated: dict) -> str:
    """
    Generate a narrative text summary for the cycle using the LLM.

    Args:
        cycle_id: e.g. "gced_cycle4"
        aggregated: Output of classify_cycle() —
                    {vertical: {"total": int, "sub_categories": {str: int}}}

    Returns:
        A narrative string summarizing the cycle.
    """
    prompt = _build_prompt(cycle_id, aggregated)

    client = get_llm_client()
    try:
        response = client.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )
    except Exception as exc:
        logger.exception("LLM invocation failed for cycle %s", cycle_id)
        raise LLMGenerationError(
            f"LLM invocation failed for cycle '{cycle_id}': {exc}"
        ) from exc

    content = (response.get("content", "") or "").strip()
    if not content:
        logger.error(
            "LLM returned empty content for cycle %s", cycle_id
        )
        raise LLMGenerationError(
            f"LLM returned empty content for cycle '{cycle_id}'"
        )

    return content