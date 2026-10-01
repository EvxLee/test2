from unittest.mock import MagicMock, patch

from chat.tools import RAGTools


def _row(**overrides):
    row = {
        "id": "chunk-1",
        "document_id": "doc-1",
        "source_type": "project",
        "source_id": "source-1",
        "file_name": None,
        "spaces_key": None,
        "file_type": None,
        "category": None,
        "owner": None,
        "created_at": None,
        "chunk_text": "Atlas context",
        "page_number": None,
        "section_title": None,
        "metadata": {},
        "similarity": 0.91,
    }
    row.update(overrides)
    return row


def _embedding_client():
    client = MagicMock()
    client.embed.return_value = [0.1] * 1024
    return client


def test_retrieve_context_semantic_project_path():
    with patch("chat.tools.fetch_all", return_value=[_row()]) as fetch_all:
        result = RAGTools(embedding_client=_embedding_client()).retrieve_context(
            query="AI startups",
            source_types=["project"],
            limit=5,
            mode="semantic",
        )

    assert result.artifacts[0]["source_type"] == "project"
    assert result.artifacts[0]["snippet"] == "Atlas context"
    assert fetch_all.call_count == 1
    assert "d.source_type = ANY" in fetch_all.call_args.args[0]


def test_retrieve_context_hybrid_file_path_with_file_type():
    semantic = [_row(source_type="file", file_name="Travel Policy.pdf", file_type="pdf")]
    filename = [_row(source_type="file", file_name="Travel Policy.pdf", file_type="pdf", keyword_score=0.9)]

    with patch("chat.tools.fetch_all", side_effect=[semantic, filename, []]):
        result = RAGTools(embedding_client=_embedding_client()).retrieve_context(
            query="Travel Policy",
            source_types=["file"],
            limit=5,
            mode="auto",
            file_type="pdf",
        )

    assert result.artifacts
    assert result.artifacts[0]["file_name"] == "Travel Policy.pdf"
    assert result.artifacts[0]["file_type"] == "pdf"


def test_hybrid_file_ranking_prefers_policy_filename_over_reminder():
    reminder = _row(
        id="chunk-reminder",
        document_id="doc-reminder",
        source_type="file",
        file_name="Travel Reminders.pdf",
        file_type="pdf",
        similarity=0.95,
    )
    policy = _row(
        id="chunk-policy",
        document_id="doc-policy",
        source_type="file",
        file_name="Corporate Travel & Expense Policy.pdf",
        file_type="pdf",
        similarity=0.90,
    )

    with patch("chat.tools.fetch_all", side_effect=[[reminder, policy], [], []]):
        result = RAGTools(embedding_client=_embedding_client()).retrieve_context(
            query="Travel Policy",
            source_types=["file"],
            limit=5,
            mode="hybrid",
        )

    assert result.artifacts[0]["file_name"] == "Corporate Travel & Expense Policy.pdf"
    assert result.artifacts[0]["rank_reason"] == "filename_match"
    assert result.artifacts[0]["document_score"] > result.artifacts[1]["document_score"]


def test_hybrid_file_search_dedupes_and_counts_matching_chunks():
    policy_1 = _row(
        id="chunk-policy-1",
        document_id="doc-policy",
        source_type="file",
        file_name="Corporate Travel & Expense Policy.pdf",
        file_type="pdf",
        similarity=0.90,
    )
    policy_2 = _row(
        id="chunk-policy-2",
        document_id="doc-policy",
        source_type="file",
        file_name="Corporate Travel & Expense Policy.pdf",
        file_type="pdf",
        similarity=0.88,
    )
    reminder = _row(
        id="chunk-reminder",
        document_id="doc-reminder",
        source_type="file",
        file_name="Travel Reminders.pdf",
        file_type="pdf",
        similarity=0.87,
    )

    with patch("chat.tools.fetch_all", side_effect=[[policy_1, policy_2, reminder], [], []]):
        result = RAGTools(embedding_client=_embedding_client()).retrieve_context(
            query="Travel Policy",
            source_types=["file"],
            limit=5,
            mode="hybrid",
        )

    assert [artifact["document_id"] for artifact in result.artifacts] == ["doc-policy", "doc-reminder"]
    assert result.artifacts[0]["matched_chunk_count"] == 2
    assert result.artifacts[0]["document_score"] > result.artifacts[1]["document_score"]


def test_get_document_context_fetches_chunks_in_document_order():
    rows = [
        _row(id="chunk-1", document_id="doc-policy", source_type="file", file_name="Policy.pdf", page_number=1),
        _row(id="chunk-2", document_id="doc-policy", source_type="file", file_name="Policy.pdf", page_number=2),
    ]

    with patch("chat.tools.fetch_all", return_value=rows) as fetch_all:
        result = RAGTools(embedding_client=None).get_document_context("doc-policy")

    assert len(result.artifacts) == 2
    assert result.artifacts[0]["file_name"] == "Policy.pdf"
    sql = fetch_all.call_args.args[0]
    assert "WHERE dc.document_id = %s" in sql
    assert "ORDER BY dc.page_number" in sql


def test_retrieve_context_without_embedding_client_is_controlled_empty_result():
    result = RAGTools(embedding_client=None).retrieve_context(query="Travel Policy")

    assert result.artifacts == []
    assert "unavailable" in result.content


def test_cycle_startup_count_prefers_gced_board_with_rows(monkeypatch):
    monkeypatch.setenv("MONDAY_BOARD_GCED_MFTF25_CYCLE5_ID", "10000000022")

    def fake_fetch_one(_sql, params):
        counts = {
            ("10000000022",): {"count": 50},
            ("legacy-board",): {"count": 0},
        }
        return counts.get(params, {"count": 0})

    sample_rows = [
        {
            "startup_name": "ExampleCo",
            "monday_board_id": "10000000022",
            "team_decision": "Yes for later",
            "track": "CleanTech",
        }
    ]

    with patch("chat.tools.fetch_one", side_effect=fake_fetch_one):
        with patch("chat.tools.fetch_all", return_value=sample_rows):
            with patch("cycles.queries.board_id_for_cycle", return_value="legacy-board"):
                result = RAGTools(embedding_client=None).get_cycle_startup_count(
                    cycle_number=5,
                    year=2025,
                )

    assert "Cycle 5 in 2025 had 50 startups" in result.content
    assert result.artifacts[0]["board_id"] == "10000000022"
    assert result.artifacts[0]["total_startups"] == 50
    assert result.artifacts[0]["sample_startups"] == sample_rows
