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

from .providers import LLMProvider, OpenAIProvider, VertexGeminiProvider


class LLMClient:
    """
    Main LLM client that wraps a provider.

    This class provides a simple interface for agents to call LLMs
    without knowing which provider is being used.
    """

    def __init__(self, provider: str | None = None) -> None:
        """
        Initialize LLM client from environment variables.

        Args:
            provider: Override provider ("vertexai" or "openai"). If None, uses LLM_PROVIDER env var.

        Raises:
            ValueError: If required environment variables are not set.
        """
        provider = provider or os.environ.get("LLM_PROVIDER", "vertex").lower()

        if provider == "openai":
            self.provider = self._init_openai()
        elif provider == "vertexai":
            self.provider = self._init_vertex()
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER: {provider}. Must be 'vertexai' or 'openai'."
            )

    def _init_vertex(self) -> LLMProvider:
        """Initialize Vertex AI Gemini provider."""
        project_id = os.environ.get("VERTEX_PROJECT_ID")
        if not project_id:
            raise ValueError(
                "VERTEX_PROJECT_ID environment variable must be set for Vertex AI. "
                "Add it to your .env file or use LLM_PROVIDER=openai with OPENAI_API_KEY."
            )

        location = os.environ.get("VERTEX_LOCATION", "us-central1")
        model = os.environ.get("VERTEX_MODEL", "gemini-2.5-pro")
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        max_tokens = os.environ.get("LLM_MAX_TOKENS")

        return VertexGeminiProvider(
            project_id=project_id,
            location=location,
            model=model,
            temperature=temperature,
            max_tokens=int(max_tokens) if max_tokens else None,
        )

    def _init_openai(self) -> LLMProvider:
        """Initialize OpenAI provider."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable must be set for OpenAI. "
                "Add it to your .env file."
            )

        model = os.environ.get("OPENAI_MODEL", "gpt-5.2")
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        max_tokens = os.environ.get("LLM_MAX_TOKENS")
        base_url = os.environ.get("OPENAI_BASE_URL")

        return OpenAIProvider(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=int(max_tokens) if max_tokens else None,
            base_url=base_url,
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
        **kwargs: Any,
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
        ValueError: If required environment variables are not set
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
