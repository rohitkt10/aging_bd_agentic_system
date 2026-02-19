from __future__ import annotations

import json

from aging_bd_agentic_system.agents.phase1_bp_identifier import phase1_finalize
from aging_bd_agentic_system.agents.phase2_gene_researcher import (
    advance_bp,
    phase2_critic,
    seed_gene_candidates,
    select_bp,
)


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


def test_seed_gene_candidates_genage_only() -> None:
    state = {"current_bp_name": "TP53"}
    updates = seed_gene_candidates(state, include_opengenes=False)
    candidates = json.loads(updates["research_scratchpad"])
    assert "TP53" in candidates


def test_phase2_critic_pass_and_fail() -> None:
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
