"""
Observability: LangGraph callback tracing and logging.

Provides callbacks and utilities for monitoring workflow execution.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from aging_bd_agentic_system.literature_pipeline import config

# Configure logger
logger = logging.getLogger(__name__)


class TracingCallbackHandler(BaseCallbackHandler):
    """
    Custom callback handler for LangGraph execution tracing.

    Logs:
    - Node entry/exit with timing
    - State changes
    - LLM calls
    - Tool calls
    """

    def __init__(
        self, log_dir: Path | None = None, *, hallmark_name: str | None = None
    ):
        """
        Initialize tracing handler.

        Args:
            log_dir: Directory to store trace logs. If not provided, uses
                     data/logs/ or logs/{hallmark}/ if hallmark_name given.
            hallmark_name: Name of the hallmark being processed. If provided,
                          logs are stored in logs/{hallmark}/.
        """
        super().__init__()
        # If hallmark_name provided, use logs/{hallmark}/, else use provided log_dir or default
        if hallmark_name:
            # Sanitize hallmark name for use in directory path
            safe_name = (
                hallmark_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            )
            self.log_dir = Path("logs") / safe_name
        else:
            self.log_dir = log_dir or config.DATA_DIR / "logs"

        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"trace_{timestamp}.jsonl"

        # Execution context
        self.current_node: str | None = None
        self.node_start_time: float | None = None
        self.trace_data: list[dict[str, Any]] = []

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called when a chain (graph) starts execution."""
        logger.info(f"Chain started: {run_id}")
        self._log_event(
            "chain_start", {"run_id": str(run_id), "inputs": self._sanitize(inputs)}
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called when a chain (graph) ends execution."""
        logger.info(f"Chain ended: {run_id}")
        self._log_event(
            "chain_end", {"run_id": str(run_id), "outputs": self._sanitize(outputs)}
        )

        # Write trace file
        self._write_trace_file()

    def on_chain_error(
        self,
        error: Exception,
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called when a chain (graph) encounters an error."""
        logger.error(f"Chain error: {run_id} - {error}")
        self._log_event("chain_error", {"run_id": str(run_id), "error": str(error)})

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called before LLM invocation."""
        model_name = serialized.get("name", "unknown")
        logger.info(f"LLM start: {model_name} (run_id: {run_id})")
        self._log_event(
            "llm_start",
            {
                "run_id": str(run_id),
                "model": model_name,
                "prompt_preview": prompts[0][:200] if prompts else "",
                "current_node": self.current_node,
            },
        )

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called after LLM invocation completes."""
        logger.info(f"LLM end: {run_id}")

        # Extract response content
        content = ""
        if hasattr(response, "content"):
            content = response.content[:500]
        elif isinstance(response, str):
            content = response[:500]
        elif isinstance(response, dict):
            content = json.dumps(response, default=str)[:500]

        self._log_event(
            "llm_end",
            {
                "run_id": str(run_id),
                "response_preview": content,
                "current_node": self.current_node,
            },
        )

    def on_llm_error(
        self,
        error: Exception,
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called when LLM invocation fails."""
        logger.error(f"LLM error: {run_id} - {error}")
        self._log_event(
            "llm_error",
            {
                "run_id": str(run_id),
                "error": str(error),
                "current_node": self.current_node,
            },
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called before tool invocation."""
        tool_name = serialized.get("name", "unknown")
        logger.info(f"Tool start: {tool_name} (run_id: {run_id})")
        self._log_event(
            "tool_start",
            {
                "run_id": str(run_id),
                "tool": tool_name,
                "input": input_str[:200],
                "current_node": self.current_node,
            },
        )

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called after tool invocation completes."""
        logger.info(f"Tool end: {run_id}")
        self._log_event(
            "tool_end",
            {
                "run_id": str(run_id),
                "output": output[:200],
                "current_node": self.current_node,
            },
        )

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: str,
        **kwargs: Any,
    ) -> None:
        """Called when tool invocation fails."""
        logger.error(f"Tool error: {run_id} - {error}")
        self._log_event(
            "tool_error",
            {
                "run_id": str(run_id),
                "error": str(error),
                "current_node": self.current_node,
            },
        )

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log an event with timestamp."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **data,
        }
        self.trace_data.append(event)

        # Also log to file incrementally
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def _write_trace_file(self) -> None:
        """Write complete trace data to JSON file."""
        summary_file = self.log_file.with_suffix(".json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(self.trace_data, f, indent=2, default=str)
        logger.info(f"Trace written to {summary_file}")

    def _sanitize(self, data: Any) -> Any:
        """Sanitize data for logging (truncate large values)."""
        if isinstance(data, dict):
            return {k: self._sanitize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize(item) for item in data[:10]]  # Limit lists
        elif isinstance(data, str):
            return data[:500]  # Truncate strings
        else:
            return data


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (default: INFO).
    """
    log_dir = config.DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"app_{timestamp}.log"

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    logger.info(f"Logging initialized. Log file: {log_file}")


def create_tracing_callback(
    log_dir: Path | None = None, *, hallmark_name: str | None = None
) -> TracingCallbackHandler:
    """
    Create a tracing callback handler.

    Args:
        log_dir: Directory to store trace logs.
        hallmark_name: Name of the hallmark being processed. If provided,
                       logs are stored in logs/{hallmark}/.

    Returns:
        TracingCallbackHandler instance.
    """
    return TracingCallbackHandler(log_dir=log_dir, hallmark_name=hallmark_name)
