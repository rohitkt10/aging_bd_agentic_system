from __future__ import annotations

from typing import Any


def dedupe_genes(genes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate genes by symbol, keeping highest score then longest summary."""
    best: dict[str, dict[str, Any]] = {}
    for gene in genes:
        symbol = gene.get("gene_symbol")
        if not symbol:
            continue
        current = best.get(symbol)
        if current is None:
            best[symbol] = gene
            continue
        current_score = int(current.get("score", 0))
        new_score = int(gene.get("score", 0))
        if new_score > current_score:
            best[symbol] = gene
            continue
        if new_score == current_score:
            current_summary = current.get("evidence_summary", "") or ""
            new_summary = gene.get("evidence_summary", "") or ""
            if len(new_summary) > len(current_summary):
                best[symbol] = gene

    return list(best.values())


def merge_go_terms(go_terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge GO terms by go_id, preserving all biological_process values."""
    merged: dict[str, dict[str, Any]] = {}
    for term in go_terms:
        go_id = term.get("go_id")
        if not go_id:
            continue
        current = merged.get(go_id)
        bp = term.get("biological_process")
        bp_list = [bp] if not isinstance(bp, list) else bp
        if current is None:
            merged[go_id] = {
                **term,
                "biological_process": [bp_item for bp_item in bp_list if bp_item],
            }
            continue
        current_bps = current.get("biological_process", [])
        if not isinstance(current_bps, list):
            current_bps = [current_bps]
        current["biological_process"] = list(
            {bp_item for bp_item in current_bps + bp_list if bp_item}
        )
        current_definition = current.get("definition", "") or ""
        new_definition = term.get("definition", "") or ""
        if len(new_definition) > len(current_definition):
            current["definition"] = new_definition
        if not current.get("go_label") and term.get("go_label"):
            current["go_label"] = term.get("go_label")
        merged[go_id] = current

    return list(merged.values())


def sort_genes(genes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort genes by score descending, then symbol ascending."""
    return sorted(
        genes,
        key=lambda gene: (-int(gene.get("score", 0)), gene.get("gene_symbol", "")),
    )


def aggregate_outputs(
    genes: list[dict[str, Any]], go_terms: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Aggregate and normalize gene/GO outputs."""
    deduped_genes = dedupe_genes(genes)
    sorted_genes = sort_genes(deduped_genes)
    merged_go_terms = merge_go_terms(go_terms)
    return sorted_genes, merged_go_terms
