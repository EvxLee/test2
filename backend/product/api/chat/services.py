"""
Service factory for Atlas chat and document search dependencies.

The factory is app-scoped so multiple Flask app instances in tests do not share
module-global agent state.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from flask import Flask, current_app

from .agent import AtlasAgent, create_agent
from .llm_client import (
    BedrockEmbeddingClient,
    BedrockLLMClient,
    get_embedding_client,
    get_llm_client,
)
from .tools import RAGTools

logger = logging.getLogger(__name__)

_EXTENSION_KEY = "atlas_chat"


@dataclass
class ChatServices:
    llm_client: Optional[BedrockLLMClient] = None
    embedding_client: Optional[BedrockEmbeddingClient] = None
    agent: Optional[AtlasAgent] = None

    def get_llm_client(self) -> BedrockLLMClient:
        if self.llm_client is None:
            self.llm_client = get_llm_client()
        return self.llm_client

    def get_embedding_client(self) -> Optional[BedrockEmbeddingClient]:
        if self.embedding_client is None:
            try:
                self.embedding_client = get_embedding_client()
            except Exception as e:
                logger.warning(f"Embedding client not available: {e}")
        return self.embedding_client

    def get_agent(self) -> AtlasAgent:
        if self.agent is None:
            try:
                self.agent = create_agent(
                    llm_client=self.get_llm_client(),
                    embedding_client=self.get_embedding_client(),
                )
            except Exception as e:
                logger.error(f"Failed to initialize agent: {e}")
                raise
        return self.agent

    def get_rag_tools(self) -> RAGTools:
        llm_client = None
        try:
            llm_client = self.get_llm_client()
        except Exception as e:
            logger.warning(f"LLM client not available: {e}")
        return RAGTools(
            embedding_client=self.get_embedding_client(),
            llm_client=llm_client,
        )


def get_chat_services() -> ChatServices:
    services = current_app.extensions.get(_EXTENSION_KEY)
    if services is None:
        services = ChatServices()
        current_app.extensions[_EXTENSION_KEY] = services
    return services


def reset_chat_services(app: Flask) -> None:
    app.extensions.pop(_EXTENSION_KEY, None)
