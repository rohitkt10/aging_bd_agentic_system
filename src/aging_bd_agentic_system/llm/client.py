"""
LLM client singleton for agent use.

Usage:
    from aging_bd_agentic_system.llm.client import get_llm, init_llm

    # Initialize with config (call once at startup)
    init_llm(config.llm)

    # Get the singleton client
    llm = get_llm()
    response = llm.invoke("What are biological processes?")
"""

from __future__ import annotations

import os
from typing import Any

from aging_bd_agentic_system.config import LLMConfig

from .providers import LLMProvider, OpenAIProvider, VertexGeminiProvider


class LLMClient:
    """
    Main LLM client that wraps a provider.

    This class provides a simple interface for agents to call LLMs
    without knowing which provider is being used.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        """
        Initialize LLM client from config.

        Args:
            config: LLMConfig with provider, model, temperature, etc.
                    If None, uses defaults from LLMConfig().

        Raises:
            ValueError: If required config variables are not set.
        """
        self.config = config or LLMConfig()

        if self.config.provider == "openai":
            self.provider = self._init_openai()
        elif self.config.provider == "vertex":
            self.provider = self._init_vertex()
        else:
            raise ValueError(
                f"Unknown LLM provider: {self.config.provider}. Must be 'vertex' or 'openai'."
            )

    def _init_vertex(self) -> LLMProvider:
        """Initialize Vertex AI Gemini provider."""
        project_id = os.environ.get("VERTEX_PROJECT_ID")
        if not project_id:
            raise ValueError(
                "VERTEX_PROJECT_ID environment variable must be set for Vertex AI. "
                "Add it to your .env file."
            )

        return VertexGeminiProvider(
            project_id=project_id,
            location=self.config.vertex_location,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    def _init_openai(self) -> LLMProvider:
        """Initialize OpenAI provider."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable must be set for OpenAI. "
                "Add it to your .env file."
            )

        return OpenAIProvider(
            api_key=api_key,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            base_url=self.config.openai_base_url,
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


def init_llm(config: LLMConfig) -> LLMClient:
    """
    Initialize the global LLM client with config.

    Must be called once at startup before get_llm() is used.

    Args:
        config: LLMConfig with provider, model, temperature, etc.

    Returns:
        The initialized LLMClient
    """
    global _global_client
    _global_client = LLMClient(config)
    return _global_client


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

    Useful for testing or when config changes.
    """
    global _global_client
    _global_client = None
