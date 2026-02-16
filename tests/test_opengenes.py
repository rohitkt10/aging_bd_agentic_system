from __future__ import annotations

import pytest

from aging_bd_agentic_system.tools import query_opengenes


def test_query_opengenes_returns_results() -> None:
    results = query_opengenes("GHR", max_results=3)
    assert results
    first = results[0]
    assert set(first.keys()) == {
        "symbol",
        "name",
        "agingMechanisms",
        "functionalClusters",
        "proteinClasses",
        "commentCause",
    }


def test_query_opengenes_max_results_limit() -> None:
    results = query_opengenes("GHR", max_results=1)
    assert len(results) <= 1


def test_query_opengenes_empty_query_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        query_opengenes(" ")


def test_query_opengenes_invalid_max_results_raises() -> None:
    with pytest.raises(ValueError, match="max_results"):
        query_opengenes("GHR", max_results=0)
