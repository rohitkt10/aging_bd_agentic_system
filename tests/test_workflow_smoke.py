from __future__ import annotations

import os

import pytest

from aging_bd_agentic_system.agents.phase1_bp_identifier import (
    load_lopez_otin_context,
    phase1_finalize,
    phase1_research,
)
from aging_bd_agentic_system.literature_pipeline import config


def test_phase1_smoke_run() -> None:
    if not os.getenv("NCBI_EMAIL"):
        pytest.skip("NCBI_EMAIL not set")
    if not (config.INDEX_DIR / "faiss.index").exists():
        pytest.skip("FAISS index not found")

    state = {
        "hallmark_name": "cellular senescence",
        "lopez_otin_context": "",
        "tool_call_history": [],
        "warnings": [],
    }
    state.update(load_lopez_otin_context(state))
    updates = phase1_research(state)
    state.update(updates)
    finalized = phase1_finalize(state)
    assert finalized["biological_processes"]
