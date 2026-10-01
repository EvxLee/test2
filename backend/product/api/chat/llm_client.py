"""
LLM Client for AWS Bedrock integration.

This module provides a unified interface for interacting with Claude via AWS Bedrock.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class BedrockLLMClient:
    """Client for AWS Bedrock Claude models."""

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region_name: str = "us-west-1",
        bearer_token: Optional[str] = None,
    ):
        """
        Initialize the Bedrock client.

        Args:
            model_id: The Bedrock model ID to use
            region_name: AWS region
            bearer_token: Optional bearer token for authentication
        """
        self.model_id = model_id
        self.region_name = region_name

        # Set bearer token if provided
        if bearer_token:
            os.environ['AWS_BEARER_TOKEN_BEDROCK'] = bearer_token

        # Configure boto3 client
        config = Config(
            region_name=region_name,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region_name,
            config=config,
        )

    def invoke(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Invoke the LLM with messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            tools: Optional list of tool definitions
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Response dict with 'content', 'stop_reason', and optionally 'tool_calls'
        """
        # Format messages for Bedrock Converse API
        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle different content types
            if isinstance(content, str):
                formatted_content = [{"text": content}]
            elif isinstance(content, list):
                formatted_content = content
            else:
                formatted_content = [{"text": str(content)}]

            formatted_messages.append({
                "role": role,
                "content": formatted_content
            })

        # Build request
        request = {
            "modelId": self.model_id,
            "messages": formatted_messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            }
        }

        # Add system prompt if provided
        if system:
            request["system"] = [{"text": system}]

        # Add tools if provided
        if tools:
            request["toolConfig"] = {
                "tools": self._format_tools(tools)
            }

        try:
            response = self.client.converse(**request)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Bedrock invocation error: {e}")
            raise

    def _format_tools(self, tools: List[Dict]) -> List[Dict]:
        """Format tools for Bedrock API."""
        formatted = []
        for tool in tools:
            formatted.append({
                "toolSpec": {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "inputSchema": {
                        "json": tool.get("parameters", {})
                    }
                }
            })
        return formatted

    def _parse_response(self, response: Dict) -> Dict[str, Any]:
        """Parse Bedrock response into standard format."""
        output = response.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])

        result = {
            "stop_reason": response.get("stopReason", "end_turn"),
            "content": "",
            "tool_calls": [],
        }

        for block in content_blocks:
            if "text" in block:
                result["content"] += block["text"]
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                result["tool_calls"].append({
                    "id": tool_use.get("toolUseId"),
                    "name": tool_use.get("name"),
                    "arguments": tool_use.get("input", {}),
                })

        return result


class BedrockEmbeddingClient:
    """Client for AWS Bedrock embedding models (Amazon Titan)."""

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region_name: str = "us-east-1",
    ):
        """
        Initialize the embedding client.

        Args:
            model_id: The Bedrock embedding model ID
            region_name: AWS region
        """
        self.model_id = model_id
        self.region_name = region_name

        config = Config(
            region_name=region_name,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region_name,
            config=config,
        )

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "inputText": text,
            }),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body.get("embedding", [])

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        # Titan doesn't support batch embedding, so we iterate
        return [self.embed(text) for text in texts]


def get_llm_client() -> BedrockLLMClient:
    """Get configured LLM client from environment."""
    return BedrockLLMClient(
        model_id=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        region_name=os.getenv("AWS_REGION", "us-west-1"),
        bearer_token=os.getenv("AWS_BEARER_TOKEN_BEDROCK"),
    )


def get_embedding_client() -> BedrockEmbeddingClient:
    """Get configured embedding client from environment."""
    return BedrockEmbeddingClient(
        model_id=os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
        region_name=os.getenv("BEDROCK_EMBEDDING_REGION", "us-east-1"),
    )
