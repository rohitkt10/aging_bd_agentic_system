from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from pydantic import BaseModel, Field

from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.literature_pipeline.embedding import embed_texts


def _load_lookup(lookup_path: Path) -> dict[int, dict[str, Any]]:
    """Load lookup.jsonl records keyed by row_id."""
    if not lookup_path.exists():
        raise FileNotFoundError(f"Lookup file not found: {lookup_path}")

    lookup: dict[int, dict[str, Any]] = {}
    with lookup_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            row_id = record.get("row_id")
            if row_id is None:
                raise ValueError(f"Missing row_id in lookup line {line_num}")
            lookup[int(row_id)] = record
    return lookup


def _load_index_meta(meta_path: Path) -> dict[str, Any]:
    """Load FAISS index metadata (index.meta.json)."""
    if not meta_path.exists():
        raise FileNotFoundError(f"Index metadata not found: {meta_path}")
    with meta_path.open("r", encoding="utf-8") as f:
        return json.load(f)


class VectorDbQuerySchema(BaseModel):
    """Schema for vector DB search tool - enables LLM to understand parameters."""

    query: str = Field(
        description="Search text for the literature index (e.g., 'cellular senescence')"
    )
    top_k: int = Field(
        default=5, description="Maximum number of chunks to return (1-50)"
    )
    index_dir: str | None = Field(
        default=None,
        description=(
            "Optional path to FAISS artifacts directory (default: data/corpus/index)"
        ),
    )
    device: str = Field(
        default="cpu",
        description="Embedding device ('cpu' or 'cuda'); must match available hardware",
    )


def query_vector_db(
    query: str,
    *,
    top_k: int = 5,
    index_dir: Path | None = None,
    device: str = "cpu",
) -> list[dict[str, Any]]:
    """
    Search the FAISS index for relevant literature chunks.

    Args:
        query: Natural language search query (e.g., "DNA damage aging")
        top_k: Maximum number of chunks to return (default 5)
        index_dir: Optional path to FAISS artifacts directory
        device: Embedding device ("cpu" or "cuda")

    Returns:
        List of chunk records, each containing:
        - score: Similarity score (float)
        - text: Chunk text content
        - pmcid: PubMed Central ID
        - pmid: PubMed ID (if available)
        - section_title: Section title in the source paper
        - source_xml: Path to source XML file
        - chunk_id: Global chunk identifier
        - ...additional fields from lookup.jsonl

    Example:
        results = query_vector_db("epigenetic alterations aging", top_k=5)
    """
    if not query.strip():
        raise ValueError("Query must be non-empty.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")

    index_dir = index_dir or config.INDEX_DIR
    faiss_path = index_dir / "faiss.index"
    lookup_path = index_dir / "lookup.jsonl"
    meta_path = index_dir / "index.meta.json"

    if not faiss_path.exists():
        raise FileNotFoundError(f"FAISS index not found: {faiss_path}")

    index = faiss.read_index(str(faiss_path))
    meta = _load_index_meta(meta_path)
    model_id = meta.get("model_id", config.EMBEDDING_MODEL_ID)

    embeddings = embed_texts(
        [query],
        model_id=model_id,
        batch_size=1,
        device=device,
        normalize=True,
    ).astype(np.float32)

    scores, ids = index.search(embeddings, top_k)
    lookup = _load_lookup(lookup_path)

    results: list[dict[str, Any]] = []
    for score, row_id in zip(scores[0].tolist(), ids[0].tolist()):
        if row_id == -1:
            continue
        row = lookup.get(int(row_id))
        if not row:
            continue
        results.append({"score": float(score), **row})

    return results
