#!/usr/bin/env python3

import argparse
from pathlib import Path
import torch
from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.literature_pipeline.indexing import (
    build_faiss_index_from_chunks,
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=config.CHUNKS_DIR / "chunks.jsonl",
        help="Path to chunks.jsonl",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=config.INDEX_DIR,
        help="Directory to write FAISS artifacts.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing index if present.",
    )
    args = parser.parse_args()

    faiss_path, lookup_path, meta_path = build_faiss_index_from_chunks(
        chunks_path=args.chunks_path,
        out_dir=args.out_dir,
        model_id=config.EMBEDDING_MODEL_ID,
        batch_size=config.EMBEDDING_BATCH_SIZE,
        device="cuda" if torch.cuda.is_available() else "cpu",
        force=args.force,
    )

    print("Index built successfully:")
    print(f"  FAISS:  {faiss_path}")
    print(f"  Lookup: {lookup_path}")
    print(f"  Meta:   {meta_path}")


if __name__ == "__main__":
    main()
