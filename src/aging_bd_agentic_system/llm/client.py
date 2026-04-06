"""
LLM client singleton for agent use.

Supports two independent axes per call:
- model tier: "low" (cheap/fast) or "high" (capable)
- temp tier: "low", "mid", or "high"

Both axes are set together via the call() context manager:

    with llm.call(model="high", temp="low"):
        result = llm.invoke_structured(scoring_prompt, schema=schema)

Outside a context manager, defaults to model="low", temp="mid".
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

from aging_bd_agentic_system.config import LLMConfig

from .providers import LLMProvider, OpenAIProvider, VertexGeminiProvider

_DEFAULT_MODEL_TIER = "low"
_DEFAULT_TEMP_TIER = "mid"


class LLMClient:
    """
    LLM client with independent model-tier and temp-tier axes.

    Use the call() context manager to set both axes for each LLM call.
    Resets to defaults (model=low, temp=mid) on context exit.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._model_tier: str = _DEFAULT_MODEL_TIER
        self._temp_tier: str = _DEFAULT_TEMP_TIER
        self._providers: dict[str, LLMProvider | None] = {"low": None, "high": None}

    # ------------------------------------------------------------------
    # Context manager — primary interface
    # ------------------------------------------------------------------

    @contextmanager
    def call(self, *, model: str = _DEFAULT_MODEL_TIER, temp: str = _DEFAULT_TEMP_TIER) -> Generator[None, None, None]:
        """
        Context manager that sets model tier and temp tier for the enclosed calls.
        Resets both axes to their previous values on exit.

        Args:
            model: "low" or "high"
            temp:  "low", "mid", or "high"

        Usage:
            with llm.call(model="high", temp="low"):
                result = llm.invoke_structured(scoring_prompt, schema=schema)
        """
        if model not in ("low", "high"):
            raise ValueError(f"Invalid model tier: {model!r}. Must be 'low' or 'high'.")
        if temp not in ("low", "mid", "high"):
            raise ValueError(f"Invalid temp tier: {temp!r}. Must be 'low', 'mid', or 'high'.")

        prev_model = self._model_tier
        prev_temp = self._temp_tier
        self._model_tier = model
        self._temp_tier = temp
        try:
            yield
        finally:
            self._model_tier = prev_model
            self._temp_tier = prev_temp

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_init_provider(self, tier: str) -> LLMProvider:
        if self._providers[tier] is None:
            model = self.config.get_model_low() if tier == "low" else self.config.get_model_high()
            self._providers[tier] = self._init_provider(model)
        return self._providers[tier]

    def _init_provider(self, model: str) -> LLMProvider:
        if self.config.provider == "openai":
            return self._init_openai(model)
        elif self.config.provider == "vertex":
            return self._init_vertex(model)
        else:
            raise ValueError(
                f"Unknown LLM provider: {self.config.provider}. Must be 'vertex' or 'openai'."
            )

    def _init_vertex(self, model: str) -> LLMProvider:
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
    def _current_provider(self) -> LLMProvider:
        return self._get_or_init_provider(self._model_tier)

    @property
    def _current_temperature(self) -> float:
        if self._temp_tier == "low":
            return self.config.get_temperature_low()
        elif self._temp_tier == "mid":
            return self.config.get_temperature_mid()
        else:
            return self.config.get_temperature_high()

    # ------------------------------------------------------------------
    # Public invoke methods
    # ------------------------------------------------------------------

    def invoke(
        self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        return self._current_provider.invoke(
            prompt,
            system_prompt=system_prompt,
            temperature=self._current_temperature,
            **kwargs,
        )

    def invoke_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._current_provider.invoke_structured(
            prompt,
            schema,
            system_prompt=system_prompt,
            temperature=self._current_temperature,
            **kwargs,
        )


# Singleton instance
_global_client: LLMClient | None = None


def init_llm(config: LLMConfig) -> LLMClient:
    """Initialize the global LLM client. Call once at startup."""
    global _global_client
    _global_client = LLMClient(config)
    return _global_client


def get_llm() -> LLMClient:
    """Get the global LLM client instance."""
    global _global_client
    if _global_client is None:
        _global_client = LLMClient()
    return _global_client


def reset_llm() -> None:
    """Reset the global LLM client. Useful for testing."""
    global _global_client
    _global_client = None
