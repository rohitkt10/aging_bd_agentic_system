from __future__ import annotations

from typing import Any, Callable, Iterable

from aging_bd_agentic_system.utils.audit_logger import log_event

ToolResult = list[dict[str, Any]]
ToolCallable = Callable[..., ToolResult]

TOOL_EXCEPTIONS = (ValueError, RuntimeError, FileNotFoundError, OSError)


def build_tool_record(
    *,
    phase: str,
    node: str,
    tool: str,
    args: dict[str, Any],
    result_count: int,
    bp: str | None = None,
    error: str | None = None,
    hallmark: str | None = None,
) -> dict[str, Any]:
    """Create a structured tool call record for audit logging."""
    record: dict[str, Any] = {
        "phase": phase,
        "node": node,
        "tool": tool,
        "args": args,
        "result_count": result_count,
    }
    if bp:
        record["bp"] = bp
    if error:
        record["error"] = error
    if hallmark:
        record["hallmark"] = hallmark
    return record


def append_warning(message: str) -> dict[str, list[str]]:
    """Return a state update that appends a warning message."""
    return {"warnings": [message]}


def run_tool(
    *,
    tool_fn: ToolCallable,
    tool_name: str,
    args: dict[str, Any],
    phase: str,
    node: str,
    bp: str | None = None,
    hallmark: str | None = None,
) -> tuple[ToolResult, dict[str, Any]]:
    """Execute a tool and return results with audit updates.

    On failure, returns an empty list plus warning/audit updates.
    """
    try:
        results = tool_fn(**args)
        record = build_tool_record(
            phase=phase,
            node=node,
            tool=tool_name,
            args=args,
            result_count=len(results),
            bp=bp,
            hallmark=hallmark,
        )
        log_event(record)
        return results, {"tool_call_history": [record]}
    except TOOL_EXCEPTIONS as exc:
        record = build_tool_record(
            phase=phase,
            node=node,
            tool=tool_name,
            args=args,
            result_count=0,
            bp=bp,
            error=str(exc),
            hallmark=hallmark,
        )
        log_event(record)
        return [], {
            "tool_call_history": [record],
            **append_warning(f"{tool_name} failed: {exc}"),
        }


def unique_non_empty(values: Iterable[str]) -> list[str]:
    """Return sorted, de-duplicated non-empty strings."""
    deduped = {value.strip() for value in values if value and value.strip()}
    return sorted(deduped)
