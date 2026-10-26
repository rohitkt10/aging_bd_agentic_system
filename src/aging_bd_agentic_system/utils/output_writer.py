from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def ensure_output_dir(base_dir: Path, hallmark: str) -> Path:
    """Ensure an output directory exists for the hallmark."""
    out_dir = base_dir / hallmark
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def serialize_sources(sources: Iterable[str]) -> str:
    """Serialize a list of sources into a semicolon-delimited string."""
    return ";".join([str(source) for source in sources if source])


def write_tsv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    """Write tab-separated values with header row."""
    path.write_text(
        "\t".join(header) + "\n" + "\n".join(["\t".join(row) for row in rows]),
        encoding="utf-8",
    )


def write_processes_tsv(out_dir: Path, processes: list[dict[str, Any]]) -> Path:
    """Write Phase 1 biological processes to processes.tsv."""
    path = out_dir / "processes.tsv"
    header = [
        "rank",
        "process_name",
        "evidence_score",
        "evidence_summary",
        "sources",
    ]
    rows: list[list[str]] = []
    for proc in processes:
        rows.append(
            [
                str(proc.get("rank", "")),
                str(proc.get("process_name", "")),
                str(proc.get("evidence_score", "")),
                str(proc.get("evidence_summary", "")),
                serialize_sources(proc.get("sources", [])),
            ]
        )
    write_tsv(path, header, rows)
    return path


def write_genes_tsv(out_dir: Path, genes: list[dict[str, Any]]) -> Path:
    """Write Phase 2 genes to genes.tsv."""
    path = out_dir / "genes.tsv"
    header = [
        "rank",
        "gene_symbol",
        "score",
        "biological_process",
        "evidence_summary",
        "sources",
    ]
    rows: list[list[str]] = []
    for idx, gene in enumerate(genes, start=1):
        rows.append(
            [
                str(idx),
                str(gene.get("gene_symbol", "")),
                str(gene.get("score", "")),
                str(gene.get("biological_process", "")),
                str(gene.get("evidence_summary", "")),
                serialize_sources(gene.get("sources", [])),
            ]
        )
    write_tsv(path, header, rows)
    return path


def write_hallmark_genes_tsv(out_dir: Path, df: Any) -> Path:
    """Write aggregated hallmark-level gene table to hallmark_genes.tsv."""
    path = out_dir / "hallmark_genes.tsv"
    df.to_csv(path, sep="\t", index=False)
    return path


def write_go_terms_tsv(out_dir: Path, go_terms: list[dict[str, Any]]) -> Path:
    """Write GO terms to go_terms.tsv."""
    path = out_dir / "go_terms.tsv"
    header = [
        "go_id",
        "go_label",
        "biological_process",
        "definition",
        "sources",
    ]
    rows: list[list[str]] = []
    for term in go_terms:
        bp_value = term.get("biological_process", [])
        if isinstance(bp_value, list):
            bp_text = ";".join([str(bp) for bp in bp_value if bp])
        else:
            bp_text = str(bp_value)
        rows.append(
            [
                str(term.get("go_id", "")),
                str(term.get("go_label", "")),
                bp_text,
                str(term.get("definition", "")),
                serialize_sources(term.get("sources", [])),
            ]
        )
    write_tsv(path, header, rows)
    return path
