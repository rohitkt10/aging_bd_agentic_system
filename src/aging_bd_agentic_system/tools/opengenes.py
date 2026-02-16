from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field


class OpenGenesQuerySchema(BaseModel):
    """Schema for Open Genes search tool - enables LLM to understand parameters."""

    query: str = Field(
        description="Search keywords for Open Genes (e.g., 'GHR', 'insulin signaling')"
    )
    max_results: int = Field(
        default=10, description="Maximum number of results to return"
    )


def _extract_names(items: list[dict[str, Any]] | None) -> list[str]:
    if not items:
        return []
    names: list[str] = []
    for entry in items:
        name = entry.get("name")
        if name:
            names.append(str(name))
    return names


def query_opengenes(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """
    Search the Open Genes API for aging-related gene metadata.

    Args:
        query: Search text for gene symbols or keywords (e.g., "GHR", "insulin")
        max_results: Maximum number of results to return (default 10)

    Returns:
        List of gene records, each containing:
        - symbol: Gene symbol
        - name: Gene name
        - agingMechanisms: List of aging mechanism names
        - functionalClusters: List of functional cluster names
        - proteinClasses: List of protein class names
        - commentCause: List of evidence/cause names

    Example:
        results = query_opengenes("GHR", max_results=5)
    """
    if not query.strip():
        raise ValueError("Query must be non-empty.")
    if max_results <= 0:
        raise ValueError("max_results must be positive.")

    params = urlencode({"bySuggestions": query, "pageSize": max_results})
    url = f"https://open-genes.com/api/gene/search?{params}"
    request = Request(url, headers={"Accept": "application/json"})

    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Open Genes API error: HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Open Genes API request failed: {exc.reason}") from exc

    try:
        data = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Open Genes API returned invalid JSON.") from exc

    results: list[dict[str, Any]] = []
    for item in data.get("items", []):
        results.append(
            {
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "agingMechanisms": _extract_names(item.get("agingMechanisms")),
                "functionalClusters": _extract_names(item.get("functionalClusters")),
                "proteinClasses": _extract_names(item.get("proteinClasses")),
                "commentCause": _extract_names(item.get("commentCause")),
            }
        )
        if len(results) >= max_results:
            break

    return results
