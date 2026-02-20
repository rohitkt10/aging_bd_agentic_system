"""
Context management for long-running research workflows.

Implements ADK-style two-tier context management:
- Working memory (in-memory) → summarized when large
- Persistent log (disk) → everything logged, never deleted
"""

from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using character-based heuristic.

    Rough heuristic: ~4 characters per token for English text.
    This is more accurate than word count for technical content.
    """
    return len(text) // 4


def _summarize_research_scratchpad(scratchpad: str, max_words: int = 300) -> str:
    """
    Summarize research scratchpad while preserving critical information.

    Preserves:
    - High-confidence genes found
    - Research gaps/questions
    - Recent high-value leads
    - Current iteration state

    Args:
        scratchpad: JSON string containing research data
        max_words: Maximum words for summary

    Returns:
        Summarized text
    """
    try:
        research_data = json.loads(scratchpad)
    except json.JSONDecodeError:
        # Not valid JSON, just truncate
        words = scratchpad.split()
        if len(words) <= max_words:
            return scratchpad
        return " ".join(words[:max_words]) + " ..."

    # Extract critical information
    summary_parts = []

    # Candidates found
    candidates = research_data.get("candidates", [])
    if candidates:
        candidate_symbols = [c.get("symbol", "") for c in candidates[:10]]
        summary_parts.append(f"Candidates: {', '.join(candidate_symbols)}")

    # Recent findings (last 10)
    findings = research_data.get("findings", [])
    if findings:
        recent_findings = findings[-10:] if len(findings) > 10 else findings
        for finding in recent_findings[:5]:  # Top 5 recent
            gene = finding.get("gene", "")
            source = finding.get("source", "")
            finding_text = finding.get("finding", "")[:100]
            if gene:
                summary_parts.append(f"{gene} ({source}): {finding_text}")
            else:
                summary_parts.append(f"{source}: {finding_text}")

    # Build summary
    summary = ". ".join(summary_parts)

    # Truncate if needed
    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]) + " ..."

    return summary


def summarize_if_needed(
    state: dict[str, Any], max_tokens: int = 50000
) -> dict[str, Any]:
    """
    Summarize context fields when token budget is exceeded.

    Returns an empty dict if no summarization is needed. Otherwise returns updates
    that include context_summary and cleared large fields.

    Preserves critical information:
    - High-confidence genes found
    - Research gaps/questions
    - Recent high-value leads
    - Current iteration state
    """
    tool_history = state.get("tool_call_history", [])
    reasoning = state.get("reasoning_trace", [])
    scratchpad = state.get("research_scratchpad", "")

    # Calculate token count
    blob = "\n".join([
        " ".join([str(item) for item in tool_history]),
        " ".join([str(item) for item in reasoning]),
        scratchpad,
    ])

    token_count = estimate_tokens(blob)

    # Check if we need to summarize
    if token_count <= max_tokens:
        return {}

    # Create intelligent summary
    summary_parts = []

    # Add current iteration info if available
    current_iteration = state.get("phase2_research_iteration", 0)
    if current_iteration > 0:
        summary_parts.append(f"Research iteration: {current_iteration}")

    # Summarize scratchpad (preserves critical info)
    if scratchpad:
        scratchpad_summary = _summarize_research_scratchpad(scratchpad)
        summary_parts.append(f"Research: {scratchpad_summary}")

    # Build final summary
    if summary_parts:
        summary = ". ".join(summary_parts)
    else:
        summary = "Research in progress"

    # Return state updates
    # Note: We preserve tool_call_history and reasoning_trace in their original form
    # They will be written to disk via audit_logger, but cleared from working memory
    return {
        "context_summary": summary,
        "tool_call_history": [],  # Clear from working memory
        "reasoning_trace": [],  # Clear from working memory
        "research_scratchpad": "",  # Clear from working memory
        "token_count": token_count,
    }
