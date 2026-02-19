from __future__ import annotations

import json
from typing import Any

from aging_bd_agentic_system.agents.helpers import (
    append_warning,
    run_tool,
    unique_non_empty,
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
    """Select the current biological process based on the queue index."""
    bp_queue = state.get("bp_queue", [])
    index = state.get("current_bp_index", 0)
    if index >= len(bp_queue):
        return {}
    return {"current_bp_name": bp_queue[index]}


def seed_gene_candidates(
    state: dict[str, Any],
    *,
    include_opengenes: bool = True,
) -> dict[str, Any]:
    """Seed candidate genes using GenAge and OpenGenes."""
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")
    updates: dict[str, Any] = {}
    candidates: set[str] = set()

    genage_results, genage_updates = run_tool(
        tool_fn=query_genage,
        tool_name="query_genage",
        args={"query": bp_name, "max_results": 50},
        phase="phase2",
        node="seed_gene_candidates",
        bp=bp_name,
        hallmark=hallmark,
    )
    updates.update(genage_updates)
    candidates.update({row.get("symbol", "") for row in genage_results})

    if include_opengenes:
        opengenes_results, opengenes_updates = run_tool(
            tool_fn=query_opengenes,
            tool_name="query_opengenes",
            args={"query": bp_name, "max_results": 50},
            phase="phase2",
            node="seed_gene_candidates",
            bp=bp_name,
            hallmark=hallmark,
        )
        updates = _merge_updates(updates, opengenes_updates)
        candidates.update({row.get("symbol", "") for row in opengenes_results})

    candidates_list = unique_non_empty(candidates)
    updates["research_scratchpad"] = json.dumps(candidates_list)
    return updates


def phase2_research(state: dict[str, Any], *, gene_limit: int = 30) -> dict[str, Any]:
    """Collect evidence for candidate genes from PubMed and the corpus."""
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")
    updates: dict[str, Any] = {}

    try:
        candidates = json.loads(state.get("research_scratchpad", "[]"))
    except json.JSONDecodeError:
        candidates = []
        updates = _merge_updates(updates, append_warning("Invalid scratchpad JSON"))

    genes: list[dict[str, Any]] = []
    for gene in candidates[:gene_limit]:
        pubmed_results, pubmed_updates = run_tool(
            tool_fn=query_pubmed,
            tool_name="query_pubmed",
            args={"query": f"{gene} {bp_name} aging", "retmax": 3},
            phase="phase2",
            node="phase2_research",
            bp=bp_name,
            hallmark=hallmark,
        )
        updates = _merge_updates(updates, pubmed_updates)

        vector_results, vector_updates = run_tool(
            tool_fn=query_vector_db,
            tool_name="query_vector_db",
            args={"query": f"{gene} {bp_name} aging", "top_k": 3},
            phase="phase2",
            node="phase2_research",
            bp=bp_name,
            hallmark=hallmark,
        )
        updates = _merge_updates(updates, vector_updates)

        sources = []
        sources.extend(
            [f"PMID:{rec['pmid']}" for rec in pubmed_results if rec.get("pmid")]
        )
        sources.extend(
            [rec.get("pmcid") for rec in vector_results if rec.get("pmcid")]
        )
        sources = unique_non_empty([src for src in sources if src])

        evidence_score = 0
        if pubmed_results and vector_results:
            evidence_score = 8
        elif pubmed_results or vector_results:
            evidence_score = 6

        if evidence_score < 5:
            continue

        summary_parts = []
        if pubmed_results:
            summary_parts.append(pubmed_results[0].get("title", "PubMed evidence"))
        if vector_results:
            text = vector_results[0].get("text", "")
            summary_parts.append(text[:200].strip())

        genes.append(
            {
                "gene_symbol": gene,
                "score": evidence_score,
                "biological_process": bp_name,
                "evidence_summary": " | ".join(
                    [part for part in summary_parts if part]
                ),
                "sources": sources,
            }
        )

    updates["genes_found"] = genes
    return updates


def phase2_critic(
    state: dict[str, Any], *, min_genes_expected: int = 20
) -> dict[str, Any]:
    """Evaluate gene evidence coverage for the current biological process."""
    bp_name = state.get("current_bp_name", "")
    genes = [
        gene
        for gene in state.get("genes_found", [])
        if gene.get("biological_process") == bp_name
    ]
    issues: list[str] = []
    if len(genes) < min_genes_expected:
        issues.append(f"expected >= {min_genes_expected} genes, got {len(genes)}")

    for idx, gene in enumerate(genes):
        if not gene.get("sources"):
            issues.append(f"gene[{idx}] missing sources")
        if not gene.get("evidence_summary"):
            issues.append(f"gene[{idx}] missing evidence summary")

    grade = "pass" if not issues else "fail"
    follow_up = []
    if issues:
        follow_up = [f"{bp_name} aging gene evidence"]

    eval_data = {
        "grade": grade,
        "comment": "; ".join(issues) or "coverage looks sufficient",
        "follow_up_queries": follow_up,
        "min_genes_expected": min_genes_expected,
    }
    log_event(
        {
            "hallmark": state.get("hallmark_name"),
            "phase": "phase2",
            "bp": bp_name,
            "node": "phase2_critic",
            "grade": eval_data["grade"],
            "follow_up_queries": eval_data["follow_up_queries"],
            "comment": eval_data["comment"],
        }
    )
    return {"phase2_eval": eval_data}


def phase2_refine(state: dict[str, Any]) -> dict[str, Any]:
    """Run follow-up queries when Phase 2 critique fails."""
    eval_data = state.get("phase2_eval", {})
    follow_up = eval_data.get("follow_up_queries", [])
    iteration = state.get("phase2_iteration", 0) + 1
    updates: dict[str, Any] = {"phase2_iteration": iteration}
    bp_name = state.get("current_bp_name", "")
    hallmark = state.get("hallmark_name")

    for query in follow_up:
        pubmed_results, pubmed_updates = run_tool(
            tool_fn=query_pubmed,
            tool_name="query_pubmed",
            args={"query": query, "retmax": 3},
            phase="phase2",
            node="phase2_refine",
            bp=bp_name,
            hallmark=hallmark,
        )
        updates = _merge_updates(updates, pubmed_updates)

        vector_results, vector_updates = run_tool(
            tool_fn=query_vector_db,
            tool_name="query_vector_db",
            args={"query": query, "top_k": 3},
            phase="phase2",
            node="phase2_refine",
            bp=bp_name,
            hallmark=hallmark,
        )
        updates = _merge_updates(updates, vector_updates)

        if not pubmed_results and not vector_results:
            updates = _merge_updates(
                updates,
                append_warning(f"No evidence for follow-up query: {query}"),
            )

    log_event(
        {
            "hallmark": hallmark,
            "phase": "phase2",
            "bp": bp_name,
            "node": "iteration_end",
            "iteration": iteration,
        }
    )

    return updates


def map_go_terms(state: dict[str, Any], *, max_results: int = 10) -> dict[str, Any]:
    """Map GO terms for the current biological process."""
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")
    updates: dict[str, Any] = {}

    go_results, go_updates = run_tool(
        tool_fn=query_go_terms,
        tool_name="query_go_terms",
        args={"query": bp_name, "max_results": max_results},
        phase="phase2",
        node="map_go_terms",
        bp=bp_name,
        hallmark=hallmark,
    )
    updates.update(go_updates)

    go_terms = [
        {
            "go_id": rec.get("go_id", ""),
            "go_label": rec.get("go_label", ""),
            "definition": rec.get("definition", ""),
            "biological_process": bp_name,
            "sources": [rec.get("go_id", "GO")],
        }
        for rec in go_results
    ]

    log_event(
        {
            "hallmark": hallmark,
            "phase": "phase2",
            "bp": bp_name,
            "node": "map_go_terms",
            "result_count": len(go_terms),
        }
    )

    updates["go_terms_found"] = go_terms
    return updates


def advance_bp(state: dict[str, Any]) -> dict[str, Any]:
    """Advance to the next biological process."""
    return {
        "current_bp_index": state.get("current_bp_index", 0) + 1,
        "current_bp_name": "",
        "research_scratchpad": "",
        "phase2_iteration": 0,
    }


def _merge_updates(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Merge update dicts, concatenating list fields when needed."""
    merged = dict(base)
    for key, value in extra.items():
        if key in merged and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + value
        else:
            merged[key] = value
    return merged
