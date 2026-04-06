#!/usr/bin/env python3
"""
Phase 1 script for SLURM-based end-to-end testing.

Generates biological processes for a hallmark and saves outputs for Phase 2.

Usage:
    python test_expt/run_phase1.py
    python test_expt/run_phase1.py --config test_expt/custom_config.yaml

Outputs:
    outputs/test_expt/<hallmark>/
        processes.tsv       - Biological processes with evidence
        full_state.json     - Complete Phase 1 state for Phase 2 to load

Requires OPENAI_API_KEY in .env
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

from aging_bd_agentic_system.config import RunConfig
from aging_bd_agentic_system.graph.workflow import build_phase1_graph
from aging_bd_agentic_system.llm import init_llm
from aging_bd_agentic_system.utils.output_writer import ensure_output_dir, write_processes_tsv


REPO_ROOT = Path(__file__).parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1: Generate biological processes")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to config YAML file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Load config from YAML
    config_path = Path(args.config)
    print(f"CONFIG PATH: {config_path}")
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        return 1

    config = RunConfig.from_yaml(config_path)

    # Ensure output_dir is absolute
    if not Path(config.output_dir).is_absolute():
        config.output_dir = REPO_ROOT / config.output_dir

    # Initialize LLM
    init_llm(config.llm)

    print(f"\n{'='*60}")
    print(f"PHASE 1: BIOLOGICAL PROCESS IDENTIFICATION")
    print(f"{'='*60}")
    print(f"Hallmark: {config.hallmark}")
    print(f"Output dir: {config.output_dir}")
    print(f"LLM: {config.llm.provider}/{config.llm.model}")
    print(f"Max iterations: {config.phase1.max_iterations}")
    print(f"Max processes: {config.phase1.max_processes}")

    # Build initial state
    initial_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
    }

    # Run Phase 1 graph
    print(f"\n{'='*60}")
    print("Running Phase 1...")
    print(f"{'='*60}")

    graph = build_phase1_graph()
    result = graph.invoke(initial_state)

    # Extract results
    processes = result.get("biological_processes", [])
    bp_queue = result.get("bp_queue", [])

    if not processes:
        print("ERROR: No biological processes found")
        return 1

    # Ensure output directory exists
    hallmark_dir = ensure_output_dir(config.output_dir, config.hallmark)

    # Save processes.tsv
    write_processes_tsv(hallmark_dir, processes)
    print(f"Saved: {hallmark_dir / 'processes.tsv'}")

    # Save full state for Phase 2
    state_file = hallmark_dir / "full_state.json"
    with state_file.open("w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Saved: {state_file}")

    # Summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Processes found: {len(processes)}")
    print(f"BP Queue length: {len(bp_queue)}")

    print("\nBiological Processes:")
    for i, p in enumerate(processes, 1):
        print(f"  [{i}] {p.get('process_name')} (score: {p.get('evidence_score')})")

    # Print BP queue for SLURM array job planning
    print(f"\n{'='*60}")
    print("SLURM ARRAY TASK INFO")
    print(f"{'='*60}")
    print(f"Total BPs: {len(bp_queue)}")
    print(f"Array range: 1-{len(bp_queue)}")
    print("\nBP names for --bp-rank argument:")
    for i, bp in enumerate(bp_queue, 1):
        print(f"  --bp-rank {i}: {bp}")

    print(f"\n✅ Phase 1 complete")
    print(f"✅ Outputs saved to: {hallmark_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
