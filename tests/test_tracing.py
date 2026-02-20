"""
Tests for observability and tracing.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from aging_bd_agentic_system.observability import (
    TracingCallbackHandler,
    create_tracing_callback,
    setup_logging,
)


def test_create_tracing_callback() -> None:
    """Test creating a tracing callback handler."""
    handler = create_tracing_callback()
    assert handler is not None
    assert handler.log_dir is not None


def test_tracing_callback_logs_events() -> None:
    """Test that tracing callback logs events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TracingCallbackHandler(log_dir=Path(tmpdir))

        # Simulate chain start
        handler.on_chain_start(
            serialized={"name": "test_chain"},
            inputs={"test": "input"},
            run_id="test-run-1",
        )

        # Simulate LLM start
        handler.on_llm_start(
            serialized={"name": "test-model"},
            prompts=["test prompt"],
            run_id="test-run-2",
        )

        # Simulate chain end
        handler.on_chain_end(
            outputs={"test": "output"},
            run_id="test-run-1",
        )

        # Verify log file was created
        assert handler.log_file.exists()

        # Verify trace file was written
        trace_file = handler.log_file.with_suffix(".json")
        assert trace_file.exists()

        # Verify events were captured
        assert len(handler.trace_data) == 3


def test_tracing_callback_writes_jsonl_format() -> None:
    """Test that tracing callback writes JSONL format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TracingCallbackHandler(log_dir=Path(tmpdir))

        # Simulate some events
        handler.on_chain_start(
            serialized={"name": "test"},
            inputs={},
            run_id="test-1",
        )
        handler.on_chain_end(
            outputs={},
            run_id="test-1",
        )

        # Read JSONL file
        with handler.log_file.open("r") as f:
            lines = f.readlines()

        # Should have 2 lines (2 events)
        assert len(lines) == 2

        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "event_type" in data
            assert "timestamp" in data


def test_tracing_callback_captures_llm_events() -> None:
    """Test that LLM events are captured with correct details."""
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TracingCallbackHandler(log_dir=Path(tmpdir))

        # Simulate LLM start/end
        handler.on_llm_start(
            serialized={"name": "gemini-2.0-flash"},
            prompts=["What are biological processes?"],
            run_id="test-1",
        )

        # Mock response
        mock_response = Mock()
        mock_response.content = "Here are some biological processes..."

        handler.on_llm_end(
            response=mock_response,
            run_id="test-1",
        )

        # Check events were captured
        assert len(handler.trace_data) == 2

        # First event should be llm_start
        start_event = handler.trace_data[0]
        assert start_event["event_type"] == "llm_start"
        assert "model" in start_event
        assert start_event["model"] == "gemini-2.0-flash"

        # Second event should be llm_end
        end_event = handler.trace_data[1]
        assert end_event["event_type"] == "llm_end"
        assert "response_preview" in end_event


def test_tracing_callback_captures_tool_events() -> None:
    """Test that tool events are captured with correct details."""
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TracingCallbackHandler(log_dir=Path(tmpdir))

        # Simulate tool start/end
        handler.on_tool_start(
            serialized={"name": "query_genage"},
            input_str="DNA repair",
            run_id="test-1",
        )

        handler.on_tool_end(
            output='{"genes": ["TP53", "BRCA1"]}',
            run_id="test-1",
        )

        # Check events were captured
        assert len(handler.trace_data) == 2

        # First event should be tool_start
        start_event = handler.trace_data[0]
        assert start_event["event_type"] == "tool_start"
        assert start_event["tool"] == "query_genage"

        # Second event should be tool_end
        end_event = handler.trace_data[1]
        assert end_event["event_type"] == "tool_end"


def test_tracing_callback_handles_errors() -> None:
    """Test that error events are captured."""
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TracingCallbackHandler(log_dir=Path(tmpdir))

        # Simulate LLM error
        test_error = Exception("Test error")
        handler.on_llm_error(
            error=test_error,
            run_id="test-1",
        )

        # Check error event was captured
        assert len(handler.trace_data) == 1
        assert handler.trace_data[0]["event_type"] == "llm_error"
        assert "error" in handler.trace_data[0]


def test_setup_logging() -> None:
    """Test logging setup."""
    import logging

    from aging_bd_agentic_system.observability.tracing import config

    # Use a temp directory for logs
    with tempfile.TemporaryDirectory() as tmpdir:
        original_data_dir = config.DATA_DIR
        config.DATA_DIR = Path(tmpdir)

        try:
            setup_logging(level=logging.INFO)

            # Verify log directory was created
            log_dir = Path(tmpdir) / "logs"
            assert log_dir.exists()

            # Verify at least one log file was created
            log_files = list(log_dir.glob("*.log"))
            assert len(log_files) > 0
        finally:
            config.DATA_DIR = original_data_dir


def test_main_import_with_tracing() -> None:
    """Test that main.py can be imported and creates tracing callback."""
    # This verifies that the import works and create_tracing_callback is accessible
    from aging_bd_agentic_system.main import create_tracing_callback as main_callback

    handler = main_callback()
    assert handler is not None
    assert handler.log_dir is not None


def test_tracing_callback_with_hallmark_name() -> None:
    """Test that tracing callback uses hallmark-based directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Change to tmpdir to avoid polluting the repo
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            handler = TracingCallbackHandler(hallmark_name="test hallmark")

            # Verify log directory is logs/test_hallmark/
            expected_dir = Path("logs") / "test_hallmark"
            assert handler.log_dir == expected_dir
            assert handler.log_dir.exists()

            # Verify log file name
            assert handler.log_file.parent == expected_dir
            assert handler.log_file.name.startswith("trace_")
            assert handler.log_file.suffix == ".jsonl"

        finally:
            os.chdir(original_cwd)


def test_create_tracing_callback_with_hallmark() -> None:
    """Test create_tracing_callback factory with hallmark_name."""
    import os
    original_cwd = os.getcwd()

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)

            handler = create_tracing_callback(hallmark_name="epigenetic alterations")

            # Verify directory structure
            assert handler.log_dir == Path("logs") / "epigenetic_alterations"
            assert handler.log_dir.exists()

        finally:
            os.chdir(original_cwd)


def test_audit_logger_unified_directory() -> None:
    """Test that audit_logger uses logs/{hallmark}/audit.jsonl structure."""
    from aging_bd_agentic_system.utils.audit_logger import log_event

    import os
    original_cwd = os.getcwd()

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)

            # Log an event
            log_event({
                "hallmark": "test_hallmark",
                "event_type": "test_event",
                "test_data": "value",
            })

            # Verify log file location
            expected_path = Path("logs") / "test_hallmark" / "audit.jsonl"
            assert expected_path.exists()

            # Verify content
            with expected_path.open("r") as f:
                content = f.read()

            data = json.loads(content.strip())
            assert data["event_type"] == "test_event"
            assert data["hallmark"] == "test_hallmark"
            assert "timestamp" in data

        finally:
            os.chdir(original_cwd)


def test_hallmark_name_sanitization() -> None:
    """Test that hallmark names are sanitized for use in directory paths."""
    import os
    original_cwd = os.getcwd()

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)

            # Test various problematic characters
            test_cases = [
                ("test hallmark", "test_hallmark"),
                ("test/hallmark", "test_hallmark"),
                ("test\\hallmark", "test_hallmark"),
                ("test hallmark with spaces", "test_hallmark_with_spaces"),
            ]

            for input_name, expected_dir in test_cases:
                handler = TracingCallbackHandler(hallmark_name=input_name)
                assert handler.log_dir == Path("logs") / expected_dir

        finally:
            os.chdir(original_cwd)
