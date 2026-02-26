#!/usr/bin/env python3
"""
Smoke test for Phase 2 gene research.

Uses saved Phase 1 data to test Phase 2 independently.

Usage:
    python scripts/phase2_research_smoketest.py --hallmark "genomic instability"
    python scripts/phase2_research_smoketest.py --hallmark "genomic instability" --bp-index 0

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

from aging_bd_agentic_system.config import RunConfig
from aging_bd_agentic_system.graph.workflow import build_phase2_graph
from aging_bd_agentic_system.llm import init_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 smoke test")
    parser.add_argument(
        "--hallmark",
        help="Aging hallmark (must have saved Phase 1 data)",
        default="genomic instability",
    )
    parser.add_argument(
        "--bp-index",
        type=int,
        default=0,
        help="Index of BP in queue to test (default: 0 = first BP)",
    )
    parser.add_argument(
        "--max-research-iterations",
        type=int,
        default=1,
        help="Max research iterations per BP (default: 1 for smoke test)",
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
    print(f"PHASE 2 SMOKE TEST: {args.hallmark}")
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

    if args.bp_index >= len(bp_queue):
        print(f"ERROR: bp_index {args.bp_index} out of range (queue has {len(bp_queue)} BPs)")
        return 1

    print(f"Loaded {len(bp_queue)} BPs from Phase 1")
    print(f"Testing BP [{args.bp_index}]: {bp_queue[args.bp_index]}")

    # Build RunConfig from saved config dict
    config = RunConfig()
    config.hallmark = config_dict.get("hallmark", args.hallmark)
    config.output_dir = Path(config_dict.get("output_dir", str(output_dir)))
    config.use_llm_summarization = config_dict.get("use_llm_summarization", True)
    config.phase1_only = False  # We want to run Phase 2

    # Override for smoke test
    config.phase2.max_research_iterations = args.max_research_iterations
    config.phase2.max_refine_iterations = 1
    config.phase2.genage_seed_max_results = 10
    config.phase2.opengenes_seed_max_results = 10

    # Initialize LLM
    init_llm(config.llm)

    # Build initial state for Phase 2
    # Only process the single BP we want to test
    initial_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "biological_processes": saved_state.get("biological_processes", []),
        "bp_queue": [bp_queue[args.bp_index]],  # Single BP
        "current_bp_index": 0,
        "current_bp_name": bp_queue[args.bp_index],
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
    print("Running Phase 2...")
    print(f"{'='*60}")
    set_trace()
    graph = build_phase2_graph()
    result = graph.invoke(initial_state)

    # Summary
    genes = result.get("genes_found", [])
    go_terms = result.get("go_terms_found", [])

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Genes found: {len(genes)}")
    print(f"GO terms found: {len(go_terms)}")

    if genes:
        print("\nTop genes:")
        seen = set()
        for g in genes[:10]:
            name = g.get("gene_name") or g.get("symbol", "unknown")
            if name not in seen:
                print(f"  - {name}")
                seen.add(name)

    print("\n✅ Phase 2 smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
