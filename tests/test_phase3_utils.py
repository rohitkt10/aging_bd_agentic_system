from __future__ import annotations

from pathlib import Path

from aging_bd_agentic_system.utils.aggregation import (
    aggregate_outputs,
    dedupe_genes,
    merge_go_terms,
    sort_genes,
)
from aging_bd_agentic_system.utils.context_manager import (
    estimate_tokens,
    summarize_if_needed,
)
from aging_bd_agentic_system.utils.output_writer import (
    ensure_output_dir,
    write_genes_tsv,
    write_go_terms_tsv,
    write_processes_tsv,
)
from aging_bd_agentic_system.utils.validation import (
    validate_all,
    validate_phase1,
    validate_phase2,
)


def _sample_processes(count: int) -> list[dict[str, object]]:
    return [
        {
            "rank": idx + 1,
            "process_name": f"Process {idx}",
            "evidence_score": 7,
            "evidence_summary": "summary",
            "sources": ["PMID:1"],
        }
        for idx in range(count)
    ]


def _sample_genes(count: int) -> list[dict[str, object]]:
    return [
        {
            "gene_symbol": f"GENE{idx}",
            "score": 8,
            "biological_process": "BP",
            "evidence_summary": "summary",
            "sources": ["PMID:1"],
        }
        for idx in range(count)
    ]


def _sample_go_terms(count: int) -> list[dict[str, object]]:
    return [
        {
            "go_id": f"GO:{idx:07d}",
            "go_label": f"Term {idx}",
            "definition": "definition",
            "biological_process": "BP",
            "sources": [f"GO:{idx:07d}"],
        }
        for idx in range(count)
    ]


def test_validate_phase1_passes_and_fails() -> None:
    assert validate_phase1(_sample_processes(10))["passed"] is True
    fail = validate_phase1(_sample_processes(9))
    assert fail["passed"] is False
    assert "expected 10-15 processes" in fail["issues"][0]


def test_validate_phase2_passes_and_fails() -> None:
    genes = _sample_genes(300)
    go_terms = _sample_go_terms(50)
    assert validate_phase2(genes, go_terms)["passed"] is True

    fail = validate_phase2(_sample_genes(10), _sample_go_terms(10))
    assert fail["passed"] is False
    assert any("expected 300-500 genes" in issue for issue in fail["issues"])
    assert any("expected 50-80 GO terms" in issue for issue in fail["issues"])


def test_validate_all_flattens_issues() -> None:
    result = validate_all([], [], [])
    assert result["passed"] is False
    assert result["issues"]


def test_dedupe_genes_prefers_high_score_then_longer_summary() -> None:
    genes = [
        {
            "gene_symbol": "TP53",
            "score": 5,
            "evidence_summary": "short",
            "biological_process": "BP",
            "sources": ["PMID:1"],
        },
        {
            "gene_symbol": "TP53",
            "score": 7,
            "evidence_summary": "longer summary",
            "biological_process": "BP",
            "sources": ["PMID:2"],
        },
        {
            "gene_symbol": "BRCA1",
            "score": 7,
            "evidence_summary": "summary",
            "biological_process": "BP",
            "sources": ["PMID:3"],
        },
    ]
    deduped = dedupe_genes(genes)
    assert {gene["gene_symbol"] for gene in deduped} == {"TP53", "BRCA1"}
    tp53 = next(g for g in deduped if g["gene_symbol"] == "TP53")
    assert tp53["score"] == 7


def test_sort_genes_orders_by_score_then_symbol() -> None:
    genes = [
        {"gene_symbol": "B", "score": 7},
        {"gene_symbol": "A", "score": 7},
        {"gene_symbol": "C", "score": 9},
    ]
    sorted_genes = sort_genes(genes)
    assert [g["gene_symbol"] for g in sorted_genes] == ["C", "A", "B"]


def test_merge_go_terms_combines_processes() -> None:
    go_terms = [
        {
            "go_id": "GO:0000001",
            "go_label": "term",
            "definition": "short",
            "biological_process": "BP1",
        },
        {
            "go_id": "GO:0000001",
            "go_label": "term",
            "definition": "longer definition",
            "biological_process": "BP2",
        },
    ]
    merged = merge_go_terms(go_terms)
    assert merged[0]["definition"] == "longer definition"
    assert set(merged[0]["biological_process"]) == {"BP1", "BP2"}


def test_aggregate_outputs_runs_all_steps() -> None:
    genes = _sample_genes(3)
    genes.append({
        "gene_symbol": "GENE0",
        "score": 10,
        "biological_process": "BP",
        "evidence_summary": "summary",
        "sources": ["PMID:2"],
    })
    go_terms = [
        {
            "go_id": "GO:0000001",
            "go_label": "term",
            "definition": "definition",
            "biological_process": "BP",
        }
    ]
    deduped_genes, merged_go = aggregate_outputs(genes, go_terms)
    assert len(deduped_genes) == 3
    assert merged_go[0]["go_id"] == "GO:0000001"


def test_context_manager_summarizes_when_over_budget() -> None:
    state = {
        "tool_call_history": ["tool"] * 50,
        "reasoning_trace": ["reason"] * 50,
        "research_scratchpad": "word " * 200,
    }
    updates = summarize_if_needed(state, max_tokens=10)
    assert updates["context_summary"]
    assert updates["tool_call_history"] == []
    assert updates["reasoning_trace"] == []


def test_context_manager_no_summary_when_under_budget() -> None:
    state = {
        "tool_call_history": ["tool"],
        "reasoning_trace": ["reason"],
        "research_scratchpad": "notes",
    }
    assert summarize_if_needed(state, max_tokens=1000) == {}
    assert estimate_tokens("one two three") == 3


def test_output_writer_writes_all_tsvs(tmp_path: Path) -> None:
    out_dir = ensure_output_dir(tmp_path, "hallmark")
    processes = _sample_processes(2)
    genes = _sample_genes(2)
    go_terms = _sample_go_terms(2)

    process_path = write_processes_tsv(out_dir, processes)
    gene_path = write_genes_tsv(out_dir, genes)
    go_path = write_go_terms_tsv(out_dir, go_terms)

    assert process_path.read_text(encoding="utf-8").splitlines()[0].startswith("rank\t")
    assert gene_path.read_text(encoding="utf-8").splitlines()[0].startswith("rank\t")
    assert go_path.read_text(encoding="utf-8").splitlines()[0].startswith("go_id\t")
