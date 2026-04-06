#!/usr/bin/env python3
"""
Phase 2 script for SLURM-based end-to-end testing.

Runs the complete Phase 2 pipeline for a single biological process using
the isolated graph that handles seeding + research + critic/refine in one flow.

Usage:
    python test_expt/run_phase2_bp.py --bp-rank 1
    python test_expt/run_phase2_bp.py --bp-rank 2 --config test_expt/custom_config.yaml

Prerequisites:
    - Phase 1 must be complete: outputs/test_expt/<hallmark>/full_state.json
    - Processes file: outputs/test_expt/<hallmark>/processes.tsv

Outputs:
    outputs/test_expt/<hallmark>/bp{rank}/
        seed_genes.json           - Initial seed genes from databases
        seeding_queries.json      - OpenGenes queries used for seeding
        gene_evidence.json        - Per-gene evidence accumulator
        state_of_knowledge.json   - Compressed research state
        research_scratchpad.json  - Full research data
        tool_call_history.json    - All tool calls made
        reasoning_trace.json      - LLM reasoning traces
        warnings.json             - Any warnings
        critic_review.json        - Final critic review
        refinement_history.json   - All refinement outputs
        scored_genes.tsv          - Final scored genes
        full_result.json          - Complete result state

Requires OPENAI_API_KEY in .env
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

from aging_bd_agentic_system.config import RunConfig
from aging_bd_agentic_system.graph.workflow import build_phase2_isolated_graph
from aging_bd_agentic_system.llm import init_llm


REPO_ROOT = Path(__file__).parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2: Gene research for single BP")
    parser.add_argument(
        "--bp-rank",
        type=int,
        default=1,
        help="BP rank (1-indexed, matches processes.tsv)",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to config YAML file",
    )
    return parser.parse_args()


def load_phase1_state(hallmark: str, output_dir: Path) -> dict:
    """Load saved Phase 1 state from full_state.json."""
    state_file = output_dir / hallmark / "full_state.json"
    if not state_file.exists():
        raise FileNotFoundError(
            f"Phase 1 data not found: {state_file}\n"
            f"Run Phase 1 first: python test_expt/run_phase1.py"
        )

    with state_file.open("r") as f:
        return json.load(f)


def load_bp_name(hallmark_dir: Path, bp_rank: int) -> str:
    """Load BP name from processes.tsv by rank."""
    processes_file = hallmark_dir / "processes.tsv"
    if not processes_file.exists():
        raise FileNotFoundError(f"Processes file not found: {processes_file}")

    with processes_file.open("r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if int(row["rank"]) == bp_rank:
                return row["process_name"]

    raise ValueError(f"BP rank {bp_rank} not found in {processes_file}")


def save_json(data, path: Path) -> None:
    """Save data as JSON with indent."""
    with path.open("w") as f:
        json.dump(data, f, indent=2, default=str)


def main() -> int:
    args = parse_args()

    # Load config from YAML
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        return 1

    config = RunConfig.from_yaml(config_path)

    # Ensure output_dir is absolute
    if not Path(config.output_dir).is_absolute():
        config.output_dir = REPO_ROOT / config.output_dir

    hallmark_dir = config.output_dir / config.hallmark
    bp_dir = hallmark_dir / f"bp{args.bp_rank}"

    # Create BP-specific output directory
    bp_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"PHASE 2: GENE RESEARCH FOR SINGLE BP (ISOLATED GRAPH)")
    print(f"{'='*60}")
    print(f"Hallmark: {config.hallmark}")
    print(f"BP Rank: {args.bp_rank}")
    print(f"Output dir: {bp_dir}")
    print(f"LLM: {config.llm.provider}/{config.llm.model}")
    print(f"Max research iterations: {config.phase2.max_research_iterations}")
    print(f"Max critic iterations: {config.phase2.max_critic_iterations}")

    # Load Phase 1 state
    print("\nLoading Phase 1 data...")
    try:
        saved_state = load_phase1_state(config.hallmark, config.output_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    # Load BP name
    try:
        bp_name = load_bp_name(hallmark_dir, args.bp_rank)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return 1

    print(f"BP Name: {bp_name}")

    # Initialize LLM
    init_llm(config.llm)

    # =========================================================================
    # BUILD INITIAL STATE FOR ISOLATED GRAPH
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"RUNNING ISOLATED GRAPH: SEEDING + RESEARCH + CRITIC/REFINE")
    print(f"{'='*60}")

    initial_state = {
        "hallmark_name": config.hallmark,
        "config": config.to_dict(),
        "biological_processes": saved_state.get("biological_processes", []),
        "bp_queue": [bp_name],
        "current_bp_index": args.bp_rank - 1,
        "current_bp_name": bp_name,
        "phase2_research_iteration": 0,  # Start at 0 to trigger seeding
        "phase2_critic_iteration": 0,
        "phase2_eval": {},
        "critic_iteration": 0,
        "critic_review": None,
        "refinement_history": [],
        "genes_found": [],
        "go_terms_found": [],
        "tool_call_history": [],
        "reasoning_trace": [],
        "warnings": [],
        "research_scratchpad": "",
        "state_of_knowledge": "",
        "gene_evidence": {},
    }

    # Run isolated graph (handles seeding, research, critic/refine in one flow)
    graph = build_phase2_isolated_graph()
    result = graph.invoke(initial_state)

    # =========================================================================
    # EXTRACT AND SAVE ALL OUTPUTS
    # =========================================================================
    print(f"\n{'='*60}")
    print("SAVING OUTPUTS")
    print(f"{'='*60}")

    # Extract results
    genes_found = result.get("genes_found", [])
    gene_evidence = result.get("gene_evidence", {})
    critic_review = result.get("critic_review", {})
    refinement_history = result.get("refinement_history", [])
    tool_calls = result.get("tool_call_history", [])
    reasoning = result.get("reasoning_trace", [])
    warnings = result.get("warnings", [])
    research_scratchpad = result.get("research_scratchpad", "{}")
    state_of_knowledge = result.get("state_of_knowledge", "{}")

    # Save all outputs
    print(f"Saving outputs to {bp_dir}...")

    # Research data
    scratchpad_data = json.loads(research_scratchpad) if isinstance(research_scratchpad, str) else research_scratchpad
    save_json(scratchpad_data, bp_dir / "research_scratchpad.json")

    # Seed genes (if present in scratchpad)
    if scratchpad_data.get("initial_database_genes"):
        save_json(scratchpad_data["initial_database_genes"], bp_dir / "seed_genes.json")
        print(f"  - seed_genes.json: {len(scratchpad_data['initial_database_genes'])} genes")

    # Seeding queries (if present)
    if scratchpad_data.get("opengenes_seeding_queries"):
        save_json(
            {"opengenes_queries": scratchpad_data["opengenes_seeding_queries"]},
            bp_dir / "seeding_queries.json"
        )
        print(f"  - seeding_queries.json")

    # State of knowledge
    sok_data = json.loads(state_of_knowledge) if isinstance(state_of_knowledge, str) else state_of_knowledge
    save_json(sok_data, bp_dir / "state_of_knowledge.json")
    print(f"  - state_of_knowledge.json")

    # Gene evidence
    save_json(gene_evidence, bp_dir / "gene_evidence.json")
    print(f"  - gene_evidence.json: {len(gene_evidence)} genes")

    # Traces
    save_json(tool_calls, bp_dir / "tool_call_history.json")
    print(f"  - tool_call_history.json: {len(tool_calls)} calls")

    save_json(reasoning, bp_dir / "reasoning_trace.json")
    print(f"  - reasoning_trace.json: {len(reasoning)} entries")

    save_json(warnings, bp_dir / "warnings.json")
    print(f"  - warnings.json: {len(warnings)} warnings")

    # Critic/refine outputs
    save_json(critic_review, bp_dir / "critic_review.json")
    print(f"  - critic_review.json: grade={critic_review.get('grade', 'unknown')}")

    save_json(refinement_history, bp_dir / "refinement_history.json")
    print(f"  - refinement_history.json: {len(refinement_history)} cycles")

    # Full result
    save_json(result, bp_dir / "full_result.json")
    print(f"  - full_result.json")

    # Save genes to TSV
    genes_file = bp_dir / "scored_genes.tsv"
    with genes_file.open("w") as f:
        f.write("gene_symbol\tscore\tevidence_summary\tsources\tbiological_process\n")
        for g in genes_found:
            f.write(
                f"{g.get('gene_symbol', '')}\t"
                f"{g.get('score', '')}\t"
                f"{g.get('evidence_summary', '')}\t"
                f"{','.join(g.get('sources', []))}\t"
                f"{g.get('biological_process', '')}\n"
            )
    print(f"  - scored_genes.tsv: {len(genes_found)} genes")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total genes: {len(genes_found)}")
    print(f"Critic grade: {critic_review.get('grade', 'unknown')}")
    print(f"Refinement cycles: {len(refinement_history)}")
    print(f"Tool calls: {len(tool_calls)}")
    print(f"Warnings: {len(warnings)}")

    if genes_found:
        print("\nTop genes:")
        seen = set()
        for g in genes_found[:10]:
            name = g.get("gene_symbol") or g.get("symbol", "unknown")
            score = g.get("score", "?")
            if name not in seen:
                print(f"  - {name} (score: {score})")
                seen.add(name)

    print(f"\n✅ Phase 2 complete for BP {args.bp_rank}")
    print(f"✅ All outputs saved to: {bp_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
