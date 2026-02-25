"""
Context management for long-running research workflows.

Implements ADK-style two-tier context management:
- Working memory (in-memory) → summarized when large
- Persistent log (disk) → everything logged, never deleted
"""

from __future__ import annotations

import json
import os
from typing import Any

from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.prompts.phase2_prompts import (
    PHASE2_ACTIONABILITY_SUMMARY_PROMPT,
    PHASE2_SCORING_SUMMARY_PROMPT,
)

# Schema constants for structured output validation
ACTIONABILITY_SUMMARY_SCHEMA = {
    "title": "actionability_summary",
    "type": "object",
    "properties": {
        "top_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "source": {"type": "string"},
                    "confidence": {"type": "integer"},
                    "key_evidence": {"type": "string"},
                },
                "required": ["symbol", "source", "confidence", "key_evidence"],
            },
        },
        "high_value_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gene": {"type": "string"},
                    "source": {"type": "string"},
                    "finding": {"type": "string"},
                    "value_score": {"type": "integer"},
                },
                "required": ["gene", "source", "finding", "value_score"],
            },
        },
        "research_gaps": {"type": "array", "items": {"type": "string"}},
        "covered_topics": {"type": "array", "items": {"type": "string"}},
        "iteration_state": {
            "type": "object",
            "properties": {
                "current_iteration": {"type": "integer"},
                "total_candidates": {"type": "integer"},
                "total_findings": {"type": "integer"},
            },
            "required": ["current_iteration", "total_candidates", "total_findings"],
        },
    },
    "required": [
        "top_candidates",
        "high_value_findings",
        "research_gaps",
        "covered_topics",
        "iteration_state",
    ],
}


SCORING_SUMMARY_SCHEMA = {
    "title": "scoring_summary",
    "type": "object",
    "properties": {
        "candidate_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gene_symbol": {"type": "string"},
                    "supporting_evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "finding": {"type": "string"},
                                "strength": {"type": "string"},
                                "pmid_or_ref": {"type": "string"},
                            },
                            "required": [
                                "source",
                                "finding",
                                "strength",
                                "pmid_or_ref",
                            ],
                        },
                    },
                    "contradicting_evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "finding": {"type": "string"},
                                "strength": {"type": "string"},
                                "pmid_or_ref": {"type": "string"},
                            },
                            "required": [
                                "source",
                                "finding",
                                "strength",
                                "pmid_or_ref",
                            ],
                        },
                    },
                    "cross_source_corroboration": {"type": "boolean"},
                    "evidence_strength_score": {"type": "integer"},
                },
                "required": [
                    "gene_symbol",
                    "supporting_evidence",
                    "contradicting_evidence",
                    "cross_source_corroboration",
                    "evidence_strength_score",
                ],
            },
        },
        "evidence_summary": {"type": "string"},
        "total_genes_with_evidence": {"type": "integer"},
        "total_sources_queried": {"type": "integer"},
    },
    "required": [
        "candidate_evidence",
        "evidence_summary",
        "total_genes_with_evidence",
        "total_sources_queried",
    ],
}


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using character-based heuristic.

    Rough heuristic: ~4 characters per token for English text.
    This is more accurate than word count for technical content.
    """
    return len(text) // 4


def _fallback_actionability_summary(research_data: dict, state: dict) -> dict:
    """
    Rule-based fallback for actionability summarization when LLM fails.

    Simple extraction logic:
    - Top candidates: Seeds from GenAge/OpenGenes first, then any with multiple mentions
    - High-value findings: Recent findings from GenAge/OpenGenes sources
    - Research gaps: None (can't infer from data alone)
    - Covered topics: Extracted from finding keywords
    """
    candidates = research_data.get("initial_database_genes", [])
    findings = research_data.get("research_findings", [])

    # Count gene mentions in findings
    gene_mentions: dict[str, int] = {}
    for f in findings:
        gene = f.get("gene")
        if gene:
            gene_mentions[gene] = gene_mentions.get(gene, 0) + 1

    # Top candidates: prioritize seeds, then by mention count
    top_candidates = []
    for c in candidates[:15]:  # First 15 candidates
        symbol = c.get("symbol", "")
        source = c.get("source", "unknown")
        mention_count = gene_mentions.get(symbol, 0)

        # Confidence: seeds get 7, plus 1 for every 2 mentions
        confidence = 7 if source in ["genage", "opengenes"] else 5
        confidence += min(mention_count // 2, 3)

        top_candidates.append(
            {
                "symbol": symbol,
                "source": source,
                "confidence": min(confidence, 10),
                "key_evidence": f"Seed from {source}"
                + (f", mentioned in {mention_count} findings" if mention_count else ""),
            }
        )

    # High-value findings: recent ones from quality sources
    high_value_findings = []
    for f in findings[-30:]:  # Last 30 findings
        source = f.get("source", "")
        gene = f.get("gene", "Unknown")
        finding_text = f.get("finding", "")

        # Score: GenAge/OpenGenes = 8, PubMed = 7, corpus = 6
        value_score = {"genage": 8, "opengenes": 8, "pubmed": 7}.get(source.lower(), 6)

        high_value_findings.append(
            {
                "gene": gene,
                "source": source,
                "finding": finding_text[:200],
                "value_score": value_score,
            }
        )

    return {
        "top_candidates": top_candidates,
        "high_value_findings": high_value_findings[:30],
        "research_gaps": [],  # Can't infer without LLM
        "covered_topics": [],  # Can't infer without LLM
        "iteration_state": {
            "current_iteration": state.get("phase2_research_iteration", 0),
            "total_candidates": len(candidates),
            "total_findings": len(findings),
        },
    }


def _fallback_scoring_summary(research_data: dict) -> dict:
    """
    Rule-based fallback for scoring summarization when LLM fails.

    Simple grouping by gene symbol:
    - Aggregate all findings per gene
    - Count sources for corroboration
    - Simple strength scoring
    """
    findings = research_data.get("research_findings", [])
    candidates = research_data.get("initial_database_genes", [])

    # Group findings by gene
    gene_evidence: dict[str, dict] = {}

    for c in candidates:
        symbol = c.get("symbol", "")
        if symbol:
            gene_evidence[symbol] = {
                "supporting": [],
                "contradicting": [],
                "sources": set(),
            }

    for f in findings:
        gene = f.get("gene")
        if not gene:
            continue

        if gene not in gene_evidence:
            gene_evidence[gene] = {
                "supporting": [],
                "contradicting": [],
                "sources": set(),
            }

        source = f.get("source", "unknown")
        finding_text = f.get("finding", "")

        # Naive strength classification based on source
        strength_map = {"genage": "strong", "opengenes": "strong", "pubmed": "moderate"}
        strength = strength_map.get(source.lower(), "weak")

        gene_evidence[gene]["supporting"].append(
            {
                "source": source,
                "finding": finding_text[:300],
                "strength": strength,
                "pmid_or_ref": source,
            }
        )
        gene_evidence[gene]["sources"].add(source)

    # Build candidate_evidence array
    candidate_evidence = []
    for symbol, evidence in gene_evidence.items():
        sources_list = list(evidence["sources"])
        candidate_evidence.append(
            {
                "gene_symbol": symbol,
                "supporting_evidence": evidence["supporting"],
                "contradicting_evidence": evidence["contradicting"],
                "cross_source_corroboration": len(sources_list) >= 2,
                "evidence_strength_score": min(5 + len(evidence["supporting"]) // 3, 9),
            }
        )

    return {
        "candidate_evidence": candidate_evidence,
        "evidence_summary": f"Aggregated evidence for {len(candidate_evidence)} genes.",
        "total_genes_with_evidence": len(candidate_evidence),
        "total_sources_queried": 4,
    }


def summarize_for_actionability(research_data: dict, state: dict) -> dict:
    """
    Create actionability-focused summary for mid-loop research decisions.

    This function READS from research_data and returns a structured summary
    to help the LLM decide what to research next.

    Args:
        research_data: Complete research data (candidates, findings)
        state: Current workflow state (for iteration info)

    Returns:
        Structured actionability summary with top candidates, high-value findings, gaps
    """
    # Check if LLM summarization is disabled
    use_llm_summarization = (
        os.environ.get("USE_LLM_SUMMARIZATION", "true").lower() == "true"
    )

    if not use_llm_summarization:
        return _fallback_actionability_summary(research_data, state)

    llm = get_llm()

    # Build user prompt with research data
    user_prompt = PHASE2_ACTIONABILITY_SUMMARY_PROMPT.format(
        research_data_json=json.dumps(research_data, indent=2, default=str)
    )

    try:
        summary = llm.invoke_structured(
            user_prompt,
            schema=ACTIONABILITY_SUMMARY_SCHEMA,
            system_prompt="You are a research context analyzer.",
        )
        return summary
    except Exception:
        # Fallback to rule-based
        return _fallback_actionability_summary(research_data, state)


def summarize_for_scoring(research_data: dict, biological_process: str) -> dict:
    """
    Create comprehensive evidence summary for final gene scoring.

    This function READS from research_data and aggregates ALL evidence
    for comprehensive gene ranking. No truncation.

    Args:
        research_data: Complete research data (candidates, findings)
        biological_process: Name of biological process for context

    Returns:
        Structured evidence summary with all supporting/contradicting evidence
    """
    # Check if LLM summarization is disabled
    use_llm_summarization = (
        os.environ.get("USE_LLM_SUMMARIZATION", "true").lower() == "true"
    )

    if not use_llm_summarization:
        return _fallback_scoring_summary(research_data)

    llm = get_llm()

    # Build user prompt with research data
    user_prompt = PHASE2_SCORING_SUMMARY_PROMPT.format(
        biological_process=biological_process,
        research_data_json=json.dumps(research_data, indent=2, default=str),
    )

    try:
        summary = llm.invoke_structured(
            user_prompt,
            schema=SCORING_SUMMARY_SCHEMA,
            system_prompt="You are an evidence synthesis specialist.",
        )
        return summary
    except Exception:
        # Fallback to rule-based
        return _fallback_scoring_summary(research_data)


def summarize_if_needed(
    state: dict[str, Any], max_tokens: int = 50000
) -> dict[str, Any]:
    """
    Summarize context fields when token budget is exceeded.

    Returns an empty dict if no summarization is needed. Otherwise returns updates
    that include context_summary (structured JSON) and cleared large fields.

    Uses LLM-based actionability summarization for intelligent context reduction.
    Falls back to rule-based summarization if LLM fails or is disabled.
    """
    tool_history = state.get("tool_call_history", [])
    reasoning = state.get("reasoning_trace", [])
    scratchpad = state.get("research_scratchpad", "")

    # Calculate token count
    blob = "\n".join(
        [
            " ".join([str(item) for item in tool_history]),
            " ".join([str(item) for item in reasoning]),
            scratchpad,
        ]
    )

    token_count = estimate_tokens(blob)

    # Check if we need to summarize
    if token_count <= max_tokens:
        return {}

    # Parse research data from scratchpad
    try:
        research_data = (
            json.loads(scratchpad)
            if scratchpad
            else {"initial_database_genes": [], "research_findings": []}
        )
    except json.JSONDecodeError:
        research_data = {"initial_database_genes": [], "research_findings": []}

    # Use LLM-based actionability summarization
    summary_data = summarize_for_actionability(research_data, state)

    # Return state updates with structured JSON summary
    return {
        "context_summary": json.dumps(summary_data, indent=2),
        "tool_call_history": [],  # Clear from working memory
        "reasoning_trace": [],  # Clear from working memory
        "research_scratchpad": scratchpad,  # KEEP - never clear the source data
        "token_count": token_count,
    }
