#!/usr/bin/env python3
"""
Smoke test for Phase 2 gene research across multiple BPs.

Uses saved Phase 1 data to test Phase 2 with 3 BPs and final aggregation.

Usage:
    python scripts/phase2_multi_bp_smoketest.py --hallmark "genomic instability"
    python scripts/phase2_multi_bp_smoketest.py --hallmark "genomic instability" --num-bps 3

Requires OPENAI_API_KEY in .env
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from pdb import set_trace
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

from aging_bd_agentic_system.config import LLMConfig, Phase2Config, RunConfig
from aging_bd_agentic_system.graph.workflow import build_phase2_graph
from aging_bd_agentic_system.llm import init_llm, get_llm
from aging_bd_agentic_system.utils.aggregation import aggregate_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 multi-BP smoke test")
    parser.add_argument(
        "--hallmark",
        help="Aging hallmark (must have saved Phase 1 data)",
        default="genomic instability",
    )
    parser.add_argument(
        "--num-bps",
        type=int,
        default=3,
        help="Number of BPs to process (default: 3)",
    )
    parser.add_argument(
        "--max-research-iterations",
        type=int,
        default=2,
        help="Max research iterations per BP (default: 2 for smoke test)",
    )
    return parser.parse_args()


def load_phase1_state(hallmark: str, output_dir: Path) -> dict:
    """Load saved Phase 1 state from full_state.json."""
    state_file = output_dir / hallmark / "full_state.json"
    if not state_file.exists():
        raise FileNotFoundError(
            f"Phase 1 data not found: {state_file}\n"
            f"Run Phase 1 first: python -m aging_bd_agentic_system.main --config config/test_config.yaml"
        )

    with state_file.open("r") as f:
        return json.load(f)


def main() -> int:
    args = parse_args()
    output_dir = Path(__file__).parent.parent / "outputs"

    print(f"\n{'='*60}")
    print(f"PHASE 2 MULTI-BP SMOKE TEST: {args.hallmark}")
    print(f"{'='*60}")

    # Load saved Phase 1 state
    print("\nLoading Phase 1 data...")
    try:
        saved_state = load_phase1_state(args.hallmark, output_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    # Extract key data
    bp_queue = saved_state.get("bp_queue", [])
    config_dict = saved_state.get("config", {})

    if not bp_queue:
        print("ERROR: No BPs found in saved state")
        return 1

    # Take first N BPs
    num_bps = min(args.num_bps, len(bp_queue))
    selected_bps = bp_queue[:num_bps]

    print(f"Loaded {len(bp_queue)} BPs from Phase 1")
    print(f"Testing {num_bps} BPs:")
    for i, bp in enumerate(selected_bps):
        print(f"  [{i}] {bp}")

    # Configure LLM for OpenAI
    llm_config = LLMConfig(
        provider="openai",
        model="gpt-5-nano",
        temperature=0.7,
    )

    # Build RunConfig from saved config dict
    config = RunConfig()
    config.hallmark = config_dict.get("hallmark", args.hallmark)
    config.output_dir = Path(config_dict.get("output_dir", str(output_dir)))
    config.use_llm_summarization = config_dict.get("use_llm_summarization", True)
    config.phase1_only = False  # We want to run Phase 2
    config.llm = llm_config

    # Override for smoke test
    config.phase2.max_research_iterations = args.max_research_iterations
    config.phase2.max_refine_iterations = 1
    config.phase2.genage_seed_max_results = 30
    config.phase2.opengenes_seed_results_per_query = 15
    config.phase2.phase2_vector_db_top_k = 5
    config.phase2.phase2_pubmed_retmax = 5

    # Initialize LLM
    init_llm(config.llm)

    # Build initial state for Phase 2 with multiple BPs
    initial_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "biological_processes": saved_state.get("biological_processes", []),
        "bp_queue": selected_bps,  # Multiple BPs
        "current_bp_index": 0,
        "current_bp_name": selected_bps[0],
        "phase2_research_iteration": 0,
        "phase2_critic_iteration": 0,
        "phase2_eval": {},
        "genes_found": [],
        "go_terms_found": [],
        "tool_call_history": [],
        "reasoning_trace": [],
        "warnings": [],
    }

    # Run Phase 2 graph
    print(f"\n{'='*60}")
    print(f"Running Phase 2 for {num_bps} BPs...")
    print(f"{'='*60}")

    graph = build_phase2_graph()
    result = graph.invoke(initial_state)

    # Get raw results
    raw_genes = result.get("genes_found", [])
    raw_go_terms = result.get("go_terms_found", [])

    # Run aggregation
    print(f"\n{'='*60}")
    print("Running final aggregation...")
    print(f"{'='*60}")

    genes, go_terms = aggregate_outputs(raw_genes, raw_go_terms)

    # Summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Raw genes collected: {len(raw_genes)}")
    print(f"After aggregation: {len(genes)} unique genes")
    print(f"Raw GO terms collected: {len(raw_go_terms)}")
    print(f"After aggregation: {len(go_terms)} unique GO terms")

    if genes:
        print(f"\nTop genes (first 15):")
        seen = set()
        count = 0
        for g in genes:
            name = g.get("gene_symbol") or g.get("symbol") or g.get("gene_name", "unknown")
            if name not in seen and count < 15:
                score = g.get("score", "?")
                print(f"  - {name} (score: {score})")
                seen.add(name)
                count += 1

    # Per-BP breakdown
    print(f"\nGenes per BP:")
    bp_gene_counts = {}
    for g in raw_genes:
        bp = g.get("biological_process", "unknown")
        bp_gene_counts[bp] = bp_gene_counts.get(bp, 0) + 1
    for bp, count in bp_gene_counts.items():
        print(f"  - {bp[:50]}...: {count} genes")

    print(f"\n✅ Phase 2 multi-BP smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
