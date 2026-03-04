#!/usr/bin/env python3
"""
Smoke test for full Phase 2 pipeline: research + critic-refine.

Runs the complete post-seed pipeline for a given BP:
1. Research iterations (from seed genes)
2. Critic-refine loop

Output structure:
    outputs/{hallmark}/bp{rank}/
        # Research outputs
        seed_genes.json           # Copy of seed genes
        seeding_queries.json      # Copy of seeding queries
        research_scratchpad.json  # Research data after iterations
        tool_call_history.json    # All tool calls made
        reasoning_trace.json      # LLM reasoning traces
        warnings.json             # Any warnings

        # Critic-refine outputs
        critic_review.json        # Final critic review
        refinement_history.json   # All refinement outputs

        # Final state (overwritten by critic-refine)
        gene_evidence.json        # Final gene evidence
        state_of_knowledge.json   # Final state of knowledge
        scored_genes.tsv          # Final scored genes
        full_result.json          # Complete result state

Usage:
    python scripts/phase2_full_pipeline_smoketest.py --hallmark "genomic instability" --bp-rank 1
    python scripts/phase2_full_pipeline_smoketest.py --hallmark "genomic instability" --bp-rank 1 --max-research-iterations 3 --max-critic-iterations 2

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

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

from aging_bd_agentic_system.config import LLMConfig, RunConfig
from aging_bd_agentic_system.graph.workflow import (
    build_phase2_research_only_graph,
    build_phase2_critic_refine_graph,
)
from aging_bd_agentic_system.llm import init_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 full pipeline smoke test")
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
        "--max-research-iterations",
        type=int,
        default=3,
        help="Max research iterations (default: 3)",
    )
    parser.add_argument(
        "--max-critic-iterations",
        type=int,
        default=1,
        help="Max critic-refine iterations (default: 1)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Output directory (default: outputs)",
    )
    return parser.parse_args()


def load_seed_genes(hallmark_dir: Path, bp_dir: Path) -> list[dict]:
    """Load saved seed genes - check new location first, then legacy."""
    seed_file = bp_dir / "seed_genes.json"
    if seed_file.exists():
        with seed_file.open("r") as f:
            return json.load(f)

    bp_rank = bp_dir.name.replace("bp", "")
    legacy_file = hallmark_dir / f"bp{bp_rank}_seed_genes.json"
    if legacy_file.exists():
        with legacy_file.open("r") as f:
            return json.load(f)

    raise FileNotFoundError(f"Seed file not found in {seed_file} or {legacy_file}")


def load_seeding_queries(hallmark_dir: Path, bp_dir: Path) -> list[dict]:
    """Load seeding queries - check new location first, then legacy."""
    queries_file = bp_dir / "seeding_queries.json"
    if queries_file.exists():
        with queries_file.open("r") as f:
            data = json.load(f)
            return data.get("opengenes_queries", [])

    bp_rank = bp_dir.name.replace("bp", "")
    legacy_file = hallmark_dir / f"bp{bp_rank}_seeding_queries.json"
    if legacy_file.exists():
        with legacy_file.open("r") as f:
            data = json.load(f)
            return data.get("opengenes_queries", [])

    return []


def load_gene_evidence(hallmark_dir: Path, bp_dir: Path) -> dict:
    """Load gene evidence - check new location first, then legacy."""
    evidence_file = bp_dir / "gene_evidence.json"
    if evidence_file.exists():
        with evidence_file.open("r") as f:
            return json.load(f)

    bp_rank = bp_dir.name.replace("bp", "")
    legacy_file = hallmark_dir / f"bp{bp_rank}_gene_evidence.json"
    if legacy_file.exists():
        with legacy_file.open("r") as f:
            return json.load(f)

    return {}


def load_state_of_knowledge(hallmark_dir: Path, bp_dir: Path) -> dict:
    """Load state of knowledge - check new location first, then legacy."""
    sok_file = bp_dir / "state_of_knowledge.json"
    if sok_file.exists():
        with sok_file.open("r") as f:
            return json.load(f)

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
    print(f"PHASE 2 FULL PIPELINE SMOKE TEST")
    print(f"{'='*60}")
    print(f"Hallmark: {args.hallmark}")
    print(f"BP Rank: {args.bp_rank}")
    print(f"Output dir: {bp_dir}")
    print(f"Max research iterations: {args.max_research_iterations}")
    print(f"Max critic iterations: {args.max_critic_iterations}")

    # Load saved data
    print("\nLoading saved seed data...")
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

    # Research settings
    config.phase2.max_research_iterations = args.max_research_iterations
    config.phase2.max_refine_iterations = 0
    config.phase2.genage_seed_max_results = 10
    config.phase2.opengenes_seed_results_per_query = 15
    config.phase2.phase2_vector_db_top_k = 5
    config.phase2.phase2_pubmed_retmax = 5
    config.phase2.phase2_summarize_max_tokens = 50000
    config.phase2.min_actions_per_iteration = 4
    config.phase2.max_actions_per_iteration = 6

    # Critic-refine settings
    config.phase2.max_critic_iterations = args.max_critic_iterations
    config.phase2.refine_opengenes_max_results = 3
    config.phase2.refine_pubmed_max_results = 7
    config.phase2.refine_vector_db_top_k = 7

    # Initialize LLM
    init_llm(config.llm)

    # =========================================================================
    # PART 1: RESEARCH ITERATIONS
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"PART 1: RESEARCH ITERATIONS (1 to {args.max_research_iterations})")
    print(f"{'='*60}")

    # Build research_data from saved seed genes
    research_data = {
        "initial_database_genes": seed_genes,
        "opengenes_seeding_queries": opengenes_seeding_queries,
        "research_findings": [],
    }

    # Build initial state for Phase 2 (starting at iteration 1)
    research_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "biological_processes": [],
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

    # Run research graph
    research_graph = build_phase2_research_only_graph()
    research_result = research_graph.invoke(research_state)

    # Extract research results
    genes_found = research_result.get("genes_found", [])
    go_terms = research_result.get("go_terms_found", [])
    tool_calls = research_result.get("tool_call_history", [])
    reasoning = research_result.get("reasoning_trace", [])
    warnings = research_result.get("warnings", [])
    final_scratchpad = research_result.get("research_scratchpad", "{}")
    research_sok = research_result.get("state_of_knowledge", "{}")
    research_evidence = research_result.get("gene_evidence", {})

    # Save research outputs
    print(f"\nSaving research outputs to {bp_dir}...")

    # Copy/save input files
    save_json(seed_genes, bp_dir / "seed_genes.json")
    save_json({"opengenes_queries": opengenes_seeding_queries}, bp_dir / "seeding_queries.json")

    # Save research state files
    save_json(research_evidence, bp_dir / "gene_evidence.json")
    save_json(json.loads(research_sok) if isinstance(research_sok, str) else research_sok, bp_dir / "state_of_knowledge.json")
    save_json(json.loads(final_scratchpad) if isinstance(final_scratchpad, str) else final_scratchpad, bp_dir / "research_scratchpad.json")

    # Save trace files
    save_json(tool_calls, bp_dir / "tool_call_history.json")
    save_json(reasoning, bp_dir / "reasoning_trace.json")
    save_json(warnings, bp_dir / "warnings.json")

    # Save research result for audit
    save_json(research_result, bp_dir / "research_result.json")

    print(f"Research complete: {len(genes_found)} genes found")
    print(f"Tool calls: {len(tool_calls)}, Warnings: {len(warnings)}")

    # =========================================================================
    # PART 2: CRITIC-REFINE LOOP
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"PART 2: CRITIC-REFINE LOOP (max {args.max_critic_iterations} iterations)")
    print(f"{'='*60}")

    # Build initial state for critic-refine from research output
    critic_refine_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "current_bp_name": bp_name,
        "critic_iteration": 0,
        "critic_review": None,
        "refinement_history": [],
        "genes_found": genes_found,
        "gene_evidence": research_evidence,
        "state_of_knowledge": research_sok,
    }

    # Run critic-refine graph
    critic_refine_graph = build_phase2_critic_refine_graph()
    critic_refine_result = critic_refine_graph.invoke(critic_refine_state)

    # Extract final results
    final_genes = critic_refine_result.get("genes_found", [])
    critic_review = critic_refine_result.get("critic_review", {})
    refinement_history = critic_refine_result.get("refinement_history", [])
    final_evidence = critic_refine_result.get("gene_evidence", {})
    final_sok = critic_refine_result.get("state_of_knowledge", "{}")

    # Save critic-refine outputs
    print(f"\nSaving critic-refine outputs to {bp_dir}...")

    save_json(critic_review, bp_dir / "critic_review.json")
    save_json(refinement_history, bp_dir / "refinement_history.json")
    save_json(final_evidence, bp_dir / "gene_evidence.json")

    sok_data = json.loads(final_sok) if isinstance(final_sok, str) else final_sok
    save_json(sok_data, bp_dir / "state_of_knowledge.json")

    # Save full result
    save_json(critic_refine_result, bp_dir / "full_result.json")

    # Save genes to TSV
    genes_file = bp_dir / "scored_genes.tsv"
    with genes_file.open("w") as f:
        f.write("gene_symbol\tscore\tevidence_summary\tsources\tbiological_process\n")
        for g in final_genes:
            f.write(f"{g.get('gene_symbol', '')}\t{g.get('score', '')}\t{g.get('evidence_summary', '')}\t{','.join(g.get('sources', []))}\t{g.get('biological_process', '')}\n")
    print(f"Saved scored genes to: {genes_file}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Research genes: {len(genes_found)}")
    print(f"Final genes: {len(final_genes)}")
    print(f"Critic grade: {critic_review.get('grade', 'unknown')}")
    print(f"Refinement cycles: {len(refinement_history)}")

    if final_genes:
        print("\nTop genes:")
        seen = set()
        for g in final_genes[:10]:
            name = g.get("gene_symbol") or g.get("symbol", "unknown")
            score = g.get("score", "?")
            if name not in seen:
                print(f"  - {name} (score: {score})")
                seen.add(name)

    print(f"\n✅ Full pipeline smoke test passed")
    print(f"✅ All outputs saved to: {bp_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
