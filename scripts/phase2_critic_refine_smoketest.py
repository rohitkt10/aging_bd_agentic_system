#!/usr/bin/env python3
"""
Smoke test for Phase 2 critic-refine loop starting from saved research state.

Loads saved state from end of phase 2 research and runs only the critic-refine loop.

Output structure:
    outputs/{hallmark}/bp{rank}/
        critic_review.json        # Final critic review
        refinement_history.json   # All refinement outputs
        gene_evidence.json        # Updated gene evidence
        state_of_knowledge.json   # Updated state of knowledge
        scored_genes.tsv          # Final scored genes
        full_result.json          # Complete result state

Usage:
    python scripts/phase2_critic_refine_smoketest.py --hallmark "genomic instability" --bp-rank 1
    python scripts/phase2_critic_refine_smoketest.py --hallmark "genomic instability" --bp-rank 1 --max-critic-iterations 2

Requires:
    - Full result file: outputs/{hallmark}/bp{rank}/full_result.json
    - Gene evidence file: outputs/{hallmark}/bp{rank}/gene_evidence.json
    - State of knowledge file: outputs/{hallmark}/bp{rank}/state_of_knowledge.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from pdb import set_trace

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

from aging_bd_agentic_system.config import LLMConfig, RunConfig
from aging_bd_agentic_system.graph.workflow import build_phase2_critic_refine_graph
from aging_bd_agentic_system.llm import init_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 critic-refine smoke test")
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


def load_json_file(path: Path) -> dict | None:
    """Load JSON file if it exists."""
    if path.exists():
        with path.open("r") as f:
            return json.load(f)
    return None


def save_json(data: any, path: Path) -> None:
    """Save data as JSON with indent."""
    with path.open("w") as f:
        json.dump(data, f, indent=2, default=str)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    hallmark_dir = output_dir / args.hallmark
    bp_dir = hallmark_dir / f"bp{args.bp_rank}"

    print(f"\n{'='*60}")
    print(f"PHASE 2 CRITIC-REFINE SMOKE TEST")
    print(f"{'='*60}")
    print(f"Hallmark: {args.hallmark}")
    print(f"BP Rank: {args.bp_rank}")
    print(f"Output dir: {bp_dir}")

    # Load saved state files
    print("\nLoading saved state...")

    full_result = load_json_file(bp_dir / "full_result.json")
    if not full_result:
        print(f"ERROR: full_result.json not found in {bp_dir}")
        return 1

    gene_evidence = load_json_file(bp_dir / "gene_evidence.json") or {}
    state_of_knowledge = load_json_file(bp_dir / "state_of_knowledge.json") or {}

    # Extract BP name from genes or state
    genes_found = full_result.get("genes_found", [])
    bp_name = ""
    if genes_found:
        bp_name = genes_found[0].get("biological_process", "")

    print(f"BP Name: {bp_name}")
    print(f"Loaded {len(genes_found)} genes from research")
    print(f"Loaded gene_evidence: {len(gene_evidence)} genes")
    print(f"Loaded state_of_knowledge: {len(state_of_knowledge.get('candidate_genes', []))} candidates")

    # Configure LLM (same as research smoketest)
    llm_config = LLMConfig(
        provider="openai",
        model="gpt-5-nano",
        temperature=0.5,
    )

    # Build RunConfig (copy params from research smoketest)
    config = RunConfig()
    config.hallmark = args.hallmark
    config.output_dir = output_dir
    config.phase1_only = False
    config.llm = llm_config

    # Override for critic-refine test
    config.phase2.max_research_iterations = 3
    config.phase2.max_refine_iterations = 0
    config.phase2.genage_seed_max_results = 10
    config.phase2.opengenes_seed_results_per_query = 15
    config.phase2.phase2_vector_db_top_k = 5
    config.phase2.phase2_pubmed_retmax = 5
    config.phase2.phase2_summarize_max_tokens = 50000
    config.phase2.min_actions_per_iteration = 4
    config.phase2.max_actions_per_iteration = 6

    # Critic-refine specific settings
    config.phase2.max_critic_iterations = 1
    config.phase2.refine_opengenes_max_results = 3
    config.phase2.refine_pubmed_max_results = 7
    config.phase2.refine_vector_db_top_k = 7

    # Initialize LLM
    init_llm(config.llm)

    # Build initial state from loaded data
    initial_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "current_bp_name": bp_name,
        "critic_iteration": 0,
        "critic_review": None,
        "refinement_history": [],
        "genes_found": genes_found,
        "gene_evidence": gene_evidence,
        "state_of_knowledge": json.dumps(state_of_knowledge),
    }

    # Run critic-refine graph
    print(f"\n{'='*60}")
    print(f"Running critic-refine loop (max {args.max_critic_iterations} iterations)...")
    print(f"{'='*60}")

    graph = build_phase2_critic_refine_graph()
    result = graph.invoke(initial_state)
    

    # Extract results
    genes = result.get("genes_found", [])
    critic_review = result.get("critic_review", {})
    refinement_history = result.get("refinement_history", [])
    final_evidence = result.get("gene_evidence", {})
    final_sok = result.get("state_of_knowledge", "{}")

    # Save all outputs
    print(f"\nSaving outputs to {bp_dir}...")

    save_json(critic_review, bp_dir / "critic_review.json")
    save_json(refinement_history, bp_dir / "refinement_history.json")
    save_json(final_evidence, bp_dir / "gene_evidence.json")

    sok_data = json.loads(final_sok) if isinstance(final_sok, str) else final_sok
    save_json(sok_data, bp_dir / "state_of_knowledge.json")

    # Save full result
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
    print(f"Final genes: {len(genes)}")
    print(f"Critic grade: {critic_review.get('grade', 'unknown')}")
    print(f"Refinement cycles: {len(refinement_history)}")

    if genes:
        print("\nTop genes:")
        seen = set()
        for g in genes[:10]:
            name = g.get("gene_symbol") or g.get("symbol", "unknown")
            score = g.get("score", "?")
            if name not in seen:
                print(f"  - {name} (score: {score})")
                seen.add(name)

    print(f"\n✅ Critic-refine smoke test passed")
    print(f"✅ All outputs saved to: {bp_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
