from __future__ import annotations

import os
from pathlib import Path

# Resolve repo root:
# <repo>/src/aging_bd_agentic_system/literature_pipeline/config.py -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[3]

# Explicitly load .env from repo root
from dotenv import load_dotenv  # type: ignore
load_dotenv(REPO_ROOT / ".env")

# Data directories
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "corpus" / "raw"
CHUNKS_DIR = DATA_DIR / "corpus" / "chunks"

# Artifacts
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
#INDEX_DIR = ARTIFACTS_DIR / "index"
INDEX_DIR = DATA_DIR / "corpus" / "index"

# Chunking
CHUNK_SIZE_WORDS = int(os.getenv("CHUNK_SIZE_WORDS", "300"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "50"))
MIN_WORDS = int(os.getenv("MIN_WORDS", "1"))

# Embeddings
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-base-en-v1.5")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))