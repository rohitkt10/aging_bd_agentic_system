#!/usr/bin/env python3
"""
Aggregate per-BP gene results into a hallmark-level table.

Prerequisites:
    - Phase 1 complete: outputs/<hallmark>/processes.tsv must exist
    - Phase 2 complete: outputs/<hallmark>/bp{i}/scored_genes.tsv must exist for all BPs

Usage:
    # From project root, after all phase 1 + phase 2 BP jobs have finished:
    python run_scripts/run_aggregation.py --config <config_path>

    # With a custom hallmark_core threshold (default 0.5 = gene must appear in >50% of BPs):
    python run_scripts/run_aggregation.py --config <config_path> --k-threshold 0.3

Output:
    outputs/<hallmark>/hallmark_genes.tsv  — hallmark-level ranked gene table
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from aging_bd_agentic_system.config import RunConfig
from aging_bd_agentic_system.utils.aggregation import aggregate_hallmark_genes
from aging_bd_agentic_system.utils.output_writer import write_hallmark_genes_tsv

REPO_ROOT = Path(__file__).parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate per-BP genes into hallmark table")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument(
        "--k-threshold",
        type=float,
        default=0.5,
        help="Fraction of BPs a gene must appear in to be flagged hallmark_core (default: 0.5)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        return 1

    config = RunConfig.from_yaml(config_path)
    if not Path(config.output_dir).is_absolute():
        config.output_dir = REPO_ROOT / config.output_dir

    hallmark_dir = Path(config.output_dir) / config.hallmark

    print(f"\n{'='*60}")
    print(f"AGGREGATION: {config.hallmark}")
    print(f"{'='*60}")
    print(f"Output dir:  {hallmark_dir}")
    print(f"k_threshold: {args.k_threshold}")

    try:
        df = aggregate_hallmark_genes(
            output_dir=config.output_dir,
            hallmark=config.hallmark,
            k_threshold=args.k_threshold,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    out_path = write_hallmark_genes_tsv(hallmark_dir, df)

    print(f"\nTotal genes:      {len(df)}")
    print(f"Hallmark core:    {df['hallmark_core'].sum()}")
    print(f"Max score range:  {df['max_score'].min()} - {df['max_score'].max()}")
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
