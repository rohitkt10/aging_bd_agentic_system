from __future__ import annotations

import json
import os

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
    # Note: GO term count validation was removed - minimum warning is logged in main.py


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
    """Test that summarize_if_needed creates context_summary when over budget."""
    # Disable LLM summarization to use fallback
    original = os.environ.get("USE_LLM_SUMMARIZATION")
    os.environ["USE_LLM_SUMMARIZATION"] = "false"

    try:
        state = {
            "tool_call_history": ["tool"] * 50,
            "reasoning_trace": ["reason"] * 50,
            "research_scratchpad": json.dumps({"initial_database_genes": [], "research_findings": []}),
        }
        updates = summarize_if_needed(state, max_tokens=10)
        assert updates["context_summary"]
        assert updates["tool_call_history"] == []
        assert updates["reasoning_trace"] == []
    finally:
        if original is None:
            os.environ.pop("USE_LLM_SUMMARIZATION", None)
        else:
            os.environ["USE_LLM_SUMMARIZATION"] = original


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


def test_estimate_tokens_uses_character_heuristic() -> None:
    """Test that token estimation uses character-based heuristic (~4 chars per token)."""
    # Simple cases
    assert estimate_tokens("") == 0
    assert estimate_tokens("word") == 1  # 4 chars = 1 token
    assert estimate_tokens("word " * 100) == 125  # 500 chars = 125 tokens

    # Technical content has more chars per word, should still work
    technical = "mitochondrial autophagy biogenesis senescence apoptosis "
    assert estimate_tokens(technical) > 0


def test_summarize_for_actionability_fallback_preserves_info() -> None:
    """Test that _fallback_actionability_summary preserves candidates and findings."""
    from aging_bd_agentic_system.utils.context_manager import _fallback_actionability_summary

    # Create realistic research data
    research_data = {
        "initial_database_genes": [
            {"symbol": "TP53", "name": "Tumor protein p53", "source": "genage"},
            {"symbol": "FOXO3", "name": "Forkhead box O3", "source": "opengenes"},
            {"symbol": "SIRT1", "name": "Sirtuin 1", "source": "genage"},
        ],
        "research_findings": [
            {"gene": "TP53", "source": "genage", "finding": "Longevity association: pro-longevity"},
            {"gene": "FOXO3", "source": "opengenes", "finding": "Intervention: lifespan extension"},
            {"gene": "SIRT1", "source": "pubmed", "finding": "Regulates autophagy"},
        ] * 5,  # 15 findings total
    }

    state = {"phase2_research_iteration": 3}
    summary = _fallback_actionability_summary(research_data, state)

    # Check that critical info is preserved
    assert "top_candidates" in summary
    assert "high_value_findings" in summary
    assert "iteration_state" in summary
    assert summary["iteration_state"]["current_iteration"] == 3
    # Check at least one candidate is present
    assert len(summary["top_candidates"]) > 0


def test_summarize_for_scoring_fallback_groups_evidence() -> None:
    """Test that _fallback_scoring_summary groups evidence by gene."""
    from aging_bd_agentic_system.utils.context_manager import _fallback_scoring_summary

    research_data = {
        "initial_database_genes": [
            {"symbol": "TP53", "name": "Tumor protein p53", "source": "genage"},
        ],
        "research_findings": [
            {"gene": "TP53", "source": "genage", "finding": "Longevity association"},
            {"gene": "TP53", "source": "pubmed", "finding": "Regulates aging"},
        ],
    }

    summary = _fallback_scoring_summary(research_data)

    # Check structure
    assert "candidate_evidence" in summary
    assert "total_genes_with_evidence" in summary
    assert summary["total_genes_with_evidence"] >= 1


def test_summarize_if_needed_preserves_iteration_state() -> None:
    """Test that summarization clears working memory and creates context_summary."""
    # Disable LLM summarization to use fallback
    original = os.environ.get("USE_LLM_SUMMARIZATION")
    os.environ["USE_LLM_SUMMARIZATION"] = "false"

    try:
        state = {
            "tool_call_history": ["call1", "call2", "call3"],
            "reasoning_trace": ["reason1", "reason2"],
            "research_scratchpad": json.dumps({"initial_database_genes": [], "research_findings": []}),
            "phase2_research_iteration": 5,
        }

        # Create a large state that will trigger summarization
        large_state = state.copy()
        large_state["tool_call_history"] = ["tool"] * 10000
        large_state["reasoning_trace"] = ["reason"] * 10000

        updates = summarize_if_needed(large_state, max_tokens=100)

        # Check that working memory is cleared
        assert updates["tool_call_history"] == []
        assert updates["reasoning_trace"] == []
        # Check that context_summary is created (structured JSON)
        assert "context_summary" in updates
        assert updates["context_summary"]  # Non-empty
    finally:
        if original is None:
            os.environ.pop("USE_LLM_SUMMARIZATION", None)
        else:
            os.environ["USE_LLM_SUMMARIZATION"] = original


def test_summarize_if_needed_returns_empty_when_under_budget() -> None:
    """Test that summarize_if_needed returns empty dict when under token budget."""
    state = {
        "tool_call_history": ["tool"],
        "reasoning_trace": ["reason"],
        "research_scratchpad": "small data",
    }

    updates = summarize_if_needed(state, max_tokens=50000)

    assert updates == {}


def test_context_manager_with_realistic_research_state() -> None:
    """Test context management with realistic Phase 2 research state."""
    # Disable LLM summarization to use fallback
    original = os.environ.get("USE_LLM_SUMMARIZATION")
    os.environ["USE_LLM_SUMMARIZATION"] = "false"

    try:
        # Create realistic research scratchpad with many findings
        findings = [
            {
                "source": "genage",
                "gene": f"GENE{i}",
                "query": f"aging mechanism {i}",
                "finding": f"Longevity association result {i}: " + "details " * 20,
            }
            for i in range(100)
        ]

        candidates = [
            {"symbol": f"GENE{i}", "name": f"Gene {i}", "source": "genage"}
            for i in range(50)
        ]

        research_data = {
            "initial_database_genes": candidates,
            "research_findings": findings,
        }

        state = {
            "tool_call_history": ["call"] * 1000,
            "reasoning_trace": ["reason"] * 1000,
            "research_scratchpad": json.dumps(research_data),
            "phase2_research_iteration": 7,
        }

        # This should trigger summarization
        updates = summarize_if_needed(state, max_tokens=10000)

        # Verify updates
        assert "context_summary" in updates
        assert updates["tool_call_history"] == []
        assert updates["reasoning_trace"] == []

        # Verify summary is structured JSON
        summary = updates["context_summary"]
        summary_data = json.loads(summary)
        assert "top_candidates" in summary_data or "iteration_state" in summary_data
    finally:
        if original is None:
            os.environ.pop("USE_LLM_SUMMARIZATION", None)
        else:
            os.environ["USE_LLM_SUMMARIZATION"] = original
