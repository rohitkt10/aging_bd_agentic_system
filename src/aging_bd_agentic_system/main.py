from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aging_bd_agentic_system.graph.workflow import build_workflow
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
        "phase2_critic_iteration": 0,
        "phase2_research_iteration": 0,
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

    # Create tracing callback for observability
    tracing_handler = create_tracing_callback(hallmark_name=args.hallmark)

    graph = build_workflow()
    state = _initial_state(args.hallmark)

    # Invoke workflow with tracing callback
    result = graph.invoke(state, config={"callbacks": [tracing_handler]})

    genes, go_terms = aggregate_outputs(
        result.get("genes_found", []), result.get("go_terms_found", [])
    )
    processes = result.get("biological_processes", [])

    # Warn if total GO terms is low
    if len(go_terms) < 50:
        print(f"WARNING: Only {len(go_terms)} GO terms found across all biological processes. Expected at least 50.")

    validation = validate_all(processes, genes, go_terms)
    if not validation["passed"]:
        print("Validation issues:")
        for issue in validation["issues"]:
            print(f"- {issue}")

    out_dir = ensure_output_dir(Path(args.output_dir), args.hallmark)
    write_processes_tsv(out_dir, processes)
    write_genes_tsv(out_dir, genes)
    write_go_terms_tsv(out_dir, go_terms)

    # Write full state to JSON for complete audit trail
    state_file = out_dir / "full_state.json"
    with state_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    # Log workflow completion event
    log_event({
        "hallmark": args.hallmark,
        "event_type": "workflow_complete",
        "biological_processes_count": len(processes),
        "genes_count": len(genes),
        "go_terms_count": len(go_terms),
        "go_terms_below_threshold": len(go_terms) < 50,
        "validation_passed": validation.get("passed", False),
        "validation_issues": validation.get("issues", []),
    })

    print(
        f"Completed hallmark '{args.hallmark}'. BPs={len(processes)}, "
        f"genes={len(genes)}, GO terms={len(go_terms)}."
    )


if __name__ == "__main__":
    main()
