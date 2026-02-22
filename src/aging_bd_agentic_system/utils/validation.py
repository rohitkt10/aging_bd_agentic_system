from __future__ import annotations

from typing import Any


def _issue(message: str) -> str:
    return message


def validate_phase1(biological_processes: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate Phase 1 biological process outputs.

    Returns a dict with:
    - passed: True if all checks pass
    - issues: list of human-readable validation issues
    """
    issues: list[str] = []
    count = len(biological_processes)
    if count < 10 or count > 15:
        issues.append(_issue(f"expected 10-15 processes, got {count}"))

    for idx, proc in enumerate(biological_processes):
        missing = [
            key
            for key in [
                "rank",
                "process_name",
                "evidence_score",
                "evidence_summary",
                "sources",
            ]
            if key not in proc
        ]
        if missing:
            issues.append(_issue(f"process[{idx}] missing keys: {', '.join(missing)}"))
            continue
        score = proc.get("evidence_score")
        if not isinstance(score, int) or not 1 <= score <= 10:
            issues.append(_issue(f"process[{idx}] evidence_score not in 1-10"))
        if not proc.get("process_name"):
            issues.append(_issue(f"process[{idx}] empty process_name"))
        if not proc.get("evidence_summary"):
            issues.append(_issue(f"process[{idx}] empty evidence_summary"))
        sources = proc.get("sources")
        if not isinstance(sources, list) or not sources:
            issues.append(_issue(f"process[{idx}] missing sources"))

    return {"passed": not issues, "issues": issues}


def validate_phase2(
    genes: list[dict[str, Any]], go_terms: list[dict[str, Any]]
) -> dict[str, Any]:
    """Validate Phase 2 gene and GO term outputs."""
    issues: list[str] = []
    gene_count = len(genes)
    if gene_count < 300 or gene_count > 500:
        issues.append(_issue(f"expected 300-500 genes, got {gene_count}"))

    for idx, gene in enumerate(genes):
        missing = [
            key
            for key in [
                "gene_symbol",
                "score",
                "biological_process",
                "evidence_summary",
                "sources",
            ]
            if key not in gene
        ]
        if missing:
            issues.append(_issue(f"gene[{idx}] missing keys: {', '.join(missing)}"))
            continue
        score = gene.get("score")
        if not isinstance(score, int) or not 1 <= score <= 10:
            issues.append(_issue(f"gene[{idx}] score not in 1-10"))
        if not gene.get("evidence_summary"):
            issues.append(_issue(f"gene[{idx}] empty evidence_summary"))
        sources = gene.get("sources")
        if not isinstance(sources, list) or not sources:
            issues.append(_issue(f"gene[{idx}] missing sources"))

    # Note: GO term count validation removed - user handles filtering/sorting by score
    # Minimum warning is logged in main.py
    _ = len(go_terms)  # Keep for reference, unused in validation

    for idx, term in enumerate(go_terms):
        missing = [
            key
            for key in ["go_id", "go_label", "definition", "biological_process"]
            if key not in term
        ]
        if missing:
            issues.append(_issue(f"go_terms[{idx}] missing keys: {', '.join(missing)}"))
            continue
        go_id = term.get("go_id", "")
        if not str(go_id).startswith("GO:"):
            issues.append(_issue(f"go_terms[{idx}] go_id must start with GO:"))
        if not term.get("go_label"):
            issues.append(_issue(f"go_terms[{idx}] empty go_label"))
        if not term.get("definition"):
            issues.append(_issue(f"go_terms[{idx}] empty definition"))

    return {"passed": not issues, "issues": issues}


def validate_all(
    biological_processes: list[dict[str, Any]],
    genes: list[dict[str, Any]],
    go_terms: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate Phase 1 and Phase 2 outputs and flatten issues."""
    issues: list[str] = []
    issues.extend(validate_phase1(biological_processes)["issues"])
    issues.extend(validate_phase2(genes, go_terms)["issues"])
    return {"passed": not issues, "issues": issues}
