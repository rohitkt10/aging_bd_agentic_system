from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def log_event(record: dict[str, Any], *, log_dir: Path | None = None) -> None:
    """Append a structured event record to the hallmark JSONL log.

    The record is enriched with an ISO timestamp and stored under
    logs/{hallmark}/audit.jsonl. If hallmark is missing, defaults to "run".
    """
    record = dict(record)
    record["timestamp"] = datetime.now().isoformat(timespec="seconds")

    # Determine log directory
    if log_dir:
        resolved_dir = log_dir
    else:
        # Use logs/{hallmark}/ structure
        hallmark = record.get("hallmark", "run")
        # Sanitize hallmark name for use in directory path
        safe_name = hallmark.replace(" ", "_").replace("/", "_").replace("\\", "_")
        resolved_dir = Path("logs") / safe_name

    resolved_dir.mkdir(parents=True, exist_ok=True)

    # Use fixed filename "audit.jsonl"
    path = resolved_dir / "audit.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
