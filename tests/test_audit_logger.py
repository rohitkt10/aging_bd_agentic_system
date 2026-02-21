from __future__ import annotations

import json
import os
from pathlib import Path

from aging_bd_agentic_system.utils.audit_logger import log_event


def test_log_event_writes_jsonl(tmp_path: Path) -> None:
    """Test that log_event writes to logs/{hallmark}/audit.jsonl structure."""
    # Change to tmp_path to avoid polluting the repo
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        log_event({"hallmark": "test", "phase": "phase1"})

        # The actual implementation uses logs/{hallmark}/audit.jsonl
        log_path = Path("logs") / "test" / "audit.jsonl"
        contents = log_path.read_text(encoding="utf-8").splitlines()
        assert len(contents) == 1
        payload = json.loads(contents[0])
        assert payload["hallmark"] == "test"
        assert payload["phase"] == "phase1"
        assert "timestamp" in payload
    finally:
        os.chdir(original_cwd)
