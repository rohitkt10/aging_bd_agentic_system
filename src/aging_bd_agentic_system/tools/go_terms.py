from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from aging_bd_agentic_system.literature_pipeline import config


@lru_cache
def _load_go_graph(json_path: str) -> dict[str, Any]:
    """Load the GO basic JSON file and return the parsed content."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"GO JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _is_biological_process(node: dict[str, Any]) -> bool:
    meta = node.get("meta", {})
    for entry in meta.get("basicPropertyValues", []):
        value = entry.get("val", "")
        if value == "biological_process" or value.endswith("biological_process"):
            return True
    return False


def _extract_definition(node: dict[str, Any]) -> str | None:
    definition = node.get("meta", {}).get("definition", {})
    value = definition.get("val")
    if not value:
        return None
    return str(value).strip() or None


def _extract_go_id(node_id: str) -> str:
    go_id = node_id.split("/")[-1]
    return go_id.replace("_", ":")


def query_go_terms(query: str, max_results: int = 10) -> list[dict[str, str]]:
    """
    Search GO term definitions for biological process entries.

    Args:
        query: Text to search within GO definitions (e.g., "mitochondria inheritance")
        max_results: Maximum number of results to return (default 10)

    Returns:
        List of matching GO terms, each containing:
        - go_id: GO identifier (e.g., "GO:0000001")
        - go_label: GO term label
        - definition: Definition text

    Example:
        results = query_go_terms("cell cycle arrest", max_results=5)
    """
    if not query.strip():
        raise ValueError("Query must be non-empty.")
    if max_results <= 0:
        raise ValueError("max_results must be positive.")

    data = _load_go_graph(str(config.DATA_DIR / "go-basic.json"))
    graphs = data.get("graphs", [])
    if not graphs:
        return []

    needle = query.lower()
    results: list[dict[str, str]] = []
    for node in graphs[0].get("nodes", []):
        if not _is_biological_process(node):
            continue
        definition = _extract_definition(node)
        if not definition:
            continue
        if needle not in definition.lower():
            continue
        node_id = node.get("id")
        label = node.get("lbl")
        if not node_id or not label:
            continue
        results.append(
            {
                "go_id": _extract_go_id(str(node_id)),
                "go_label": str(label),
                "definition": definition,
            }
        )
        if len(results) >= max_results:
            break

    return results
