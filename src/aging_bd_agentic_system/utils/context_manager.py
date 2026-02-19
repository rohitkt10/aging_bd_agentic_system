from __future__ import annotations

from typing import Any


def estimate_tokens(text: str) -> int:
    """Estimate token count using whitespace-separated word count."""
    return len(text.split())


def _summarize_text(text: str, max_words: int = 200) -> str:
    """Create a deterministic summary by truncating to max_words words."""
    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + " ..."


def summarize_if_needed(
    state: dict[str, Any], max_tokens: int = 50000
) -> dict[str, Any]:
    """Summarize context fields when token budget is exceeded.

    Returns an empty dict if no summarization is needed. Otherwise returns updates
    that include context_summary and clear large fields.
    """
    tool_history = state.get("tool_call_history", [])
    reasoning = state.get("reasoning_trace", [])
    scratchpad = state.get("research_scratchpad", "")

    blob = "\n".join([
        " ".join([str(item) for item in tool_history]),
        " ".join([str(item) for item in reasoning]),
        scratchpad,
    ])

    token_count = estimate_tokens(blob)
    if token_count <= max_tokens:
        return {}

    summary = _summarize_text(blob)
    return {
        "context_summary": summary,
        "tool_call_history": [],
        "reasoning_trace": [],
        "research_scratchpad": "",
        "token_count": token_count,
    }
