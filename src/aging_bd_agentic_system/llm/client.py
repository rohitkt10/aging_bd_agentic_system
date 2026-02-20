"""
LLM client singleton for agent use.

Usage:
    from aging_bd_agentic_system.llm.client import get_llm

    llm = get_llm()
    response = llm.invoke("What are biological processes?")
"""

from __future__ import annotations

import os
from typing import Any

from .providers import VertexGeminiProvider


class LLMClient:
    """
    Main LLM client that wraps a provider.

    This class provides a simple interface for agents to call LLMs
    without knowing which provider is being used.
    """

    def __init__(self) -> None:
        """Initialize LLM client from environment variables."""
        project_id = os.environ.get("VERTEX_PROJECT_ID")
        if not project_id:
            raise ValueError(
                "VERTEX_PROJECT_ID environment variable must be set. "
                "Add it to your .env file."
            )

        location = os.environ.get("VERTEX_LOCATION", "us-central1")
        model = os.environ.get("VERTEX_MODEL", "gemini-2.0-flash-exp-01-21")
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        max_tokens = os.environ.get("LLM_MAX_TOKENS")

        self.provider = VertexGeminiProvider(
            project_id=project_id,
            location=location,
            model=model,
            temperature=temperature,
            max_tokens=int(max_tokens) if max_tokens else None,
        )

    def invoke(
        self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """
        Invoke the LLM with a text prompt.

        Args:
            prompt: The user prompt to send
            system_prompt: Optional system prompt with instructions
            **kwargs: Override parameters (temperature, max_tokens, etc.)

        Returns:
            LLM response text
        """
        return self.provider.invoke(prompt, system_prompt=system_prompt, **kwargs)

    def invoke_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
        **kwargs: Any
    ) -> dict[str, Any]:
        """
        Invoke the LLM with structured output.

        Args:
            prompt: The user prompt to send
            schema: Expected output schema (dict with type hints)
            system_prompt: Optional system prompt with instructions
            **kwargs: Override parameters

        Returns:
            LLM response as dict matching schema
        """
        return self.provider.invoke_structured(
            prompt, schema, system_prompt=system_prompt, **kwargs
        )


# Singleton instance
_global_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """
    Get the global LLM client instance.

    Returns:
        The singleton LLMClient

    Raises:
        ValueError: If VERTEX_PROJECT_ID is not set
    """
    global _global_client
    if _global_client is None:
        _global_client = LLMClient()
    return _global_client


def reset_llm() -> None:
    """
    Reset the global LLM client.

    Useful for testing or when environment variables change.
    """
    global _global_client
    _global_client = None
