from __future__ import annotations

import os

import pytest

from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.tools import query_pubmed


def _get_ncbi_email() -> str:
    _ = config.REPO_ROOT
    email = os.getenv("NCBI_EMAIL")
    if not email:
        raise AssertionError("NCBI_EMAIL must be set in .env for PubMed tests.")
    return email


def test_query_pubmed_returns_results() -> None:
    email = _get_ncbi_email()
    results = query_pubmed("cellular senescence", retmax=2, email=email)
    assert results
    assert results[0]["pmid"]
    assert results[0]["title"]
    assert "authors" in results[0]
    assert isinstance(results[0]["authors"], list)
    assert "pub_date" in results[0]


def test_query_pubmed_date_range() -> None:
    email = _get_ncbi_email()
    results = query_pubmed(
        "cellular senescence",
        retmax=1,
        email=email,
        date_from="2018/01/01",
        date_to="2026/12/31",
    )
    assert results


def test_query_pubmed_empty_query_raises() -> None:
    email = _get_ncbi_email()
    with pytest.raises(ValueError, match="non-empty"):
        query_pubmed(" ", email=email)


def test_query_pubmed_invalid_retmax_raises() -> None:
    email = _get_ncbi_email()
    with pytest.raises(ValueError, match="retmax"):
        query_pubmed("aging", retmax=0, email=email)
