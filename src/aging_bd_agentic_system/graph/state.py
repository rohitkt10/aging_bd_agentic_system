from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class ResearchState(TypedDict):
    """
    Workflow state container for the aging hallmark curation pipeline.

    Fields capture Phase 1 outputs, Phase 2 progress, accumulated gene/GO evidence,
    and context management details. Reducer-enabled fields use Annotated with
    operator.add for list aggregation across LangGraph node updates.
    """

    # Input
    hallmark_name: str

    # Audit
    tool_call_history: Annotated[List[Dict[str, Any]], operator.add]
    reasoning_trace: Annotated[List[str], operator.add]
    warnings: Annotated[List[str], operator.add]

    # Context
    lopez_otin_context: str  # Lopez-Otin paper content for Phase 1
    context_summary: Optional[str]
    token_count: int
    research_scratchpad: str

    # Phase 1 outputs
    phase1_plan: List[str]
    phase1_iteration: int
    phase1_eval: Dict[str, Any]
    biological_processes: List[Dict[str, Any]]
    bp_queue: List[str]

    # Phase 2 tracking
    current_bp_index: int
    current_bp_name: str
    phase2_iteration: int
    phase2_research_iteration: int
    phase2_eval: Dict[str, Any]

    # Phase 2 outputs (accumulated across all BPs)
    genes_found: Annotated[List[Dict[str, Any]], operator.add]
    go_terms_found: Annotated[List[Dict[str, Any]], operator.add]
