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

    tool_call_history: Annotated[List[Dict[str, any]], operator.add]  # Full audit trail
    lopez_otin_context: str  # Lopez-Otin paper content for Phase 1

    # Phase 1 outputs
    biological_processes: List[Dict[str, Any]]

    # Phase 2 tracking
    current_bp_index: int
    current_bp_name: str

    # Phase 2 outputs (accumulated across all BPs)
    genes_found: Annotated[List[Dict[str, Any]], operator.add]
    go_terms_found: Annotated[List[Dict[str, Any]], operator.add]

    # Agent working memory
    research_scratchpad: str

    # Context management
    context_summary: Optional[str]
    token_count: int
