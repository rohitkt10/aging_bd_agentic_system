"""
Phase 1 Agent: Biological Process Identification

Uses LLM-powered reasoning to identify biological processes for aging hallmarks.

Workflow:
1. load_lopez_otin_context - Load reference paper
2. phase1_plan - Generate research plan with tool-specific search terms
3. phase1_research - Execute plan and identify BPs
4. phase1_critic - Two-step review (unstructured + structured)
5. phase1_refine - Execute refinement based on critic recommendations
6. phase1_finalize - Sort and create BP queue for Phase 2
"""

from __future__ import annotations

import json
from typing import Any

from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.llm.prompts import (
    PHASE1_CRITIC_STRUCTURED_PROMPT,
    PHASE1_CRITIC_UNSTRUCTURED_PROMPT,
    PHASE1_PLAN_SYSTEM_PROMPT,
    PHASE1_SYSTEM_PROMPT,
)
from aging_bd_agentic_system.tools import query_pubmed, query_vector_db

# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

RESEARCH_PLAN_SCHEMA = {
    "title": "research_plan",
    "type": "object",
    "properties": {
        "research_goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "vector_db_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "pubmed_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["goal", "vector_db_terms", "pubmed_terms"],
            },
        }
    },
    "required": ["research_goals"],
}

BIOLOGICAL_PROCESS_SCHEMA = {
    "title": "biological_processes",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "process_name": {"type": "string"},
            "evidence_score": {"type": "integer"},
            "evidence_summary": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "process_name",
            "evidence_score",
            "evidence_summary",
            "sources",
        ],
    },
}

CRITIC_STRUCTURED_SCHEMA = {
    "title": "critic_recommendations",
    "type": "object",
    "properties": {
        "grade": {"type": "string", "enum": ["pass", "fail"]},
        "vector_db_queries": {
            "type": "array",
            "items": {"type": "string"},
        },
        "pubmed_queries": {
            "type": "array",
            "items": {"type": "string"},
        },
        "focus_areas": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["grade", "vector_db_queries", "pubmed_queries", "focus_areas"],
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _extract_json_from_response(response: str) -> Any:
    """
    Extract JSON from LLM response that may contain extra text.

    Looks for JSON array [...] or object {...} patterns.
    """
    # Try array first
    json_start = response.find("[")
    json_end = response.rfind("]") + 1
    if json_start >= 0 and json_end > json_start:
        return json.loads(response[json_start:json_end])

    # Try object
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        return json.loads(response[json_start:json_end])

    raise ValueError("No valid JSON found in response")


def _format_corpus_results(results: list[dict]) -> str:
    """Format vector DB results for LLM context."""
    return "\n".join(
        [
            f"PMID: {rec.get('pmid', 'unknown')}\n{rec.get('text', '')}"
            for rec in results
        ]
    )


def _format_pubmed_results(results: list[dict]) -> str:
    """Format PubMed results for LLM context."""
    lines = []
    for rec in results:
        pmid = rec.get("pmid")
        title = rec.get("title", "")
        abstract = rec.get("abstract", "")
        lines.append(f"PMID:{pmid} - {title}\n{abstract}")
    return "\n".join(lines)


def _deduplicate_processes(processes: list[dict]) -> list[dict]:
    """Remove duplicate biological processes by name (case-insensitive)."""
    seen = set()
    unique = []
    for proc in processes:
        name_lower = proc.get("process_name", "").lower().strip()
        if name_lower not in seen:
            seen.add(name_lower)
            unique.append(proc)
    return unique


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================


def load_lopez_otin_context(state: dict[str, Any]) -> dict[str, Any]:
    """
    Load the Lopez-Otin paper text into state if missing.

    Args:
        state: Workflow state

    Returns:
        Dict with lopez_otin_context if not already loaded
    """
    if state.get("lopez_otin_context"):
        return {}
    path = config.DATA_DIR / "lopez-otin-22.md"
    text = path.read_text(encoding="utf-8")
    return {"lopez_otin_context": text}


def phase1_plan(state: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a structured research plan with tool-specific search terms.

    The plan includes research goals with suggested search terms for both
    vector_db and pubmed tools.

    Args:
        state: Workflow state with hallmark_name, lopez_otin_context, and config

    Returns:
        Dict with phase1_plan containing research_goals list
    """
    hallmark = state["hallmark_name"].strip()
    lopez_context = state.get("lopez_otin_context", "")

    # Read config from state
    cfg = state.get("config", {})
    p1 = cfg.get("phase1", {})
    min_research_goals = p1.get("min_research_goals", 4)
    max_research_goals = p1.get("max_research_goals", 6)

    system_prompt = PHASE1_PLAN_SYSTEM_PROMPT.format(
        hallmark_name=hallmark,
        min_goals=min_research_goals,
        max_goals=max_research_goals,
    )

    user_prompt = f"""## Reference Context

### Lopez-Otin Hallmarks Paper
{lopez_context}

Generate a research plan for identifying biological processes related to "{hallmark}".
"""

    llm = get_llm()

    try:
        plan = llm.invoke_structured(
            user_prompt, schema=RESEARCH_PLAN_SCHEMA, system_prompt=system_prompt
        )
    except Exception as e:
        # Fallback: try to parse JSON from text response
        print(f"Structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(user_prompt, system_prompt=system_prompt)
        plan = _extract_json_from_response(response)

    return {"phase1_plan": plan}


def phase1_research(state: dict[str, Any]) -> dict[str, Any]:
    """
    Execute the research plan and identify biological processes.

    Consumes the plan from phase1_plan and executes searches using the
    suggested search terms. Produces a liberal list of BPs (duplicates removed).

    Args:
        state: Workflow state with phase1_plan and config

    Returns:
        Dict with biological_processes list
    """
    hallmark = state["hallmark_name"].strip()
    lopez_context = state.get("lopez_otin_context", "")
    plan = state.get("phase1_plan", {})
    critic_recommendations = state.get("phase1_critic_recommendations", {})

    # Read config from state
    cfg = state.get("config", {})
    p1 = cfg.get("phase1", {})
    vector_db_top_k = p1.get("vector_db_top_k", 20)
    pubmed_retmax = p1.get("pubmed_retmax", 10)
    max_iterations = p1.get("max_iterations", 2)

    # Track iteration
    current_iteration = state.get("phase1_iteration", 0) + 1

    # Gather evidence from multiple sources
    all_corpus_results = []
    all_pubmed_results = []

    # 1. Execute searches from the plan (initial or refined)
    research_goals = plan.get("research_goals", [])

    for goal in research_goals:
        # Vector DB searches
        for term in goal.get("vector_db_terms", []):
            results = query_vector_db(query=term, top_k=vector_db_top_k)
            all_corpus_results.extend(results)

        # PubMed searches
        for term in goal.get("pubmed_terms", []):
            results = query_pubmed(query=term, retmax=pubmed_retmax)
            all_pubmed_results.extend(results)

    # 2. Execute additional searches from critic recommendations (if refining)
    if critic_recommendations:
        for query in critic_recommendations.get("vector_db_queries", []):
            results = query_vector_db(query=query, top_k=vector_db_top_k)
            all_corpus_results.extend(results)

        for query in critic_recommendations.get("pubmed_queries", []):
            results = query_pubmed(query=query, retmax=pubmed_retmax)
            all_pubmed_results.extend(results)

    # 3. Build context for LLM
    corpus_section = _format_corpus_results(all_corpus_results)
    pubmed_section = _format_pubmed_results(all_pubmed_results)

    # Include iteration context in prompt
    iteration_context = ""
    if current_iteration > 1:
        iteration_context = f"""
## Iteration Context
This is iteration {current_iteration} of {max_iterations}.
Focus on: {', '.join(critic_recommendations.get('focus_areas', []))}
"""
        if current_iteration == max_iterations:
            iteration_context += (
                "\nThis is the FINAL iteration. Produce the final list now."
            )

    user_context = f"""## Reference Context

### Lopez-Otin Hallmarks Paper
{lopez_context}

### Relevant Literature from Corpus
{corpus_section}

### PubMed Search Results
{pubmed_section}
{iteration_context}
Identify biological processes related to {hallmark} based on this evidence.
"""

    # 4. Call LLM to identify processes
    system_prompt = PHASE1_SYSTEM_PROMPT.format(hallmark_name=hallmark)
    llm = get_llm()

    try:
        processes = llm.invoke_structured(
            user_context,
            schema=BIOLOGICAL_PROCESS_SCHEMA,
            system_prompt=system_prompt,
        )
    except Exception as e:
        print(f"Structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(user_context, system_prompt=system_prompt)
        processes = _extract_json_from_response(response)

    # 5. Validate and deduplicate
    if not processes:
        raise ValueError("LLM returned empty process list")

    processes = _deduplicate_processes(processes)

    # 6. Add rank field
    for idx, proc in enumerate(processes, start=1):
        proc["rank"] = idx

    return {"biological_processes": processes}


def phase1_critic(state: dict[str, Any]) -> dict[str, Any]:
    """
    Two-step critique: unstructured review followed by structured recommendations.

    Step 1: Free-form text critique (~100 words)
    Step 2: Structured output with pass/fail grade and tool recommendations

    Args:
        state: Workflow state with biological_processes and config

    Returns:
        Dict with phase1_critique (text) and phase1_critic_recommendations (structured)
    """
    hallmark = state["hallmark_name"]
    processes = state.get("biological_processes", [])

    # Read config from state
    cfg = state.get("config", {})
    p1 = cfg.get("phase1", {})
    max_iterations = p1.get("max_iterations", 2)

    # Track iteration
    current_iteration = state.get("phase1_iteration", 0) + 1

    if not processes:
        return {
            "phase1_critique": "No biological processes identified.",
            "phase1_critic_recommendations": {
                "grade": "fail",
                "vector_db_queries": [f"{hallmark} aging mechanism"],
                "pubmed_queries": [f'"{hallmark}" AND aging AND mechanism'],
                "focus_areas": ["all"],
            },
        }

    processes_json = json.dumps(processes, indent=2)
    llm = get_llm()

    # Step 1: Unstructured critique
    unstructured_prompt = PHASE1_CRITIC_UNSTRUCTURED_PROMPT.format(
        hallmark_name=hallmark,
        current_iteration=current_iteration,
        max_iterations=max_iterations,
        processes_json=processes_json,
    )

    critique_text = llm.invoke(unstructured_prompt)

    # Step 2: Structured recommendations
    structured_prompt = PHASE1_CRITIC_STRUCTURED_PROMPT.format(
        critique_text=critique_text,
        processes_json=processes_json,
    )

    try:
        recommendations = llm.invoke_structured(
            structured_prompt, schema=CRITIC_STRUCTURED_SCHEMA
        )
    except Exception as e:
        print(f"Structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(structured_prompt)
        recommendations = _extract_json_from_response(response)

    return {
        "phase1_critique": critique_text,
        "phase1_critic_recommendations": recommendations,
    }


def phase1_refine(state: dict[str, Any]) -> dict[str, Any]:
    """
    Execute refinement based on critic recommendations.

    This function re-runs the research step with additional queries from
    the critic. The actual refinement logic is handled by phase1_research
    when it sees critic_recommendations in state.

    Args:
        state: Workflow state with phase1_critic_recommendations and config

    Returns:
        Updated biological_processes from re-running research
    """
    # Increment iteration counter
    iteration = state.get("phase1_iteration", 0) + 1

    # Re-run research with critic recommendations
    result = phase1_research(state)
    result["phase1_iteration"] = iteration
    return result


def phase1_finalize(state: dict[str, Any]) -> dict[str, Any]:
    """
    Finalize Phase 1 by sorting processes and creating BP queue.

    Args:
        state: Workflow state with biological_processes and config

    Returns:
        Dict with sorted biological_processes and bp_queue
    """
    # Read config from state
    cfg = state.get("config", {})
    p1 = cfg.get("phase1", {})
    max_processes = p1.get("max_processes", 15)

    processes = list(state.get("biological_processes", []))

    # Sort by evidence score desc, then by process name
    processes.sort(
        key=lambda p: (-p.get("evidence_score", 0), p.get("process_name", ""))
    )

    # Trim to max
    processes = processes[:max_processes]

    # Re-rank
    for idx, proc in enumerate(processes, start=1):
        proc["rank"] = idx

    # Create queue for Phase 2
    bp_queue = [p["process_name"] for p in processes if p.get("process_name")]

    return {"biological_processes": processes, "bp_queue": bp_queue}
