from __future__ import annotations

import pytest

from aging_bd_agentic_system.tools import query_genage


def test_query_genage_matches_symbol() -> None:
    results = query_genage("TP53", max_results=10)
    assert results
    symbols = {row.get("symbol") for row in results}
    assert "TP53" in symbols


def test_query_genage_case_insensitive() -> None:
    results = query_genage("tp53", max_results=10)
    assert results


def test_query_genage_max_results_limit() -> None:
    results = query_genage("growth hormone", max_results=1)
    assert len(results) == 1


def test_query_genage_empty_query_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        query_genage(" ")
