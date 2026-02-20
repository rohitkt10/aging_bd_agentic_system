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
    PHASE2_CRITIQUE_PROMPT,
    PHASE2_GO_MAPPING_PROMPT,
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


def phase2_research(state: dict[str, Any], gene_limit: int = 30) -> dict[str, Any]:
    """
    Autonomous ReAct research loop for gene discovery.

    This function runs a multi-iteration research loop where the LLM scientist agent:
    1. Queries all 4 sources (GenAge, OpenGenes, PubMed, Vector DB)
    2. Decides what to search for based on findings
    3. Shifts from exploration → exploitation over iterations
    4. Synthesizes and scores genes at the end

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
        genage_results = query_genage(query=bp_name, max_results=50)
        opengenes_results = query_opengenes(query=bp_name, max_results=50)

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
                    "longevity_score": rec.get("longevity_effect", ""),
                })

        for rec in opengenes_results:
            symbol = rec.get("symbol")
            if symbol and symbol not in seen:
                seen.add(symbol)
                candidates.append({
                    "symbol": symbol,
                    "name": rec.get("name", ""),
                    "source": "opengenes",
                    "intervention": rec.get("intervention", ""),
                })

        # Store in scratchpad as structured JSON
        research_data = {
            "candidates": candidates,
            "findings": [],  # Accumulated findings from iterations
            "searched_genes": list(),  # Genes we've already researched
        }
        return {
            "research_scratchpad": json.dumps(research_data, default=str),
            "phase2_research_iteration": 1
        }

    # Load current research state
    try:
        research_data = json.loads(state.get("research_scratchpad", "{}"))
    except json.JSONDecodeError:
        research_data = {"candidates": [], "findings": [], "searched_genes": []}

    # Add context management
    from aging_bd_agentic_system.utils.context_manager import summarize_if_needed

    context_updates = summarize_if_needed(state)
    if context_updates:
        state.update(context_updates)

    llm = get_llm()

    # Determine research phase based on iteration
    if current_iteration <= 2:
        phase = "exploration"
        guidance = "Cast a wide net. Query all 4 sources with broad terms. Note what looks interesting."
    elif current_iteration <= 4:
        phase = "rabbit_hole"
        guidance = "Follow interesting leads you found. Search for specific genes or terms that keep appearing."
    elif current_iteration < max_iterations:
        phase = "exploitation"
        guidance = "Deepen your findings. Fill gaps in weak evidence. Cross-reference."
    else:
        phase = "finalization"
        guidance = "Synthesize all findings. Score genes 1-10. Return only genes with score 5+."

    # Build research summary for LLM - use RECENT findings, not first findings
    findings_summary = json.dumps(research_data.get("findings", [])[-10:], indent=2)
    candidates_summary = json.dumps([c["symbol"] for c in research_data.get("candidates", [])[:20]], indent=2)

    # Build context with summary if available
    context_parts = []
    if state.get("context_summary"):
        context_parts.append(f"## Previous Research Summary\n{state['context_summary']}")
    context_parts.append(f"## Recent Findings\n{findings_summary}")

    # Create system prompt for this iteration
    research_prompt = f"""You are a gene research scientist studying "{bp_name}" as part of aging hallmark "{hallmark}".

## Research Phase: {phase.upper()}
{guidance}

## Current State
- Iteration: {current_iteration} of {max_iterations}
- Candidates identified so far: {candidates_summary}

{"\n".join(context_parts)}

## Available Tools
1. query_genage - Search GenAge database for longevity genes
2. query_opengenes - Search OpenGenes database for intervention effects
3. query_pubmed - Search PubMed for literature
4. query_vector_db - Search local literature corpus

## Your Task
Based on the phase and current findings:
1. Decide which source(s) to query
2. Decide what search terms to use
3. Call the appropriate tools
4. Record your findings

## Tools Information
- GenAge: Contains genes with longevity associations and scores
- OpenGenes: Contains genes with lifespan intervention data
- PubMed: Use for recent literature and specific gene-term associations
- Corpus: Use for broad contextual information and mechanistic insights

If this is the final iteration (iteration {max_iterations}), output a FINAL_SUMMARY with scored genes.
"""

    # Prompt LLM to decide what to research
    decision_prompt = f"""{research_prompt}

Based on the current phase ({phase}), what should you search for?

Return JSON:
```json
{{
  "actions": [
    {{"source": "genage|opengenes|pubmed|vector_db", "query": "search term", "reason": "why"}}
  ],
  "findings_notes": ["interesting observation 1", "interesting observation 2"]
}}
```

Be specific with your queries. Use 1-3 actions per iteration.
"""

    response = llm.invoke(decision_prompt)

    # Parse LLM's research decisions
    try:
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            decisions = json.loads(json_str)
        else:
            decisions = {"actions": [], "findings_notes": []}
    except json.JSONDecodeError:
        decisions = {"actions": [], "findings_notes": []}

    # Execute the research actions
    new_findings = []

    for action in decisions.get("actions", []):
        source = action.get("source")
        query = action.get("query")

        if source == "genage":
            results = query_genage(query=query, max_results=20)
            for rec in results[:5]:
                new_findings.append({
                    "source": "genage",
                    "gene": rec.get("symbol"),
                    "query": query,
                    "finding": f"Longevity association: {rec.get('longevity_effect', 'N/A')}"
                })

        elif source == "opengenes":
            results = query_opengenes(query=query, max_results=20)
            for rec in results[:5]:
                new_findings.append({
                    "source": "opengenes",
                    "gene": rec.get("symbol"),
                    "query": query,
                    "finding": f"Intervention: {rec.get('intervention', 'N/A')}"
                })

        elif source == "pubmed":
            results = query_pubmed(query=query, retmax=10)
            for rec in results[:5]:
                new_findings.append({
                    "source": "pubmed",
                    "gene": None,  # May or may not mention a gene
                    "query": query,
                    "finding": f"{rec.get('title', '')}: {rec.get('abstract', '')[:200]}"
                })

        elif source == "vector_db":
            results = query_vector_db(query=query, top_k=10)
            for rec in results[:5]:
                new_findings.append({
                    "source": "corpus",
                    "gene": None,
                    "query": query,
                    "finding": rec.get("text", "")[:300]
                })

    # Update research data
    research_data["findings"].extend(new_findings)
    research_data["findings"].extend(decisions.get("findings_notes", []))

    # If final iteration, synthesize and score genes
    if current_iteration >= max_iterations:
        # Prepare final summary for scoring
        all_findings = research_data.get("findings", [])
        all_candidates = research_data.get("candidates", [])

        scoring_prompt = f"""You are finalizing gene research for "{bp_name}" (part of "{hallmark}").

## All Candidates
{json.dumps([c['symbol'] for c in all_candidates], indent=2)}

## Research Findings
{json.dumps(all_findings[:50], indent=2)}

## Your Task
1. Synthesize all evidence
2. Score each gene 1-10 (only genes with score 5+)
3. Write 2-3 sentence evidence summaries
4. List sources (PMIDs, database names)

Return JSON array:
```json
[
  {{
    "gene_symbol": "TP53",
    "score": 8,
    "evidence_summary": "PMID:123 shows...",
    "sources": ["PMID:123", "GenAge"]
  }}
]
```
"""

        llm_response = llm.invoke(scoring_prompt)

        try:
            json_start = llm_response.find("[")
            json_end = llm_response.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                scored_genes = json.loads(json_str)
            else:
                scored_genes = []
        except json.JSONDecodeError:
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
    system_prompt = PHASE2_CRITIQUE_PROMPT.format(
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
        # Fallback
        response = llm.invoke(user_context, system_prompt=system_prompt)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            eval_result = json.loads(json_str)
        else:
            eval_result = {
                "grade": "pass" if len(bp_genes) >= min_genes_expected else "fail",
                "comment": f"Found {len(bp_genes)} genes",
                "follow_up_queries": [],
            }

    eval_result["min_genes_expected"] = min_genes_expected
    return {"phase2_eval": eval_result}


def phase2_refine(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run follow-up queries when Phase 2 critique fails.
    """
    eval_data = state.get("phase2_eval", {})
    follow_up = eval_data.get("follow_up_queries", [])
    iteration = state.get("phase2_iteration", 0) + 1

    bp_name = state.get("current_bp_name", "")
    updates: dict[str, Any] = {"phase2_iteration": iteration}

    # Simple refinement: query tools and append results
    for query in follow_up[:2]:
        # Use the query to find more genes
        vector_results = query_vector_db(query=query, top_k=5)
        pubmed_results = query_pubmed(query=query, retmax=3)

        # Extract gene mentions from results
        # This is a simple heuristic; could be improved with LLM extraction
        new_genes = []

        for vec in vector_results:
            text = vec.get("text", "")
            # Simple gene mention extraction (capitalized words)
            words = text.split()
            potential_genes = [w for w in words if w.isupper() and len(w) <= 10]
            for gene in potential_genes[:3]:
                new_genes.append({
                    "gene_symbol": gene,
                    "score": 6,
                    "biological_process": bp_name,
                    "evidence_summary": f"Found in corpus: {query}",
                    "sources": [vec.get("pmcid", "corpus")],
                })

        if new_genes:
            updates["genes_found"] = new_genes

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
    system_prompt = PHASE2_GO_MAPPING_PROMPT.format(
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
        # Fallback to JSON parsing
        response = llm.invoke(user_context, system_prompt=system_prompt)
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            scored_terms = json.loads(json_str)
        else:
            scored_terms = []

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
        "phase2_iteration": 0,
    }
