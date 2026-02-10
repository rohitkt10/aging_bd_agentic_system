#!/usr/bin/env python3

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.literature_pipeline.ingestion import fetch_pmc_corpus


def default_query(start_year: int, end_year: int) -> str:
    return (
        '("Aging"[MeSH] OR "Ageing"[Title/Abstract] OR "aging"[Title/Abstract]) AND '
        '("Biological Aging"[MeSH] OR "cellular senescence"[MeSH] '
        'OR "senescence"[Title/Abstract] OR "longevity"[Title/Abstract]) '
        f'AND ("{start_year}"[dp] : "{end_year}"[dp])'
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-year", type=int, default=datetime.now().year)
    parser.add_argument("--query", type=str, default=None)
    parser.add_argument("--oversample", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.4)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=config.RAW_DIR / "manifest.jsonl",
    )
    args = parser.parse_args()

    email = os.environ.get("NCBI_EMAIL")
    if not email:
        print("Error: NCBI_EMAIL must be set in .env", file=sys.stderr)
        sys.exit(2)

    api_key = os.environ.get("NCBI_API_KEY")
    query = args.query or default_query(args.start_year, args.end_year)

    counts = fetch_pmc_corpus(
        query=query,
        out_dir=config.RAW_DIR,
        email=email,
        target_n=args.n,
        oversample=args.oversample,
        sleep_s=args.sleep,
        api_key=api_key,
        resume=True,
        manifest_path=args.manifest,
    )

    print(f"Done. Summary: {counts}")
    print(f"Manifest: {args.manifest.resolve()}")


if __name__ == "__main__":
    main()
