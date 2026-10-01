"""
Tests for:
- GET /cycles/<cycle_id>/summary endpoint
- classify_cycle() aggregation logic
- generate_cycle_summary() prompt output
- LLM error handling (LLMGenerationError)
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from cycles.classifier import classify_cycle, aggregate_results
from cycles.summary import generate_cycle_summary
from cycles.exceptions import LLMGenerationError

# Fixtures

AUTH_HEADER = {"Authorization": "Bearer test-token"}

MOCK_STARTUPS_AI = [
    {"company_name": "AlphaBot", "description": "An agentic AI platform for enterprise automation.", "vertical": "AI"},
    {"company_name": "DataVault", "description": "ML data pipeline and curation tooling for LLM training.", "vertical": "AI"},
    {"company_name": "NoDesc Corp", "description": None, "vertical": "AI"},
    {"company_name": "UnknownCo", "description": "Some product.", "vertical": "Other"},
]

MOCK_AGGREGATED = {
    "AI": {
        "total": 2,
        "sub_categories": {
            "Agentic AI & Automation": 1,
            "Data Infrastructure & Curation": 1,
        },
    }
}


# aggregate_results tests

class TestAggregateResults:
    def test_basic_aggregation(self):
        classified = [
            {"company_name": "A", "vertical": "AI", "sub_category": "Agentic AI & Automation"},
            {"company_name": "B", "vertical": "AI", "sub_category": "Agentic AI & Automation"},
            {"company_name": "C", "vertical": "HealthTech", "sub_category": "Clinical Decision Support & Diagnostics"},
        ]
        result = aggregate_results(classified)
        assert result["AI"]["total"] == 2
        assert result["AI"]["sub_categories"]["Agentic AI & Automation"] == 2
        assert result["HealthTech"]["total"] == 1

    def test_empty_input(self):
        assert aggregate_results([]) == {}

    def test_missing_vertical_defaults_to_unknown(self):
        classified = [{"company_name": "X", "vertical": None, "sub_category": "Other"}]
        result = aggregate_results(classified)
        assert "Unknown" in result

    def test_missing_sub_category_defaults_to_other(self):
        classified = [{"company_name": "X", "vertical": "AI", "sub_category": None}]
        result = aggregate_results(classified)
        assert result["AI"]["sub_categories"]["Other"] == 1


# classify_cycle tests

class TestClassifyCycle:
    @patch("cycles.classifier.classify_startup", return_value="Agentic AI & Automation")
    def test_skips_missing_description(self, mock_classify):
        startups = [
            {"company_name": "A", "description": "An AI agent.", "vertical": "AI"},
            {"company_name": "B", "description": None, "vertical": "AI"},
        ]
        result = classify_cycle(startups)
        assert mock_classify.call_count == 1
        assert result["AI"]["total"] == 1

    @patch("cycles.classifier.classify_startup", return_value="Other")
    def test_skips_unknown_vertical(self, mock_classify):
        startups = [
            {"company_name": "A", "description": "Some product.", "vertical": "Unknown"},
        ]
        result = classify_cycle(startups)
        mock_classify.assert_not_called()
        assert result == {}

    @patch("cycles.classifier.classify_startup", return_value="Agentic AI & Automation")
    def test_full_cycle(self, mock_classify):
        result = classify_cycle(MOCK_STARTUPS_AI)
        assert result["AI"]["total"] == 2


# generate_cycle_summary tests

class TestGenerateCycleSummary:
    @patch("cycles.summary.get_llm_client")
    def test_returns_string(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.invoke.return_value = {"content": "This is the summary."}
        mock_get_client.return_value = mock_client

        result = generate_cycle_summary("gced_cycle4", MOCK_AGGREGATED)
        assert isinstance(result, str)
        assert result == "This is the summary."

    @patch("cycles.summary.get_llm_client")
    def test_prompt_contains_cycle_id(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.invoke.return_value = {"content": "Summary text."}
        mock_get_client.return_value = mock_client

        generate_cycle_summary("gced_cycle5", MOCK_AGGREGATED)
        call_args = mock_client.invoke.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "gced_cycle5" in prompt

    @patch("cycles.summary.get_llm_client")
    def test_empty_response_raises_llm_error(self, mock_get_client):
        """Empty LLM response should raise LLMGenerationError instead of silently returning ''."""
        mock_client = MagicMock()
        mock_client.invoke.return_value = {"content": ""}
        mock_get_client.return_value = mock_client

        with pytest.raises(LLMGenerationError):
            generate_cycle_summary("gced_cycle4", MOCK_AGGREGATED)

    @patch("cycles.summary.get_llm_client")
    def test_llm_exception_raises_llm_error(self, mock_get_client):
        """LLM client exception should be wrapped in LLMGenerationError."""
        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("Bedrock unavailable")
        mock_get_client.return_value = mock_client

        with pytest.raises(LLMGenerationError):
            generate_cycle_summary("gced_cycle4", MOCK_AGGREGATED)

    @patch("cycles.summary.get_llm_client")
    def test_whitespace_only_response_raises_llm_error(self, mock_get_client):
        """Whitespace-only content should be treated as empty and raise."""
        mock_client = MagicMock()
        mock_client.invoke.return_value = {"content": "   \n  "}
        mock_get_client.return_value = mock_client

        with pytest.raises(LLMGenerationError):
            generate_cycle_summary("gced_cycle4", MOCK_AGGREGATED)


# API endpoint tests

class TestCycleSummaryEndpoint:
    @pytest.fixture
    def flask_client(self):
        with patch.dict(os.environ, {"INGEST_API_TOKEN": "test-token"}, clear=False):
            from app import create_app
            app = create_app()
            app.config["TESTING"] = True
            with app.test_client() as client:
                yield client

    @patch("cycles.routes.get_cached_summary", return_value=None)
    @patch("cycles.routes.write_cached_summary")
    @patch("cycles.routes.get_startups_for_cycle")
    @patch("cycles.routes.classify_cycle", return_value=MOCK_AGGREGATED)
    @patch("cycles.routes.generate_cycle_summary", return_value="Strong AI cohort this cycle.")
    def test_success(self, mock_summary, mock_classify, mock_get_startups, mock_write, mock_cache, flask_client):
        mock_get_startups.return_value = MOCK_STARTUPS_AI
        response = flask_client.get("/cycles/gced_cycle4/summary", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.get_json()
        assert data["cycle_id"] == "gced_cycle4"
        assert data["summary"] == "Strong AI cohort this cycle."
        assert "AI" in data["verticals"]
        assert data["total_startups"] == 2

    @patch("cycles.routes.get_startups_for_cycle", side_effect=ValueError("Invalid cycle_id"))
    def test_invalid_cycle_id_returns_404(self, mock_get_startups, flask_client):
        response = flask_client.get("/cycles/bad_cycle/summary", headers=AUTH_HEADER)
        assert response.status_code == 404
        assert "Invalid cycle_id" in response.get_json()["error"]

    @patch("cycles.routes.get_startups_for_cycle", return_value=[])
    def test_empty_cycle_returns_422(self, mock_get_startups, flask_client):
        response = flask_client.get("/cycles/gced_cycle4/summary", headers=AUTH_HEADER)
        assert response.status_code == 422
        assert "No startups found" in response.get_json()["error"]

    @patch("cycles.routes.get_cached_summary", return_value=None)
    @patch("cycles.routes.get_startups_for_cycle", return_value=MOCK_STARTUPS_AI)
    @patch("cycles.routes.classify_cycle", return_value={})
    def test_no_classifiable_startups_returns_422(self, mock_classify, mock_get_startups, mock_cache, flask_client):
        response = flask_client.get("/cycles/gced_cycle4/summary", headers=AUTH_HEADER)
        assert response.status_code == 422
        assert "No classifiable startups" in response.get_json()["error"]

    def test_missing_auth_returns_401(self, flask_client):
        """Request without Authorization header must return 401."""
        response = flask_client.get("/cycles/gced_cycle4/summary")
        assert response.status_code == 401

    def test_invalid_auth_returns_401(self, flask_client):
        """Request with wrong bearer token must return 401."""
        response = flask_client.get(
            "/cycles/gced_cycle4/summary",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    @patch("cycles.routes.get_cached_summary", return_value=None)
    @patch("cycles.routes.get_startups_for_cycle", return_value=MOCK_STARTUPS_AI)
    @patch("cycles.routes.classify_cycle", return_value=MOCK_AGGREGATED)
    @patch(
        "cycles.routes.generate_cycle_summary",
        side_effect=LLMGenerationError("Bedrock failure"),
    )
    def test_llm_failure_returns_503(
        self, mock_summary, mock_classify, mock_get_startups, mock_cache, flask_client
    ):
        """When generate_cycle_summary raises LLMGenerationError, endpoint returns 503."""
        response = flask_client.get("/cycles/gced_cycle4/summary", headers=AUTH_HEADER)
        assert response.status_code == 503
        data = response.get_json()
        assert data["error"] == "Summary generation failed, try again later"

    @patch("cycles.routes.get_cached_summary")
    @patch("cycles.routes.get_startups_for_cycle", return_value=MOCK_STARTUPS_AI)
    @patch("cycles.routes.classify_cycle", return_value=MOCK_AGGREGATED)
    @patch("cycles.routes.generate_cycle_summary", return_value="AI cohort summary.")
    @patch("cycles.routes.write_cached_summary")
    def test_cache_miss_calls_llm_and_writes_cache(
        self, mock_write, mock_summary, mock_classify, mock_get_startups, mock_get_cache, flask_client
    ):
        """On cache miss, the endpoint runs classification and writes to cache."""
        mock_get_cache.return_value = None

        response = flask_client.get("/cycles/gced_cycle4/summary", headers=AUTH_HEADER)

        assert response.status_code == 200
        mock_summary.assert_called_once()
        mock_write.assert_called_once()

    @patch("cycles.routes.get_startups_for_cycle", return_value=MOCK_STARTUPS_AI)
    @patch("cycles.routes.get_cached_summary")
    def test_cache_hit_skips_llm(self, mock_get_cache, mock_get_startups, flask_client):
        """On cache hit, the endpoint returns cached data without calling classify or LLM."""
        cached_payload = {
            "cycle_id": "gced_cycle4",
            "summary": "Cached summary.",
            "verticals": MOCK_AGGREGATED,
            "total_startups": 2,
        }
        mock_get_cache.return_value = cached_payload

        with patch("cycles.routes.classify_cycle") as mock_classify:
            with patch("cycles.routes.generate_cycle_summary") as mock_summary:
                response = flask_client.get("/cycles/gced_cycle4/summary", headers=AUTH_HEADER)

        assert response.status_code == 200
        assert response.get_json()["summary"] == "Cached summary."
        mock_classify.assert_not_called()
        mock_summary.assert_not_called()
