from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_DIR = Path("logs/agent_traces")


def log_event(record: dict[str, Any], *, log_dir: Path | None = None) -> None:
    """Append a structured event record to the hallmark JSONL log.

    The record is enriched with an ISO timestamp and stored under
    logs/agent_traces/{hallmark}.jsonl. If hallmark is missing, defaults to "run".
    """
    resolved_dir = log_dir or LOG_DIR
    resolved_dir.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record["timestamp"] = datetime.now().isoformat(timespec="seconds")
    hallmark = record.get("hallmark", "run")
    path = resolved_dir / f"{hallmark}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
