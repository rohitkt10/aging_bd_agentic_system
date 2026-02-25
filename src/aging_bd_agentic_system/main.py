"""
Main entry point for the aging BD agentic system.

Usage:
    python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"
    python -m aging_bd_agentic_system.main --hallmark "..." --config config.yaml
    python -m aging_bd_agentic_system.main --hallmark "..." --max-iterations 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aging_bd_agentic_system.config import REPO_ROOT, RunConfig
from aging_bd_agentic_system.graph.workflow import build_workflow
from aging_bd_agentic_system.llm import init_llm
from aging_bd_agentic_system.observability.tracing import create_tracing_callback
from aging_bd_agentic_system.utils.aggregation import aggregate_outputs
from aging_bd_agentic_system.utils.audit_logger import log_event
from aging_bd_agentic_system.utils.output_writer import (
    ensure_output_dir,
    write_genes_tsv,
    write_go_terms_tsv,
    write_processes_tsv,
)
from aging_bd_agentic_system.utils.validation import validate_all

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run aging BD workflow for hallmark curation"
    )

    # Required
    parser.add_argument(
        "--hallmark", required=True, help="Aging hallmark name (e.g., 'epigenetic alterations')"
    )

    # Config file
    parser.add_argument(
        "--config", type=Path, help="Path to YAML config file"
    )

    # Output
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "outputs"),
        help="Base directory for output artifacts",
    )

    # Phase 1 overrides
    parser.add_argument("--min-research-goals", type=int, help="Min research goals")
    parser.add_argument("--max-research-goals", type=int, help="Max research goals")
    parser.add_argument("--vector-db-top-k", type=int, help="Vector DB results per query")
    parser.add_argument("--pubmed-retmax", type=int, help="PubMed results per query")
    parser.add_argument("--max-iterations", type=int, help="Max refinement iterations")
    parser.add_argument("--max-processes", type=int, help="Max final processes")

    # Phase 2 overrides
    parser.add_argument(
        "--max-research-iterations", type=int, help="Max research iterations per BP"
    )
    parser.add_argument(
        "--max-refine-iterations", type=int, help="Max refine iterations per BP"
    )

    return parser.parse_args()


def _initial_state(config: RunConfig) -> dict[str, Any]:
    """Build the initial ResearchState dictionary with config."""
    return {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "tool_call_history": [],
        "reasoning_trace": [],
        "warnings": [],
        "lopez_otin_context": "",
        "context_summary": None,
        "token_count": 0,
        "research_scratchpad": "",
        "phase1_plan": {},
        "phase1_iteration": 0,
        "phase1_critique": None,
        "phase1_critic_recommendations": None,
        "phase1_eval": None,
        "biological_processes": [],
        "bp_queue": [],
        "current_bp_index": 0,
        "current_bp_name": "",
        "phase2_critic_iteration": 0,
        "phase2_research_iteration": 0,
        "phase2_eval": {},
        "genes_found": [],
        "go_terms_found": [],
    }


def main() -> None:
    args = parse_args()

    # Build config: defaults → YAML → CLI
    config = RunConfig()

    if args.config:
        config = RunConfig.from_yaml(args.config)

    config = config.merge_cli(
        hallmark=args.hallmark,
        output_dir=args.output_dir,
        min_research_goals=args.min_research_goals,
        max_research_goals=args.max_research_goals,
        vector_db_top_k=args.vector_db_top_k,
        pubmed_retmax=args.pubmed_retmax,
        max_iterations=args.max_iterations,
        max_processes=args.max_processes,
        max_research_iterations=args.max_research_iterations,
        max_refine_iterations=args.max_refine_iterations,
    )

    # Initialize LLM client with config
    init_llm(config.llm)

    # Create tracing callback for observability
    tracing_handler = create_tracing_callback(hallmark_name=config.hallmark)

    graph = build_workflow()
    state = _initial_state(config)

    # Invoke workflow with tracing callback
    result = graph.invoke(state, config={"callbacks": [tracing_handler]})

    genes, go_terms = aggregate_outputs(
        result.get("genes_found", []), result.get("go_terms_found", [])
    )
    processes = result.get("biological_processes", [])

    # Warn if total GO terms is low
    if len(go_terms) < 50:
        print(
            f"WARNING: Only {len(go_terms)} GO terms found. Expected at least 50."
        )

    validation = validate_all(processes, genes, go_terms)
    if not validation["passed"]:
        print("Validation issues:")
        for issue in validation["issues"]:
            print(f"- {issue}")

    out_dir = ensure_output_dir(config.output_dir, config.hallmark)
    write_processes_tsv(out_dir, processes)
    write_genes_tsv(out_dir, genes)
    write_go_terms_tsv(out_dir, go_terms)

    # Write full state to JSON for complete audit trail
    state_file = out_dir / "full_state.json"
    with state_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    # Log workflow completion event
    log_event(
        {
            "hallmark": config.hallmark,
            "event_type": "workflow_complete",
            "biological_processes_count": len(processes),
            "genes_count": len(genes),
            "go_terms_count": len(go_terms),
            "go_terms_below_threshold": len(go_terms) < 50,
            "validation_passed": validation.get("passed", False),
            "validation_issues": validation.get("issues", []),
        }
    )

    print(
        f"Completed hallmark '{config.hallmark}'. "
        f"BPs={len(processes)}, genes={len(genes)}, GO terms={len(go_terms)}."
    )


if __name__ == "__main__":
    main()
