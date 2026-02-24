#!/usr/bin/env python3
"""
Smoke test for Phase 1 biological process identification.

Usage:
    python scripts/phase1_research_smoketest.py --hallmark "epigenetic alterations"

Requires OPENAI_API_KEY in .env
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pdb import set_trace
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

from aging_bd_agentic_system.config import LLMConfig, Phase1Config, RunConfig
from aging_bd_agentic_system.graph.workflow import build_phase1_graph
from aging_bd_agentic_system.llm import init_llm, get_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 smoke test")
    parser.add_argument("--hallmark", help="Aging hallmark", default="genomic instability")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Configure LLM for OpenAI
    llm_config = LLMConfig(
                provider="openai",
                model="gpt-5-nano",
                temperature=0.7,
    )

    # Explicitly configure for smoke test
    config = RunConfig(
        hallmark=args.hallmark,
        llm=llm_config,
        phase1=Phase1Config(
            min_research_goals=2,
            max_research_goals=3,
            vector_db_top_k=5,
            pubmed_retmax=5,
            max_iterations=1,
            max_processes=10,
        ),
    )

    # Initialize LLM with config
    init_llm(config.llm)
    client = get_llm()

    print(f"\n{'='*50}")
    print(f"Phase 1 Smoke Test: {args.hallmark}")
    print(f"{'='*50}")
    print(f"Config: max_iterations={config.phase1.max_iterations}, max_processes={config.phase1.max_processes}")

    # Build state with config
    initial_state = {
        "hallmark_name": args.hallmark,
        "config": config.to_dict(),
    }

    # Run Phase 1 graph
    graph = build_phase1_graph()
    
    print("\nRunning Phase 1...")
    result = graph.invoke(initial_state)

    set_trace()

    # Summary
    processes = result.get("biological_processes", [])
    bp_queue = result.get("bp_queue", [])

    print(f"\n{'='*50}")
    print("RESULTS")
    print(f"{'='*50}")
    print(f"Processes found: {len(processes)}")
    print(f"BP Queue: {len(bp_queue)}")

    if processes:
        print("\nTop 3:")
        for p in processes[:3]:
            print(f"  - {p.get('process_name')} (score: {p.get('evidence_score')})")

    print("\n✅ Smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
