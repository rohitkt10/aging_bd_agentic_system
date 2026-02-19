from __future__ import annotations

import json
from pathlib import Path

from aging_bd_agentic_system.utils.audit_logger import log_event


def test_log_event_writes_jsonl(tmp_path: Path) -> None:
    log_event({"hallmark": "test", "phase": "phase1"}, log_dir=tmp_path)
    log_path = tmp_path / "test.jsonl"
    contents = log_path.read_text(encoding="utf-8").splitlines()
    assert len(contents) == 1
    payload = json.loads(contents[0])
    assert payload["hallmark"] == "test"
    assert payload["phase"] == "phase1"
    assert "timestamp" in payload
