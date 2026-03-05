"""
Phase 2 Refinement Agent: Responding to Manuscript Review

This module implements the refinement agent that responds to critic
feedback and updates the gene list.
"""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from pdb import set_trace
from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.prompts.phase2_refine_prompts import (
    REFINEMENT_RESEARCH_SUMMARIZER_PROMPT,
    REFINEMENT_ASSESSMENT_SYSTEM_PROMPT,
    REFINEMENT_ASSESSMENT_USER_PROMPT,
    REFINEMENT_STATE_UPDATE_PROMPT,
)
from aging_bd_agentic_system.prompts.phase2_prompts import PHASE2_SCORING_SYSTEM_PROMPT
from aging_bd_agentic_system.tools import (
    query_opengenes,
    query_pubmed,
    query_vector_db_batch,
)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[3] / ".env")

def phase2_refine(state: dict[str, Any]) -> dict[str, Any]:
    """
    Respond to critic review by performing additional research and updates.

    This function acts as a researcher responding to manuscript review,
    exercising judgment on reviewer suggestions and updating the draft.
    Always produces a finalized gene list (30-50 genes) as output.

    Args:
        state: Current workflow state containing the draft and critic_review.

    Returns:
        Dict with updated scored_genes, gene_evidence, state_of_knowledge,
        and refinement metadata. The output is always a finalized draft.
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name", "")
    cfg = state.get("config", {})
    p2 = cfg.get("phase2", {})

    # Read config
    refine_opengenes_max_results = p2.get("refine_opengenes_max_results", 15)
    refine_pubmed_max_results = p2.get("refine_pubmed_max_results", 10)
    refine_vector_db_top_k = p2.get("refine_vector_db_top_k", 10)
    min_genes_target = 30
    max_genes_target = 50

    # Get critic review
    critic_review = state.get("critic_review", {})
    recommendations = critic_review.get("recommendations", {})

    # Get current draft
    genes_found = state.get("genes_found", [])
    gene_evidence = state.get("gene_evidence", {})
    try:
        state_of_knowledge = json.loads(state.get("state_of_knowledge", "{}"))
    except json.JSONDecodeError:
        state_of_knowledge = {"candidate_genes": [], "citations": [], "summary": ""}

    print(f"\n{'='*60}")
    print(f"REFINE: Responding to review for {bp_name}")
    print(f"{'='*60}")
    print(f"  Current genes: {len(genes_found)}")
    print(f"  Review grade: {critic_review.get('grade', 'unknown')}")

    llm = get_llm()

    # ===== STEP 1: Assess the reviewer's feedback and plan response =====
    print("  Assessing reviewer feedback...")

    # Schema for assessment output
    assessment_schema = {
        "title": "assessment_response",
        "type": "object",
        "properties": {
            "rebuttal": {"type": "string"},
            "tool_calls": {
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
            "comments": {"type": "string"},
        },
        "required": ["rebuttal", "tool_calls", "comments"],
    }

    # Format assessment user prompt
    review_data = critic_review.get("review", {})
    assessment_user_prompt = REFINEMENT_ASSESSMENT_USER_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        gene_count=len(genes_found),
        scored_genes_json=json.dumps(genes_found, indent=2),
        review_summary=review_data.get("summary", "No summary provided."),
        review_strengths=json.dumps(review_data.get("strengths", []), indent=2),
        review_weaknesses=json.dumps(review_data.get("weaknesses", []), indent=2),
        review_recommendations=json.dumps(critic_review.get("recommendations", {}), indent=2),
    )
    try:
        assessment = llm.invoke_structured(
            assessment_user_prompt,
            schema=assessment_schema,
            system_prompt=REFINEMENT_ASSESSMENT_SYSTEM_PROMPT,
        )

        # Post-process: Ensure all three query types exist in tool_calls
        # If assessment omitted any, fall back to critic's recommendations for that source
        tool_calls = assessment.get("tool_calls", {})
        critic_recs = critic_review.get("recommendations", {})

        for query_type in ["opengenes_queries", "pubmed_queries", "vector_db_queries"]:
            if query_type not in tool_calls:
                print(f"    Warning: Assessment missing {query_type}, using critic's recommendations")
                tool_calls[query_type] = critic_recs.get(query_type, [])

        assessment["tool_calls"] = tool_calls

        print(f"    Rebuttal: {assessment['rebuttal'][:80]}...")
        print(f"    Tool calls planned: OG={len(assessment['tool_calls']['opengenes_queries'])}, "
              f"PM={len(assessment['tool_calls']['pubmed_queries'])}, "
              f"VD={len(assessment['tool_calls']['vector_db_queries'])}")
        if assessment.get("comments"):
            print(f"    Comments: {assessment['comments'][:80]}...")
        # Use assessment tool_calls instead of raw reviewer recommendations
        recommendations = assessment["tool_calls"]
    except Exception as e:
        print(f"    Warning: Assessment failed, using raw reviewer recommendations: {e}")
        recommendations = critic_review.get("recommendations", {})
    
    # ===== STEP 2: Execute queries from assessment =====
    print("  Executing planned queries...")
    
    # Summarizer schema for tool results
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

    # Define summarizer system prompt (used for all three sources)
    summarizer_system = REFINEMENT_RESEARCH_SUMMARIZER_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        scored_genes_json=json.dumps(genes_found, indent=2),
    )

    # Process OpenGenes queries
    opengenes_summary = None
    opengenes_findings = []
    for rec in recommendations.get("opengenes_queries", []): 
        query = rec.get("query", "")
        reason = rec.get("reason", "")
        if not query:
            continue
        formatted_query = query.replace(" ", ", ")
        results = query_opengenes(query=formatted_query, max_results=refine_opengenes_max_results)
        for rec_data in results:
            opengenes_findings.append({
                "source": "opengenes",
                "gene": rec_data.get("symbol"),
                "query": query,
                "finding": f"Mechanisms: {rec_data.get('agingMechanisms', [])}; Clusters: {rec_data.get('functionalClusters', [])}",
            })

    if opengenes_findings:
        user_prompt = f"""## Source: OpenGenes

                        ## Raw Results ({len(opengenes_findings)} records)
                        {json.dumps(opengenes_findings, indent=2)}

                        Summarize these OpenGenes results. Extract genes, key findings about aging mechanisms, and citations (format: opengenes:GENE_SYMBOL)."""
        try:
            print("Summarizing data retrieved from OpenGenes...")
            opengenes_summary = llm.invoke_structured(user_prompt, schema=summarizer_schema, system_prompt=summarizer_system)
            print(f"    OpenGenes: {len(opengenes_summary.get('genes_mentioned', []))} genes found")
        except Exception as e:
            print(f"    OpenGenes summarization failed: {e}")

    # Process PubMed queries
    pubmed_summary = None
    pubmed_findings = []
    for rec in recommendations.get("pubmed_queries", []):
        query = rec.get("query", "")
        if not query:
            continue
        results = query_pubmed(query=query, retmax=refine_pubmed_max_results)
        for rec_data in results:
            if rec_data.get("abstract"):
                pubmed_findings.append({
                    "source": f"pmid:{rec_data.get('pmid', 'unknown')}",
                    "gene": None,
                    "query": query,
                    "finding": f"{rec_data.get('title', '')}: {rec_data.get('abstract', '')[:500]}",
                })

    if pubmed_findings:
        user_prompt = f"""## Source: PubMed

                    ## Raw Results ({len(pubmed_findings)} articles)
                    {json.dumps(pubmed_findings, indent=2)}

                    Summarize these PubMed results. Extract genes mentioned, key findings, and citations (format: pmid:12345678)."""
        try:
            print("Summarizing data retrieved from PubMed...")
            pubmed_summary = llm.invoke_structured(user_prompt, schema=summarizer_schema, system_prompt=summarizer_system)
            print(f"    PubMed: {len(pubmed_summary.get('genes_mentioned', []))} genes found")
        except Exception as e:
            print(f"    PubMed summarization failed: {e}")

    # Process Vector DB queries
    vectordb_summary = None
    vectordb_findings = []
    vector_db_queries = [rec.get("query") for rec in recommendations.get("vector_db_queries", []) if rec.get("query")]
    if vector_db_queries:
        batched_results = query_vector_db_batch(queries=vector_db_queries, top_k=refine_vector_db_top_k)
        for query, results in zip(vector_db_queries, batched_results):
            for rec_data in results:
                vectordb_findings.append({
                    "source": f"pmid:{rec_data.get('pmid', 'unknown')}",
                    "gene": None,
                    "query": query,
                    "finding": rec_data.get("text", ""),
                })

    if vectordb_findings:
        user_prompt = f"""## Source: Vector DB (Literature Corpus)

                    ## Raw Results ({len(vectordb_findings)} passages)
                    {json.dumps(vectordb_findings, indent=2)}

                    Summarize these corpus results. Extract genes mentioned, mechanistic insights, and citations (format: pmid:XXXXX)."""
        try:
            print("Summarizing data retrieved from local vector DB...")
            vectordb_summary = llm.invoke_structured(user_prompt, schema=summarizer_schema, system_prompt=summarizer_system)
            print(f"    Vector DB: {len(vectordb_summary.get('genes_mentioned', []))} genes found")
        except Exception as e:
            print(f"    Vector DB summarization failed: {e}")
    
    # ===== STEP 3: Synthesize findings and update draft =====
    print("  Synthesizing findings and updating draft...")

    # Collect all genes mentioned this iteration
    all_genes_mentioned = set()
    for summary in [opengenes_summary, pubmed_summary, vectordb_summary]:
        if summary:
            all_genes_mentioned.update(summary.get("genes_mentioned", []))

    # Filter gene_evidence to only genes mentioned this iteration
    gene_evidence_subset = {
        gene: gene_evidence.get(gene, {"opengenes": False, "genage": False, "evidence_notes": "", "citations": []})
        for gene in all_genes_mentioned
    }

    # ===== STEP 3: State Update (synthesize findings + reviewer feedback) =====
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
    review_data = critic_review.get("review", {})
    state_update_prompt = REFINEMENT_STATE_UPDATE_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        review_summary=review_data.get("summary", "No summary provided."),
        review_strengths=json.dumps(review_data.get("strengths", []), indent=2),
        review_weaknesses=json.dumps(review_data.get("weaknesses", []), indent=2),
        candidate_genes=", ".join(state_of_knowledge.get("candidate_genes", [])),
        citations=", ".join(state_of_knowledge.get("citations", [])),
        current_summary=state_of_knowledge.get("summary", "No summary yet."),
        opengenes_summary=json.dumps(opengenes_summary, indent=2) if opengenes_summary else "{}",
        pubmed_summary=json.dumps(pubmed_summary, indent=2) if pubmed_summary else "{}",
        vectordb_summary=json.dumps(vectordb_summary, indent=2) if vectordb_summary else "{}",
        gene_evidence_subset=json.dumps(gene_evidence_subset, indent=2),
    )
    llm.set_tier("high")
    try:
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
        for gene, updates in gene_evidence_updates.items():
            if gene not in gene_evidence:
                gene_evidence[gene] = {"opengenes": False, "genage": False, "evidence_notes": "", "citations": []}
            gene_evidence[gene]["evidence_notes"] = updates.get("evidence_notes", "")
            # Merge citations
            existing_citations = set(gene_evidence[gene].get("citations", []))
            existing_citations.update(updates.get("new_citations", []))
            gene_evidence[gene]["citations"] = list(existing_citations)
            # Update source flags
            sources_found = updates.get("sources_found", [])
            if "opengenes" in sources_found:
                gene_evidence[gene]["opengenes"] = True

        print(f"  State updated: {len(new_genes)} new genes, {len(new_citations)} new citations")

    except Exception as e:
        print(f"  Warning: State update failed: {e}")
    
    llm.set_tier("low")
    
    # ===== STEP 4: Scoring (separate call, same as phase2_research) =====
    print("  Scoring genes...")

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

    scoring_prompt = PHASE2_SCORING_SYSTEM_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        research_summary=state_of_knowledge.get("summary", "No summary available."),
        gene_evidence=json.dumps(gene_evidence, indent=2),
    )

    llm.set_tier("high")
    try:
        scoring_response = llm.invoke_structured(scoring_prompt, schema=scored_genes_schema)
        updated_genes = scoring_response.get("genes", [])
        for gene in updated_genes:
            gene["biological_process"] = bp_name

        # Ensure gene count is within target (30-50)
        if len(updated_genes) > max_genes_target:
            updated_genes = sorted(updated_genes, key=lambda g: g.get("score", 5), reverse=True)
            updated_genes = updated_genes[:max_genes_target]
            print(f"  Trimmed to {max_genes_target} genes")
        elif len(updated_genes) < min_genes_target:
            print(f"  Warning: Only {len(updated_genes)} genes (target: {min_genes_target}-{max_genes_target})")

        print(f"  Final genes: {len(updated_genes)}")

    except Exception as e:
        print(f"  Warning: Scoring failed: {e}")
        # Fallback: preserve existing genes
        updated_genes = genes_found

        # Try to add new genes from research summaries
        for summary in [opengenes_summary, pubmed_summary, vectordb_summary]:
            if summary:
                for gene in summary.get("genes_mentioned", []):
                    if gene not in [g.get("gene_symbol") for g in updated_genes]:
                        updated_genes.append({
                            "gene_symbol": gene,
                            "score": 5,
                            "evidence_summary": "Found during refinement research",
                            "sources": summary.get("citations", [])[:2],
                            "biological_process": bp_name,
                        })
    llm.set_tier("low")

    # Build refinement record for audit trail
    old_gene_symbols = {g.get("gene_symbol") for g in genes_found}
    new_gene_symbols = {g.get("gene_symbol") for g in updated_genes}
    new_genes_added = new_gene_symbols - old_gene_symbols

    refinement_record = {
        "iteration": state.get("critic_iteration", 0) + 1,
        "assessment_rebuttal": assessment.get("rebuttal", "") if "assessment" in dir() else "",
        "assessment_comments": assessment.get("comments", "") if "assessment" in dir() else "",
        "queries_executed": {
            "opengenes": len(opengenes_findings),
            "pubmed": len(pubmed_findings),
            "vector_db": len(vectordb_findings),
        },
        "genes_before": len(genes_found),
        "genes_after": len(updated_genes),
        "new_genes_added": list(new_genes_added),
        "new_genes_count": len(new_genes_added),
    }

    refinement_history = state.get("refinement_history", [])
    refinement_history.append(refinement_record)

    print(f"{'='*60}\n")
    return {
        "genes_found": updated_genes,
        "gene_evidence": gene_evidence,
        "state_of_knowledge": json.dumps(state_of_knowledge),
        "critic_iteration": state.get("critic_iteration", 0) + 1,
        "refinement_history": refinement_history,
    }
