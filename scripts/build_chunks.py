#!/usr/bin/env python3

import argparse
from pathlib import Path

from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.literature_pipeline.chunking import build_chunks_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=config.RAW_DIR,
        help="Directory containing PMC XML files.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=config.CHUNKS_DIR,
        help="Directory to write chunks.jsonl.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=config.RAW_DIR / "manifest.jsonl",
        help="Manifest JSONL from ingestion (optional).",
    )
    args = parser.parse_args()

    chunks_path, meta_path = build_chunks_dataset(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        chunk_size_words=config.CHUNK_SIZE_WORDS,
        overlap_words=config.CHUNK_OVERLAP_WORDS,
        min_words=config.MIN_WORDS,
        manifest_path=args.manifest if args.manifest.exists() else None,
    )

    print(f"Chunks written to: {chunks_path}")
    print(f"Chunk metadata: {meta_path}")


if __name__ == "__main__":
    main()
