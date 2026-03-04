#!/usr/bin/env python3
"""
Smoke test for Phase 2 research starting from saved seed genes.

Loads seed genes from disk and continues from iteration 1 onwards.
Skips the seeding step (iteration 0).

Output structure:
    outputs/{hallmark}/bp{rank}/
        seed_genes.json           # Copy of seed genes
        seeding_queries.json      # Copy of seeding queries
        gene_evidence.json        # Final gene evidence
        state_of_knowledge.json   # Final state of knowledge
        research_scratchpad.json  # Final research data
        scored_genes.tsv          # Scored genes output
        tool_call_history.json    # All tool calls made
        reasoning_trace.json      # LLM reasoning traces
        warnings.json             # Any warnings
        full_result.json          # Complete result state

Usage:
    python scripts/phase2_research_from_seed_smoketest.py --hallmark "genomic instability" --bp-rank 1
    python scripts/phase2_research_from_seed_smoketest.py --hallmark "genomic instability" --bp-rank 1 --max-iterations 3

Requires:
    - Seed genes file: outputs/{hallmark}/bp{rank}_seed_genes.json (or bp{rank}/seed_genes.json)
    - Processes file: outputs/{hallmark}/processes.tsv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from pdb import set_trace

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

from aging_bd_agentic_system.config import LLMConfig, RunConfig
from aging_bd_agentic_system.graph.workflow import build_phase2_research_only_graph
from aging_bd_agentic_system.llm import init_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 smoke test from saved seed genes")
    parser.add_argument(
        "--hallmark",
        help="Aging hallmark",
        default="genomic instability",
    )
    parser.add_argument(
        "--bp-rank",
        type=int,
        default=1,
        help="BP rank (1-indexed, matches processes.tsv)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max research iterations (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Output directory (default: outputs)",
    )
    return parser.parse_args()


def load_seed_genes(hallmark_dir: Path, bp_dir: Path) -> list[dict]:
    """Load saved seed genes - check new location first, then legacy."""
    # New location
    seed_file = bp_dir / "seed_genes.json"
    if seed_file.exists():
        with seed_file.open("r") as f:
            return json.load(f)

    # Legacy location
    legacy_file = hallmark_dir / f"bp{bp_dir.name.replace('bp', '')}_seed_genes.json"
    if legacy_file.exists():
        with legacy_file.open("r") as f:
            return json.load(f)

    raise FileNotFoundError(f"Seed file not found in {seed_file} or {legacy_file}")


def load_seeding_queries(hallmark_dir: Path, bp_dir: Path) -> list[dict]:
    """Load seeding queries - check new location first, then legacy."""
    # New location
    queries_file = bp_dir / "seeding_queries.json"
    if queries_file.exists():
        with queries_file.open("r") as f:
            data = json.load(f)
            return data.get("opengenes_queries", [])

    # Legacy location
    bp_rank = bp_dir.name.replace("bp", "")
    legacy_file = hallmark_dir / f"bp{bp_rank}_seeding_queries.json"
    if legacy_file.exists():
        with legacy_file.open("r") as f:
            data = json.load(f)
            return data.get("opengenes_queries", [])

    return []


def load_gene_evidence(hallmark_dir: Path, bp_dir: Path) -> dict:
    """Load gene evidence - check new location first, then legacy."""
    # New location
    evidence_file = bp_dir / "gene_evidence.json"
    if evidence_file.exists():
        with evidence_file.open("r") as f:
            return json.load(f)

    # Legacy location
    bp_rank = bp_dir.name.replace("bp", "")
    legacy_file = hallmark_dir / f"bp{bp_rank}_gene_evidence.json"
    if legacy_file.exists():
        with legacy_file.open("r") as f:
            return json.load(f)

    return {}


def load_state_of_knowledge(hallmark_dir: Path, bp_dir: Path) -> dict:
    """Load state of knowledge - check new location first, then legacy."""
    # New location
    sok_file = bp_dir / "state_of_knowledge.json"
    if sok_file.exists():
        with sok_file.open("r") as f:
            return json.load(f)

    # Legacy location
    bp_rank = bp_dir.name.replace("bp", "")
    legacy_file = hallmark_dir / f"bp{bp_rank}_state_of_knowledge.json"
    if legacy_file.exists():
        with legacy_file.open("r") as f:
            return json.load(f)

    return {"candidate_genes": [], "citations": [], "summary": ""}


def load_bp_name(hallmark_dir: Path, bp_rank: int) -> str:
    """Load BP name from processes.tsv."""
    processes_file = hallmark_dir / "processes.tsv"
    if not processes_file.exists():
        raise FileNotFoundError(f"Processes file not found: {processes_file}")

    with processes_file.open("r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if int(row["rank"]) == bp_rank:
                return row["process_name"]

    raise ValueError(f"BP rank {bp_rank} not found in {processes_file}")


def save_json(data: any, path: Path) -> None:
    """Save data as JSON with indent."""
    with path.open("w") as f:
        json.dump(data, f, indent=2, default=str)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    hallmark_dir = output_dir / args.hallmark
    bp_dir = hallmark_dir / f"bp{args.bp_rank}"

    # Create BP-specific output directory
    bp_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"PHASE 2 SMOKE TEST (FROM SAVED SEED)")
    print(f"{'='*60}")
    print(f"Hallmark: {args.hallmark}")
    print(f"BP Rank: {args.bp_rank}")
    print(f"Output dir: {bp_dir}")

    # Load saved data
    print("\nLoading saved data...")
    try:
        seed_genes = load_seed_genes(hallmark_dir, bp_dir)
        bp_name = load_bp_name(hallmark_dir, args.bp_rank)
        opengenes_seeding_queries = load_seeding_queries(hallmark_dir, bp_dir)
        gene_evidence = load_gene_evidence(hallmark_dir, bp_dir)
        state_of_knowledge = load_state_of_knowledge(hallmark_dir, bp_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return 1

    print(f"BP Name: {bp_name}")
    print(f"Loaded {len(seed_genes)} seed genes")
    print(f"Loaded {len(opengenes_seeding_queries)} seeding queries")
    print(f"Loaded gene_evidence: {len(gene_evidence)} genes")
    print(f"Loaded state_of_knowledge: {len(state_of_knowledge.get('candidate_genes', []))} candidates")

    # Configure LLM
    llm_config = LLMConfig(
        provider="openai",
        model="gpt-5-nano",
        temperature=0.5,
    )

    # Build RunConfig
    config = RunConfig()
    config.hallmark = args.hallmark
    config.output_dir = output_dir
    config.phase1_only = False
    config.llm = llm_config

    # Override for smoke test
    config.phase2.max_research_iterations = args.max_iterations
    config.phase2.max_refine_iterations = 0
    config.phase2.genage_seed_max_results = 10
    config.phase2.opengenes_seed_results_per_query = 15
    config.phase2.phase2_vector_db_top_k = 5
    config.phase2.phase2_pubmed_retmax = 5
    config.phase2.phase2_summarize_max_tokens = 50000
    config.phase2.min_actions_per_iteration = 4
    config.phase2.max_actions_per_iteration = 6

    # Initialize LLM
    init_llm(config.llm)

    # Build research_data from saved seed genes
    research_data = {
        "initial_database_genes": seed_genes,
        "opengenes_seeding_queries": opengenes_seeding_queries,
        "research_findings": [],
    }

    # Build initial state for Phase 2 (starting at iteration 1)
    initial_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "biological_processes": [],  # Not needed for iteration 1+
        "bp_queue": [bp_name],
        "current_bp_index": 0,
        "current_bp_name": bp_name,
        "phase2_research_iteration": 1,  # Start at iteration 1 (skip seeding)
        "phase2_critic_iteration": 0,
        "phase2_eval": {},
        "genes_found": [],
        "go_terms_found": [],
        "tool_call_history": [],
        "reasoning_trace": [],
        "warnings": [],
        "research_scratchpad": json.dumps(research_data),
        "state_of_knowledge": json.dumps(state_of_knowledge),
        "gene_evidence": gene_evidence,
    }

    # Run Phase 2 graph (research only, no critic/refine)
    print(f"\n{'='*60}")
    print(f"Running Phase 2 (iteration 1 to {args.max_iterations})...")
    print(f"{'='*60}")

    graph = build_phase2_research_only_graph()
    result = graph.invoke(initial_state)
    set_trace()

    # Extract results
    genes = result.get("genes_found", [])
    go_terms = result.get("go_terms_found", [])
    tool_calls = result.get("tool_call_history", [])
    reasoning = result.get("reasoning_trace", [])
    warnings = result.get("warnings", [])
    final_scratchpad = result.get("research_scratchpad", "{}")
    final_sok = result.get("state_of_knowledge", "{}")
    final_evidence = result.get("gene_evidence", {})

    # Save all outputs to BP-specific directory
    print(f"\nSaving outputs to {bp_dir}...")

    # Copy/save input files (for reproducibility)
    save_json(seed_genes, bp_dir / "seed_genes.json")
    save_json({"opengenes_queries": opengenes_seeding_queries}, bp_dir / "seeding_queries.json")

    # Save final state files
    save_json(final_evidence, bp_dir / "gene_evidence.json")
    save_json(json.loads(final_sok) if isinstance(final_sok, str) else final_sok, bp_dir / "state_of_knowledge.json")
    save_json(json.loads(final_scratchpad) if isinstance(final_scratchpad, str) else final_scratchpad, bp_dir / "research_scratchpad.json")

    # Save trace files
    save_json(tool_calls, bp_dir / "tool_call_history.json")
    save_json(reasoning, bp_dir / "reasoning_trace.json")
    save_json(warnings, bp_dir / "warnings.json")

    # Save full result for complete audit trail
    save_json(result, bp_dir / "full_result.json")

    # Save genes to TSV
    genes_file = bp_dir / "scored_genes.tsv"
    with genes_file.open("w") as f:
        f.write("gene_symbol\tscore\tevidence_summary\tsources\tbiological_process\n")
        for g in genes:
            f.write(f"{g.get('gene_symbol', '')}\t{g.get('score', '')}\t{g.get('evidence_summary', '')}\t{','.join(g.get('sources', []))}\t{g.get('biological_process', '')}\n")
    print(f"Saved scored genes to: {genes_file}")

    # Summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Genes found: {len(genes)}")
    print(f"GO terms found: {len(go_terms)}")
    print(f"Tool calls: {len(tool_calls)}")
    print(f"Warnings: {len(warnings)}")

    if genes:
        print("\nTop genes:")
        seen = set()
        for g in genes[:10]:
            name = g.get("gene_symbol") or g.get("symbol", "unknown")
            score = g.get("score", "?")
            if name not in seen:
                print(f"  - {name} (score: {score})")
                seen.add(name)

    print(f"\n✅ Phase 2 smoke test (from seed) passed")
    print(f"✅ All outputs saved to: {bp_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
