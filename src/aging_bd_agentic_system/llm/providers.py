"""
LLM provider abstraction layer.

Allows swapping between different LLM providers (Vertex AI, OpenAI, etc.)
without changing agent code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """
        Invoke the LLM with a text prompt.

        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Additional provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            The LLM response as a string
        """
        pass

    @abstractmethod
    def invoke_structured(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """
        Invoke the LLM with structured output expectations.

        Args:
            prompt: The prompt to send to the LLM
            schema: The expected output schema (for structured output)
            **kwargs: Additional provider-specific parameters

        Returns:
            The LLM response as a dict matching the schema
        """
        pass


class VertexGeminiProvider(LLMProvider):
    """Vertex AI Gemini implementation of LLMProvider."""

    def __init__(
        self,
        project_id: str,
        location: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        """
        Initialize Vertex AI Gemini provider.

        Args:
            project_id: Google Cloud project ID
            location: Vertex AI region (e.g., "us-central1")
            model: Model name (e.g., "gemini-2.0-flash-exp-01-21")
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response (None for default)
        """
        from langchain_google_vertexai import ChatVertexAI

        self.llm = ChatVertexAI(
            project=project_id,
            location=location,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def invoke(
        self,w
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs: Any
    ) -> str:
        """
        Invoke LLM with text prompt, return response text.

        Args:
            prompt: The user prompt/task
            system_prompt: Optional system prompt with instructions
            **kwargs: Additional provider-specific parameters
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        if system_prompt:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
        else:
            messages = [HumanMessage(content=prompt)]

        response = self.llm.invoke(messages, **kwargs)
        return response.content

    def invoke_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
        **kwargs: Any
    ) -> dict[str, Any]:
        """
        Invoke LLM with structured output schema.

        Args:
            prompt: The user prompt/task
            schema: Expected output schema
            system_prompt: Optional system prompt with instructions
            **kwargs: Additional provider-specific parameters

        Note: Uses LangChain's with_structured_output() which works with
        models that support tool/function calling (Gemini does).
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        # Wrap the LLM with structured output
        llm_structured = self.llm.with_structured_output(schema)

        if system_prompt:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
        else:
            messages = [HumanMessage(content=prompt)]

        response = llm_structured.invoke(messages, **kwargs)
        return response
