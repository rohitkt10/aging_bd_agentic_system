from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch

import faiss
import numpy as np
from pydantic import BaseModel, Field

from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.literature_pipeline.config import EMBEDDING_MODEL_ID

from sentence_transformers import SentenceTransformer
from transformers.utils import logging as hf_logging
import logging
hf_logging.set_verbosity_error()
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)


_global_emb_model  = None
def init_embedding_model():
    global _global_emb_model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(EMBEDDING_MODEL_ID, device=device)

    _global_emb_model = model
    return _global_emb_model

def get_embedding_model():
    global _global_emb_model
    if _global_emb_model is None:
        init_embedding_model()
    return _global_emb_model

def embed_texts(
    texts: list[str],
    batch_size: int,
    device: str,
    normalize: bool = True,
) -> np.ndarray:
    """
    Generate embeddings for a list of texts using SentenceTransformers.
    """
    if not texts:
        raise ValueError("The 'texts' list is empty. Cannot generate embeddings.")

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )

    return embeddings.astype(np.float32)

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

    if not faiss_path.exists():
        raise FileNotFoundError(f"FAISS index not found: {faiss_path}")

    index = faiss.read_index(str(faiss_path))
    lookup = _load_lookup(lookup_path)

    embeddings = embed_texts(
        [query],
        batch_size=1,
        device=device,
        normalize=True,
    ).astype(np.float32)

    scores, ids = index.search(embeddings, top_k)

    results: list[dict[str, Any]] = []
    for score, row_id in zip(scores[0].tolist(), ids[0].tolist()):
        if row_id == -1:
            continue
        row = lookup.get(int(row_id))
        if not row:
            continue
        results.append({"score": float(score), **row})

    return results


def query_vector_db_batch(
    queries: list[str],
    *,
    top_k: int = 5,
    index_dir: Path | None = None,
    device: str = "cpu",
) -> list[list[dict[str, Any]]]:
    """
    Batch version of query_vector_db - searches multiple queries efficiently.

    Embeds all queries in one batch call (more efficient than individual calls),
    then searches the FAISS index for each query separately to ensure identical
    results to calling query_vector_db() individually.

    Args:
        queries: List of natural language search queries
        top_k: Maximum number of chunks to return per query (default 5)
        index_dir: Optional path to FAISS artifacts directory
        device: Embedding device ("cpu" or "cuda")

    Returns:
        List of result lists, one per query (same order as input queries).
        Each inner list has the same format as query_vector_db() return value.

    Example:
        results = query_vector_db_batch(
            ["DNA damage aging", "cellular senescence"],
            top_k=5
        )
        # results[0] = results for "DNA damage aging"
        # results[1] = results for "cellular senescence"

    Note:
        Results are identical to calling query_vector_db() for each query:
        batch_results = query_vector_db_batch(["q1", "q2"], top_k=5)
        # batch_results[0] == query_vector_db("q1", top_k=5)
        # batch_results[1] == query_vector_db("q2", top_k=5)
    """
    if not queries:
        return []
    if any(not q.strip() for q in queries):
        raise ValueError("All queries must be non-empty.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")

    index_dir = index_dir or config.INDEX_DIR
    faiss_path = index_dir / "faiss.index"
    lookup_path = index_dir / "lookup.jsonl"

    if not faiss_path.exists():
        raise FileNotFoundError(f"FAISS index not found: {faiss_path}")

    index = faiss.read_index(str(faiss_path))
    lookup = _load_lookup(lookup_path)

    # Embed all queries in one batch (efficient)
    embeddings = embed_texts(
        queries,
        batch_size=len(queries),
        device=device,
        normalize=True,
    ).astype(np.float32)

    # Search index for each query separately (ensures same results as individual calls)
    all_results: list[list[dict[str, Any]]] = []
    for i, query_embedding in enumerate(embeddings):
        # Reshape to (1, dim) for FAISS search
        query_emb = query_embedding.reshape(1, -1)
        scores, ids = index.search(query_emb, top_k)

        query_results: list[dict[str, Any]] = []
        for score, row_id in zip(scores[0].tolist(), ids[0].tolist()):
            if row_id == -1:
                continue
            row = lookup.get(int(row_id))
            if not row:
                continue
            query_results.append({"score": float(score), **row})

        all_results.append(query_results)

    return all_results
