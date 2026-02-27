"""
Phase 2 Helper Functions

Helper functions for gene research seeding, normalization, and evidence summarization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from pdb import set_trace

from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.prompts.phase2_prompts import (
    PHASE2_EVIDENCE_CONTEXT,
    PHASE2_GENAGE_EVIDENCE_PROMPT,
    PHASE2_GENAGE_SEED_PROMPT,
    PHASE2_OPENGENES_EVIDENCE_PROMPT,
    PHASE2_OPENGENES_SEED_PROMPT,
)

# Path to GenAge database
GENAGE_CSV_PATH = Path(__file__).parent.parent.parent.parent / "data" / "databases" / "genage.csv"

# Module-level cache for GenAge lookup
_GENAGE_LOOKUP: dict[str, dict] | None = None


# ===== SCHEMAS =====

GENAGE_SEED_SCHEMA = {
    "title": "genage_seed_genes",
    "type": "object",
    "properties": {
        "genage_genes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Gene symbols selected from GenAge database",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of selection",
        },
    },
    "required": ["genage_genes", "reasoning"],
}

OPENGENES_SEED_SCHEMA = {
    "title": "opengenes_seed_queries",
    "type": "object",
    "properties": {
        "opengenes_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Search queries for OpenGenes database",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of query strategy",
        },
    },
    "required": ["opengenes_queries", "reasoning"],
}

EVIDENCE_SUMMARY_SCHEMA = {
    "title": "evidence_summaries",
    "type": "object",
    "properties": {
        "summaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["symbol", "evidence"],
            },
        },
    },
    "required": ["summaries"],
}


# ===== GENAGE CSV HELPERS =====

def _load_genage_csv() -> str:
    """Load the GenAge CSV file as a string."""
    if not GENAGE_CSV_PATH.exists():
        raise FileNotFoundError(f"GenAge CSV not found at {GENAGE_CSV_PATH}")
    return GENAGE_CSV_PATH.read_text(encoding="utf-8")


def _get_genage_lookup() -> dict[str, dict]:
    """Get cached GenAge lookup dict (symbol -> record). Builds once on first access."""
    global _GENAGE_LOOKUP
    if _GENAGE_LOOKUP is None:
        csv_data = _load_genage_csv()
        _GENAGE_LOOKUP = {}
        for line in csv_data.strip().split('\n')[1:]:  # skip header
            parts = line.split(',')
            if len(parts) >= 6:
                _GENAGE_LOOKUP[parts[1]] = {  # key by symbol
                    "genage_id": parts[0],
                    "symbol": parts[1],
                    "name": parts[2],
                    "entrez_gene_id": parts[3],
                    "uniprot": parts[4],
                    "why": parts[5],
                }
    return _GENAGE_LOOKUP


# ===== SEEDING FUNCTIONS =====

def select_genage_seed_genes(bp_name: str, hallmark: str, genage_data: str) -> list[str]:
    """
    Use LLM to select relevant genes from GenAge database.

    Args:
        bp_name: Biological process name
        hallmark: Aging hallmark name
        genage_data: Full GenAge CSV data as string

    Returns:
        List of gene symbols selected from GenAge
    """
    llm = get_llm()

    user_prompt = PHASE2_GENAGE_SEED_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
        genage_data=genage_data,
    )

    try:
        result = llm.invoke_structured(
            user_prompt,
            schema=GENAGE_SEED_SCHEMA,
        )
        return result.get("genage_genes", [])
    except Exception as e:
        print(f"GenAge seed structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(user_prompt)
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                return result.get("genage_genes", [])
        except json.JSONDecodeError:
            pass
        raise ValueError(f"Failed to select GenAge seed genes: {e}")


def generate_opengenes_seed_queries(bp_name: str, hallmark: str) -> list[str]:
    """
    Use LLM to generate search queries for OpenGenes database.

    Args:
        bp_name: Biological process name
        hallmark: Aging hallmark name

    Returns:
        List of search queries for OpenGenes
    """
    llm = get_llm()

    user_prompt = PHASE2_OPENGENES_SEED_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark,
    )

    try:
        result = llm.invoke_structured(
            user_prompt,
            schema=OPENGENES_SEED_SCHEMA,
        )
        return result.get("opengenes_queries", [])
    except Exception as e:
        print(f"OpenGenes seed structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(user_prompt)
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                return result.get("opengenes_queries", [])
        except json.JSONDecodeError:
            pass
        raise ValueError(f"Failed to generate OpenGenes seed queries: {e}")


# ===== NORMALIZATION FUNCTIONS =====

def normalize_seed_candidates(candidates: list[dict]) -> list[dict]:
    """
    Deduplicate and normalize seed candidates from GenAge and OpenGenes.

    - Deduplicates by symbol
    - Merges sources ("genage" | "opengenes" | "genage, opengenes")
    - Accumulates all OpenGenes data for genes with multiple hits
    - Keeps GenAge evidence as-is
    - Stores raw OpenGenes data for later summarization

    Args:
        candidates: Raw list of candidates from seeding (may have duplicates)

    Returns:
        Deduplicated list with merged sources and accumulated data
    """
    # Group by symbol
    grouped: dict[str, dict] = {}

    for c in candidates:
        symbol = c.get("symbol")
        if not symbol:
            continue

        if symbol not in grouped:
            grouped[symbol] = {
                "symbol": symbol,
                "name": c.get("name", ""),
                "sources": set(),
                "genage_evidence": None,
                "opengenes_data": {
                    "aging_mechanisms": set(),
                    "functional_clusters": set(),
                    "protein_classes": set(),
                    "evidence_causes": set(),
                    "queries": set(),
                },
            }

        entry = grouped[symbol]
        source = c.get("source", "")

        # Track source
        if source == "genage":
            entry["sources"].add("genage")
            # Keep GenAge evidence (from "why" field)
            if c.get("evidence") and not entry["genage_evidence"]:
                entry["genage_evidence"] = c.get("evidence")
        elif source == "opengenes":
            entry["sources"].add("opengenes")
            # Accumulate OpenGenes data
            od = entry["opengenes_data"]
            for item in c.get("aging_mechanisms", []):
                if item:
                    od["aging_mechanisms"].add(item)
            for item in c.get("functional_clusters", []):
                if item:
                    od["functional_clusters"].add(item)
            for item in c.get("protein_classes", []):
                if item:
                    od["protein_classes"].add(item)
            for item in c.get("evidence_causes", []):
                if item:
                    od["evidence_causes"].add(item)
            if c.get("query_used"):
                od["queries"].add(c.get("query_used"))
            # Use name from OpenGenes if not set
            if not entry["name"] and c.get("name"):
                entry["name"] = c.get("name")

    # Convert to output format
    result = []
    for symbol, entry in grouped.items():
        sources_str = ", ".join(sorted(entry["sources"]))
        od = entry["opengenes_data"]

        normalized = {
            "symbol": symbol,
            "name": entry["name"],
            "source": sources_str,
            "evidence": entry["genage_evidence"],  # Will be None for opengenes-only genes
            "raw_opengenes": {
                "aging_mechanisms": sorted(list(od["aging_mechanisms"])),
                "functional_clusters": sorted(list(od["functional_clusters"])),
                "protein_classes": sorted(list(od["protein_classes"])),
                "evidence_causes": sorted(list(od["evidence_causes"])),
                "queries": sorted(list(od["queries"])),
            } if od["queries"] else None,  # Only include if we have opengenes data
        }
        result.append(normalized)

    return result


def _summarize_evidence_batch(candidates: list[dict], bp_name: str, hallmark: str, batch_type: str) -> dict[str, str]:
    """
    Call LLM to summarize evidence for a batch of candidates.

    Args:
        candidates: List of candidates to summarize
        bp_name: Biological process name
        hallmark: Aging hallmark name
        batch_type: "genage" or "opengenes"

    Returns:
        Dict mapping symbol -> evidence (empty on failure)
    """
    llm = get_llm()

    if batch_type == "genage":
        genes_json = json.dumps(
            [{"symbol": c["symbol"], "name": c["name"], "genage_evidence": c["evidence"]}
             for c in candidates], indent=2
        )
        prompt = PHASE2_GENAGE_EVIDENCE_PROMPT.format(
            context=PHASE2_EVIDENCE_CONTEXT,
            biological_process=bp_name,
            hallmark_name=hallmark,
            genes_json=genes_json,
        )
    else:  # opengenes
        genes_json = json.dumps(
            [{"symbol": c["symbol"], "name": c["name"], "genage_evidence": c.get("evidence"),
              "opengenes_data": c.get("raw_opengenes")} for c in candidates], indent=2
        )
        prompt = PHASE2_OPENGENES_EVIDENCE_PROMPT.format(
            context=PHASE2_EVIDENCE_CONTEXT,
            biological_process=bp_name,
            hallmark_name=hallmark,
            genes_json=genes_json,
        )

    try:
        results = llm.invoke_structured(prompt, schema=EVIDENCE_SUMMARY_SCHEMA)
        return {r["symbol"]: r["evidence"] for r in results.get("summaries", [])}
    except Exception as e:
        print(f"  {batch_type} summarization failed: {e}")
        return {}


def summarize_seed_evidence(candidates: list[dict], bp_name: str, hallmark: str) -> list[dict]:
    """
    Use LLM to generate evidence summaries for normalized seed candidates.

    Processes in 2 batches:
    1. GenAge-only genes: Expand sparse "why" field into contextualized evidence
    2. Genes with OpenGenes data: Summarize raw_opengenes (+ merge GenAge if present)

    Includes validation and retry for missed genes.

    Args:
        candidates: Normalized candidates from normalize_seed_candidates()
        bp_name: Biological process name
        hallmark: Aging hallmark name

    Returns:
        Candidates with evidence field populated (raw_opengenes removed)
    """
    evidence_map = {}
    still_missing = set()

    # Process each batch type
    for batch_type in ["genage", "opengenes"]:
        if batch_type == "genage":
            batch = [c for c in candidates if c["source"] == "genage"]
        else:
            batch = [c for c in candidates if c.get("raw_opengenes") is not None]

        if not batch:
            continue

        # Initial call
        batch_evidence = _summarize_evidence_batch(batch, bp_name, hallmark, batch_type)
        evidence_map.update(batch_evidence)

        # Check for missing genes, retry once
        missing = set(c["symbol"] for c in batch) - set(batch_evidence.keys())
        if missing:
            print(f"  {batch_type}: {len(missing)} genes missed, retrying...")
            missed = [c for c in batch if c["symbol"] in missing]
            retry_evidence = _summarize_evidence_batch(missed, bp_name, hallmark, batch_type)
            evidence_map.update(retry_evidence)
            still_missing.update(missing - set(retry_evidence.keys()))

    if still_missing:
        print(f"  {len(still_missing)} genes still missing after retry, using fallback evidence")

    # Check for and remove hallucinated genes
    candidate_symbols = set(c["symbol"] for c in candidates)
    hallucinated = set(evidence_map.keys()) - candidate_symbols
    if hallucinated:
        print(f"  WARNING: LLM hallucinated {len(hallucinated)} genes: {sorted(hallucinated)[:5]}...")
        for sym in hallucinated:
            evidence_map.pop(sym, None)

    # Merge evidence back into candidates
    for c in candidates:
        c["evidence"] = evidence_map.get(c["symbol"], c.get("evidence"))
        c.pop("raw_opengenes", None)

    return candidates
