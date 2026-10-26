from __future__ import annotations

import re
from math import ceil
from pathlib import Path
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


def aggregate_hallmark_genes(
    output_dir: str | Path,
    hallmark: str,
    k_threshold: float = 0.5,
) -> Any:
    """
    Aggregate per-BP scored_genes.tsv files into a hallmark-level gene table.

    Reads processes.tsv to determine BP count, loads bp{i}/scored_genes.tsv for
    each BP, and merges into a unified ranked table. Genes appearing in more than
    ceil(n_bps * k_threshold) BPs are flagged as hallmark_core.

    Args:
        output_dir: Root output directory containing hallmark subdirectories.
        hallmark: Hallmark name (must match directory name under output_dir).
        k_threshold: Fraction of BPs a gene must appear in to be hallmark_core.

    Returns:
        pandas DataFrame with columns: rank, gene_symbol, max_score, mean_score,
        bp_count, hallmark_core, biological_processes, sources, evidence_summary.
        Sorted by max_score desc, bp_count desc.
    """
    import pandas as pd

    output_dir = Path(output_dir)
    base = output_dir / hallmark
    processes = (
        pd.read_csv(base / "processes.tsv", sep="\t")
        .loc[:, ["rank", "process_name"]]
        .set_index("rank")
    )
    n_bps = len(processes)

    bp_tables = []
    for i in range(1, n_bps + 1):
        p = base / f"bp{i}" / "scored_genes.tsv"
        if not p.exists():
            print(f"  Warning: scored_genes.tsv missing for bp{i}, skipping")
            continue
        bp_tables.append(pd.read_csv(p, sep="\t"))

    if not bp_tables:
        raise FileNotFoundError(f"No scored_genes.tsv files found under {base}")

    df = pd.concat(bp_tables, ignore_index=True)

    def agg_sources(series: Any) -> str:
        seen, out = set(), []
        for s in series:
            for tok in re.split(r"[,|]", str(s)):
                tok = tok.strip()
                if tok and tok not in seen:
                    seen.add(tok)
                    out.append(tok)
        return "|".join(out)

    evidence_agg = (
        df.groupby("gene_symbol")[["biological_process", "evidence_summary"]]
        .apply(
            lambda g: " | ".join(
                f"[{r['biological_process']}]: {r['evidence_summary']}"
                for _, r in g.iterrows()
            )
        )
        .reset_index()
        .rename(columns={0: "evidence_summary"})
    )

    agg = (
        df.groupby("gene_symbol")
        .agg(
            max_score=("score", "max"),
            mean_score=("score", "mean"),
            bp_count=("biological_process", "count"),
            biological_processes=("biological_process", lambda x: ";".join(x)),
            sources=("sources", agg_sources),
        )
        .reset_index()
    )
    agg["mean_score"] = agg["mean_score"].round(2)
    agg = agg.merge(evidence_agg, on="gene_symbol")

    threshold = ceil(n_bps * k_threshold)
    agg["hallmark_core"] = agg["bp_count"] > threshold
    agg = agg.sort_values(
        ["max_score", "bp_count"], ascending=[False, False]
    ).reset_index(drop=True)
    agg.insert(0, "rank", agg.index + 1)

    return agg[
        [
            "rank",
            "gene_symbol",
            "max_score",
            "mean_score",
            "bp_count",
            "hallmark_core",
            "biological_processes",
            "sources",
            "evidence_summary",
        ]
    ]


def aggregate_outputs(
    genes: list[dict[str, Any]], go_terms: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Aggregate and normalize gene/GO outputs."""
    deduped_genes = dedupe_genes(genes)
    sorted_genes = sort_genes(deduped_genes)
    merged_go_terms = merge_go_terms(go_terms)
    return sorted_genes, merged_go_terms
