"""
Phase 2 Agent: Gene Research and GO Term Mapping

Uses LLM-powered reasoning to identify genes and GO terms for biological processes.
"""

from __future__ import annotations

import json
import os
from typing import Any

from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.llm.prompts import (
    PHASE2_CRITIQUE_SYSTEM_PROMPT,
    PHASE2_DECISION_USER_PROMPT,
    PHASE2_GO_MAPPING_SYSTEM_PROMPT,
    PHASE2_RESEARCH_SYSTEM_PROMPT,
    PHASE2_SCORING_SYSTEM_PROMPT,
    PHASE2_TOOL_DESCRIPTIONS,
)
from aging_bd_agentic_system.utils.context_manager import (
    summarize_for_scoring,
    summarize_if_needed,
)
from aging_bd_agentic_system.tools import (
    query_genage,
    query_go_terms,
    query_opengenes,
    query_pubmed,
    query_vector_db,
)
from aging_bd_agentic_system.utils.audit_logger import log_event


def select_bp(state: dict[str, Any]) -> dict[str, Any]:
    """Select the current biological process from the queue."""
    bp_queue = state.get("bp_queue", [])
    index = state.get("current_bp_index", 0)

    if index >= len(bp_queue):
        return {}  # Signal to exit loop

    return {"current_bp_name": bp_queue[index]}


def phase2_research(
    state: dict[str, Any],
    genage_seed_max_results: int = 50,
    opengenes_seed_max_results: int = 50,
    max_opengenes_items_per_field: int = -1,
    min_actions_per_iteration: int = 1,
    max_actions_per_iteration: int = 3,
    pubmed_max_results: int = 5,
    vector_db_max_results: int = 5,
) -> dict[str, Any]:
    """
    Autonomous ReAct research loop for gene discovery.

    This function runs a multi-iteration research loop where the LLM scientist agent:
    1. Queries all 4 sources (GenAge, OpenGenes, PubMed, Vector DB)
    2. Decides what to search for based on findings
    3. Shifts from exploration → exploitation over iterations
    4. Synthesizes and scores genes at the end

    Args:
        genage_seed_max_results: Maximum GenAge results to fetch during seeding (default 50)
        opengenes_seed_max_results: Maximum OpenGenes results to fetch during seeding (default 50)
        max_opengenes_items_per_field: Maximum items per OpenGenes field to include.
            -1 (default): Include all items (no truncation)
            0+: Truncate to first N items per field
        min_actions_per_iteration: Minimum research actions per iteration (default 1)
        max_actions_per_iteration: Maximum research actions per iteration (default 3)
        pubmed_max_results: Maximum PubMed results to process per action (default 5)
        vector_db_max_results: Maximum vector DB results to process per action (default 5)

    Iterations (configurable via PHASE2_RESEARCH_MAX_ITERATIONS):
    - Iteration 1-2: Wide exploration (all sources, broad queries)
    - Iteration 3-4: Follow rabbit holes (explore interesting leads)
    - Iteration 5-6: Balance + exploitation (deepen findings, fill gaps)
    - Iteration 7: Final summary (synthesize, score, finalize)

    Returns:
        Genes with scores (5+ only) and evidence summaries
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")
    max_iterations = int(os.environ.get("PHASE2_RESEARCH_MAX_ITERATIONS", "7"))

    # Get current iteration
    current_iteration = state.get("phase2_research_iteration", 0)

    # Initialize scratchpad if first iteration
    if current_iteration == 0:
        # Seed with candidates from databases
        genage_results = query_genage(query=bp_name, max_results=genage_seed_max_results)
        opengenes_results = query_opengenes(query=bp_name, max_results=opengenes_seed_max_results)

        # Combine and dedupe
        seen = set()
        candidates = []

        for rec in genage_results:
            symbol = rec.get("symbol")
            if symbol and symbol not in seen:
                seen.add(symbol)
                candidates.append({
                    "symbol": symbol,
                    "name": rec.get("name", ""),
                    "source": "genage",
                    "evidence_type": rec.get("why", ""),
                })

        for rec in opengenes_results:
            symbol = rec.get("symbol")
            if symbol and symbol not in seen:
                seen.add(symbol)
                candidates.append({
                    "symbol": symbol,
                    "name": rec.get("name", ""),
                    "source": "opengenes",
                    "aging_mechanisms": rec.get("agingMechanisms", []),
                    "functional_clusters": rec.get("functionalClusters", []),
                    "protein_classes": rec.get("proteinClasses", []),
                    "evidence_causes": rec.get("commentCause", []),
                })

        # Store in scratchpad as structured JSON
        research_data = {
            "initial_database_genes": candidates,
            "research_findings": [],  # Accumulated findings from iterations
        }
        return {
            "research_scratchpad": json.dumps(research_data, default=str),
            "phase2_research_iteration": 1
        }

    # Load current research state
    try:
        research_data = json.loads(state.get("research_scratchpad", "{}"))
    except json.JSONDecodeError:
        research_data = {"initial_database_genes": [], "research_findings": []}

    # Add context management
    context_updates = summarize_if_needed(state)
    if context_updates:
        state.update(context_updates)

    llm = get_llm()

    # Determine research phase based on iteration (dynamic boundaries based on max_iterations)
    exploration_end = max(1, int(max_iterations * 0.3))
    rabbit_hole_end = max(exploration_end + 1, int(max_iterations * 0.6))

    if current_iteration <= exploration_end:
        phase = "exploration"
        guidance = "Cast a wide net. Query all 4 sources with broad terms. Note what looks interesting."
    elif current_iteration <= rabbit_hole_end:
        phase = "rabbit_hole"
        guidance = "Follow interesting leads you found. Search for specific genes or terms that keep appearing."
    elif current_iteration < max_iterations:
        phase = "exploitation"
        guidance = "Deepen your findings. Fill gaps in weak evidence. Cross-reference."
    else:
        phase = "finalization"
        guidance = "Synthesize all findings. Score genes 1-10. Return only genes with score 5+."

    # Build context with structured summary if available
    context_parts = []
    if state.get("context_summary"):
        try:
            summary_data = json.loads(state["context_summary"])
            top_candidates = summary_data.get("top_candidates", [])
            iteration_state = summary_data.get("iteration_state", {})
            gaps = summary_data.get("research_gaps", [])
            high_value_findings = summary_data.get("high_value_findings", [])

            context_str = f"""## Research Summary
                            Top Candidates: {', '.join([c['symbol'] for c in top_candidates[:10]])}
                            Total Findings: {iteration_state.get('total_findings', 'N/A')}
                            Research Gaps: {', '.join(gaps[:3]) if gaps else 'None identified'}

                            ## High-Value Findings
                            {json.dumps(high_value_findings[:10], indent=2)}
                            """
            context_parts.append(context_str)
        except json.JSONDecodeError:
            # Fallback to raw summary text
            context_parts.append(f"## Previous Research Summary\n{state['context_summary']}")
    else:
        # No summarization needed - pass full unsummarized context
        all_candidates = json.dumps([c["symbol"] for c in research_data.get("initial_database_genes", [])], indent=2)
        all_findings = json.dumps(research_data.get("research_findings", []), indent=2)
        context_parts.append(f"## All Candidates\n{all_candidates}")
        context_parts.append(f"## All Findings\n{all_findings}")
    context_str = "\n".join(context_parts)

    # Format system prompt for research loop iterations
    system_prompt = PHASE2_RESEARCH_SYSTEM_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        tool_descriptions=PHASE2_TOOL_DESCRIPTIONS
    )

    # Format user prompt with current state and get decision
    user_prompt = PHASE2_DECISION_USER_PROMPT.format(
        current_iteration=current_iteration,
        max_iterations=max_iterations,
        phase=phase.upper(),
        guidance=guidance,
        candidates_summary="",  # Not used - context_str has everything
        recent_findings=context_str,
        min_actions=min_actions_per_iteration,
        max_actions=max_actions_per_iteration
    )

    # Get research decisions from LLM with structured output
    decision_schema = {
        "title": "research_decision",
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "minItems": min_actions_per_iteration,
                "maxItems": max_actions_per_iteration,
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "enum": ["genage", "opengenes", "pubmed", "vector_db"]},
                        "query": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["source", "query"],
                },
            },
            "findings_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["actions", "findings_notes"],
    }

    try:
        decisions = llm.invoke_structured(
            user_prompt,
            schema=decision_schema,
            system_prompt=system_prompt
        )
    except Exception:
        decisions = {"actions": [], "findings_notes": []}

    # Execute the research actions
    new_findings = []

    # Helper to truncate OpenGenes lists if max_opengenes_items_per_field > 0, else keep all
    def truncate_field(items):
        if max_opengenes_items_per_field < 0:
            return items
        return items[:max_opengenes_items_per_field]

    for action in decisions.get("actions", []):
        source = action.get("source")
        query = action.get("query")

        if source == "genage":
            results = query_genage(query=query, max_results=20)
            for rec in results:
                new_findings.append({
                    "source": "genage",
                    "gene": rec.get("symbol"),
                    "query": query,
                    "finding": f"Evidence: {rec.get('why', 'N/A')}"
                })

        elif source == "opengenes":
            results = query_opengenes(query=query, max_results=20)
            for rec in results:
                mechanisms = truncate_field(rec.get("agingMechanisms", []))
                clusters = truncate_field(rec.get("functionalClusters", []))
                proteins = truncate_field(rec.get("proteinClasses", []))
                causes = truncate_field(rec.get("commentCause", []))
                finding_text = f"OpenGenes - Mechanisms: {mechanisms}; Clusters: {clusters}; Proteins: {proteins}; Evidence: {causes}"

                new_findings.append({
                    "source": "opengenes",
                    "gene": rec.get("symbol"),
                    "query": query,
                    "finding": finding_text
                })

        elif source == "pubmed":
            results = query_pubmed(query=query, retmax=10)
            for rec in results[:pubmed_max_results]:
                new_findings.append({
                    "source": "pubmed",
                    "gene": None,  # May or may not mention a gene
                    "query": query,
                    "finding": f"{rec.get('title', '')}: {rec.get('abstract', '')[:200]}"
                })

        elif source == "vector_db":
            results = query_vector_db(query=query, top_k=10)
            for rec in results[:vector_db_max_results]:
                new_findings.append({
                    "source": "corpus",
                    "gene": None,
                    "query": query,
                    "finding": rec.get("text", "")[:300]
                })

    # Update research data
    research_data["research_findings"].extend(new_findings)
    research_data["research_findings"].extend(decisions.get("findings_notes", []))

    # If final iteration, synthesize and score genes
    if current_iteration >= max_iterations:
        # Use LLM-based comprehensive evidence aggregation (no truncation)
        scoring_summary = summarize_for_scoring(research_data, bp_name)

        # System prompt with scoring instructions and rubric
        system_prompt = PHASE2_SCORING_SYSTEM_PROMPT.format(
            biological_process=bp_name,
            hallmark_name=hallmark
        )

        # Schema for scored genes output
        scored_genes_schema = {
            "title": "scored_genes",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gene_symbol": {"type": "string"},
                    "score": {"type": "integer", "minimum": 5, "maximum": 10},
                    "evidence_summary": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["gene_symbol", "score", "evidence_summary", "sources"],
            },
        }

        # User message with comprehensive evidence summary
        user_context = f"""## Comprehensive Evidence Summary
                        {json.dumps(scoring_summary, indent=2)}

                        Based on the comprehensive evidence summary above, identify and score relevant genes.
                        """

        # Get scored genes using structured output
        try:
            scored_genes = llm.invoke_structured(
                                        user_context,
                                        schema=scored_genes_schema,
                                        system_prompt=system_prompt
                                             )
        except Exception:
            scored_genes = []

        # Add biological_process field
        for gene in scored_genes:
            gene["biological_process"] = bp_name

        return {
            "genes_found": scored_genes,
            "phase2_research_iteration": 0  # Reset for next BP
        }

    # Not final iteration - continue research loop
    return {
        "research_scratchpad": json.dumps(research_data, default=str),
        "phase2_research_iteration": current_iteration + 1
    }


def phase2_critic(state: dict[str, Any], min_genes_expected: int = 20) -> dict[str, Any]:
    """
    Use LLM to evaluate gene evidence coverage for the current BP.

    LLM judges:
    - Are there enough genes?
    - Is evidence strong?
    - Are genes relevant to the BP?
    """
    bp_name = state.get("current_bp_name", "")

    # Get genes for this BP only
    all_genes = state.get("genes_found", [])
    bp_genes = [g for g in all_genes if g.get("biological_process") == bp_name]

    if not bp_genes:
        return {
            "phase2_eval": {
                "grade": "fail",
                "comment": f"No genes found for {bp_name}",
                "follow_up_queries": [f"{bp_name} genes aging mechanisms"],
                "min_genes_expected": min_genes_expected,
            }
        }

    # User message contains the gene data
    user_context = json.dumps(bp_genes, indent=2)

    # Format system prompt
    system_prompt = PHASE2_CRITIQUE_SYSTEM_PROMPT.format(
        biological_process=bp_name,
        genes_json="{GENES_JSON}"  # Placeholder
    )

    # Remove the genes_json from system prompt since it's now in user message
    system_prompt = system_prompt.replace("{genes_json}", "See the genes in the user message.")

    llm = get_llm()

    try:
        schema = {
            "title": "phase2_evaluation",
            "type": "object",
            "properties": {
                "grade": {"type": "string", "enum": ["pass", "fail"]},
                "comment": {"type": "string"},
                "follow_up_queries": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["grade", "comment", "follow_up_queries"],
        }

        eval_result = llm.invoke_structured(
            user_context,
            schema=schema,
            system_prompt=system_prompt
        )

    except Exception:
        # Fallback: simple rule-based evaluation
        gene_count = len(bp_genes)
        eval_result = {
            "grade": "pass" if gene_count >= min_genes_expected else "fail",
            "comment": f"Found {gene_count} genes (expected {min_genes_expected}+).",
            "follow_up_queries": [f"{bp_name} additional genes"] if gene_count < min_genes_expected else [],
        }

    eval_result["min_genes_expected"] = min_genes_expected
    return {"phase2_eval": eval_result}


def phase2_refine(
    state: dict[str, Any],
    max_follow_up_queries: int = 2,
    refine_vector_db_results: int = 5,
    refine_pubmed_results: int = 3,
    max_genes_per_query: int = 5,
) -> dict[str, Any]:
    """
    Run follow-up queries when Phase 2 critique fails.

    Args:
        max_follow_up_queries: Maximum follow-up queries to execute (default 2)
        refine_vector_db_results: Max vector DB results per query (default 5)
        refine_pubmed_results: Max PubMed results per query (default 3)
        max_genes_per_query: Max genes to extract per query (default 5)
    """
    eval_data = state.get("phase2_eval", {})
    follow_up = eval_data.get("follow_up_queries", [])
    iteration = state.get("phase2_critic_iteration", 0) + 1

    bp_name = state.get("current_bp_name", "")
    updates: dict[str, Any] = {"phase2_critic_iteration": iteration}

    # Simple refinement: query tools and extract genes using LLM
    for query in follow_up[:max_follow_up_queries]:
        # Use the query to find more genes
        vector_results = query_vector_db(query=query, top_k=refine_vector_db_results)
        pubmed_results = query_pubmed(query=query, retmax=refine_pubmed_results)

        # Collect text for LLM extraction
        extraction_context = []
        for vec in vector_results:
            extraction_context.append(f"Corpus: {vec.get('text', '')[:500]}")

        for pub in pubmed_results:
            title = pub.get('title', '')
            abstract = pub.get('abstract', '')
            extraction_context.append(f"PubMed: {title}\n{abstract[:400]}")

        if not extraction_context:
            continue

        # Use LLM to extract actual gene symbols
        llm = get_llm()

        extraction_prompt = f"""## Text from Literature Search

        Query: {query}

        {" ".join(extraction_context)}

        ## Task
        Extract gene symbols mentioned in the text above that are relevant to: {bp_name}

        Return ONLY a JSON array of gene symbols (e.g., ["TP53", "FOXO3"]).
        """

        extraction_schema = {
            "title": "gene_symbols",
            "type": "array",
            "items": {"type": "string"},
        }

        try:
            extracted_genes = llm.invoke_structured(
                extraction_prompt,
                schema=extraction_schema,
                system_prompt="You are a gene symbol extractor. Return only standard gene symbols."
            )

            # Create gene entries
            new_genes = [
                {
                    "gene_symbol": gene,
                    "score": 6,
                    "biological_process": bp_name,
                    "evidence_summary": f"Found via follow-up query: {query}",
                    "sources": ["refinement"],
                }
                for gene in extracted_genes[:max_genes_per_query]
            ]

            if new_genes:
                updates["genes_found"] = new_genes

        except Exception:
            # Fallback: skip gene extraction on failure
            pass

    return updates


def map_go_terms(state: dict[str, Any], max_results: int = 10) -> dict[str, Any]:
    """
    Map GO biological process terms using LLM for relevance scoring.

    Process:
    1. Query GO database for terms
    2. Pass results to LLM
    3. LLM scores relevance and filters
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")

    # Query GO terms
    go_results = query_go_terms(query=bp_name, max_results=20)

    if not go_results:
        return {"go_terms_found": []}

    # User message contains the GO terms data
    user_context = f"""## GO Terms to Evaluate

                        {json.dumps(go_results, indent=2)}

                        For each GO term, provide:
                        - go_id (exactly as provided)
                        - go_label (exactly as provided)
                        - relevance_score (1-10, only include terms with score 6+)
                        - evidence_summary (1-2 sentences explaining relevance)

                        Return a JSON array.
                        """

    # System prompt with instructions
    system_prompt = PHASE2_GO_MAPPING_SYSTEM_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark
    )

    llm = get_llm()

    try:
        schema = {
            "title": "go_terms",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "go_id": {"type": "string"},
                    "go_label": {"type": "string"},
                    "relevance_score": {"type": "integer"},
                    "evidence_summary": {"type": "string"},
                },
                "required": ["go_id", "go_label", "relevance_score", "evidence_summary"],
            },
        }

        scored_terms = llm.invoke_structured(
            user_context,
            schema=schema,
            system_prompt=system_prompt
        )

    except Exception:
        # Fallback: return all terms with default relevance score
        scored_terms = [
            {
                "go_id": term.get("go_id", ""),
                "go_label": term.get("name", ""),
                "relevance_score": 7,  # Default moderate relevance
                "evidence_summary": f"Matched query '{bp_name}'",
            }
            for term in go_results[:10]
        ]

    # Add definition and biological_process
    for term in scored_terms:
        # Find original definition
        go_id = term.get("go_id", "")
        original = next((g for g in go_results if g.get("go_id") == go_id), {})
        term["definition"] = original.get("definition", "")
        term["biological_process"] = bp_name
        term["sources"] = [go_id]

    return {"go_terms_found": scored_terms}


def advance_bp(state: dict[str, Any]) -> dict[str, Any]:
    """Advance to the next biological process."""
    # Log BP completion with scratchpad snapshot for audit trail
    bp_name = state.get("current_bp_name", "")
    hallmark = state.get("hallmark_name", "")

    if bp_name:
        # Get genes found for this BP
        all_genes = state.get("genes_found", [])
        bp_genes = [g for g in all_genes if g.get("biological_process") == bp_name]

        log_event({
            "hallmark": hallmark,
            "event_type": "bp_research_complete",
            "bp_name": bp_name,
            "research_scratchpad": state.get("research_scratchpad", ""),
            "genes_count": len(bp_genes),
            "iteration": state.get("phase2_research_iteration", 0),
        })

    return {
        "current_bp_index": state.get("current_bp_index", 0) + 1,
        "current_bp_name": "",
        "research_scratchpad": "",
        "phase2_critic_iteration": 0,
        "phase2_research_iteration": 0,  # Also reset research iteration for next BP
    }
