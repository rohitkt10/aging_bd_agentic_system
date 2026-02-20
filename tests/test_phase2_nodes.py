from __future__ import annotations

import json

from aging_bd_agentic_system.agents.phase1_bp_identifier import phase1_finalize
from aging_bd_agentic_system.agents.phase2_gene_researcher import (
    advance_bp,
    phase2_critic,
    select_bp,
)
from aging_bd_agentic_system.llm import get_llm, reset_llm
from aging_bd_agentic_system.llm.testing import FakeLLMProvider


def test_phase1_finalize_ranks_and_queue() -> None:
    state = {
        "biological_processes": [
            {
                "rank": 0,
                "process_name": "Process B",
                "evidence_score": 6,
                "evidence_summary": "summary",
                "sources": ["PMID:1"],
            },
            {
                "rank": 0,
                "process_name": "Process A",
                "evidence_score": 9,
                "evidence_summary": "summary",
                "sources": ["PMID:2"],
            },
        ]
    }

    updates = phase1_finalize(state)
    processes = updates["biological_processes"]
    assert processes[0]["process_name"] == "Process A"
    assert processes[0]["rank"] == 1
    assert updates["bp_queue"] == ["Process A", "Process B"]


def test_select_bp_and_advance() -> None:
    state = {"bp_queue": ["BP1", "BP2"], "current_bp_index": 0}
    select_updates = select_bp(state)
    assert select_updates["current_bp_name"] == "BP1"

    advance_updates = advance_bp({"current_bp_index": 0})
    assert advance_updates["current_bp_index"] == 1
    assert advance_updates["current_bp_name"] == ""


def test_phase2_critic_pass_and_fail() -> None:
    # Use FakeLLMProvider for this test
    import os
    os.environ["VERTEX_PROJECT_ID"] = "test-project"

    # Reset and set up fake LLM with predefined responses
    reset_llm()
    fake_provider = FakeLLMProvider(structured_responses=[
        # First call (pass case)
        {"grade": "pass", "comment": "Found 1 gene", "follow_up_queries": []},
        # Second call (fail case)
        {"grade": "fail", "comment": "Not enough genes", "follow_up_queries": ["more research"]},
    ])

    # Replace the global LLM's provider
    client = get_llm()
    client.provider = fake_provider

    try:
        state = {
            "current_bp_name": "DNA repair",
            "genes_found": [
                {
                    "gene_symbol": "TP53",
                    "score": 8,
                    "biological_process": "DNA repair",
                    "evidence_summary": "PMID:123",
                    "sources": ["PMID:123"],
                }
            ],
        }

        pass_eval = phase2_critic(state, min_genes_expected=1)["phase2_eval"]
        assert pass_eval["grade"] == "pass"

        fail_eval = phase2_critic(state, min_genes_expected=2)["phase2_eval"]
        assert fail_eval["grade"] == "fail"
    finally:
        # Clean up
        reset_llm()
