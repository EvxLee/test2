import pytest
from unittest.mock import MagicMock, patch

from app import create_app
from chat.tools import ToolResult


# ---------------------------------------------------------------------------
# Sample artifacts returned by semantic_search
# ---------------------------------------------------------------------------

SAMPLE_ARTIFACTS = [
    {
        "id": "chunk-1",
        "document_id": "doc-1",
        "source_type": "project",
        "source_id": "proj-1",
        "chunk_text": "Atlas is an AI-powered platform.",
        "page_number": 1,
        "section_title": "Overview",
        "metadata": {},
        "similarity": 0.92,
    },
    {
        "id": "chunk-2",
        "document_id": "doc-2",
        "source_type": "file",
        "source_id": "file-1",
        "chunk_text": "Machine learning capabilities.",
        "page_number": 3,
        "section_title": "Technical Details",
        "metadata": {},
        "similarity": 0.85,
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_cache():
    import cache as cache_module
    cache_module._cache_instance = None
    yield
    cache_module._cache_instance = None


@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True, "RATELIMIT_ENABLED": False})
    return app


@pytest.fixture
def client(app):
    with patch("app._require_auth", return_value=None):
        with app.test_client() as c:
            yield c


def _mock_rag(artifacts=None):
    mock = MagicMock()
    result = ToolResult(
        content="formatted text",
        artifacts=artifacts if artifacts is not None else SAMPLE_ARTIFACTS,
    )
    mock.semantic_search.return_value = result
    mock.hybrid_document_search.return_value = result
    mock.retrieve_context.return_value = result
    return mock


def _set_rag(mock_services, rag):
    mock_services.return_value.get_rag_tools.return_value = rag


def _set_llm(mock_services, content="Formatted Atlas answer. [1]"):
    llm = MagicMock()
    llm.invoke.return_value = {"content": content}
    mock_services.return_value.get_llm_client.return_value = llm
    return llm


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_missing_query_returns_400(client):
    response = client.post(
        "/atlas/document-search",
        json={},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_empty_query_returns_400(client):
    response = client.post(
        "/atlas/document-search",
        json={"query": "   "},
        content_type="application/json",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Successful search
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_returns_results_on_valid_query(mock_services, client):
    _set_rag(mock_services, _mock_rag())

    response = client.post(
        "/atlas/document-search",
        json={"query": "AI platform"},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["query"] == "AI platform"
    assert data["count"] == 2
    assert len(data["results"]) == 2


@patch("chat.routes.get_chat_services")
def test_response_shape(mock_services, client):
    artifacts = [
        {
            **SAMPLE_ARTIFACTS[0],
            "document_score": 0.94,
            "matched_chunk_count": 3,
            "rank_reason": "filename_match",
        }
    ]
    _set_rag(mock_services, _mock_rag(artifacts=artifacts))

    response = client.post(
        "/atlas/document-search",
        json={"query": "machine learning"},
        content_type="application/json",
    )

    data = response.get_json()
    assert "query" in data
    assert "count" in data
    assert "results" in data
    first = data["results"][0]
    assert "snippet" in first
    assert "similarity" in first
    assert "source_type" in first
    assert first["document_score"] == 0.94
    assert first["matched_chunk_count"] == 3
    assert first["rank_reason"] == "filename_match"


@patch("chat.routes.get_chat_services")
def test_format_response_false_does_not_call_llm(mock_services, client):
    _set_rag(mock_services, _mock_rag())
    llm = _set_llm(mock_services)

    response = client.post(
        "/atlas/document-search",
        json={"query": "machine learning"},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "answer" not in data
    mock_services.return_value.get_llm_client.assert_not_called()
    llm.invoke.assert_not_called()


@patch("chat.routes.get_chat_services")
def test_format_response_string_false_does_not_call_llm(mock_services, client):
    _set_rag(mock_services, _mock_rag())
    llm = _set_llm(mock_services)

    response = client.post(
        "/atlas/document-search",
        json={"query": "machine learning", "format_response": "false"},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "answer" not in data
    mock_services.return_value.get_llm_client.assert_not_called()
    llm.invoke.assert_not_called()


@patch("chat.routes.get_chat_services")
def test_format_response_calls_llm_and_returns_answer_fields(mock_services, client):
    _set_rag(mock_services, _mock_rag())
    llm = _set_llm(mock_services, "Atlas is an AI-powered platform. [1]")

    response = client.post(
        "/atlas/document-search",
        json={
            "query": "AI platform",
            "format_response": True,
            "answer_style": "direct",
            "max_answer_chunks": 1,
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["answer"] == "Atlas is an AI-powered platform. [1]"
    assert data["answer_source"] == "atlas_context"
    assert data["grounding_status"] == "grounded"
    assert data["confidence"] == "high"
    assert data["warning"] is None
    assert len(data["citations"]) == 1
    assert data["citations"][0]["document_id"] == "doc-1"
    assert len(data["results"]) == 2
    llm.invoke.assert_called_once()
    prompt = llm.invoke.call_args.kwargs["messages"][0]["content"]
    assert "AI platform" in prompt
    assert "Atlas is an AI-powered platform." in prompt
    assert "Machine learning capabilities." not in prompt


@patch("chat.routes.get_chat_services")
def test_format_response_empty_results_does_not_call_llm(mock_services, client):
    _set_rag(mock_services, _mock_rag(artifacts=[]))
    llm = _set_llm(mock_services)

    response = client.post(
        "/atlas/document-search",
        json={"query": "nothing matches", "format_response": True},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 0
    assert data["answer_source"] == "none"
    assert data["grounding_status"] == "empty"
    assert data["confidence"] == "low"
    assert data["citations"] == []
    llm.invoke.assert_not_called()


@patch("chat.routes.get_chat_services")
def test_format_response_weak_results_does_not_call_llm(mock_services, client):
    weak_artifacts = [{**SAMPLE_ARTIFACTS[0], "similarity": 0.2, "score": 0.2}]
    _set_rag(mock_services, _mock_rag(artifacts=weak_artifacts))
    llm = _set_llm(mock_services)

    response = client.post(
        "/atlas/document-search",
        json={"query": "weak match", "format_response": True},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["answer_source"] == "none"
    assert data["grounding_status"] == "weak"
    assert data["confidence"] == "low"
    assert "not enough reliable context" in data["answer"]
    assert len(data["citations"]) == 1
    llm.invoke.assert_not_called()


@patch("chat.routes.get_chat_services")
def test_format_response_llm_failure_keeps_results(mock_services, client):
    _set_rag(mock_services, _mock_rag())
    llm = _set_llm(mock_services)
    llm.invoke.side_effect = RuntimeError("Bedrock unavailable")

    response = client.post(
        "/atlas/document-search",
        json={"query": "AI platform", "format_response": True},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["answer"] is None
    assert data["answer_source"] == "atlas_context"
    assert data["grounding_status"] == "grounded"
    assert data["confidence"] == "medium"
    assert "Claude formatting failed" in data["warning"]
    assert data["count"] == 2
    assert len(data["results"]) == 2


# ---------------------------------------------------------------------------
# limit parameter
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_default_limit_is_10(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "test"},
        content_type="application/json",
    )

    mock_instance.retrieve_context.assert_called_once_with(
        query="test", source_types=None, limit=10, mode="auto", file_type=None, rerank=False
    )


@patch("chat.routes.get_chat_services")
def test_custom_limit_is_passed_through(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "test", "limit": 3},
        content_type="application/json",
    )

    mock_instance.retrieve_context.assert_called_once_with(
        query="test", source_types=None, limit=3, mode="auto", file_type=None, rerank=False
    )


# ---------------------------------------------------------------------------
# source_type filter
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_source_type_is_passed_through(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "test", "source_type": "project"},
        content_type="application/json",
    )

    mock_instance.retrieve_context.assert_called_once_with(
        query="test", source_types=["project"], limit=10, mode="auto", file_type=None, rerank=False
    )


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_empty_results_returns_count_zero(mock_services, client):
    _set_rag(mock_services, _mock_rag(artifacts=[]))

    response = client.post(
        "/atlas/document-search",
        json={"query": "nothing matches"},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 0
    assert data["results"] == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_internal_error_returns_500(mock_services, client):
    mock_instance = MagicMock()
    mock_instance.retrieve_context.side_effect = RuntimeError("DB connection failed")
    _set_rag(mock_services, mock_instance)

    response = client.post(
        "/atlas/document-search",
        json={"query": "test"},
        content_type="application/json",
    )

    assert response.status_code == 500
    data = response.get_json()
    assert data["error"]["type"] == "internal_error"


# ---------------------------------------------------------------------------
# Feature 6: file_type filter
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_file_type_filter_passed_to_semantic_search(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "budget report", "file_type": "PDF"},
        content_type="application/json",
    )

    mock_instance.retrieve_context.assert_called_once_with(
        query="budget report", source_types=None, limit=10, mode="auto", file_type="pdf", rerank=False
    )


@patch("chat.routes.get_chat_services")
def test_file_type_is_lowercased(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "slides", "file_type": "PPTX"},
        content_type="application/json",
    )

    call_kwargs = mock_instance.retrieve_context.call_args.kwargs
    assert call_kwargs["file_type"] == "pptx"


@patch("chat.routes.get_chat_services")
def test_missing_file_type_passes_none(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "test"},
        content_type="application/json",
    )

    call_kwargs = mock_instance.retrieve_context.call_args.kwargs
    assert call_kwargs["file_type"] is None


# ---------------------------------------------------------------------------
# Feature 6: score field in response
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_score_field_present_in_results(mock_services, client):
    artifacts = [
        {**SAMPLE_ARTIFACTS[0], "score": 0.95},
        {**SAMPLE_ARTIFACTS[1], "score": 0.88},
    ]
    _set_rag(mock_services, _mock_rag(artifacts=artifacts))

    response = client.post(
        "/atlas/document-search",
        json={"query": "AI platform"},
        content_type="application/json",
    )

    data = response.get_json()
    assert data["results"][0]["score"] == 0.95
    assert data["results"][1]["score"] == 0.88


@patch("chat.routes.get_chat_services")
def test_score_falls_back_to_similarity(mock_services, client):
    _set_rag(mock_services, _mock_rag())

    response = client.post(
        "/atlas/document-search",
        json={"query": "test"},
        content_type="application/json",
    )

    data = response.get_json()
    first = data["results"][0]
    assert first["score"] == first["similarity"]


# ---------------------------------------------------------------------------
# Feature 6: hybrid path + edge cases
# ---------------------------------------------------------------------------

@patch("chat.routes.get_chat_services")
def test_file_type_filter_passed_to_hybrid_search(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "budget report", "source_type": "file", "file_type": "pdf"},
        content_type="application/json",
    )

    mock_instance.retrieve_context.assert_called_once_with(
        query="budget report", source_types=["file"], limit=10, mode="auto", file_type="pdf", rerank=False
    )


@patch("chat.routes.get_chat_services")
def test_hybrid_results_include_score_field(mock_services, client):
    from datetime import datetime, timezone
    artifacts = [
        {**SAMPLE_ARTIFACTS[0], "file_type": "pdf", "created_at": datetime.now(timezone.utc), "score": 0.94},
        {**SAMPLE_ARTIFACTS[1], "file_type": None, "created_at": None, "score": 0.85},
    ]
    _set_rag(mock_services, _mock_rag(artifacts=artifacts))

    response = client.post(
        "/atlas/document-search",
        json={"query": "budget", "source_type": "file", "mode": "hybrid"},
        content_type="application/json",
    )

    data = response.get_json()
    assert data["results"][0]["score"] == 0.94
    assert data["results"][1]["score"] == 0.85


@patch("chat.routes.get_chat_services")
def test_empty_string_file_type_passes_none(mock_services, client):
    mock_instance = _mock_rag()
    _set_rag(mock_services, mock_instance)

    client.post(
        "/atlas/document-search",
        json={"query": "test", "file_type": ""},
        content_type="application/json",
    )

    call_kwargs = mock_instance.retrieve_context.call_args.kwargs
    assert call_kwargs["file_type"] is None


def test_file_type_changes_cache_key():
    from cache import make_cache_key

    base_params = {"query": "test", "source_type": "", "limit": "10", "mode": "", "rerank": "False"}
    key_no_type = make_cache_key("docsearch", {**base_params, "file_type": ""})
    key_pdf = make_cache_key("docsearch", {**base_params, "file_type": "pdf"})
    key_docx = make_cache_key("docsearch", {**base_params, "file_type": "docx"})

    assert key_no_type != key_pdf
    assert key_pdf != key_docx


def test_format_response_changes_cache_key():
    from cache import make_cache_key

    base_params = {
        "query": "test",
        "source_type": "",
        "limit": "10",
        "mode": "auto",
        "rerank": "False",
        "file_type": "",
        "filter_category": "",
        "answer_style": "summary",
        "max_answer_chunks": "6",
    }
    raw_key = make_cache_key("docsearch", {**base_params, "format_response": "False"})
    formatted_key = make_cache_key("docsearch", {**base_params, "format_response": "True"})
    bullets_key = make_cache_key(
        "docsearch",
        {**base_params, "format_response": "True", "answer_style": "bullets"},
    )

    assert raw_key != formatted_key
    assert formatted_key != bullets_key
