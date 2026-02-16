from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from aging_bd_agentic_system.literature_pipeline import config


@lru_cache
def _load_genage(csv_path: str) -> tuple[dict[str, str], ...]:
    """Load GenAge CSV rows into memory."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"GenAge CSV not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return tuple({k: (v or "").strip() for k, v in row.items()} for row in reader)


class GenAgeQuerySchema(BaseModel):
    """Schema for GenAge search tool - enables LLM to understand parameters."""

    query: str = Field(
        description="Gene symbol or keyword (e.g., 'TP53', 'growth hormone')"
    )
    csv_path: str | None = Field(
        default=None,
        description=(
            "Optional path to GenAge CSV (default: data/databases/genage_human.csv)"
        ),
    )
    max_results: int | None = Field(
        default=50, description="Maximum number of matches to return"
    )


def query_genage(
    query: str,
    *,
    csv_path: Path | None = None,
    max_results: int | None = 50,
) -> list[dict[str, str]]:
    """
    Search GenAge entries by symbol, name, or annotation fields.

    Args:
        query: Gene symbol or keyword (e.g., "TP53", "growth hormone")
        csv_path: Optional path to GenAge CSV
        max_results: Maximum number of matches to return (default 50)

    Returns:
        List of GenAge records, each containing:
        - GenAge ID
        - symbol
        - name
        - entrez gene id
        - uniprot
        - why (annotation)

    Example:
        results = query_genage("telomerase", max_results=5)
    """
    if not query.strip():
        raise ValueError("Query must be non-empty.")
    if max_results is not None and max_results <= 0:
        raise ValueError("max_results must be positive or None.")

    csv_path = csv_path or (config.DATA_DIR / "databases" / "genage_human.csv")
    rows = _load_genage(str(csv_path))

    needle = query.lower()
    results: list[dict[str, str]] = []
    for row in rows:
        haystack = " ".join(
            [
                row.get("symbol", ""),
                row.get("name", ""),
                row.get("why", ""),
            ]
        )
        if needle in haystack.lower():
            results.append(dict(row))
            if max_results is not None and len(results) >= max_results:
                break

    return results
