"""
LLM integration module.

Provides LLM client and provider abstractions for the deep research system.
Supports multiple providers: Vertex AI Gemini and OpenAI.

Two-tier model system:
- Low tier (default): Cheaper/faster model for most tasks
- High tier: More capable model for complex tasks

Usage:
    llm = get_llm()
    response = llm.invoke(prompt)  # Uses low tier by default

    # Switch to high tier temporarily
    with llm.high_tier():
        result = llm.invoke(complex_prompt)
"""

from .client import LLMClient, get_llm, init_llm, reset_llm
from .providers import LLMProvider, OpenAIProvider, VertexGeminiProvider


def set_llm_tier(tier: str) -> None:
    """
    Switch global LLM tier.

    Args:
        tier: 'low' for cheap/fast model, 'high' for capable model.
    """
    get_llm().set_tier(tier)


__all__ = [
    "LLMClient",
    "get_llm",
    "init_llm",
    "reset_llm",
    "set_llm_tier",
    "LLMProvider",
    "VertexGeminiProvider",
    "OpenAIProvider",
]
