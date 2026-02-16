from __future__ import annotations

import pytest

from aging_bd_agentic_system.tools import query_go_terms


def test_query_go_terms_returns_results() -> None:
    results = query_go_terms("mitochondria", max_results=3)
    assert results
    first = results[0]
    assert set(first.keys()) == {"go_id", "go_label", "definition"}
    assert first["go_id"].startswith("GO:")


def test_query_go_terms_max_results_limit() -> None:
    results = query_go_terms("mitochondria", max_results=1)
    assert len(results) == 1


def test_query_go_terms_empty_query_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        query_go_terms(" ")


def test_query_go_terms_invalid_max_results_raises() -> None:
    with pytest.raises(ValueError, match="max_results"):
        query_go_terms("aging", max_results=0)
