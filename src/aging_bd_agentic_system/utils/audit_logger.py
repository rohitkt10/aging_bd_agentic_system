from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def log_event(
    record: dict[str, Any],
    *,
    output_dir: Path | str | None = None,
    log_dir: Path | None = None,
) -> None:
    """Append a structured event record to the hallmark JSONL log.

    The record is enriched with an ISO timestamp and stored under
    {output_dir}/{hallmark}/logs/audit.jsonl.

    Args:
        record: Event record dict (must include "hallmark" key)
        output_dir: Base output directory (e.g., "outputs"). If provided,
                    logs go to {output_dir}/{hallmark}/logs/
        log_dir: Explicit log directory (overrides output_dir if provided)
    """
    record = dict(record)
    record["timestamp"] = datetime.now().isoformat(timespec="seconds")

    hallmark = record.get("hallmark", "run")

    # Determine log directory (priority: log_dir > output_dir > default)
    if log_dir:
        resolved_dir = log_dir
    elif output_dir:
        resolved_dir = Path(output_dir) / hallmark / "logs"
    else:
        resolved_dir = Path("logs") / hallmark

    resolved_dir.mkdir(parents=True, exist_ok=True)

    # Use fixed filename "audit.jsonl"
    path = resolved_dir / "audit.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
