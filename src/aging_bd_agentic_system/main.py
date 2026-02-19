from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from aging_bd_agentic_system.graph.workflow import build_workflow
from aging_bd_agentic_system.utils.aggregation import aggregate_outputs
from aging_bd_agentic_system.utils.output_writer import (
    ensure_output_dir,
    write_genes_tsv,
    write_go_terms_tsv,
    write_processes_tsv,
)
from aging_bd_agentic_system.utils.validation import validate_all


def _initial_state(hallmark: str) -> dict[str, Any]:
    """Build the initial ResearchState dictionary."""
    return {
        "hallmark_name": hallmark,
        "tool_call_history": [],
        "reasoning_trace": [],
        "warnings": [],
        "lopez_otin_context": "",
        "context_summary": None,
        "token_count": 0,
        "research_scratchpad": "",
        "phase1_plan": [],
        "phase1_iteration": 0,
        "phase1_eval": {},
        "biological_processes": [],
        "bp_queue": [],
        "current_bp_index": 0,
        "current_bp_name": "",
        "phase2_iteration": 0,
        "phase2_eval": {},
        "genes_found": [],
        "go_terms_found": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run aging BD workflow")
    parser.add_argument("--hallmark", required=True, help="Aging hallmark name")
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Base directory for output artifacts",
    )
    args = parser.parse_args()

    graph = build_workflow()
    state = _initial_state(args.hallmark)
    result = graph.invoke(state)

    genes, go_terms = aggregate_outputs(
        result.get("genes_found", []), result.get("go_terms_found", [])
    )
    processes = result.get("biological_processes", [])

    validation = validate_all(processes, genes, go_terms)
    if not validation["passed"]:
        print("Validation issues:")
        for issue in validation["issues"]:
            print(f"- {issue}")

    out_dir = ensure_output_dir(Path(args.output_dir), args.hallmark)
    write_processes_tsv(out_dir, processes)
    write_genes_tsv(out_dir, genes)
    write_go_terms_tsv(out_dir, go_terms)

    print(
        f"Completed hallmark '{args.hallmark}'. BPs={len(processes)}, "
        f"genes={len(genes)}, GO terms={len(go_terms)}."
    )


if __name__ == "__main__":
    main()
