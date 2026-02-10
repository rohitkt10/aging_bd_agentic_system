from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from Bio import Entrez

logger = logging.getLogger(__name__)


def _init_entrez(email: str, api_key: str | None = None) -> None:
    """
    Initialize NCBI Entrez global configuration.
    """
    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key


def search_pubmed(query: str, retmax: int) -> list[str]:
    """
    Search PubMed and return a list of PMIDs.
    """
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=retmax,
        sort="relevance",
    )
    res = Entrez.read(handle)
    handle.close()
    return list(res.get("IdList", []))


def get_pmcid_from_pmid(pmid: str) -> str | None:
    """
    Map a PMID to a PMCID via Entrez ELink.
    """
    try:
        handle = Entrez.elink(dbfrom="pubmed", id=pmid, linkname="pubmed_pmc")
        res = Entrez.read(handle)
        handle.close()
    except Exception as e:
        logger.warning(f"Failed elink for PMID {pmid}: {e}")
        return None

    if not res:
        return None
    linksets = res[0].get("LinkSetDb", [])
    if not linksets:
        return None
    links = linksets[0].get("Link", [])
    if not links:
        return None
    return links[0].get("Id")


def fetch_pmc_xml(pmcid: str, out_path: Path) -> bool:
    """
    Fetch PMC full-text XML and write to out_path.
    """
    try:
        handle = Entrez.efetch(db="pmc", id=pmcid, rettype="full", retmode="xml")
        xml_bytes = handle.read()
        handle.close()
        out_path.write_bytes(xml_bytes)
        return True
    except Exception as e:
        logger.error(f"Failed efetch for PMC{pmcid}: {e}")
        return False


def _write_jsonl(path: Path, record: dict[str, Any]) -> None:
    """
    Append a single JSON record to a JSONL file.
    """
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def fetch_pmc_corpus(
    query: str,
    out_dir: Path,
    *,
    email: str,
    target_n: int,
    oversample: int = 3,
    sleep_s: float = 0.35,
    api_key: str | None = None,
    resume: bool = True,
    manifest_path: Path | None = None,
) -> dict[str, int]:
    """
    Orchestrate PMC ingestion:
    PubMed search → PMID → PMCID → XML download, with manifest logging.
    """
    _init_entrez(email, api_key)

    out_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

    query_n = max(target_n * oversample, target_n)
    logger.info(f"Searching PubMed (retmax={query_n}) for: {query}")
    pmids = search_pubmed(query, query_n)
    logger.info(f"Found {len(pmids)} PMIDs")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    if manifest_path:
        _write_jsonl(
            manifest_path,
            {
                "type": "run",
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "query": query,
                "target_n": target_n,
                "query_retmax": query_n,
                "raw_dir": str(out_dir),
            },
        )

    counts = {"downloaded": 0, "skipped": 0, "failed": 0, "no_link": 0}

    for pmid in pmids:
        if counts["downloaded"] + counts["skipped"] >= target_n:
            break

        rec = {
            "type": "article",
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "pmid": pmid,
            "pmcid": None,
            "xml_path": None,
            "ok": False,
            "error": None,
        }

        try:
            pmcid_num = get_pmcid_from_pmid(pmid)
            if sleep_s > 0:
                time.sleep(sleep_s)

            if not pmcid_num:
                rec["error"] = "no_pmc_link"
                counts["no_link"] += 1
                if manifest_path:
                    _write_jsonl(manifest_path, rec)
                continue

            pmcid = f"PMC{pmcid_num}"
            rec["pmcid"] = pmcid
            xml_path = out_dir / f"{pmcid}.xml"

            if resume and xml_path.exists():
                rec["xml_path"] = str(xml_path.resolve())
                rec["ok"] = True
                counts["skipped"] += 1
                if manifest_path:
                    _write_jsonl(manifest_path, rec)
                continue

            success = fetch_pmc_xml(pmcid_num, xml_path)
            if sleep_s > 0:
                time.sleep(sleep_s)

            if success:
                rec["xml_path"] = str(xml_path.resolve())
                rec["ok"] = True
                counts["downloaded"] += 1
                logger.info(f"Downloaded: {pmcid}")
            else:
                rec["error"] = "fetch_failed"
                counts["failed"] += 1

            if manifest_path:
                _write_jsonl(manifest_path, rec)

        except Exception as e:
            rec["error"] = str(e)
            counts["failed"] += 1
            if manifest_path:
                _write_jsonl(manifest_path, rec)
            if sleep_s > 0:
                time.sleep(sleep_s)

    return counts
