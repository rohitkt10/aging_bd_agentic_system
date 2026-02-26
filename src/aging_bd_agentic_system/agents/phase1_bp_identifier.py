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
from pdb import set_trace
import json
from pathlib import Path
import time
from typing import Any
from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.prompts.phase1_prompts import (
    PHASE1_CORPUS_SUMMARY_PROMPT,
    PHASE1_CRITIC_STRUCTURED_PROMPT,
    PHASE1_CRITIC_SYSTEM_PROMPT,
    PHASE1_CRITIC_UNSTRUCTURED_PROMPT,
    PHASE1_PUBMED_SUMMARY_PROMPT,
    PHASE1_PLAN_SYSTEM_PROMPT,
    PHASE1_REFINE_SYSTEM_PROMPT,
    PHASE1_SUMMARY_SYSTEM_PROMPT,
    PHASE1_SYSTEM_PROMPT,
)
from aging_bd_agentic_system.tools import query_pubmed, query_vector_db, query_vector_db_batch
from aging_bd_agentic_system.utils.output_writer import ensure_output_dir, write_processes_tsv
from aging_bd_agentic_system.utils.audit_logger import log_event

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
    "title": "biological_processes_wrapper",
    "type": "object",
    "properties": {
        "processes": {
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
    },
    "required": ["processes"],
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

GOAL_SUMMARY_SCHEMA = {
    "title": "goal_summary",
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["goal", "summary"],
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


def _summarize_goal_results(
    goal: str,
    hallmark_name: str,
    corpus_results: list[dict],
    pubmed_results: list[dict],
    max_words: int = 300,
) -> dict[str, str]:
    """
    Summarize corpus and PubMed results for a single research goal.

    Makes two separate LLM calls (one for corpus, one for PubMed) for reliability.

    Args:
        goal: The research goal being summarized
        hallmark_name: The aging hallmark being researched
        corpus_results: List of corpus search results
        pubmed_results: List of PubMed search results
        max_words: Approximate max words per summary section (default 300)

    Returns:
        Dict with goal, corpus_summary, and pubmed_summary
    """
    llm = get_llm()

    # Format raw results
    corpus_text = _format_corpus_results(corpus_results) if corpus_results else "No results"
    pubmed_text = _format_pubmed_results(pubmed_results) if pubmed_results else "No results"

    # Summarize corpus results
    corpus_prompt = PHASE1_CORPUS_SUMMARY_PROMPT.format(
        system_prompt=PHASE1_SUMMARY_SYSTEM_PROMPT,
        goal=goal,
        hallmark_name=hallmark_name,
        results=corpus_text,
        max_words=max_words,
    )
    try:
        corpus_result = llm.invoke_structured(corpus_prompt, schema=GOAL_SUMMARY_SCHEMA)
    except Exception as e:
        print(f"Corpus structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(corpus_prompt)
        corpus_result = _extract_json_from_response(response)

    # Summarize PubMed results
    pubmed_prompt = PHASE1_PUBMED_SUMMARY_PROMPT.format(
        system_prompt=PHASE1_SUMMARY_SYSTEM_PROMPT,
        goal=goal,
        hallmark_name=hallmark_name,
        results=pubmed_text,
        max_words=max_words,
    )
    try:
        pubmed_result = llm.invoke_structured(pubmed_prompt, schema=GOAL_SUMMARY_SCHEMA)
    except Exception as e:
        print(f"PubMed structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(pubmed_prompt)
        pubmed_result = _extract_json_from_response(response)

    # Combine results into expected format
    return {
        "goal": goal,
        "corpus_summary": corpus_result.get("summary", ""),
        "pubmed_summary": pubmed_result.get("summary", ""),
    }
    

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

                    Generate a research plan for identifying biological 
                    processes related to "{hallmark}".
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
    Execute research and identify biological processes.

    Two modes based on iteration:
    - Initial (iteration 0): Execute plan goals, summarize per goal
    - Refinement (iteration > 0): Execute critic queries only

    Args:
        state: Workflow state with phase1_plan and config

    Returns:
        Dict with biological_processes list
    """
    hallmark = state["hallmark_name"].strip()
    lopez_context = state.get("lopez_otin_context", "")
    plan = state.get("phase1_plan", {})
    critic_recommendations = state.get("phase1_critic_recommendations", {})
    existing_processes = state.get("biological_processes", [])

    # Read config from state
    cfg = state.get("config", {})
    p1 = cfg.get("phase1", {})
    vector_db_top_k = p1.get("phase1_vector_db_top_k", 20)
    pubmed_retmax = p1.get("phase1_pubmed_retmax", 10)
    summary_max_words = p1.get("summary_max_words", 300)

    # Determine current iteration
    current_iteration = state.get("phase1_iteration", 0)

    llm = get_llm()

    # === TWO PATHS: INITIAL vs REFINEMENT ===
    if current_iteration == 0:
        # === INITIAL RESEARCH PATH ===
        # Execute plan goals, summarize per goal, use PHASE1_SYSTEM_PROMPT

        research_goals = plan.get("research_goals", [])
        goal_summaries = []
        print("\n" + "-" * 50)
        print("RESEARCH GOALS")
        print("-" * 50)
        for i, goal in enumerate(research_goals, 1):
            goal_text = goal.get("goal", "")
            vector_db_terms = goal.get("vector_db_terms", [])
            pubmed_terms = goal.get("pubmed_terms", [])
            print(f"\n  [{i}] {goal_text}")
            print(f"      vector_db_terms: {len(vector_db_terms)}, pubmed_terms: {len(pubmed_terms)}")
        print("\n" + "-" * 50 + "\n")
        for goal in research_goals:
            goal_text = goal.get("goal", "")
            goal_corpus_results = []
            goal_pubmed_results = []

            # Vector DB searches for this goal (batched)
            vector_db_terms = goal.get("vector_db_terms", [])
            if vector_db_terms:
                batch_results = query_vector_db_batch(
                    queries=vector_db_terms, top_k=vector_db_top_k
                )
                goal_corpus_results.extend(
                    [rec for results in batch_results for rec in results]
                )

            # PubMed searches for this goal (rate limited: 3 req/sec without API key)
            for term in goal.get("pubmed_terms", []):
                results = query_pubmed(query=term, retmax=pubmed_retmax)
                goal_pubmed_results.extend(results)
                time.sleep(0.34)  # Rate limit: stay under 3 req/sec

            # Summarize this goal's results
            if goal_corpus_results or goal_pubmed_results:
                summary = _summarize_goal_results(
                    goal=goal_text,
                    hallmark_name=hallmark,
                    corpus_results=goal_corpus_results,
                    pubmed_results=goal_pubmed_results,
                    max_words=summary_max_words,
                )
                goal_summaries.append(summary)

        # Build context for initial research
        summaries_section = ""
        for i, summary in enumerate(goal_summaries):
            summaries_section += f"""
                            ### Goal {i+1}: {summary.get('goal', 'Unknown')}
                            **Corpus Summary:**
                            {summary.get('corpus_summary', 'No results')}

                            **PubMed Summary:**
                            {summary.get('pubmed_summary', 'No results')}

                            ---
                            """

        user_context = f"""## Reference Context

                            ### Lopez-Otin Hallmarks Paper
                            {lopez_context}

                            ## Summarized Research Findings by Goal
                            {summaries_section}

                            Identify biological processes related to {hallmark} based on this evidence.
                            """

        system_prompt = PHASE1_SYSTEM_PROMPT.format(hallmark_name=hallmark)

    else:
        # === REFINEMENT RESEARCH PATH ===
        # Execute critic queries only, use PHASE1_REFINE_SYSTEM_PROMPT

        critic_corpus_results = []
        critic_pubmed_results = []

        # Execute critic-recommended vector DB queries (batched)
        vector_db_queries = critic_recommendations.get("vector_db_queries", [])
        if vector_db_queries:
            batch_results = query_vector_db_batch(
                queries=vector_db_queries, top_k=vector_db_top_k
            )
            critic_corpus_results.extend(
                [rec for results in batch_results for rec in results]
            )

        # Execute critic-recommended PubMed queries
        for query in critic_recommendations.get("pubmed_queries", []):
            results = query_pubmed(query=query, retmax=pubmed_retmax)
            critic_pubmed_results.extend(results)
            time.sleep(0.34)  # Rate limit: stay under 3 req/sec

        # Log refinement results
        print("\n" + "-" * 50)
        print("REFINEMENT RESEARCH")
        print("-" * 50)
        print(f"  vector_db_queries: {len(vector_db_queries)} -> {len(critic_corpus_results)} results")
        print(f"  pubmed_queries: {len(critic_recommendations.get('pubmed_queries', []))} -> {len(critic_pubmed_results)} results")
        print("-" * 50 + "\n")

        # Summarize critic query results (avoids context explosion)
        if critic_corpus_results or critic_pubmed_results:
            summary = _summarize_goal_results(
                goal="Critic refinement queries",
                hallmark_name=hallmark,
                corpus_results=critic_corpus_results,
                pubmed_results=critic_pubmed_results,
                max_words=summary_max_words,
            )
            corpus_summary = summary.get("corpus_summary", "No results")
            pubmed_summary = summary.get("pubmed_summary", "No results")
        else:
            corpus_summary = "No results"
            pubmed_summary = "No results"

        # Format focus areas
        focus_areas = critic_recommendations.get("focus_areas", [])
        focus_areas_text = "\n".join([f"- {area}" for area in focus_areas]) if focus_areas else "None specified"

        # Build context for refinement
        user_context = f"""## Existing Biological Processes
                        {json.dumps(existing_processes, indent=2)}

                        ## Summarized New Evidence from Critic Queries

                        **Corpus Summary:**
                        {corpus_summary}

                        **PubMed Summary:**
                        {pubmed_summary}

                        ## Focus Areas from Critic
                        {focus_areas_text}

                        Update the biological process list for {hallmark} based on this new evidence and focus areas.
                        """

        system_prompt = PHASE1_REFINE_SYSTEM_PROMPT.format(hallmark_name=hallmark)

    # === CALL LLM ===
    try:
        result = llm.invoke_structured(
            user_context,
            schema=BIOLOGICAL_PROCESS_SCHEMA,
            system_prompt=system_prompt,
        )

        # Validate result follows schema (not returning schema itself)
        processes = result.get("processes")
        if not isinstance(processes, list) or (processes and "type" in processes):
            # Schema mismatch - 1 retry to fix
            print("Schema mismatch detected, retrying with fix prompt...")
            fix_prompt = f"""The following JSON has a schema mismatch. Expected "processes" to be an array of objects with process_name, evidence_score, evidence_summary, sources.

                            Got this instead:
                            {json.dumps(result, indent=2)}

                            Fix the format and return the corrected JSON with the same schema structure."""

            result = llm.invoke_structured(
                fix_prompt,
                schema=BIOLOGICAL_PROCESS_SCHEMA,
                system_prompt="You are a JSON format fixer. Return only corrected JSON.",
            )
            processes = result.get("processes")

            # If still broken after retry, fail
            if not isinstance(processes, list) or (processes and "type" in processes):
                raise ValueError("Schema mismatch persists after retry")

        processes = result["processes"]  # Extract array from wrapper object
    except Exception as e:
        print(f"Structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(user_context, system_prompt=system_prompt)
        processes = _extract_json_from_response(response)
    
    # Validate and deduplicate
    if not processes:
        raise ValueError("LLM returned empty process list")
    processes = _deduplicate_processes(processes)

    # Add rank field
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

    critique_text = llm.invoke(unstructured_prompt, system_prompt=PHASE1_CRITIC_SYSTEM_PROMPT)

    # Step 2: Structured recommendations
    structured_prompt = PHASE1_CRITIC_STRUCTURED_PROMPT.format(
        critique_text=critique_text,
        processes_json=processes_json,
    )

    try:
        recommendations = llm.invoke_structured(
            structured_prompt, schema=CRITIC_STRUCTURED_SCHEMA, system_prompt=PHASE1_CRITIC_SYSTEM_PROMPT
        )
    except Exception as e:
        print(f"Structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(structured_prompt, system_prompt=PHASE1_CRITIC_SYSTEM_PROMPT)
        recommendations = _extract_json_from_response(response)

    # Log critic results
    print("\n" + "-" * 50)
    print("CRITIC REVIEW")
    print("-" * 50)
    print(f"  Grade: {recommendations.get('grade', 'unknown')}")
    print(f"  vector_db_queries: {len(recommendations.get('vector_db_queries', []))}")
    print(f"  pubmed_queries: {len(recommendations.get('pubmed_queries', []))}")
    focus_areas = recommendations.get('focus_areas', [])
    print(f"  focus_areas: {', '.join(focus_areas) if focus_areas else 'none'}")
    print("-" * 50 + "\n")

    return {
        "phase1_critique": critique_text,
        "phase1_critic_recommendations": recommendations,
    }


def phase1_refine(state: dict[str, Any]) -> dict[str, Any]:
    """
    Execute refinement based on critic recommendations.

    Increments iteration counter and calls phase1_research which will
    execute critic queries and update the biological process list.

    Args:
        state: Workflow state with phase1_critic_recommendations and config

    Returns:
        Updated biological_processes and phase1_iteration
    """
    # Increment iteration counter
    iteration = state.get("phase1_iteration", 0) + 1
    state["phase1_iteration"] = iteration

    # Run refinement research (phase1_research will use refinement path since iteration > 0)
    result = phase1_research(state)
    return result


def phase1_finalize(state: dict[str, Any]) -> dict[str, Any]:
    """
    Finalize Phase 1 by sorting processes and creating BP queue.

    If critic grade is "fail", first executes refinement research,
    then finalizes. If grade is "pass", just finalizes.

    Args:
        state: Workflow state with biological_processes and config

    Returns:
        Dict with sorted biological_processes and bp_queue
    """
    # Read config from state
    cfg = state.get("config", {})
    p1 = cfg.get("phase1", {})
    max_processes = p1.get("max_processes", 15)

    # Check critic grade
    critic_recommendations = state.get("phase1_critic_recommendations", {})
    grade = critic_recommendations.get("grade", "fail")
    
    # If critic failed, do final refinement research before finalizing
    if grade == "fail":
        result = phase1_refine(state)
        processes = result.get("biological_processes", [])
    else:
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

    # Save Phase 1 outputs
    hallmark = state.get("hallmark_name", "unknown")
    cfg = state.get("config", {})
    output_dir = Path(cfg.get("output_dir", "outputs"))
    out_dir = ensure_output_dir(output_dir, hallmark)
    write_processes_tsv(out_dir, processes)

    # Log Phase 1 completion event
    log_event({
        "hallmark": hallmark,
        "event_type": "phase1_complete",
        "biological_processes_count": len(processes),
        "critic_grade": grade,
    }, output_dir=output_dir)

    return {"biological_processes": processes, "bp_queue": bp_queue}
