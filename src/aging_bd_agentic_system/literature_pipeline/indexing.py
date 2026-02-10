from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from pdb import set_trace 
import faiss
import numpy as np

from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.literature_pipeline.embedding import embed_texts


def load_chunks(jsonl_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Load text chunks and metadata from a JSONL file.
    """
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Chunks file not found: {jsonl_path}")

    texts: list[str] = []
    metas: list[dict[str, Any]] = []

    with jsonl_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: Skipping invalid JSON at line {line_num}", file=sys.stderr)
                continue

            if "text" not in record:
                raise ValueError(f"Record at line {line_num} missing required 'text' field.")

            texts.append(record["text"])
            metas.append(record)

    return texts, metas


def build_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """
    Build a FAISS inner-product index from normalized embeddings.
    """
    d = embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    return index


def save_artifacts(
    index: faiss.Index,
    metas: list[dict[str, Any]],
    out_dir: Path,
    run_meta: dict[str, Any],
) -> tuple[Path, Path, Path]:
    """
    Save FAISS index, lookup table, and run metadata.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    faiss_path = out_dir / "faiss.index"
    lookup_path = out_dir / "lookup.jsonl"
    meta_path = out_dir / "index.meta.json"

    faiss.write_index(index, str(faiss_path))

    with lookup_path.open("w", encoding="utf-8") as f:
        for i, meta in enumerate(metas):
            row = {"row_id": i, **meta}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(run_meta, f, indent=2)

    return faiss_path, lookup_path, meta_path


def build_faiss_index_from_chunks(
    chunks_path: Path,
    out_dir: Path,
    model_id: str,
    batch_size: int,
    device: str,
    metric: str = "cosine",
    force: bool = False,
) -> tuple[Path, Path, Path]:
    """
    Load chunks → embed → build FAISS index → write artifacts.
    """
    if not chunks_path.exists():
        raise ValueError(f"Chunks file not found: {chunks_path}")

    if metric != "cosine":
        raise ValueError("Only cosine similarity is supported.")

    if not force and (out_dir / "faiss.index").exists():
        raise ValueError(f"Index already exists in {out_dir}. Use --force to overwrite.")

    print(f"Loading chunks from {chunks_path}...")
    texts, metas = load_chunks(chunks_path)

    if not texts:
        raise ValueError("No chunks found.")
    
    print(f"Embedding {len(texts)} chunks (model={model_id})...")
    embeddings = embed_texts(
        texts,
        model_id=model_id,
        batch_size=batch_size,
        device=device,
        normalize=True,
    )

    print(f"Building FAISS index (dim={embeddings.shape[1]})...")
    index = build_faiss_index(embeddings)

    run_meta = {
        "created_at": datetime.now(UTC).isoformat(),
        "metric": metric,
        "model_id": model_id,
        "device": device,
        "batch_size": batch_size,
        "embedding_dim": int(embeddings.shape[1]),
        "num_chunks": len(texts),
        "chunk_size_words": config.CHUNK_SIZE_WORDS,
        "chunk_overlap_words": config.CHUNK_OVERLAP_WORDS,
        "source_chunks_path": str(chunks_path),
    }

    print(f"Saving artifacts to {out_dir}...")
    return save_artifacts(index, metas, out_dir, run_meta)
