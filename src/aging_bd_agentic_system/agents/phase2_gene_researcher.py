"""
Phase 2 Agent: Gene Research and GO Term Mapping

Uses LLM-powered reasoning to identify genes and GO terms for biological processes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from pdb import set_trace

from aging_bd_agentic_system.agents.phase2_helpers import (
    _get_genage_lookup,
    _load_genage_csv,
    generate_opengenes_seed_queries,
    normalize_seed_candidates,
    select_genage_seed_genes,
    summarize_seed_evidence,
)
from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.prompts.phase2_prompts import (
    PHASE2_CRITIQUE_SYSTEM_PROMPT,
    PHASE2_DECIDE_PROMPT,
    PHASE2_DECISION_USER_PROMPT,
    PHASE2_GO_MAPPING_SYSTEM_PROMPT,
    PHASE2_RESEARCH_SYSTEM_PROMPT,
    PHASE2_SCORING_SYSTEM_PROMPT,
    PHASE2_STATE_UPDATE_PROMPT,
    PHASE2_SYNTHESIZE_PROMPT,
    PHASE2_TOOL_DESCRIPTIONS,
    PHASE2_TOOL_SUMMARIZER_PROMPT,
)
from aging_bd_agentic_system.tools import (
    query_go_terms,
    query_opengenes,
    query_pubmed,
    query_vector_db,
    query_vector_db_batch,
)
from aging_bd_agentic_system.utils.audit_logger import log_event
from aging_bd_agentic_system.utils.context_manager import summarize_if_needed


# ===== GRAPH NODE FUNCTIONS =====

def select_bp(state: dict[str, Any]) -> dict[str, Any]:
    """Select the current biological process from the queue."""
    bp_queue = state.get("bp_queue", [])
    index = state.get("current_bp_index", 0)

    if index >= len(bp_queue):
        return {}  # Signal to exit loop

    return {"current_bp_name": bp_queue[index]}


def phase2_seeding(state: dict[str, Any]) -> dict[str, Any]:
    """
    Generate seed genes from GenAge and OpenGenes for a biological process.

    This is iteration 0 of the Phase 2 research loop. It:
    1. Selects relevant genes from GenAge using LLM
    2. Generates OpenGenes queries using LLM
    3. Queries OpenGenes with those queries
    4. Normalizes and deduplicates candidates
    5. Summarizes evidence via LLM
    6. Persists seeds and queries to disk
    7. Initializes the research scratchpad

    Returns:
        Dict with research_scratchpad (JSON) and phase2_research_iteration set to 1
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")
    cfg = state.get("config", {})
    p2 = cfg.get("phase2", {})
    opengenes_seed_results_per_query = p2.get("opengenes_seed_results_per_query", 15)

    print(f"\n{'='*60}")
    print(f"SEEDING: {bp_name}")
    print(f"{'='*60}")

    # Load GenAge CSV data
    genage_csv_data = _load_genage_csv()

    # Step 1: Select genes directly from GenAge using LLM
    print("  Selecting GenAge genes via LLM...")
    genage_gene_symbols = select_genage_seed_genes(bp_name, hallmark, genage_csv_data)
    print(f"{len(genage_gene_symbols)} GenAge genes selected: {genage_gene_symbols}")

    # Step 2: Generate queries for OpenGenes using LLM
    print("  Generating OpenGenes queries via LLM...")
    opengenes_queries = generate_opengenes_seed_queries(bp_name, hallmark)
    print(f"{len(opengenes_queries)}  OpenGenes queries: {opengenes_queries}")

    # Build candidate list
    candidates = []

    # Add GenAge genes (lookup from cached GenAge data)
    genage_lookup = _get_genage_lookup()
    for symbol in genage_gene_symbols:
        if symbol in genage_lookup:
            rec = genage_lookup[symbol]
            candidates.append(
                {
                    "symbol": symbol,
                    "name": rec.get("name", ""),
                    "source": "genage",
                    "evidence": rec.get("why", ""),
                }
            )

    # Query OpenGenes with each generated query
    # Note: OpenGenes API requires comma-separated terms, not space-separated
    # Convert "DNA sensing" -> "DNA, sensing" for better results
    for query in opengenes_queries:
        formatted_query = query.replace(" ", ", ")
        opengenes_results = query_opengenes(query=formatted_query, max_results=opengenes_seed_results_per_query)
        print(f"    OpenGenes '{formatted_query}': {len(opengenes_results)} results")
        for rec in opengenes_results:
            symbol = rec.get("symbol")
            candidates.append(
                {
                    "symbol": symbol,
                    "name": rec.get("name", ""),
                    "source": "opengenes",
                    "aging_mechanisms": rec.get("agingMechanisms", []),
                    "functional_clusters": rec.get("functionalClusters", []),
                    "protein_classes": rec.get("proteinClasses", []),
                    "evidence_causes": rec.get("commentCause", []),
                    "query_used": query,
                }
            )

    print(f"\n  Raw candidates: {len(candidates)}")
    print(f"    - GenAge: {len([c for c in candidates if c['source'] == 'genage'])}")
    print(f"    - OpenGenes: {len([c for c in candidates if c['source'] == 'opengenes'])}")

    # Normalize and deduplicate candidates
    candidates = normalize_seed_candidates(candidates)

    # Count by source type
    genage_only = len([c for c in candidates if c['source'] == 'genage'])
    opengenes_only = len([c for c in candidates if c['source'] == 'opengenes'])
    both = len([c for c in candidates if c['source'] == 'genage, opengenes'])

    print(f"\n  Normalized: {len(candidates)} unique genes")
    print(f"    - GenAge only: {genage_only}")
    print(f"    - OpenGenes only: {opengenes_only}")
    print(f"    - Both: {both}")

    # Summarize evidence via LLM
    print(f"\n  Summarizing evidence...")
    candidates = summarize_seed_evidence(candidates, bp_name, hallmark)
    print(f"  Evidence summarization complete")
    print(f"{'='*60}\n")

    # Persist seed genes to disk
    bp_rank = state.get("current_bp_index", 0) + 1  # 1-indexed
    output_dir = Path(cfg.get("output_dir", "outputs"))
    seed_file = output_dir / hallmark / f"bp{bp_rank}_seed_genes.json"
    seed_file.parent.mkdir(parents=True, exist_ok=True)
    with seed_file.open("w") as f:
        json.dump(candidates, f, indent=2)
    print(f"  Saved seed genes to: {seed_file}")

    # Persist seeding queries to disk
    queries_file = output_dir / hallmark / f"bp{bp_rank}_seeding_queries.json"
    with queries_file.open("w") as f:
        json.dump({"opengenes_queries": opengenes_queries}, f, indent=2)
    print(f"  Saved seeding queries to: {queries_file}")

    # Store in scratchpad as structured JSON
    research_data = {
        "initial_database_genes": candidates,
        "opengenes_seeding_queries": opengenes_queries,
        "research_findings": [],
    }

    # Initialize state_of_knowledge from seeds
    candidate_genes = [c.get("symbol") for c in candidates if c.get("symbol")]
    citations = []
    for c in candidates:
        source = c.get("source", "")
        symbol = c.get("symbol", "")
        if "genage" in source:
            citations.append(f"genage:{symbol}")
        if "opengenes" in source:
            citations.append(f"opengenes:{symbol}")

    state_of_knowledge = {
        "candidate_genes": candidate_genes,
        "citations": list(set(citations)),
        "summary": "",  # Populated after first research iteration
    }

    # Initialize gene_evidence from seeds
    gene_evidence = {}
    for c in candidates:
        symbol = c.get("symbol", "")
        if not symbol:
            continue
        source = c.get("source", "").lower()
        gene_evidence[symbol] = {
            "opengenes": "opengenes" in source,
            "genage": "genage" in source,
            "evidence_notes": [],  # Populated during research iterations
            "citations": [f"{source}:{symbol}"],
        }

    # Persist gene_evidence to disk
    evidence_file = output_dir / hallmark / f"bp{bp_rank}_gene_evidence.json"
    with evidence_file.open("w") as f:
        json.dump(gene_evidence, f, indent=2)
    print(f"  Saved gene evidence to: {evidence_file}")

    # Persist state_of_knowledge to disk
    sok_file = output_dir / hallmark / f"bp{bp_rank}_state_of_knowledge.json"
    with sok_file.open("w") as f:
        json.dump(state_of_knowledge, f, indent=2)
    print(f"  Saved state_of_knowledge to: {sok_file}")

    return {
        "research_scratchpad": json.dumps(research_data, default=str),
        "phase2_research_iteration": 1,
        "state_of_knowledge": json.dumps(state_of_knowledge),
        "gene_evidence": gene_evidence,
    }


def phase2_research(state: dict[str, Any]) -> dict[str, Any]:
    """
    Autonomous ReAct research loop for gene discovery.

    This function runs a multi-iteration research loop where the LLM scientist agent:
    1. Queries all 4 sources (GenAge, OpenGenes, PubMed, Vector DB)
    2. Decides what to search for based on findings
    3. Shifts from exploration → exploitation over iterations
    4. Synthesizes and scores genes at the end

    Config read from state["config"]["phase2"]:
    - max_research_iterations: Max iterations (default 7)
    - genage_seed_max_results: GenAge results during seeding (default 50)
    - opengenes_seed_results_per_query: OpenGenes results per query during seeding (default 15)
    - pubmed_max_results: PubMed results per action (default 5)
    - vector_db_max_results: Vector DB results per action (default 5)

    Returns:
        Genes with scores (5+ only) and evidence summaries
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")

    # Read config from state
    cfg = state.get("config", {})
    p2 = cfg.get("phase2", {})
    max_iterations = p2.get("max_research_iterations", 7)
    genage_seed_max_results = p2.get("genage_seed_max_results", 50)
    opengenes_seed_results_per_query = p2.get("opengenes_seed_results_per_query", 15)
    vector_db_top_k = p2.get("phase2_vector_db_top_k", 10)
    pubmed_retmax = p2.get("phase2_pubmed_retmax", 10)
    summarize_max_tokens = p2.get("phase2_summarize_max_tokens", 100000)
    min_actions_per_iteration = p2.get("min_actions_per_iteration", 2)
    max_actions_per_iteration = p2.get("max_actions_per_iteration", 4)

    # Get current iteration
    current_iteration = state.get("phase2_research_iteration", 0)
    print(f"\n=== Phase 2 Research Iteration {current_iteration}/{max_iterations} ===")

    # Iteration 0: Seeding
    if current_iteration == 0:
        return phase2_seeding(state)

    # Load current research state
    try:
        research_data = json.loads(state.get("research_scratchpad", "{}"))
    except json.JSONDecodeError:
        research_data = {"initial_database_genes": [], "opengenes_seeding_queries": [], "research_findings": []}

    # Load state_of_knowledge (compressed context for LLM)
    try:
        state_of_knowledge = json.loads(state.get("state_of_knowledge", "{}"))
    except json.JSONDecodeError:
        state_of_knowledge = {"candidate_genes": [], "citations": [], "summary": ""}

    # Load gene_evidence (structured per-gene evidence accumulator)
    gene_evidence = state.get("gene_evidence", {})
    
    # Add context management; summarize only if we have research findings 
    # no need to compress structured seeding data 
    # if research_data["research_findings"]:
    #     context_updates = summarize_if_needed(state, max_tokens=summarize_max_tokens)
    #     if context_updates:
    #         state.update(context_updates)
    
    
    # Determine research phase based on iteration (dynamic boundaries)
    exploration_end = max(1, int(max_iterations * 0.3))
    rabbit_hole_end = max(exploration_end + 1, int(max_iterations * 0.6))
    if current_iteration <= exploration_end:
        phase = "exploration"
        guidance = (
            "Cast a wide net. Query all 3 sources with broad terms. "
            "Note what looks interesting."
        )
    elif current_iteration <= rabbit_hole_end:
        phase = "rabbit_hole"
        guidance = (
            "Follow interesting leads you found. Search for specific genes "
            "or terms that keep appearing."
        )
    elif current_iteration < max_iterations:
        phase = "exploitation"
        guidance = "Deepen your findings. Fill gaps in weak evidence. Cross-reference."
    else:
        phase = "finalization"
        guidance = (
            "Synthesize all findings. Score genes 1-10. "
            "Return only genes with score 5+."
        )

    # Build seed genes summary (genes + evidence from seeding)
    seed_genes = research_data.get("initial_database_genes", [])
    seed_genes_summary = json.dumps(
        [{"symbol": g.get("symbol"), "evidence": g.get("evidence", "")} for g in seed_genes],
        indent=2,
    )

    # ===== TWO-STEP RESEARCH DECISION PROCESS =====

    # Step 1: Synthesize research priorities (free-form invoke)
    print(f"Summarizing current state of knowledge..")
    llm = get_llm()
    synthesize_prompt = PHASE2_SYNTHESIZE_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        current_iteration=current_iteration,
        max_iterations=max_iterations,
        phase=phase.upper(),
        guidance=guidance,
        candidate_genes=", ".join(state_of_knowledge.get("candidate_genes", [])),
        citations=", ".join(state_of_knowledge.get("citations", [])),
        summary=state_of_knowledge.get("summary", "No summary yet."),
    )
    research_priorities = llm.invoke(synthesize_prompt)

    # Step 2: Decide tool calls (structured invoke)
    decision_schema = {
        "title": "research_decision",
        "type": "object",
        "properties": {
            "opengenes_queries": {
                "type": "array",
                "minItems": 2,  # Seeding already done, use sparingly
                "maxItems": 4,
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
                "minItems": min_actions_per_iteration,
                "maxItems": max_actions_per_iteration,
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
                "minItems": min_actions_per_iteration,
                "maxItems": max_actions_per_iteration,
                "items": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["query", "reason"],
                },
            },
            "findings_notes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["opengenes_queries", "pubmed_queries", "vector_db_queries", "findings_notes"],
    }

    decision_prompt = PHASE2_DECIDE_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        current_iteration=current_iteration,
        max_iterations=max_iterations,
        phase=phase.upper(),
        guidance=guidance,
        research_priorities=research_priorities,
        min_opengenes=2,
        max_opengenes=4,
        min_pubmed=min_actions_per_iteration,
        max_pubmed=max_actions_per_iteration,
        min_vectordb=min_actions_per_iteration,
        max_vectordb=max_actions_per_iteration,
    )

    print(f"Deciding on research tool calls..")
    decisions = llm.invoke_structured(decision_prompt, schema=decision_schema)
    findings_notes = decisions['findings_notes'] 
    
    # Build findings summary (from research iterations)
    findings = research_data.get("research_findings", [])
    if findings:
        findings_summary = json.dumps(findings, indent=2)
    else:
        findings_summary = "No research findings yet."
    

    # Execute the research actions
    new_findings = []

    # Initialize summaries (may remain None if no findings)
    opengenes_summary = None
    pubmed_summary = None
    vectordb_summary = None

    # Process OpenGenes queries
    print("Collecting and summarizing from opengenes..")
    opengenes_findings = []
    for action in decisions.get("opengenes_queries", []):
        query = action.get("query")
        formatted_query = query.replace(" ", ", ")
        results = query_opengenes(query=formatted_query, max_results=15)
        for rec in results:
            mechanisms = rec.get("agingMechanisms", [])
            clusters = rec.get("functionalClusters", [])
            proteins = rec.get("proteinClasses", [])
            causes = rec.get("commentCause", [])
            finding_text = f"OpenGenes - Mechanisms: {mechanisms}; Clusters: {clusters}; Proteins: {proteins}; Evidence: {causes}"

            finding = {
                "source": "opengenes",
                "gene": rec.get("symbol"),
                "query": query,
                "finding": finding_text,
            }
            new_findings.append(finding)
            opengenes_findings.append(finding)

    # Summarize OpenGenes results
    if opengenes_findings:
        summarizer_schema = {
            "title": "tool_summary",
            "type": "object",
            "properties": {
                "genes_mentioned": {"type": "array", "items": {"type": "string"}},
                "key_findings": {"type": "array", "items": {"type": "string"}},
                "citations": {"type": "array", "items": {"type": "string"}},
                "relevance_to_process": {"type": "string"},
            },
            "required": ["genes_mentioned", "key_findings", "citations", "relevance_to_process"],
        }
        summarizer_system = PHASE2_TOOL_SUMMARIZER_PROMPT.format(
            biological_process=bp_name,
            hallmark_name=hallmark,
            current_iteration=current_iteration,
            max_iterations=max_iterations,
            phase=phase.upper(),
            candidate_genes=", ".join(state_of_knowledge.get("candidate_genes", [])),
        )
        user_prompt = f"""## Source: OpenGenes

                        ## Raw Results ({len(opengenes_findings)} records)
                        {json.dumps(opengenes_findings, indent=2)}

                        Summarize these OpenGenes results. Extract genes, key findings about aging mechanisms, and citations (format: opengenes:GENE_SYMBOL)."""
        
        opengenes_summary = llm.invoke_structured(user_prompt, schema=summarizer_schema)

    # Process PubMed queries
    print("Collecting and summarizing from PubMed queries..")
    pubmed_findings = []
    for action in decisions.get("pubmed_queries", []):
        query = action.get("query")
        results = query_pubmed(query=query, retmax=pubmed_retmax)
        for rec in results:
            pmid = rec.get("pmid", "pubmed")

            finding = {
                "source": f"pmid:{pmid}",
                "gene": None,  # May or may not mention a gene
                "query": query,
                "finding": f"{rec.get('title', '')}: {rec.get('abstract', '')[:200]}",
            }
            new_findings.append(finding)
            pubmed_findings.append(finding)

    # Summarize PubMed results
    if pubmed_findings:
        user_prompt = f"""## Source: PubMed

                        ## Raw Results ({len(pubmed_findings)} articles)
                        {json.dumps(pubmed_findings, indent=2)}

                        Summarize these PubMed results. Extract genes mentioned, key findings, and citations (format: pmid:12345678)."""
        pubmed_summary = llm.invoke_structured(user_prompt, schema=summarizer_schema)

    # Process Vector DB queries (batched)
    print("Collecting and summarizing from local literature corpus..")
    vectordb_findings = []
    vector_db_queries = [a.get("query") for a in decisions.get("vector_db_queries", [])]
    if vector_db_queries:
        batched_results = query_vector_db_batch(queries=vector_db_queries, top_k=vector_db_top_k)
        for query, results in zip(vector_db_queries, batched_results):
            for rec in results:
                pmid = rec.get("pmid", "pubmed")
                finding = {
                    "source": f"pmid:{pmid}",
                    "gene": None,
                    "query": query,
                    "finding": rec.get("text", "")[:300],
                }
                new_findings.append(finding)
                vectordb_findings.append(finding)

    # Summarize Vector DB results
    if vectordb_findings:
        user_prompt = f"""## Source: Vector DB (Literature Corpus)

                        ## Raw Results ({len(vectordb_findings)} passages)
                        {json.dumps(vectordb_findings, indent=2)}

                        Summarize these corpus results. Extract genes mentioned, mechanistic insights, and citations (format: pmid:XXXXX - use the pmid from the source field)."""
        vectordb_summary = llm.invoke_structured(user_prompt, schema=summarizer_schema)

    # ===== STEP 5: UPDATE STATE OF KNOWLEDGE =====
    print("Synthesizing findings and updating state of knowledge...")

    # Collect all genes mentioned this iteration
    all_genes_mentioned = set()
    for summary in [opengenes_summary, pubmed_summary, vectordb_summary]:
        if summary:
            all_genes_mentioned.update(summary.get("genes_mentioned", []))

    # Filter gene_evidence to only relevant genes
    gene_evidence_subset = {
        gene: gene_evidence.get(gene, {"opengenes": False, "genage": False, "evidence_notes": "", "citations": []})
        for gene in all_genes_mentioned
    }

    # Schema for state update
    state_update_schema = {
        "title": "state_update",
        "type": "object",
        "properties": {
            "new_candidate_genes": {"type": "array", "items": {"type": "string"}},
            "new_citations": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
            "gene_evidence_updates": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "evidence_notes": {"type": "string"},
                        "new_citations": {"type": "array", "items": {"type": "string"}},
                        "sources_found": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["evidence_notes", "new_citations", "sources_found"],
                },
            },
        },
        "required": ["new_candidate_genes", "new_citations", "summary", "gene_evidence_updates"],
    }
    
    # Build state update prompt
    state_update_prompt = PHASE2_STATE_UPDATE_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        current_iteration=current_iteration,
        max_iterations=max_iterations,
        phase=phase.upper(),
        candidate_genes=", ".join(state_of_knowledge.get("candidate_genes", [])),
        citations=", ".join(state_of_knowledge.get("citations", [])),
        current_summary=state_of_knowledge.get("summary", "No summary yet."),
        opengenes_summary=json.dumps(opengenes_summary, indent=2) if opengenes_summary else "{}",
        pubmed_summary=json.dumps(pubmed_summary, indent=2) if pubmed_summary else "{}",
        vectordb_summary=json.dumps(vectordb_summary, indent=2) if vectordb_summary else "{}",
        gene_evidence_subset=json.dumps(gene_evidence_subset, indent=2),
    )
    
    state_update = llm.invoke_structured(state_update_prompt, schema=state_update_schema)

    # Apply updates to state_of_knowledge
    new_genes = state_update.get("new_candidate_genes", [])
    if new_genes:
        state_of_knowledge["candidate_genes"].extend(new_genes)
        state_of_knowledge["candidate_genes"] = list(set(state_of_knowledge["candidate_genes"]))

    new_citations = state_update.get("new_citations", [])
    if new_citations:
        state_of_knowledge["citations"].extend(new_citations)
        state_of_knowledge["citations"] = list(set(state_of_knowledge["citations"]))

    state_of_knowledge["summary"] = state_update.get("summary", "")

    # Apply updates to gene_evidence
    gene_evidence_updates = state_update.get("gene_evidence_updates", {})
    
    for gene, update in gene_evidence_updates.items():
        if not isinstance(update, dict):
            print(f"  Warning: gene_evidence_updates[{gene}] is {type(update).__name__}, skipping")
            continue

        if gene not in gene_evidence:
            gene_evidence[gene] = {"opengenes": False, "genage": False, "evidence_notes": "", "citations": []}

        # Replace evidence_notes
        gene_evidence[gene]["evidence_notes"] = update.get("evidence_notes", "")

        # Append citations (dedupe)
        gene_evidence[gene]["citations"].extend(update.get("new_citations", []))
        gene_evidence[gene]["citations"] = list(set(gene_evidence[gene]["citations"]))

        # OR the source flags
        for src in update.get("sources_found", []):
            src_lower = src.lower()
            if src_lower in gene_evidence[gene]:
                gene_evidence[gene][src_lower] = True

    print(f"  Updated state: {len(new_genes)} new genes, {len(new_citations)} new citations")


    # Update research data
    research_data["research_findings"].extend(new_findings)

    # Log findings_notes for audit
    for note in findings_notes:
        formatted_note = f"  [it={current_iteration}] {note}"
        print(formatted_note)
        research_data.setdefault("reasoning_notes", []).append(formatted_note)

    # Always increment iteration after research
    #next_iteration = current_iteration + 1

    # After final research iteration, score genes
    if current_iteration == max_iterations:
        
        scoring_prompt = PHASE2_SCORING_SYSTEM_PROMPT.format(
            biological_process=bp_name,
            hallmark_name=hallmark,
            research_summary=state_of_knowledge.get("summary", "No summary available."),
            gene_evidence=json.dumps(gene_evidence, indent=2),
        )
        scored_genes_schema = {
            "title": "scored_genes_response",
            "type": "object",
            "properties": {
                "genes": {
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
                },
            },
            "required": ["genes"],
        }
        print("Finalize initial research. Score available genes...")
        
        try:
            response = llm.invoke_structured(scoring_prompt, schema=scored_genes_schema)
            scored_genes = response.get("genes", [])
        except Exception:
            scored_genes = []
        for gene in scored_genes:
            gene["biological_process"] = bp_name
        
        return {
            "genes_found": scored_genes,
            "research_scratchpad": json.dumps(research_data, default=str),
            "phase2_research_iteration": 0,
            "state_of_knowledge": json.dumps(state_of_knowledge),
            "gene_evidence": gene_evidence,
        }

    # Continue research loop - persist state for next iteration
    return {
        "research_scratchpad": json.dumps(research_data, default=str),
        "phase2_research_iteration": current_iteration+1,
        "state_of_knowledge": json.dumps(state_of_knowledge),
        "gene_evidence": gene_evidence,
    }


def phase2_critic(state: dict[str, Any]) -> dict[str, Any]:
    """
    Use LLM to evaluate gene evidence coverage for the current BP.

    LLM judges:
    - Are there enough genes?
    - Is evidence strong?
    - Are genes relevant to the BP?
    """
    bp_name = state.get("current_bp_name", "")
    min_genes_expected = 20  # Fixed threshold

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
        genes_json="{GENES_JSON}",  # Placeholder
    )

    # Remove the genes_json from system prompt since it's now in user message
    system_prompt = system_prompt.replace(
        "{genes_json}", "See the genes in the user message."
    )

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
            user_context, schema=schema, system_prompt=system_prompt
        )

    except Exception:
        # Fallback: simple rule-based evaluation
        gene_count = len(bp_genes)
        eval_result = {
            "grade": "pass" if gene_count >= min_genes_expected else "fail",
            "comment": f"Found {gene_count} genes (expected {min_genes_expected}+).",
            "follow_up_queries": [f"{bp_name} additional genes"]
            if gene_count < min_genes_expected
            else [],
        }

    eval_result["min_genes_expected"] = min_genes_expected
    return {"phase2_eval": eval_result}


def phase2_refine(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run follow-up queries when Phase 2 critique fails.
    """
    # Fixed refinement parameters
    max_follow_up_queries = 2
    refine_vector_db_results = 5
    refine_pubmed_results = 3
    max_genes_per_query = 5

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
            title = pub.get("title", "")
            abstract = pub.get("abstract", "")
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
                system_prompt="You are a gene symbol extractor. Return only standard gene symbols.",
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


def map_go_terms(state: dict[str, Any]) -> dict[str, Any]:
    """
    Map GO biological process terms using LLM for relevance scoring.

    Process:
    1. Query GO database for terms
    2. Pass results to LLM
    3. LLM scores relevance and filters
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")
    max_results = 10  # Fixed max results

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
        biological_process=bp_name, hallmark_name=hallmark
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
                "required": [
                    "go_id",
                    "go_label",
                    "relevance_score",
                    "evidence_summary",
                ],
            },
        }

        scored_terms = llm.invoke_structured(
            user_context, schema=schema, system_prompt=system_prompt
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
    cfg = state.get("config", {})
    output_dir = cfg.get("output_dir", "outputs")

    if bp_name:
        # Get genes found for this BP
        all_genes = state.get("genes_found", [])
        bp_genes = [g for g in all_genes if g.get("biological_process") == bp_name]

        log_event(
            {
                "hallmark": hallmark,
                "event_type": "bp_research_complete",
                "bp_name": bp_name,
                "research_scratchpad": state.get("research_scratchpad", ""),
                "genes_count": len(bp_genes),
                "iteration": state.get("phase2_research_iteration", 0),
            },
            output_dir=output_dir,
        )

    return {
        "current_bp_index": state.get("current_bp_index", 0) + 1,
        "current_bp_name": "",
        "research_scratchpad": "",
        "phase2_critic_iteration": 0,
        "phase2_research_iteration": 0,  # Also reset research iteration for next BP
    }
