from unittest.mock import patch

from chat.agent import AtlasAgent
from chat.tools import ToolResult


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def invoke(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tool-1",
                        "name": "atlas_retrieve",
                        "arguments": {
                            "query": "Travel Policy",
                            "source_types": ["file"],
                        },
                    }
                ],
            }
        return {"content": "The Travel Policy is covered in the retrieved file context."}


class SummaryLLM:
    def __init__(self, content="The Travel Policy requires pre-approval and compliant expenses. [Corporate Travel & Expense Policy.pdf, page 1]"):
        self.calls = 0
        self.prompts = []
        self.content = content

    def invoke(self, **kwargs):
        self.calls += 1
        self.prompts.append(kwargs["messages"][0]["content"])
        return {"content": self.content}


def test_chat_agent_can_return_file_retrieval_artifacts():
    artifact = {
        "document_id": "doc-1",
        "source_type": "file",
        "source_id": "file-1",
        "file_name": "Travel Policy.pdf",
        "chunk_text": "Travel Policy details",
        "snippet": "Travel Policy details",
        "page_number": 2,
        "section_title": "Policy",
        "metadata": {},
        "score": 0.91,
    }

    with patch(
        "chat.tools.RAGTools.retrieve_context",
        return_value=ToolResult(content="Travel Policy details", artifacts=[artifact]),
    ):
        agent = AtlasAgent(llm_client=FakeLLM(), embedding_client=object())
        result = agent.invoke("Could you tell me about the Travel Policy?")

    assert "Travel Policy" in result["response"]
    assert result["artifacts"] == [artifact]
    assert result["answer_source"] == "atlas_context"
    assert result["grounding_status"] == "grounded"
    assert result["confidence"] == "high"


def test_summary_request_uses_full_document_context_without_initial_tool_selection_llm():
    llm = SummaryLLM()
    search_artifacts = [
        {
            "document_id": "doc-policy",
            "source_type": "file",
            "source_id": "file-policy",
            "file_name": "Corporate Travel & Expense Policy.pdf",
            "chunk_text": "Representative search snippet",
            "snippet": "Representative search snippet",
            "metadata": {},
            "score": 0.91,
            "document_score": 0.91,
        },
        {
            "document_id": "doc-reminder",
            "source_type": "file",
            "source_id": "file-reminder",
            "file_name": "Travel Reminders.pdf",
            "chunk_text": "Reminder snippet",
            "snippet": "Reminder snippet",
            "metadata": {},
            "score": 0.82,
            "document_score": 0.82,
        },
    ]
    full_chunks = [
        {
            **search_artifacts[0],
            "id": "chunk-1",
            "chunk_text": "Full policy page 1: pre-approval is required.",
            "snippet": "Full policy page 1: pre-approval is required.",
            "page_number": 1,
        },
        {
            **search_artifacts[0],
            "id": "chunk-2",
            "chunk_text": "Full policy page 2: receipts are required.",
            "snippet": "Full policy page 2: receipts are required.",
            "page_number": 2,
        },
    ]

    with patch(
        "chat.tools.RAGTools.retrieve_context",
        return_value=ToolResult(content="matches", artifacts=search_artifacts, metadata={"max_score": 0.91}),
    ) as retrieve_context:
        with patch(
            "chat.tools.RAGTools.get_document_context",
            return_value=ToolResult(content="full document", artifacts=full_chunks),
        ) as get_document_context:
            agent = AtlasAgent(llm_client=llm, embedding_client=object())
            result = agent.invoke("Summarize the Travel Policy")

    retrieve_context.assert_called_once()
    assert retrieve_context.call_args.kwargs["query"] == "the Travel Policy"
    assert retrieve_context.call_args.kwargs["source_types"] == ["file"]
    assert retrieve_context.call_args.kwargs["mode"] == "hybrid"
    get_document_context.assert_called_once_with("doc-policy")
    assert llm.calls == 1
    assert "Full policy page 1" in llm.prompts[0]
    assert "retrieved context does not contain enough information" not in llm.prompts[0]
    assert "Travel Reminders.pdf" in llm.prompts[0]
    assert result["response"] == llm.content
    assert result["artifacts"][0]["file_name"] == "Corporate Travel & Expense Policy.pdf"
    assert result["artifacts"][0]["alternative_file_names"] == ["Travel Reminders.pdf"]
    assert result["answer_source"] == "atlas_context"
    assert result["grounding_status"] == "grounded"


def test_summary_request_with_no_matching_file_returns_empty_grounding():
    llm = SummaryLLM()
    with patch(
        "chat.tools.RAGTools.retrieve_context",
        return_value=ToolResult(
            content="No relevant Atlas context found.",
            artifacts=[],
            metadata={"retrieval_attempted": True, "retrieval_artifact_count": 0, "grounding_status": "empty"},
        ),
    ):
        agent = AtlasAgent(llm_client=llm, embedding_client=object())
        result = agent.invoke("Summarize the Travel Policy")

    assert llm.calls == 0
    assert "No relevant Atlas document was found" in result["response"]
    assert result["answer_source"] == "none"
    assert result["grounding_status"] == "empty"


def test_internal_file_query_with_empty_retrieval_does_not_generate_with_claude():
    llm = FakeLLM()
    with patch(
        "chat.tools.RAGTools.retrieve_context",
        return_value=ToolResult(content="No relevant Atlas context found.", artifacts=[]),
    ):
        agent = AtlasAgent(llm_client=llm, embedding_client=object())
        result = agent.invoke("Could you tell me about the Travel Policy?")

    assert llm.calls == 1
    assert "No relevant Atlas context was found" in result["response"]
    assert result["answer_source"] == "none"
    assert result["grounding_status"] == "empty"
    assert result["confidence"] == "low"
    assert result["retrieval_attempted"] is True
    assert result["retrieval_artifact_count"] == 0


def test_internal_file_query_with_weak_retrieval_does_not_generate_with_claude():
    llm = FakeLLM()
    artifact = {
        "document_id": "doc-1",
        "source_type": "file",
        "source_id": "file-1",
        "file_name": "Travel Policy.pdf",
        "chunk_text": "A weak possible match",
        "snippet": "A weak possible match",
        "metadata": {},
        "score": 0.21,
    }

    with patch(
        "chat.tools.RAGTools.retrieve_context",
        return_value=ToolResult(content="A weak possible match", artifacts=[artifact]),
    ):
        agent = AtlasAgent(llm_client=llm, embedding_client=object())
        result = agent.invoke("Could you tell me about the Travel Policy?")

    assert llm.calls == 1
    assert "not enough reliable context" in result["response"]
    assert result["answer_source"] == "none"
    assert result["grounding_status"] == "weak"
    assert result["confidence"] == "low"
    assert result["max_score"] == 0.21


def test_general_question_can_use_general_knowledge_without_retrieval():
    class GeneralLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, **kwargs):
            self.calls += 1
            return {"content": "A startup is a young company."}

    llm = GeneralLLM()
    agent = AtlasAgent(llm_client=llm, embedding_client=object())
    result = agent.invoke("What is a startup?")

    assert llm.calls == 1
    assert result["response"] == "A startup is a young company."
    assert result["answer_source"] == "general_knowledge"
    assert result["grounding_status"] == "not_required"
    assert result["retrieval_attempted"] is False


def test_cycle_count_query_uses_structured_tool_before_retrieval():
    llm = FakeLLM()
    artifact = {
        "source_type": "cycle_summary",
        "cycle_id": "gced_cycle5",
        "board_id": "10000000003",
        "total_startups": 42,
    }
    structured_result = ToolResult(
        content="Cycle 5 in 2025 had 42 startups in the structured Atlas database.",
        artifacts=[artifact],
        metadata={
            "retrieval_attempted": True,
            "retrieval_artifact_count": 1,
            "max_score": 1.0,
            "grounding_status": "grounded",
            "answer_source": "atlas_structured",
            "confidence": "high",
            "direct_response": "Cycle 5 in 2025 had 42 startups in the structured Atlas database.",
        },
    )

    with patch("chat.tools.RAGTools.get_cycle_startup_count", return_value=structured_result) as count_tool:
        with patch("chat.tools.RAGTools.retrieve_context") as retrieve_context:
            agent = AtlasAgent(llm_client=llm, embedding_client=object())
            result = agent.invoke("How many startups were there in 2025 cycle 5?")

    count_tool.assert_called_once_with(cycle_number=5, year=2025)
    retrieve_context.assert_not_called()
    assert llm.calls == 0
    assert result["response"] == "Cycle 5 in 2025 had 42 startups in the structured Atlas database."
    assert result["artifacts"] == [artifact]
    assert result["answer_source"] == "atlas_structured"
    assert result["grounding_status"] == "grounded"
    assert result["confidence"] == "high"


def test_cycle_count_missing_mapping_does_not_fallback_to_files():
    llm = FakeLLM()
    structured_result = ToolResult(
        content="No configured Atlas board mapping was found for gced_cycle5.",
        artifacts=[],
        metadata={
            "retrieval_attempted": True,
            "retrieval_artifact_count": 0,
            "grounding_status": "empty",
            "answer_source": "none",
            "confidence": "low",
            "direct_response": "No configured Atlas board mapping was found for gced_cycle5.",
        },
    )

    with patch("chat.tools.RAGTools.get_cycle_startup_count", return_value=structured_result):
        with patch("chat.tools.RAGTools.retrieve_context") as retrieve_context:
            agent = AtlasAgent(llm_client=llm, embedding_client=object())
            result = agent.invoke("How many startups were there in 2025 cycle 5?")

    retrieve_context.assert_not_called()
    assert llm.calls == 0
    assert result["response"] == "No configured Atlas board mapping was found for gced_cycle5."
    assert result["answer_source"] == "none"
    assert result["grounding_status"] == "empty"


def _structured_result(response, artifact=None):
    return ToolResult(
        content=response,
        artifacts=[artifact or {"source_type": "structured_counts"}],
        metadata={
            "retrieval_attempted": True,
            "retrieval_artifact_count": 1,
            "max_score": 1.0,
            "grounding_status": "grounded",
            "answer_source": "atlas_structured",
            "confidence": "high",
            "direct_response": response,
        },
    )


def _assert_structured_route(message, method_name, expected_kwargs):
    llm = FakeLLM()
    response = f"{method_name} response"
    with patch(f"chat.tools.RAGTools.{method_name}", return_value=_structured_result(response)) as tool:
        with patch("chat.tools.RAGTools.retrieve_context") as retrieve_context:
            agent = AtlasAgent(llm_client=llm, embedding_client=object())
            result = agent.invoke(message)

    tool.assert_called_once_with(**expected_kwargs)
    retrieve_context.assert_not_called()
    assert llm.calls == 0
    assert result["response"] == response
    assert result["answer_source"] == "atlas_structured"


def test_project_count_query_uses_structured_tool():
    _assert_structured_route(
        "How many projects are there by stage?",
        "get_project_counts",
        {"group_by": "stage"},
    )


def test_contract_budget_query_uses_structured_tool():
    _assert_structured_route(
        "What are the contract budget totals by status?",
        "get_contract_metrics",
        {"group_by": "status"},
    )


def test_startup_breakdown_query_uses_structured_counts():
    _assert_structured_route(
        "How many startups in cycle 5 by vertical?",
        "get_startup_counts",
        {"group_by": "vertical", "cycle_number": 5},
    )


def test_pitchbook_deal_count_query_uses_structured_tool():
    _assert_structured_route(
        "How many PitchBook deals are there by deal type?",
        "get_pitchbook_counts",
        {"entity": "deal", "group_by": "deal_type"},
    )


def test_monday_item_count_query_uses_structured_tool():
    _assert_structured_route(
        "How many Monday items are there by board?",
        "get_monday_counts",
        {"entity": "item", "group_by": "board"},
    )


def test_file_count_query_uses_structured_tool():
    _assert_structured_route(
        "How many pdf files are there by category?",
        "get_file_counts",
        {"group_by": "category", "file_type": "pdf"},
    )
