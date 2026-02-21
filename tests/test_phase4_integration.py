"""
Phase 4 Integration & Validation Tests.

Comprehensive tests for workflow graph structure, state schema,
environment variable configuration, and end-to-end execution.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from aging_bd_agentic_system.graph.state import ResearchState
from aging_bd_agentic_system.graph.workflow import (
    bp_loop_route,
    build_phase1_graph,
    build_phase2_graph,
    build_workflow,
    phase1_route,
    phase2_research_route,
    phase2_route,
)
from aging_bd_agentic_system.utils.aggregation import (
    aggregate_outputs,
    dedupe_genes,
    merge_go_terms,
    sort_genes,
)
from aging_bd_agentic_system.utils.output_writer import (
    ensure_output_dir,
    serialize_sources,
    write_genes_tsv,
    write_go_terms_tsv,
    write_processes_tsv,
    write_tsv,
)
from aging_bd_agentic_system.utils.validation import (
    validate_all,
    validate_phase1,
    validate_phase2,
)


# =============================================================================
# Workflow Graph Structure Tests
# =============================================================================


class TestWorkflowGraphStructure:
    """Tests for workflow graph node and edge verification."""

    def test_build_phase1_graph_returns_compiled_graph(self) -> None:
        """Verify Phase 1 graph builds and returns a compiled StateGraph."""
        graph = build_phase1_graph()
        assert graph is not None
        assert hasattr(graph, "nodes")
        assert hasattr(graph, "invoke")

    def test_build_phase2_graph_returns_compiled_graph(self) -> None:
        """Verify Phase 2 graph builds and returns a compiled StateGraph."""
        graph = build_phase2_graph()
        assert graph is not None
        assert hasattr(graph, "nodes")
        assert hasattr(graph, "invoke")

    def test_build_workflow_returns_compiled_graph(self) -> None:
        """Verify top-level workflow builds and returns a compiled StateGraph."""
        graph = build_workflow()
        assert graph is not None
        assert hasattr(graph, "nodes")
        assert hasattr(graph, "invoke")

    def test_phase1_graph_has_required_nodes(self) -> None:
        """Verify Phase 1 graph contains all required nodes."""
        graph = build_phase1_graph()
        node_names = list(graph.nodes.keys())

        # Required Phase 1 nodes
        required_nodes = [
            "load_context",
            "phase1_plan",
            "phase1_research",
            "phase1_critic",
            "phase1_refine",
            "phase1_finalize",
        ]

        for node in required_nodes:
            assert node in node_names, f"Missing required node: {node}"

    def test_phase2_graph_has_required_nodes(self) -> None:
        """Verify Phase 2 graph contains all required nodes including ReAct loop."""
        graph = build_phase2_graph()
        node_names = list(graph.nodes.keys())

        # Required Phase 2 nodes
        required_nodes = [
            "select_bp",
            "phase2_research",
            "phase2_critic",
            "phase2_refine",
            "map_go_terms",
            "advance_bp",
        ]

        for node in required_nodes:
            assert node in node_names, f"Missing required node: {node}"

    def test_workflow_has_phase1_and_phase2_subgraphs(self) -> None:
        """Verify top-level workflow contains phase1 and phase2 subgraphs."""
        graph = build_workflow()
        node_names = list(graph.nodes.keys())

        assert "phase1" in node_names, "Missing phase1 subgraph"
        assert "phase2" in node_names, "Missing phase2 subgraph"


# =============================================================================
# Routing Function Tests
# =============================================================================


class TestRoutingFunctions:
    """Tests for workflow routing functions."""

    def test_phase1_route_returns_refine_on_fail_within_limit(self) -> None:
        """Verify Phase 1 routes to refine when grade is fail and under max iterations."""
        state = {
            "phase1_eval": {"grade": "fail"},
            "phase1_iteration": 2,
        }
        result = phase1_route(state)
        assert result == "phase1_refine"

    def test_phase1_route_returns_finalize_on_pass(self) -> None:
        """Verify Phase 1 routes to finalize when grade is pass."""
        state = {
            "phase1_eval": {"grade": "pass"},
            "phase1_iteration": 0,
        }
        result = phase1_route(state)
        assert result == "phase1_finalize"

    def test_phase1_route_returns_finalize_when_max_iterations_reached(self) -> None:
        """Verify Phase 1 routes to finalize when max iterations reached."""
        # Default max is 3
        state = {
            "phase1_eval": {"grade": "fail"},
            "phase1_iteration": 3,
        }
        result = phase1_route(state)
        assert result == "phase1_finalize"

    def test_phase1_route_respects_env_var_max_iterations(self) -> None:
        """Verify Phase 1 respects PHASE1_MAX_ITERATIONS environment variable."""
        original = os.environ.get("PHASE1_MAX_ITERATIONS")

        try:
            os.environ["PHASE1_MAX_ITERATIONS"] = "5"

            # Should route to refine when iteration < 5
            state = {
                "phase1_eval": {"grade": "fail"},
                "phase1_iteration": 4,
            }
            result = phase1_route(state)
            assert result == "phase1_refine"

            # Should route to finalize when iteration >= 5
            state["phase1_iteration"] = 5
            result = phase1_route(state)
            assert result == "phase1_finalize"

        finally:
            if original is None:
                os.environ.pop("PHASE1_MAX_ITERATIONS", None)
            else:
                os.environ["PHASE1_MAX_ITERATIONS"] = original

    def test_phase2_route_returns_refine_on_fail_within_limit(self) -> None:
        """Verify Phase 2 routes to refine when grade is fail and under max iterations."""
        state = {
            "phase2_eval": {"grade": "fail"},
            "phase2_critic_iteration": 1,
        }
        result = phase2_route(state)
        assert result == "phase2_refine"

    def test_phase2_route_returns_map_go_terms_on_pass(self) -> None:
        """Verify Phase 2 routes to map_go_terms when grade is pass."""
        state = {
            "phase2_eval": {"grade": "pass"},
            "phase2_critic_iteration": 0,
        }
        result = phase2_route(state)
        assert result == "map_go_terms"

    def test_phase2_route_returns_map_go_terms_when_max_iterations_reached(self) -> None:
        """Verify Phase 2 routes to map_go_terms when max iterations reached."""
        # Default max is 3
        state = {
            "phase2_eval": {"grade": "fail"},
            "phase2_critic_iteration": 3,
        }
        result = phase2_route(state)
        assert result == "map_go_terms"

    def test_phase2_route_respects_env_var_max_iterations(self) -> None:
        """Verify Phase 2 respects PHASE2_REFINE_MAX_ITERATIONS environment variable."""
        original = os.environ.get("PHASE2_REFINE_MAX_ITERATIONS")

        try:
            os.environ["PHASE2_REFINE_MAX_ITERATIONS"] = "5"

            state = {
                "phase2_eval": {"grade": "fail"},
                "phase2_critic_iteration": 4,
            }
            result = phase2_route(state)
            assert result == "phase2_refine"

            state["phase2_critic_iteration"] = 5
            result = phase2_route(state)
            assert result == "map_go_terms"

        finally:
            if original is None:
                os.environ.pop("PHASE2_REFINE_MAX_ITERATIONS", None)
            else:
                os.environ["PHASE2_REFINE_MAX_ITERATIONS"] = original

    def test_phase2_research_route_continues_loop_within_limit(self) -> None:
        """Verify Phase 2 research continues loop when under max iterations."""
        state = {"phase2_research_iteration": 5}
        result = phase2_research_route(state)
        assert result == "phase2_research"

    def test_phase2_research_route_goes_to_critic_at_max(self) -> None:
        """Verify Phase 2 research routes to critic when max iterations reached."""
        # Default max is 7
        state = {"phase2_research_iteration": 7}
        result = phase2_research_route(state)
        assert result == "phase2_critic"

    def test_phase2_research_route_respects_env_var(self) -> None:
        """Verify Phase 2 research respects PHASE2_RESEARCH_MAX_ITERATIONS environment variable."""
        original = os.environ.get("PHASE2_RESEARCH_MAX_ITERATIONS")

        try:
            os.environ["PHASE2_RESEARCH_MAX_ITERATIONS"] = "5"

            state = {"phase2_research_iteration": 4}
            result = phase2_research_route(state)
            assert result == "phase2_research"

            state["phase2_research_iteration"] = 5
            result = phase2_research_route(state)
            assert result == "phase2_critic"

        finally:
            if original is None:
                os.environ.pop("PHASE2_RESEARCH_MAX_ITERATIONS", None)
            else:
                os.environ["PHASE2_RESEARCH_MAX_ITERATIONS"] = original

    def test_bp_loop_route_returns_select_bp_when_queue_not_exhausted(self) -> None:
        """Verify BP loop routes to select_bp when more BPs in queue."""
        state = {
            "current_bp_index": 0,
            "bp_queue": ["BP1", "BP2", "BP3"],
        }
        result = bp_loop_route(state)
        assert result == "select_bp"

    def test_bp_loop_route_returns_end_when_queue_exhausted(self) -> None:
        """Verify BP loop routes to END when queue is exhausted."""
        from langgraph.graph import END

        state = {
            "current_bp_index": 3,
            "bp_queue": ["BP1", "BP2", "BP3"],
        }
        result = bp_loop_route(state)
        assert result == END

    def test_bp_loop_route_handles_empty_queue(self) -> None:
        """Verify BP loop routes to END when queue is empty."""
        from langgraph.graph import END

        state = {
            "current_bp_index": 0,
            "bp_queue": [],
        }
        result = bp_loop_route(state)
        assert result == END


# =============================================================================
# State Schema Tests
# =============================================================================


class TestStateSchema:
    """Tests for ResearchState schema verification."""

    def test_state_has_all_required_fields(self) -> None:
        """Verify ResearchState has all required fields."""
        # Get annotations from TypedDict
        annotations = ResearchState.__annotations__

        required_fields = [
            "hallmark_name",
            "tool_call_history",
            "reasoning_trace",
            "warnings",
            "lopez_otin_context",
            "context_summary",
            "token_count",
            "research_scratchpad",
            "phase1_plan",
            "phase1_iteration",
            "phase1_eval",
            "biological_processes",
            "bp_queue",
            "current_bp_index",
            "current_bp_name",
            "phase2_critic_iteration",
            "phase2_research_iteration",
            "phase2_eval",
            "genes_found",
            "go_terms_found",
        ]

        for field in required_fields:
            assert field in annotations, f"Missing required field: {field}"

    def test_state_list_fields_use_operator_add(self) -> None:
        """Verify list fields that need aggregation use operator.add reducer."""
        from typing import get_origin

        annotations = ResearchState.__annotations__

        # Fields that should use operator.add reducer
        reducer_fields = [
            "tool_call_history",
            "reasoning_trace",
            "warnings",
            "genes_found",
            "go_terms_found",
        ]

        for field in reducer_fields:
            annotation = annotations[field]
            # Annotated types with operator.add should be Annotated
            origin = get_origin(annotation)
            assert origin is not None or "Annotated" in str(annotation), \
                f"Field {field} should be Annotated with operator.add"


# =============================================================================
# Validation Edge Case Tests
# =============================================================================


class TestValidationEdgeCases:
    """Tests for validation utility edge cases."""

    def test_validate_phase1_with_empty_processes(self) -> None:
        """Verify validation fails for empty process list."""
        result = validate_phase1([])
        assert result["passed"] is False
        assert any("expected 10-15" in issue for issue in result["issues"])

    def test_validate_phase1_with_too_many_processes(self) -> None:
        """Verify validation fails for too many processes."""
        processes = _sample_processes(20)
        result = validate_phase1(processes)
        assert result["passed"] is False
        assert any("expected 10-15" in issue for issue in result["issues"])

    def test_validate_phase1_with_missing_required_keys(self) -> None:
        """Verify validation fails when required keys are missing."""
        processes = [{"rank": 1}]  # Missing most required keys
        result = validate_phase1(processes)
        assert result["passed"] is False
        assert any("missing keys" in issue for issue in result["issues"])

    def test_validate_phase1_with_invalid_evidence_score(self) -> None:
        """Verify validation fails for evidence scores outside 1-10 range."""
        processes = _sample_processes(10)
        processes[0]["evidence_score"] = 15  # Invalid score
        result = validate_phase1(processes)
        assert result["passed"] is False
        assert any("evidence_score not in 1-10" in issue for issue in result["issues"])

    def test_validate_phase1_with_empty_sources(self) -> None:
        """Verify validation fails for empty sources list."""
        processes = _sample_processes(10)
        processes[0]["sources"] = []  # Empty sources
        result = validate_phase1(processes)
        assert result["passed"] is False
        assert any("missing sources" in issue for issue in result["issues"])

    def test_validate_phase2_with_too_few_genes(self) -> None:
        """Verify validation fails for too few genes."""
        genes = _sample_genes(50)
        go_terms = _sample_go_terms(50)
        result = validate_phase2(genes, go_terms)
        assert result["passed"] is False
        assert any("expected 300-500 genes" in issue for issue in result["issues"])

    def test_validate_phase2_with_missing_gene_keys(self) -> None:
        """Verify validation fails when gene required keys are missing."""
        genes = [{"gene_symbol": "TP53"}]  # Missing required keys
        go_terms = _sample_go_terms(50)
        result = validate_phase2(genes, go_terms)
        assert result["passed"] is False
        assert any("missing keys" in issue for issue in result["issues"])

    def test_validate_phase2_with_invalid_go_id_format(self) -> None:
        """Verify validation fails for GO IDs not starting with 'GO:'."""
        genes = _sample_genes(300)
        go_terms = _sample_go_terms(50)
        go_terms[0]["go_id"] = "INVALID_ID"  # Invalid format
        result = validate_phase2(genes, go_terms)
        assert result["passed"] is False
        assert any("go_id must start with GO:" in issue for issue in result["issues"])

    def test_validate_all_combines_phase1_and_phase2_issues(self) -> None:
        """Verify validate_all combines issues from both phases."""
        result = validate_all([], [], [])
        assert result["passed"] is False
        # Should have issues from both phases
        assert len(result["issues"]) >= 2


# =============================================================================
# Aggregation Edge Case Tests
# =============================================================================


class TestAggregationEdgeCases:
    """Tests for aggregation utility edge cases."""

    def test_dedupe_genes_with_empty_list(self) -> None:
        """Verify dedupe_genes handles empty list."""
        result = dedupe_genes([])
        assert result == []

    def test_dedupe_genes_with_no_gene_symbol(self) -> None:
        """Verify dedupe_genes skips entries without gene_symbol."""
        genes = [
            {"score": 5, "evidence_summary": "test"},
            {"gene_symbol": "TP53", "score": 7},
        ]
        result = dedupe_genes(genes)
        assert len(result) == 1
        assert result[0]["gene_symbol"] == "TP53"

    def test_dedupe_genes_keeps_higher_score(self) -> None:
        """Verify dedupe_genes keeps entry with higher score."""
        genes = [
            {"gene_symbol": "TP53", "score": 5, "evidence_summary": "short"},
            {"gene_symbol": "TP53", "score": 8, "evidence_summary": "other"},
        ]
        result = dedupe_genes(genes)
        assert len(result) == 1
        assert result[0]["score"] == 8

    def test_dedupe_genes_keeps_longer_summary_on_tie(self) -> None:
        """Verify dedupe_genes keeps longer summary when scores are equal."""
        genes = [
            {"gene_symbol": "TP53", "score": 7, "evidence_summary": "short"},
            {"gene_symbol": "TP53", "score": 7, "evidence_summary": "this is a much longer summary"},
        ]
        result = dedupe_genes(genes)
        assert len(result) == 1
        assert "longer" in result[0]["evidence_summary"]

    def test_sort_genes_with_empty_list(self) -> None:
        """Verify sort_genes handles empty list."""
        result = sort_genes([])
        assert result == []

    def test_sort_genes_orders_by_score_descending(self) -> None:
        """Verify sort_genes orders by score descending."""
        genes = [
            {"gene_symbol": "A", "score": 5},
            {"gene_symbol": "B", "score": 9},
            {"gene_symbol": "C", "score": 7},
        ]
        result = sort_genes(genes)
        assert [g["gene_symbol"] for g in result] == ["B", "C", "A"]

    def test_sort_genes_orders_by_symbol_on_score_tie(self) -> None:
        """Verify sort_genes orders by symbol ascending when scores are equal."""
        genes = [
            {"gene_symbol": "ZEB1", "score": 7},
            {"gene_symbol": "APE1", "score": 7},
            {"gene_symbol": "BRCA1", "score": 7},
        ]
        result = sort_genes(genes)
        assert [g["gene_symbol"] for g in result] == ["APE1", "BRCA1", "ZEB1"]

    def test_merge_go_terms_with_empty_list(self) -> None:
        """Verify merge_go_terms handles empty list."""
        result = merge_go_terms([])
        assert result == []

    def test_merge_go_terms_preserves_multiple_biological_processes(self) -> None:
        """Verify merge_go_terms preserves all biological_process values."""
        go_terms = [
            {"go_id": "GO:0000001", "go_label": "term", "biological_process": "BP1"},
            {"go_id": "GO:0000001", "go_label": "term", "biological_process": "BP2"},
            {"go_id": "GO:0000001", "go_label": "term", "biological_process": "BP3"},
        ]
        result = merge_go_terms(go_terms)
        assert len(result) == 1
        assert set(result[0]["biological_process"]) == {"BP1", "BP2", "BP3"}

    def test_merge_go_terms_keeps_longest_definition(self) -> None:
        """Verify merge_go_terms keeps longest definition."""
        go_terms = [
            {"go_id": "GO:0000001", "go_label": "term", "definition": "short"},
            {"go_id": "GO:0000001", "go_label": "term", "definition": "this is a longer definition"},
        ]
        result = merge_go_terms(go_terms)
        assert result[0]["definition"] == "this is a longer definition"

    def test_merge_go_terms_skips_entries_without_go_id(self) -> None:
        """Verify merge_go_terms skips entries without go_id."""
        go_terms = [
            {"go_id": "GO:0000001", "go_label": "valid"},
            {"go_label": "invalid"},  # No go_id
        ]
        result = merge_go_terms(go_terms)
        assert len(result) == 1
        assert result[0]["go_id"] == "GO:0000001"

    def test_aggregate_outputs_with_empty_inputs(self) -> None:
        """Verify aggregate_outputs handles empty inputs."""
        genes, go_terms = aggregate_outputs([], [])
        assert genes == []
        assert go_terms == []


# =============================================================================
# Output Writer Edge Case Tests
# =============================================================================


class TestOutputWriterEdgeCases:
    """Tests for output writer utility edge cases."""

    def test_serialize_sources_with_empty_list(self) -> None:
        """Verify serialize_sources handles empty list."""
        result = serialize_sources([])
        assert result == ""

    def test_serialize_sources_filters_empty_values(self) -> None:
        """Verify serialize_sources filters out empty values."""
        result = serialize_sources(["PMID:1", "", "PMID:2", None])
        assert result == "PMID:1;PMID:2"

    def test_write_tsv_creates_file_with_header(self, tmp_path: Path) -> None:
        """Verify write_tsv creates file with proper header."""
        file_path = tmp_path / "test.tsv"
        header = ["col1", "col2", "col3"]
        rows = [["a", "b", "c"], ["d", "e", "f"]]

        write_tsv(file_path, header, rows)

        assert file_path.exists()
        content = file_path.read_text()
        lines = content.splitlines()
        assert lines[0] == "col1\tcol2\tcol3"
        assert lines[1] == "a\tb\tc"
        assert lines[2] == "d\te\tf"

    def test_write_tsv_handles_empty_rows(self, tmp_path: Path) -> None:
        """Verify write_tsv handles empty rows list."""
        file_path = tmp_path / "test.tsv"
        header = ["col1", "col2"]

        write_tsv(file_path, header, [])

        content = file_path.read_text()
        assert content.strip() == "col1\tcol2"

    def test_write_processes_tsv_handles_missing_keys(self, tmp_path: Path) -> None:
        """Verify write_processes_tsv handles missing keys gracefully."""
        out_dir = ensure_output_dir(tmp_path, "test")
        processes = [
            {"rank": 1, "process_name": "Test"},  # Missing other keys
        ]

        path = write_processes_tsv(out_dir, processes)

        assert path.exists()
        content = path.read_text()
        # Should have header and one row
        assert "rank\tprocess_name" in content

    def test_write_genes_tsv_assigns_sequential_ranks(self, tmp_path: Path) -> None:
        """Verify write_genes_tsv assigns sequential ranks."""
        out_dir = ensure_output_dir(tmp_path, "test")
        genes = [
            {"gene_symbol": "A", "score": 5, "biological_process": "BP"},
            {"gene_symbol": "B", "score": 6, "biological_process": "BP"},
        ]

        path = write_genes_tsv(out_dir, genes)

        content = path.read_text()
        lines = content.splitlines()
        # Header + 2 data rows
        assert len(lines) == 3
        # Check ranks are sequential
        assert lines[1].startswith("1\t")
        assert lines[2].startswith("2\t")

    def test_write_go_terms_tsv_handles_list_biological_process(self, tmp_path: Path) -> None:
        """Verify write_go_terms_tsv handles list biological_process values."""
        out_dir = ensure_output_dir(tmp_path, "test")
        go_terms = [
            {
                "go_id": "GO:0000001",
                "go_label": "term",
                "biological_process": ["BP1", "BP2", "BP3"],
                "definition": "def",
                "sources": ["GO:0000001"],
            }
        ]

        path = write_go_terms_tsv(out_dir, go_terms)

        content = path.read_text()
        # Biological processes should be semicolon-joined
        assert "BP1;BP2;BP3" in content

    def test_ensure_output_dir_creates_directory(self, tmp_path: Path) -> None:
        """Verify ensure_output_dir creates directory if it doesn't exist."""
        new_dir = tmp_path / "new_hallmark"
        result = ensure_output_dir(tmp_path, "new_hallmark")

        assert result == new_dir
        assert new_dir.exists()

    def test_ensure_output_dir_handles_existing_directory(self, tmp_path: Path) -> None:
        """Verify ensure_output_dir handles existing directory."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        result = ensure_output_dir(tmp_path, "existing")

        assert result == existing_dir
        assert existing_dir.exists()


# =============================================================================
# Environment Variable Configuration Tests
# =============================================================================


class TestEnvironmentVariableConfiguration:
    """Tests for environment variable configuration."""

    def test_all_iteration_env_vars_have_defaults(self) -> None:
        """Verify all iteration limit env vars have sensible defaults."""
        # Clear any existing values
        env_vars = [
            "PHASE1_MAX_ITERATIONS",
            "PHASE2_RESEARCH_MAX_ITERATIONS",
            "PHASE2_REFINE_MAX_ITERATIONS",
        ]

        original_values = {}
        for var in env_vars:
            original_values[var] = os.environ.get(var)
            os.environ.pop(var, None)

        try:
            # These should work with defaults
            assert phase1_route({"phase1_eval": {"grade": "fail"}, "phase1_iteration": 2}) == "phase1_refine"
            assert phase1_route({"phase1_eval": {"grade": "fail"}, "phase1_iteration": 3}) == "phase1_finalize"

            assert phase2_research_route({"phase2_research_iteration": 6}) == "phase2_research"
            assert phase2_research_route({"phase2_research_iteration": 7}) == "phase2_critic"

            assert phase2_route({"phase2_eval": {"grade": "fail"}, "phase2_critic_iteration": 2}) == "phase2_refine"
            assert phase2_route({"phase2_eval": {"grade": "fail"}, "phase2_critic_iteration": 3}) == "map_go_terms"

        finally:
            # Restore original values
            for var, val in original_values.items():
                if val is None:
                    os.environ.pop(var, None)
                else:
                    os.environ[var] = val

    def test_env_vars_accept_valid_string_numbers(self) -> None:
        """Verify env vars accept valid string numbers."""
        original = os.environ.get("PHASE1_MAX_ITERATIONS")

        try:
            os.environ["PHASE1_MAX_ITERATIONS"] = "10"
            # Should not raise
            result = phase1_route({"phase1_eval": {"grade": "fail"}, "phase1_iteration": 9})
            assert result == "phase1_refine"

        finally:
            if original is None:
                os.environ.pop("PHASE1_MAX_ITERATIONS", None)
            else:
                os.environ["PHASE1_MAX_ITERATIONS"] = original


# =============================================================================
# Helper Functions
# =============================================================================


def _sample_processes(count: int) -> list[dict[str, Any]]:
    """Generate sample biological processes for testing."""
    return [
        {
            "rank": idx + 1,
            "process_name": f"Process {idx}",
            "evidence_score": 7,
            "evidence_summary": f"Evidence summary for process {idx}",
            "sources": ["PMID:123"],
        }
        for idx in range(count)
    ]


def _sample_genes(count: int) -> list[dict[str, Any]]:
    """Generate sample genes for testing."""
    return [
        {
            "gene_symbol": f"GENE{idx}",
            "score": 8,
            "biological_process": f"BP{idx % 5}",
            "evidence_summary": f"Evidence for GENE{idx}",
            "sources": ["PMID:123"],
        }
        for idx in range(count)
    ]


def _sample_go_terms(count: int) -> list[dict[str, Any]]:
    """Generate sample GO terms for testing."""
    return [
        {
            "go_id": f"GO:{idx:07d}",
            "go_label": f"Term {idx}",
            "definition": f"Definition for term {idx}",
            "biological_process": f"BP{idx % 5}",
            "sources": [f"GO:{idx:07d}"],
        }
        for idx in range(count)
    ]
