"""
LLM client singleton for agent use.

Supports two-tier model system:
- Low tier (default): Cheaper/faster model for most tasks
- High tier: More capable model for complex tasks

Usage:
    from aging_bd_agentic_system.llm import get_llm, init_llm

    # Initialize with config (call once at startup)
    init_llm(config.llm)

    # Get the singleton client (uses low tier by default)
    llm = get_llm()
    response = llm.invoke("What are biological processes?")

    # Use high tier for complex tasks
    with llm.high_tier():
        result = llm.invoke(complex_prompt)

    # Or explicit set/reset
    llm.set_tier("high")
    result = llm.invoke(complex_prompt)
    llm.set_tier("low")
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

from aging_bd_agentic_system.config import LLMConfig

from .providers import LLMProvider, OpenAIProvider, VertexGeminiProvider


class LLMClient:
    """
    Main LLM client with two-tier model support.

    Holds two providers (low/high tier) and allows switching between them.
    Low tier is used by default for most tasks.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        """
        Initialize LLM client from config.

        Args:
            config: LLMConfig with provider, model, model_low, model_high, etc.
                    If None, uses defaults from LLMConfig().

        Raises:
            ValueError: If required config variables are not set.
        """
        self.config = config or LLMConfig()
        self._current_tier: str = "low"

        # Lazy-init providers on first access
        self._providers: dict[str, LLMProvider | None] = {"low": None, "high": None}

    def _get_or_init_provider(self, tier: str) -> LLMProvider:
        """Get provider for tier, initializing lazily if needed."""
        if self._providers[tier] is None:
            model = self.config.get_model_low() if tier == "low" else self.config.get_model_high()
            self._providers[tier] = self._init_provider(model)
        return self._providers[tier]

    def _init_provider(self, model: str) -> LLMProvider:
        """Initialize a provider with specific model."""
        if self.config.provider == "openai":
            return self._init_openai(model)
        elif self.config.provider == "vertex":
            return self._init_vertex(model)
        else:
            raise ValueError(
                f"Unknown LLM provider: {self.config.provider}. Must be 'vertex' or 'openai'."
            )

    def _init_vertex(self, model: str) -> LLMProvider:
        """Initialize Vertex AI Gemini provider with specific model."""
        project_id = os.environ.get("VERTEX_PROJECT_ID")
        if not project_id:
            raise ValueError(
                "VERTEX_PROJECT_ID environment variable must be set for Vertex AI. "
                "Add it to your .env file."
            )

        return VertexGeminiProvider(
            project_id=project_id,
            location=self.config.vertex_location,
            model=model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    def _init_openai(self, model: str) -> LLMProvider:
        """Initialize OpenAI provider with specific model."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable must be set for OpenAI. "
                "Add it to your .env file."
            )

        return OpenAIProvider(
            api_key=api_key,
            model=model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            base_url=self.config.openai_base_url,
        )

    @property
    def provider(self) -> LLMProvider:
        """Get current active provider based on tier."""
        return self._get_or_init_provider(self._current_tier)

    def set_tier(self, tier: str) -> None:
        """
        Switch between 'low' and 'high' model tiers.

        Args:
            tier: 'low' for cheap/fast model, 'high' for capable model.

        Raises:
            ValueError: If tier is not 'low' or 'high'.
        """
        if tier not in ("low", "high"):
            raise ValueError(f"Invalid tier: {tier}. Must be 'low' or 'high'.")
        self._current_tier = tier

    @contextmanager
    def high_tier(self) -> Generator[None, None, None]:
        """
        Context manager for temporary high-tier usage.

        Automatically resets to previous tier on exit.

        Usage:
            with llm.high_tier():
                result = llm.invoke(complex_prompt)
        """
        prev = self._current_tier
        self.set_tier("high")
        try:
            yield
        finally:
            self.set_tier(prev)

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
