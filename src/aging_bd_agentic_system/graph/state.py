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

    # Configuration (travels through entire workflow)
    config: Dict[str, Any]

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
    phase1_plan: Dict[str, Any]  # Contains research_goals with search terms
    phase1_iteration: int
    phase1_critique: Optional[str]  # Unstructured critique text
    # Structured recommendations from critic
    phase1_critic_recommendations: Optional[Dict[str, Any]]
    phase1_eval: Optional[Dict[str, Any]]  # Legacy, kept for compatibility
    biological_processes: List[Dict[str, Any]]
    bp_queue: List[str]

    # Phase 2 tracking
    current_bp_index: int
    current_bp_name: str
    phase2_critic_iteration: int
    phase2_research_iteration: int
    phase2_eval: Dict[str, Any]
    state_of_knowledge: Optional[str]  # JSON: {candidate_genes, citations, summary}
    gene_evidence: Dict[str, Any]  # {gene_sym: {opengenes: bool, genage: bool, evidence_notes: [], citations: []}}

    # Phase 2 outputs (accumulated across all BPs)
    genes_found: Annotated[List[Dict[str, Any]], operator.add]
    go_terms_found: Annotated[List[Dict[str, Any]], operator.add]
