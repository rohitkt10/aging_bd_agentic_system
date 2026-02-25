from __future__ import annotations

import os
from typing import Any

from Bio import Entrez


def _init_entrez(email: str, api_key: str | None = None) -> None:
    """Initialize Entrez with required email and optional API key."""
    if not email:
        raise ValueError("NCBI email is required for PubMed access.")
    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key


def _format_abstract(abstract: dict[str, Any] | None) -> str | None:
    """Normalize abstract text from Entrez response."""
    if not abstract:
        return None
    texts = abstract.get("AbstractText", [])
    if isinstance(texts, str):
        return texts.strip() or None
    parts = [str(part).strip() for part in texts if str(part).strip()]
    return "\n".join(parts) if parts else None


def _extract_pub_date(pub_date: dict[str, Any]) -> str | None:
    """Extract a publication date string from Entrez response."""
    if not pub_date:
        return None
    year = pub_date.get("Year")
    if not year:
        return pub_date.get("MedlineDate")
    month = pub_date.get("Month")
    day = pub_date.get("Day")
    parts = [str(year)]
    if month:
        parts.append(str(month))
    if day:
        parts.append(str(day))
    return "-".join(parts)


def _extract_authors(author_list: list[dict[str, Any]] | None) -> list[str]:
    """Extract author names from Entrez response."""
    if not author_list:
        return []
    authors: list[str] = []
    for author in author_list:
        last = author.get("LastName")
        fore = author.get("ForeName") or author.get("Initials")
        if last and fore:
            authors.append(f"{fore} {last}")
        elif last:
            authors.append(str(last))
    return authors


def query_pubmed(
    query: str,
    *,
    email: str | None = None,
    api_key: str | None = None,
    retmax: int = 10,
    date_from: str = "2010/01/01",
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """
    Search PubMed for scientific papers.

    Args:
        query: Keywords to search (e.g., "DNA methylation aging")
        email: NCBI contact email (falls back to NCBI_EMAIL env var)
        api_key: Optional NCBI API key (falls back to NCBI_API_KEY env var)
        retmax: Maximum number of results to return (default 10)
        date_from: Start date filter in YYYY/MM/DD format (default: 2010/01/01)
        date_to: End date filter in YYYY/MM/DD format (default: None = present)

    Returns:
        List of papers, each containing:
        - pmid: PubMed ID
        - title: Paper title
        - abstract: Paper abstract text
        - authors: List of author names
        - journal: Journal name
        - pub_date: Publication date string

    Example:
        results = query_pubmed("epigenetic alterations aging", retmax=5)
    """
    if not query.strip():
        raise ValueError("Query must be non-empty.")
    if retmax <= 0:
        raise ValueError("retmax must be positive.")

    email = email or os.getenv("NCBI_EMAIL")
    api_key = api_key or os.getenv("NCBI_API_KEY")
    _init_entrez(email, api_key)

    search_kwargs: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "sort": "relevance",
    }
    if date_from or date_to:
        search_kwargs["datetype"] = "pdat"
        if date_from:
            search_kwargs["mindate"] = date_from
        if date_to:
            search_kwargs["maxdate"] = date_to

    handle = Entrez.esearch(**search_kwargs)
    res = Entrez.read(handle)
    handle.close()

    ids = res.get("IdList", [])
    if not ids:
        return []

    fetch_handle = Entrez.efetch(
        db="pubmed",
        id=",".join(ids),
        rettype="abstract",
        retmode="xml",
    )
    records = Entrez.read(fetch_handle)
    fetch_handle.close()

    results: list[dict[str, Any]] = []
    for article in records.get("PubmedArticle", []):
        citation = article.get("MedlineCitation", {})
        article_info = citation.get("Article", {})
        author_list = article_info.get("AuthorList", [])
        journal = article_info.get("Journal", {})
        pub_date = journal.get("JournalIssue", {}).get("PubDate", {})
        results.append(
            {
                "pmid": str(citation.get("PMID", "")).strip(),
                "title": str(article_info.get("ArticleTitle", "")).strip(),
                "abstract": _format_abstract(article_info.get("Abstract")),
                "authors": _extract_authors(author_list),
                "journal": journal.get("Title"),
                "pub_date": _extract_pub_date(pub_date),
            }
        )

    return results
