"""Custom exceptions for the cycles module."""


class LLMGenerationError(Exception):
    """Raised when an LLM generation call fails or returns empty content."""
