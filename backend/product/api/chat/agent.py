"""
LangGraph-based RAG Agent for Atlas.

This module implements a conversational agent that can:
1. Answer questions using retrieved context (RAG)
2. Query structured data (projects, companies, deals)
3. Perform analysis and comparisons
"""

import logging
import os
import re
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field

from .llm_client import BedrockLLMClient, BedrockEmbeddingClient, get_llm_client, get_embedding_client
from .tools import RAGTools, TOOL_DEFINITIONS, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Chat message."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # For tool messages


@dataclass
class AgentState:
    """State for the agent workflow."""
    messages: List[Message] = field(default_factory=list)
    current_step: str = "query_or_respond"
    tool_results: List[ToolResult] = field(default_factory=list)
    internal_retrieval_required: bool = False
    retrieval_attempted: bool = False
    retrieval_artifact_count: int = 0
    max_score: Optional[float] = None
    grounding_status: str = "not_required"
    answer_source: str = "general_knowledge"
    confidence: str = "medium"
    warning: Optional[str] = None
    direct_response: Optional[str] = None


_INTERNAL_RETRIEVAL_TOOLS = {"atlas_retrieve", "semantic_search", "hybrid_document_search", "summarize_document"}
_INTERNAL_INTENT_TERMS = (
    "atlas", "portfolio", "project", "projects",
    "startup", "startups", "company", "companies", "contract", "contracts",
    "monday", "pitchbook", "document", "documents", "file", "files",
    "policy", "policies", "report", "reports", "deck", "slides",
    "travel policy", "poc", "proof of concept", "incubation",
)
_EXTERNAL_INTENT_TERMS = (
    "latest", "current", "recent", "today", "news", "web", "internet",
    "market trends", "regulations", "external",
)


SYSTEM_PROMPT = """You are Atlas AI, an intelligent assistant for the company's startup portfolio and innovation projects.

Your primary capabilities include:
- Finding specific documents, projects, and reports from the company's internal systems
- Answering questions about startups in the portfolio
- Comparing companies and technologies
- Providing market intelligence from PitchBook data
- Analyzing project stages, verticals, and status

When answering questions:
1. PRIORITIZE STRUCTURED DATA: For internal counts, totals, lists, filters, and cycle questions, use structured SQL-backed tools before embeddings or files
2. For semantic/conceptual questions about internal data, use atlas_retrieve to find relevant context
3. For document or file questions, retrieve relevant chunks, answer from those chunks, cite file/page/section details when present, and rely on the returned artifacts to surface related files
4. Do not answer numeric Atlas questions from file excerpts unless structured tools are unavailable or the user explicitly asks about a specific file/deck
5. WEB SEARCH: For current events, recent market trends, or general information requiring up-to-date data (e.g., "What are the latest AI regulations in 2025?", "Recent developments in quantum computing"), use the web_search tool
6. GENERAL KNOWLEDGE: For well-established concepts and information within your training data, you can answer using your general knowledge
7. ALWAYS BE CLEAR: When using internal data, cite your sources. When using web search results, include URLs. When using general knowledge, acknowledge that you're providing general information
8. If you don't have enough internal information and general knowledge isn't sufficient, say so clearly

You can answer both:
- Questions about the company's specific portfolio (using internal tools)
- General questions about startups, technology, and innovation (using your knowledge)

Be concise but thorough. Provide actionable insights when possible."""


class AtlasAgent:
    """
    RAG Agent for Atlas using a state machine pattern.

    This implements a simplified version of the LangGraph pattern without
    requiring the langgraph dependency, making it more portable.
    """

    def __init__(
        self,
        llm_client: Optional[BedrockLLMClient] = None,
        embedding_client: Optional[BedrockEmbeddingClient] = None,
    ):
        """
        Initialize the agent.

        Args:
            llm_client: Optional LLM client (will use default if not provided)
            embedding_client: Optional embedding client for semantic search
        """
        self.llm = llm_client or get_llm_client()
        self.embedding_client = embedding_client

        # Try to get embedding client if not provided
        if self.embedding_client is None:
            try:
                self.embedding_client = get_embedding_client()
            except Exception as e:
                logger.warning(f"Could not initialize embedding client: {e}")

        self.tools = RAGTools(embedding_client=self.embedding_client, llm_client=self.llm)
        self.system_prompt = SYSTEM_PROMPT
        self.strict_internal = os.getenv("ATLAS_RAG_STRICT_INTERNAL", "true").lower() not in (
            "0", "false", "no", "off"
        )
        try:
            self.min_grounding_score = float(os.getenv("ATLAS_RAG_MIN_SCORE", "0.70"))
        except ValueError:
            self.min_grounding_score = 0.70

    def invoke(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and return a response.

        Args:
            user_message: The user's input message
            conversation_history: Optional previous messages
            thread_id: Optional thread ID for conversation tracking

        Returns:
            Dict with 'response', 'tool_calls', and 'artifacts'
        """
        # Initialize state
        state = AgentState()
        state.internal_retrieval_required = self._requires_internal_retrieval(user_message)
        state.answer_source = "none" if state.internal_retrieval_required else "general_knowledge"
        state.confidence = "low" if state.internal_retrieval_required else "medium"

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                state.messages.append(Message(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    tool_calls=msg.get("tool_calls"),
                    tool_call_id=msg.get("tool_call_id"),
                ))

        # Add the new user message
        state.messages.append(Message(role="user", content=user_message))

        structured_tool_call = self._structured_tool_call(user_message)
        if structured_tool_call:
            state.internal_retrieval_required = True
            state.answer_source = "none"
            state.confidence = "low"
            state.messages.append(Message(role="assistant", content="", tool_calls=[structured_tool_call]))
            state.current_step = "execute_tools"
        elif self._is_file_summary_request(user_message):
            state.internal_retrieval_required = True
            state.answer_source = "none"
            state.confidence = "low"
            state.messages.append(Message(role="assistant", content="", tool_calls=[self._summary_tool_call(user_message)]))
            state.current_step = "execute_tools"

        # Run the agent loop
        max_iterations = 5
        iteration = 0
        all_artifacts = []

        while iteration < max_iterations:
            iteration += 1

            if state.current_step == "query_or_respond":
                state = self._query_or_respond(state)

                # Check if we should call tools or respond directly
                last_msg = state.messages[-1] if state.messages else None
                if last_msg and last_msg.tool_calls:
                    state.current_step = "execute_tools"
                elif state.internal_retrieval_required:
                    state = self._force_internal_retrieval(state, user_message)
                    state.current_step = "execute_tools"
                else:
                    state.grounding_status = "not_required"
                    state.answer_source = "general_knowledge"
                    state.current_step = "done"

            elif state.current_step == "execute_tools":
                state, artifacts = self._execute_tools(state)
                all_artifacts.extend(artifacts)
                if state.direct_response is not None:
                    state.messages.append(Message(role="assistant", content=state.direct_response))
                    state.current_step = "done"
                else:
                    gated_response = self._grounding_gate_response(state)
                    if gated_response is not None:
                        state.messages.append(Message(role="assistant", content=gated_response))
                        state.current_step = "done"
                    else:
                        state.current_step = "generate"

            elif state.current_step == "generate":
                state = self._generate(state)
                state.current_step = "done"

            elif state.current_step == "done":
                break

        # Extract final response
        final_response = ""
        for msg in reversed(state.messages):
            if msg.role == "assistant" and msg.content and not msg.tool_calls:
                final_response = msg.content
                break

        return {
            "response": final_response,
            "thread_id": thread_id,
            "artifacts": all_artifacts,
            "message_count": len(state.messages),
            "answer_source": state.answer_source,
            "grounding_status": state.grounding_status,
            "confidence": state.confidence,
            "warning": state.warning,
            "retrieval_attempted": state.retrieval_attempted,
            "retrieval_artifact_count": state.retrieval_artifact_count,
            "max_score": state.max_score,
        }

    def _requires_internal_retrieval(self, user_message: str) -> bool:
        if not self.strict_internal:
            return False

        text = (user_message or "").lower()
        if not text:
            return False
        compact = " ".join(text.split()).strip(" ?!.")
        if compact in {"what is a startup", "what is an startup", "what are startups", "define startup"}:
            return False

        has_internal_term = any(term in text for term in _INTERNAL_INTENT_TERMS)
        has_external_term = any(term in text for term in _EXTERNAL_INTENT_TERMS)

        # External-only questions can use Claude/web search. Mixed questions
        # still require Atlas context first because the user may be asking about
        # current information for an internal entity.
        return has_internal_term or not has_external_term and any(
            phrase in text for phrase in ("our ", "we ", "us ", "inside ", "database")
        )

    def _infer_retrieval_source_types(self, user_message: str) -> Optional[List[str]]:
        text = (user_message or "").lower()
        if any(term in text for term in ("document", "file", "policy", "report", "deck", "slide")):
            return ["file"]
        if "contract" in text:
            return ["contract"]
        if "pitchbook" in text:
            return ["pitchbook_deal", "pitchbook_company"]
        if "monday" in text:
            return ["monday_item"]
        if any(term in text for term in ("project", "startup", "company", "portfolio", "incubation", "poc")):
            return ["project"]
        return None

    def _is_file_summary_request(self, user_message: str) -> bool:
        text = " ".join((user_message or "").lower().split())
        if not text:
            return False
        has_summary_intent = any(
            phrase in text
            for phrase in (
                "summarize",
                "summary",
                "overview",
                "recap",
                "what does this document say",
                "what does the document say",
                "what does this file say",
            )
        )
        if not has_summary_intent:
            return False
        return any(term in text for term in ("document", "file", "policy", "report", "deck", "slide", "pdf"))

    def _clean_summary_query(self, user_message: str) -> str:
        cleaned = user_message or ""
        patterns = [
            r"\bplease\b",
            r"\bsummarize\b",
            r"\bsummary of\b",
            r"\boverview of\b",
            r"\brecap of\b",
            r"\bwhat does this document say\b",
            r"\bwhat does the document say\b",
            r"\bwhat does this file say\b",
            r"\bgive me\b",
            r"\btell me\b",
            r"\babout\b",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[?!.]+", " ", cleaned)
        cleaned = " ".join(cleaned.split())
        return cleaned or user_message

    def _summary_tool_call(self, user_message: str) -> Dict[str, Any]:
        return {
            "id": "forced-document-summary",
            "name": "summarize_document",
            "arguments": {
                "query": self._clean_summary_query(user_message),
                "source_types": ["file"],
                "limit": 5,
                "mode": "hybrid",
                "file_type": self._extract_file_type(user_message),
            },
        }

    def _structured_tool_call(self, user_message: str) -> Optional[Dict[str, Any]]:
        text = (user_message or "").lower()
        if not text:
            return None

        is_count_query = any(term in text for term in ("how many", "count", "number of", "total", "sum", "breakdown"))
        is_list_query = any(term in text for term in ("list", "show", "which", "what startups", "what companies"))
        group_by = self._structured_group_by(text)
        year_match = re.search(r"\b(20\d{2})\b", text)
        year = int(year_match.group(1)) if year_match else None

        if is_count_query and any(term in text for term in ("file", "files", "document count", "documents count")):
            args: Dict[str, Any] = {"group_by": group_by if group_by in {"board", "category", "owner", "type"} else None}
            board_id = self._extract_board_id(text)
            if board_id:
                args["board_id"] = board_id
            file_type = self._extract_file_type(text)
            if file_type:
                args["file_type"] = file_type
            return {"id": "forced-file-counts", "name": "get_file_counts", "arguments": args}

        if is_count_query and "monday" in text and any(term in text for term in ("board", "boards", "item", "items")):
            entity = "board" if "board" in text and "item" not in text else "item"
            args = {"entity": entity, "group_by": "board" if " by board" in text else None}
            board_id = self._extract_board_id(text)
            if board_id:
                args["board_id"] = board_id
            if "active" in text or "current" in text:
                args["active_only"] = True
            return {"id": "forced-monday-counts", "name": "get_monday_counts", "arguments": args}

        if is_count_query and ("pitchbook" in text or "deal" in text or "deals" in text):
            entity = "deal" if "deal" in text else "company"
            args = {"entity": entity, "group_by": group_by if group_by in {"industry", "country", "region", "deal_type", "year", "vertical"} else None}
            if year:
                args["year"] = year
            return {"id": "forced-pitchbook-counts", "name": "get_pitchbook_counts", "arguments": args}

        if is_count_query and any(term in text for term in ("contract", "contracts", "budget", "amount")):
            args = {"group_by": group_by if group_by in {"status", "stage", "owner", "team", "category"} else None}
            return {"id": "forced-contract-metrics", "name": "get_contract_metrics", "arguments": args}

        if is_count_query and any(term in text for term in ("project", "projects")):
            args = {"group_by": group_by if group_by in {"stage", "vertical", "owner", "status"} else None}
            if "ongoing" in text or "current" in text:
                args["is_ongoing"] = True
            if "archived" in text:
                args["status"] = "Archived"
            return {"id": "forced-project-counts", "name": "get_project_counts", "arguments": args}

        cycle_match = re.search(r"\b(?:gced[_\s-]*)?cycle\s*(\d+)\b", text)
        is_startup_query = any(term in text for term in ("startup", "startups", "company", "companies"))
        asks_for_file_support = any(term in text for term in ("document", "file", "deck", "presentation", "source", "support"))

        if is_startup_query and is_count_query and not asks_for_file_support:
            args = {"group_by": group_by if group_by in {"cycle", "vertical", "decision", "status", "source"} else None}
            if cycle_match:
                args["cycle_number"] = int(cycle_match.group(1))
            if year:
                args["year"] = year
            # Preserve the direct count tool for simple cycle totals.
            if cycle_match and args.get("group_by") is None:
                return {
                    "id": "forced-cycle-startup-count",
                    "name": "get_cycle_startup_count",
                    "arguments": {"cycle_number": int(cycle_match.group(1)), **({"year": year} if year else {})},
                }
            return {"id": "forced-startup-counts", "name": "get_startup_counts", "arguments": args}

        if not cycle_match or not is_startup_query or asks_for_file_support:
            return None

        args = {"cycle_number": int(cycle_match.group(1))}
        if year:
            args["year"] = year

        if is_list_query:
            args["limit"] = 25
            return {
                "id": "forced-cycle-startups",
                "name": "get_cycle_startups",
                "arguments": args,
            }

        return None

    def _structured_group_by(self, text: str) -> Optional[str]:
        if "by stage" in text or "per stage" in text:
            return "stage"
        if "by vertical" in text or "per vertical" in text or "by track" in text:
            return "vertical"
        if "by owner" in text or "per owner" in text:
            return "owner"
        if "by status" in text or "per status" in text:
            return "status"
        if "by decision" in text or "per decision" in text:
            return "decision"
        if "by source" in text or "per source" in text:
            return "source"
        if "by category" in text or "per category" in text:
            return "category"
        if "by team" in text or "per team" in text:
            return "team"
        if "by board" in text or "per board" in text:
            return "board"
        if "by type" in text or "by file type" in text or "per type" in text:
            return "type"
        if "by industry" in text or "per industry" in text:
            return "industry"
        if "by country" in text or "per country" in text:
            return "country"
        if "by region" in text or "per region" in text:
            return "region"
        if "by deal type" in text or "per deal type" in text:
            return "deal_type"
        if "by year" in text or "per year" in text:
            return "year"
        return None

    def _extract_board_id(self, text: str) -> Optional[str]:
        match = re.search(r"\b\d{8,}\b", text)
        return match.group(0) if match else None

    def _extract_file_type(self, text: str) -> Optional[str]:
        for ext in ("pdf", "pptx", "docx", "xlsx", "csv", "png", "jpg", "jpeg"):
            if re.search(rf"\b{ext}\b", text):
                return ext
        return None

    def _force_internal_retrieval(self, state: AgentState, user_message: str) -> AgentState:
        state.messages.append(Message(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "forced-atlas-retrieve",
                "name": "atlas_retrieve",
                "arguments": {
                    "query": user_message,
                    "source_types": self._infer_retrieval_source_types(user_message),
                    "limit": 8,
                    "mode": "auto",
                },
            }],
        ))
        return state

    def _max_artifact_score(self, artifacts: List[Dict]) -> Optional[float]:
        scores = []
        for artifact in artifacts or []:
            value = (
                artifact.get("score")
                or artifact.get("similarity")
                or artifact.get("fusion_score")
                or artifact.get("keyword_score")
            )
            if value is None:
                continue
            try:
                scores.append(float(value))
            except (TypeError, ValueError):
                continue
        return max(scores) if scores else None

    def _grounding_gate_response(self, state: AgentState) -> Optional[str]:
        if not state.internal_retrieval_required:
            return None

        if not state.retrieval_attempted:
            state.grounding_status = "empty"
            state.answer_source = "none"
            state.confidence = "low"
            state.warning = "Atlas retrieval was required but was not attempted, so no grounded answer was generated."
            return (
                "No Atlas retrieval context was available for that question, so I can't provide a grounded answer "
                "from the internal Atlas database."
            )

        if state.retrieval_artifact_count == 0:
            state.grounding_status = "empty"
            state.answer_source = "none"
            state.confidence = "low"
            state.warning = "No Atlas context was retrieved, so no grounded answer was generated."
            return (
                "No relevant Atlas context was found for that question, so I can't provide a grounded answer "
                "from the internal Atlas database."
            )

        max_score = state.max_score
        if max_score is not None and max_score < self.min_grounding_score:
            state.grounding_status = "weak"
            state.answer_source = "none"
            state.confidence = "low"
            state.warning = (
                f"Retrieved Atlas context was below the grounding threshold "
                f"({max_score:.2f} < {self.min_grounding_score:.2f})."
            )
            return (
                "I found possible Atlas matches, but not enough reliable context to answer confidently. "
                "Try a more specific question or check the related results."
            )

        state.grounding_status = "grounded"
        state.answer_source = "atlas_context"
        state.confidence = "high"
        return None

    def _query_or_respond(self, state: AgentState) -> AgentState:
        """
        Step 1: Generate an AI response that may include tool calls.
        """
        # Format messages for the LLM
        messages = []
        for msg in state.messages:
            if msg.role == "tool":
                # Format tool results as user messages with context
                messages.append({
                    "role": "user",
                    "content": f"[Tool Result - {msg.name}]:\n{msg.content}"
                })
            elif msg.role in ("user", "assistant"):
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Call LLM with tools
        response = self.llm.invoke(
            messages=messages,
            system=self.system_prompt,
            tools=TOOL_DEFINITIONS,
            temperature=0.0,
        )

        # Create assistant message
        assistant_msg = Message(
            role="assistant",
            content=response.get("content", ""),
            tool_calls=response.get("tool_calls") if response.get("tool_calls") else None,
        )
        state.messages.append(assistant_msg)

        return state

    def _execute_tools(self, state: AgentState) -> tuple[AgentState, List[Dict]]:
        """
        Step 2: Execute any tool calls from the previous step.
        """
        artifacts = []

        # Get the last assistant message with tool calls
        last_assistant = None
        for msg in reversed(state.messages):
            if msg.role == "assistant" and msg.tool_calls:
                last_assistant = msg
                break

        if not last_assistant or not last_assistant.tool_calls:
            return state, artifacts

        # Execute each tool
        for tool_call in last_assistant.tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})
            tool_id = tool_call.get("id", tool_name)

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            # Execute the tool
            result = self.tools.execute(tool_name, tool_args)
            state.tool_results.append(result)
            self._record_tool_grounding(state, tool_name, result)

            # Add tool result message
            tool_msg = Message(
                role="tool",
                content=result.content,
                tool_call_id=tool_id,
                name=tool_name,
            )
            state.messages.append(tool_msg)

            # Collect artifacts
            if result.artifacts:
                artifacts.extend(result.artifacts)

        return state, artifacts

    def _record_tool_grounding(self, state: AgentState, tool_name: str, result: ToolResult) -> None:
        metadata = result.metadata or {}
        artifacts = result.artifacts or []

        if tool_name == "web_search" or metadata.get("grounding_status") == "external":
            state.grounding_status = "external"
            state.answer_source = "web"
            state.confidence = "medium"
            return

        if metadata.get("direct_response"):
            state.direct_response = metadata.get("direct_response")
        if metadata.get("answer_source"):
            state.answer_source = metadata["answer_source"]
        if metadata.get("confidence"):
            state.confidence = metadata["confidence"]
        if metadata.get("grounding_status"):
            state.grounding_status = metadata["grounding_status"]

        is_internal_tool = tool_name in _INTERNAL_RETRIEVAL_TOOLS or tool_name != "web_search"
        if not is_internal_tool:
            return

        attempted = bool(metadata.get("retrieval_attempted")) or tool_name in _INTERNAL_RETRIEVAL_TOOLS
        if state.internal_retrieval_required or attempted:
            state.retrieval_attempted = True

        artifact_count = metadata.get("retrieval_artifact_count")
        if artifact_count is None:
            artifact_count = len(artifacts)
        state.retrieval_artifact_count += int(artifact_count or 0)

        max_score = metadata.get("max_score")
        if max_score is None:
            max_score = self._max_artifact_score(artifacts)
        if max_score is not None:
            try:
                max_score = float(max_score)
                state.max_score = max(max_score, state.max_score or max_score)
            except (TypeError, ValueError):
                pass

    def _generate(self, state: AgentState) -> AgentState:
        """
        Step 3: Generate final response using the tool results.
        """
        # Collect tool results from recent messages
        tool_contents = []
        for msg in reversed(state.messages):
            if msg.role == "tool":
                tool_contents.append(f"[{msg.name}]: {msg.content}")
            elif msg.role == "assistant":
                break  # Stop at the last assistant message

        tool_context = "\n\n".join(reversed(tool_contents))

        # Build generation prompt
        generation_system = f"""{self.system_prompt}

Retrieved Context from Internal Data:
{tool_context if tool_context else "[No relevant internal data found]"}

Instructions:
- If the retrieved context contains relevant information, use it to answer the question and cite your sources
- For file/document context, include the file name and page or section when available
- If this is an Atlas/internal question, do not use general knowledge to fill gaps beyond retrieved context
- If this is a general non-Atlas question, you may use general knowledge and label it as such
- Always be clear about whether you're using internal data or general knowledge
- If you genuinely cannot answer the question with either internal data or general knowledge, say so clearly"""

        # Get conversation messages (excluding tool messages)
        messages = []
        for msg in state.messages:
            if msg.role in ("user", "assistant") and not msg.tool_calls:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Generate response
        response = self.llm.invoke(
            messages=messages,
            system=generation_system,
            temperature=0.0,
        )

        # Add final assistant message
        state.messages.append(Message(
            role="assistant",
            content=response.get("content", "I apologize, but I couldn't generate a response."),
        ))

        return state

    def stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
    ):
        """
        Stream responses (placeholder for future implementation).

        Currently just yields the final response.
        """
        result = self.invoke(user_message, conversation_history)
        yield {
            "type": "response",
            "content": result["response"],
            "artifacts": result.get("artifacts", []),
            "answer_source": result.get("answer_source"),
            "grounding_status": result.get("grounding_status"),
            "confidence": result.get("confidence"),
            "warning": result.get("warning"),
        }


# Convenience function
def create_agent(
    llm_client: Optional[BedrockLLMClient] = None,
    embedding_client: Optional[BedrockEmbeddingClient] = None,
) -> AtlasAgent:
    """Create and return an Atlas agent instance."""
    return AtlasAgent(
        llm_client=llm_client,
        embedding_client=embedding_client,
    )
