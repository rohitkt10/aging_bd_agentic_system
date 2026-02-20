"""
Tests for LangGraph workflow building and execution.
"""

from __future__ import annotations

import os

from aging_bd_agentic_system.agents import phase1_research
from aging_bd_agentic_system.graph import build_workflow, run_workflow
from aging_bd_agentic_system.llm import get_llm, reset_llm
from aging_bd_agentic_system.llm.testing import FakeLLMProvider


def test_build_workflow() -> None:
    """Test that the workflow graph builds successfully."""
    graph = build_workflow()
    assert graph is not None

    # Check that graph has expected structure
    nodes = graph.nodes
    assert "phase1" in nodes
    assert "phase2" in nodes


def test_run_workflow_with_fake_llm() -> None:
    """Test workflow execution with fake LLM."""
    os.environ["VERTEX_PROJECT_ID"] = "test-project"

    # Reset and set up fake LLM
    reset_llm()
    fake_provider = FakeLLMProvider(structured_responses=[
        # phase1_research returns biological processes
        [
            {
                "process_name": "Test Process",
                "evidence_score": 8,
                "evidence_summary": "Test evidence",
                "sources": ["PMID:123"],
            }
        ],
        # phase1_critic returns pass
        {"grade": "pass", "comment": "Good", "missing_themes": [], "follow_up_queries": [], "split_instructions": [], "merge_instructions": []},
        # phase2_research returns genes
        [
            {
                "gene_symbol": "TP53",
                "score": 8,
                "evidence_summary": "Test",
                "sources": ["PMID:123"],
            }
        ],
        # phase2_critic returns pass
        {"grade": "pass", "comment": "Good", "follow_up_queries": []},
        # map_go_terms returns GO terms
        [
            {
                "go_id": "GO:0001234",
                "go_label": "test process",
                "relevance_score": 8,
                "evidence_summary": "Test",
            }
        ],
    ])

    client = get_llm()
    client.provider = fake_provider

    try:
        initial_state = {"hallmark_name": "Genomic Instability"}
        result = run_workflow(initial_state)

        # Verify workflow completed
        assert result is not None
        assert "biological_processes" in result or "genes_found" in result

    finally:
        reset_llm()
