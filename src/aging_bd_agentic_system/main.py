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
from aging_bd_agentic_system.graph.workflow import build_workflow, build_phase1_graph
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

    # Required (can also be set in config file)
    parser.add_argument(
        "--hallmark",
        required=False,
        help="Aging hallmark name (e.g., 'epigenetic alterations')"
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
    parser.add_argument(
        "--use-llm-summarization",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        help="Use LLM for context summarization (true/false)"
    )
    parser.add_argument(
        "--phase1-only",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=None,
        help="Terminate after Phase 1 (skip gene research) (true/false)"
    )

    # LLM overrides
    parser.add_argument("--provider", help="LLM provider (vertex/openai)")
    parser.add_argument("--model", help="Model name (provider-specific)")
    parser.add_argument("--temperature", type=float, help="Sampling temperature (0.0-1.0)")
    parser.add_argument("--max-tokens", type=int, help="Max tokens in response")
    parser.add_argument("--vertex-location", help="Vertex AI region")
    parser.add_argument("--openai-base-url", help="Custom OpenAI base URL")

    # Phase 1 overrides
    parser.add_argument("--min-research-goals", type=int, help="Min research goals")
    parser.add_argument("--max-research-goals", type=int, help="Max research goals")
    parser.add_argument("--phase1-vector-db-top-k", type=int, help="Phase 1: Vector DB results per query")
    parser.add_argument("--phase1-pubmed-retmax", type=int, help="Phase 1: PubMed results per query")
    parser.add_argument("--max-iterations", type=int, help="Max refinement iterations")
    parser.add_argument("--max-processes", type=int, help="Max final processes")
    parser.add_argument("--summary-max-words", type=int, help="Max words per goal summary")

    # Phase 2 overrides
    parser.add_argument(
        "--max-research-iterations", type=int, help="Max research iterations per BP"
    )
    parser.add_argument(
        "--max-refine-iterations", type=int, help="Max refine iterations per BP"
    )
    parser.add_argument(
        "--genage-seed-max-results", type=int, help="Max GenAge results during gene seeding"
    )
    parser.add_argument(
        "--opengenes-seed-max-results", type=int, help="Max OpenGenes results during gene seeding"
    )
    parser.add_argument(
        "--phase2-vector-db-top-k", type=int, help="Phase 2: Vector DB results per query"
    )
    parser.add_argument(
        "--phase2-pubmed-retmax", type=int, help="Phase 2: PubMed results per query"
    )

    return parser.parse_args()


def _print_config(config: RunConfig) -> None:
    """Print the final resolved configuration to stdout."""
    config_dict = config.to_dict()

    print("\n" + "=" * 60)
    print("CONFIGURATION")
    print("=" * 60)

    # Top-level
    print(f"\n[hallmark] {config_dict.get('hallmark')}")
    print(f"[output_dir] {config_dict.get('output_dir')}")
    print(f"[use_llm_summarization] {config_dict.get('use_llm_summarization')}")
    print(f"[phase1_only] {config_dict.get('phase1_only')}")

    # LLM
    llm = config_dict.get("llm", {})
    print(f"\n[llm]")
    print(f"  provider: {llm.get('provider')}")
    print(f"  model: {llm.get('model')}")
    print(f"  temperature: {llm.get('temperature')}")
    print(f"  max_tokens: {llm.get('max_tokens')}")
    print(f"  vertex_location: {llm.get('vertex_location')}")
    print(f"  openai_base_url: {llm.get('openai_base_url')}")

    # Phase 1
    p1 = config_dict.get("phase1", {})
    print(f"\n[phase1]")
    print(f"  min_research_goals: {p1.get('min_research_goals')}")
    print(f"  max_research_goals: {p1.get('max_research_goals')}")
    print(f"  phase1_vector_db_top_k: {p1.get('phase1_vector_db_top_k')}")
    print(f"  phase1_pubmed_retmax: {p1.get('phase1_pubmed_retmax')}")
    print(f"  max_iterations: {p1.get('max_iterations')}")
    print(f"  max_processes: {p1.get('max_processes')}")
    print(f"  summary_max_words: {p1.get('summary_max_words')}")

    # Phase 2
    p2 = config_dict.get("phase2", {})
    print(f"\n[phase2]")
    print(f"  max_research_iterations: {p2.get('max_research_iterations')}")
    print(f"  max_refine_iterations: {p2.get('max_refine_iterations')}")
    print(f"  genage_seed_max_results: {p2.get('genage_seed_max_results')}")
    print(f"  opengenes_seed_max_results: {p2.get('opengenes_seed_max_results')}")
    print(f"  phase2_vector_db_top_k: {p2.get('phase2_vector_db_top_k')}")
    print(f"  phase2_pubmed_retmax: {p2.get('phase2_pubmed_retmax')}")

    print("\n" + "=" * 60 + "\n")


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
        use_llm_summarization=args.use_llm_summarization,
        phase1_only=args.phase1_only,
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        vertex_location=args.vertex_location,
        openai_base_url=args.openai_base_url,
        min_research_goals=args.min_research_goals,
        max_research_goals=args.max_research_goals,
        phase1_vector_db_top_k=args.phase1_vector_db_top_k,
        phase1_pubmed_retmax=args.phase1_pubmed_retmax,
        max_iterations=args.max_iterations,
        max_processes=args.max_processes,
        summary_max_words=args.summary_max_words,
        max_research_iterations=args.max_research_iterations,
        max_refine_iterations=args.max_refine_iterations,
        genage_seed_max_results=args.genage_seed_max_results,
        opengenes_seed_max_results=args.opengenes_seed_max_results,
        phase2_vector_db_top_k=args.phase2_vector_db_top_k,
        phase2_pubmed_retmax=args.phase2_pubmed_retmax,
    )

    # Validate hallmark is set
    if not config.hallmark:
        raise ValueError("--hallmark is required (or set it in config file)")

    # Print final config before starting workflow
    _print_config(config)

    # Initialize LLM client with config
    init_llm(config.llm)

    # Create tracing callback for observability
    tracing_handler = create_tracing_callback(
        hallmark_name=config.hallmark, output_dir=config.output_dir
    )

    # Build graph based on phase1_only flag
    if config.phase1_only:
        graph = build_phase1_graph()
    else:
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
        },
        output_dir=config.output_dir,
    )

    print(
        f"Completed hallmark '{config.hallmark}'. "
        f"BPs={len(processes)}, genes={len(genes)}, GO terms={len(go_terms)}."
    )


if __name__ == "__main__":
    main()
