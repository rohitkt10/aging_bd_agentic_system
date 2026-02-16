from __future__ import annotations

import pytest

from aging_bd_agentic_system.tools import query_vector_db


def test_query_vector_db_returns_results() -> None:
    results = query_vector_db("cellular senescence", top_k=3, device="cpu")
    assert results
    first = results[0]
    assert "score" in first
    assert "text" in first


def test_query_vector_db_top_k_limit() -> None:
    results = query_vector_db("aging", top_k=1, device="cpu")
    assert len(results) <= 1


def test_query_vector_db_empty_query_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        query_vector_db("   ")


def test_query_vector_db_invalid_top_k_raises() -> None:
    with pytest.raises(ValueError, match="top_k"):
        query_vector_db("aging", top_k=0, device="cpu")
