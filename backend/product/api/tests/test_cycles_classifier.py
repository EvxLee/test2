import pytest
from unittest.mock import patch, MagicMock

from cycles.classifier import classify_startup, aggregate_results, classify_cycle


@patch("cycles.classifier.get_llm_client")
def test_classify_startup_returns_valid_subcategory(mock_get_client):
    """Returns a valid sub-category when Bedrock responds correctly."""
    mock_client = MagicMock()
    mock_client.invoke.return_value = {"content": "Agentic AI & Automation"}
    mock_get_client.return_value = mock_client

    result = classify_startup("We build autonomous AI agents.", "AI")

    assert result == "Agentic AI & Automation"


@patch("cycles.classifier.get_llm_client")
def test_classify_startup_falls_back_to_other(mock_get_client):
    """Returns 'Other' when Bedrock returns an unrecognized category."""
    mock_client = MagicMock()
    mock_client.invoke.return_value = {"content": "Something Unrecognized"}
    mock_get_client.return_value = mock_client

    result = classify_startup("Some description.", "AI")

    assert result == "Other"


def test_classify_startup_unknown_vertical():
    """Returns 'Other' immediately for an unknown vertical without calling Bedrock."""
    result = classify_startup("Some description.", "UnknownVertical")

    assert result == "Other"


def test_aggregate_results_basic():
    """Counts startups correctly by vertical and sub-category."""
    classified = [
        {"company_name": "A", "vertical": "AI", "sub_category": "Agentic AI & Automation"},
        {"company_name": "B", "vertical": "AI", "sub_category": "Agentic AI & Automation"},
        {"company_name": "C", "vertical": "AI", "sub_category": "Data Infrastructure & Curation"},
        {"company_name": "D", "vertical": "HealthTech", "sub_category": "Mental & Behavioral Health"},
    ]

    result = aggregate_results(classified)

    assert result["AI"]["total"] == 3
    assert result["AI"]["sub_categories"]["Agentic AI & Automation"] == 2
    assert result["AI"]["sub_categories"]["Data Infrastructure & Curation"] == 1
    assert result["HealthTech"]["total"] == 1
    assert result["HealthTech"]["sub_categories"]["Mental & Behavioral Health"] == 1


def test_aggregate_results_empty():
    """Returns empty dict for empty input."""
    assert aggregate_results([]) == {}


@patch("cycles.classifier.classify_startup")
def test_classify_cycle_skips_missing_description(mock_classify):
    """Startups with no description are skipped."""
    startups = [
        {"company_name": "No Desc", "description": None, "vertical": "AI"},
        {"company_name": "Has Desc", "description": "We do AI things.", "vertical": "AI"},
    ]
    mock_classify.return_value = "Agentic AI & Automation"

    result = classify_cycle(startups)

    # Only one startup was classified
    mock_classify.assert_called_once()
    assert result["AI"]["total"] == 1


@patch("cycles.classifier.classify_startup")
def test_classify_cycle_skips_unknown_vertical(mock_classify):
    """Startups with an unknown vertical are skipped."""
    startups = [
        {"company_name": "Weird Co", "description": "Some desc.", "vertical": "Biotech"},
    ]

    result = classify_cycle(startups)

    mock_classify.assert_not_called()
    assert result == {}


@patch("cycles.classifier.get_llm_client")
def test_classify_startup_returns_other_on_llm_exception(mock_get_client):
    """When LLM client raises, classify_startup returns 'Other' (graceful degradation)."""
    mock_client = MagicMock()
    mock_client.invoke.side_effect = RuntimeError("Bedrock unavailable")
    mock_get_client.return_value = mock_client

    result = classify_startup("We build autonomous AI agents.", "AI")

    assert result == "Other"


@patch("cycles.classifier.get_llm_client")
def test_classify_cycle_continues_on_single_llm_failure(mock_get_client):
    """A single LLM failure must not abort the whole batch."""
    from cycles.classifier import classify_cycle as _classify_cycle

    mock_client = MagicMock()
    # First call raises, second call succeeds
    mock_client.invoke.side_effect = [
        RuntimeError("transient failure"),
        {"content": "Agentic AI & Automation"},
    ]
    mock_get_client.return_value = mock_client

    startups = [
        {"company_name": "A", "description": "Some AI thing.", "vertical": "AI"},
        {"company_name": "B", "description": "Another AI thing.", "vertical": "AI"},
    ]

    result = _classify_cycle(startups)

    # Both startups should be classified (first as 'Other' fallback, second as real sub-cat)
    assert result["AI"]["total"] == 2
    assert result["AI"]["sub_categories"].get("Other") == 1
    assert result["AI"]["sub_categories"].get("Agentic AI & Automation") == 1


@patch("cycles.classifier.get_llm_client")
def test_classify_cycle_runs_in_parallel(mock_get_client):
    """classify_cycle completes N calls faster than sequential N * delay would take."""
    import time

    SLEEP_SECS = 0.08
    N = 6

    mock_client = MagicMock()

    def slow_invoke(**kwargs):
        time.sleep(SLEEP_SECS)
        return {"content": "Agentic AI & Automation"}

    mock_client.invoke.side_effect = slow_invoke
    mock_get_client.return_value = mock_client

    startups = [
        {"company_name": f"Co {i}", "description": f"AI company {i}", "vertical": "AI"}
        for i in range(N)
    ]

    start = time.time()
    result = classify_cycle(startups)
    elapsed = time.time() - start

    assert elapsed < N * SLEEP_SECS / 2, f"Expected parallel execution but took {elapsed:.2f}s"
    assert result["AI"]["total"] == N


@patch("cycles.classifier.get_llm_client")
def test_classify_cycle_parallel_result_matches_sequential(mock_get_client):
    """Parallel classify_cycle produces the same aggregation as the sequential version."""
    mock_client = MagicMock()
    mock_client.invoke.return_value = {"content": "Agentic AI & Automation"}
    mock_get_client.return_value = mock_client

    startups = [
        {"company_name": f"Co {i}", "description": f"AI startup {i}", "vertical": "AI"}
        for i in range(4)
    ]

    result = classify_cycle(startups)

    assert result["AI"]["total"] == 4
    assert result["AI"]["sub_categories"]["Agentic AI & Automation"] == 4
