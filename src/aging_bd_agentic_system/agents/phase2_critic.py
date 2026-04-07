"""
Phase 2 Critic Agent: Manuscript Review for Gene Lists

This module implements the critic agent that reviews gene lists
following a manuscript review paradigm.
"""

from __future__ import annotations

import json
from typing import Any
from pdb import set_trace
from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.prompts.phase2_critic_prompts import (
    CRITIC_SYSTEM_PROMPT,
    CRITIC_USER_PROMPT_TEMPLATE,
)
from aging_bd_agentic_system.agents.phase2_helpers import get_all_biological_processes


def phase2_critic(state: dict[str, Any]) -> dict[str, Any]:
    """
    Review the current draft and provide feedback.

    This function acts as a manuscript reviewer, evaluating the quality
    of the gene list and providing actionable recommendations.

    Args:
        state: Current workflow state containing scored_genes, gene_evidence,
               state_of_knowledge, and context.

    Returns:
        Dict with "critic_review" key containing the review output.
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name", "")
    cfg = state.get("config", {})
    p2 = cfg.get("phase2", {})
    min_genes = p2.get("min_genes", 30)
    max_genes = p2.get("max_genes", 50)
    all_biological_processes = get_all_biological_processes(cfg.get("output_dir"), hallmark)

    # Get scored genes for this BP
    genes_found = state.get("genes_found", [])

    # Get gene_evidence and state_of_knowledge
    gene_evidence = state.get("gene_evidence", {})
    try:
        state_of_knowledge = json.loads(state.get("state_of_knowledge", "{}"))
    except json.JSONDecodeError:
        state_of_knowledge = {"candidate_genes": [], "citations": [], "summary": ""}

    print(f"\n{'='*60}")
    print(f"CRITIC: Reviewing draft for {bp_name}")
    print(f"{'='*60}")
    print(f"  Genes to review: {len(genes_found)}")

    # Format user prompt with draft data
    user_prompt = CRITIC_USER_PROMPT_TEMPLATE.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        all_biological_processes=all_biological_processes,
        gene_count=len(genes_found),
        scored_genes_json=json.dumps(genes_found, indent=2),
        gene_evidence_json=json.dumps(gene_evidence, indent=2),
        state_of_knowledge_summary=state_of_knowledge.get("summary", "No summary text available currently."),
        min_genes=min_genes,
        max_genes=max_genes,
    )

    
    # Define output schema for structured response
    critic_schema = {
        "title": "critic_review",
        "type": "object",
        "properties": {
            "grade": {"type": "string", "enum": ["pass", "fail"]},
            "review": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary", "strengths", "weaknesses"],
            },
            "recommendations": {
                "type": "object",
                "properties": {
                    "opengenes_queries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["query", "reason"],
                        },
                    },
                    "pubmed_queries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["query", "reason"],
                        },
                    },
                    "vector_db_queries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["query", "reason"],
                        },
                    },
                },
                "required": ["opengenes_queries", "pubmed_queries", "vector_db_queries"],
            },
        },
        "required": ["grade", "review", "recommendations"],
    }

    llm = get_llm()
    print("Generating review of current draft...")
    try:
        critic_system_prompt = CRITIC_SYSTEM_PROMPT.format(
            min_genes=min_genes,
            max_genes=max_genes,
        )
        with llm.call(model="low", temp="mid"):
            critic_review = llm.invoke_structured(
                user_prompt, schema=critic_schema, system_prompt=critic_system_prompt
            )

        # Post-process: Fix common LLM schema violations
        # Issue 1: recommendations nested inside review instead of top-level
        if "recommendations" not in critic_review:
            if "review" in critic_review and "recommendations" in critic_review.get("review", {}):
                print("  Fixing: recommendations was nested inside review")
                critic_review["recommendations"] = critic_review["review"].pop("recommendations")
            else:
                # Missing entirely - use empty defaults
                print("  Warning: recommendations missing, using empty defaults")
                critic_review["recommendations"] = {
                    "opengenes_queries": [],
                    "pubmed_queries": [],
                    "vector_db_queries": [],
                }

        # Issue 2: Ensure review has required fields
        if "review" in critic_review:
            review = critic_review["review"]
            if "summary" not in review:
                review["summary"] = "No summary provided."
            if "strengths" not in review:
                review["strengths"] = []
            if "weaknesses" not in review:
                review["weaknesses"] = []

        # Issue 3: Ensure recommendations has required fields
        recs = critic_review.get("recommendations", {})
        if "opengenes_queries" not in recs:
            recs["opengenes_queries"] = []
        if "pubmed_queries" not in recs:
            recs["pubmed_queries"] = []
        if "vector_db_queries" not in recs:
            recs["vector_db_queries"] = []
        critic_review["recommendations"] = recs

        print(f"  Grade: {critic_review['grade'].upper()}")
        print(f"  Summary: {critic_review['review']['summary'][:100]}...")

    except Exception as e:
        # Fallback: default to fail with generic recommendations
        print(f"  Warning: LLM failed, using fallback review: {e}")
        critic_review = {
            "grade": "fail",
            "review": {
                "summary": f"Automatic fallback review due to LLM error. {len(bp_genes)} genes found.",
                "strengths": ["Draft exists with scored genes"],
                "weaknesses": ["Unable to perform detailed review due to technical error"],
            },
            "recommendations": {
                "opengenes_queries": [
                    {"query": bp_name.split()[0], "reason": "Broad search for related genes"}
                ],
                "pubmed_queries": [
                    {"query": f"{bp_name} AND aging", "reason": "Find literature on this process"}
                ],
                "vector_db_queries": [
                    {"query": bp_name, "reason": "Search corpus for mechanistic insights"}
                ],
            },
        }

    print(f"{'='*60}\n")
    return {"critic_review": critic_review}
