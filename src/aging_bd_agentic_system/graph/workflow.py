from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from aging_bd_agentic_system.agents.phase1_bp_identifier import (
    load_lopez_otin_context,
    phase1_critic,
    phase1_finalize,
    phase1_plan,
    phase1_refine,
    phase1_research,
)
from aging_bd_agentic_system.agents.phase2_gene_researcher import (
    advance_bp,
    map_go_terms,
    phase2_critic,
    phase2_refine,
    phase2_research,
    select_bp,
)
from aging_bd_agentic_system.graph.state import ResearchState


def phase1_route(state: dict[str, Any]) -> str:
    """Route Phase 1 critique results to refine or finalize."""
    recommendations = state.get("phase1_critic_recommendations", {})
    iteration = state.get("phase1_iteration", 0)

    # Read max_iterations from config
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase1", {}).get("max_iterations", 2)

    grade = recommendations.get("grade", "fail")

    # If critic passes or we've hit max iterations, finalize
    if grade == "pass" or iteration + 1 >= max_iterations:
        return "phase1_finalize"
    return "phase1_refine"


def phase2_route(state: dict[str, Any]) -> str:
    """Route Phase 2 critique results to refine or GO term mapping."""
    eval_data = state.get("phase2_eval", {})
    iteration = state.get("phase2_critic_iteration", 0)

    # Read max_refine_iterations from config
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase2", {}).get("max_refine_iterations", 3)

    if eval_data.get("grade") == "fail" and iteration < max_iterations:
        return "phase2_refine"
    return "map_go_terms"


def phase2_research_route(state: dict[str, Any]) -> str:
    """Route Phase 2 research results: continue loop or go to critic."""
    iteration = state.get("phase2_research_iteration", 0)

    # Read max_research_iterations from config
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase2", {}).get("max_research_iterations", 7)

    # If we haven't reached max iterations, continue research loop
    if iteration < max_iterations:
        return "phase2_research"
    # Otherwise, move to critic
    return "phase2_critic"


def bp_loop_route(state: dict[str, Any]) -> str:
    """Loop over BPs or exit when the queue is exhausted."""
    index = state.get("current_bp_index", 0)
    queue = state.get("bp_queue", [])
    if index >= len(queue):
        return END
    return "select_bp"


def build_phase1_graph() -> StateGraph:
    """Build Phase 1 subgraph for biological process identification."""
    builder: StateGraph = StateGraph(ResearchState)
    builder.add_node("load_context", load_lopez_otin_context)
    builder.add_node("phase1_plan", phase1_plan)
    builder.add_node("phase1_research", phase1_research)
    builder.add_node("phase1_critic", phase1_critic)
    builder.add_node("phase1_refine", phase1_refine)
    builder.add_node("phase1_finalize", phase1_finalize)

    builder.set_entry_point("load_context")
    builder.add_edge("load_context", "phase1_plan")
    builder.add_edge("phase1_plan", "phase1_research")
    builder.add_edge("phase1_research", "phase1_critic")
    builder.add_conditional_edges(
        "phase1_critic",
        phase1_route,
        {"phase1_refine": "phase1_refine", "phase1_finalize": "phase1_finalize"},
    )
    builder.add_edge("phase1_refine", "phase1_critic")

    return builder.compile()


def build_phase2_graph() -> StateGraph:
    """Build Phase 2 subgraph for per-BP gene research."""
    builder: StateGraph = StateGraph(ResearchState)
    builder.add_node("select_bp", select_bp)
    builder.add_node("phase2_research", phase2_research)
    builder.add_node("phase2_critic", phase2_critic)
    builder.add_node("phase2_refine", phase2_refine)
    builder.add_node("map_go_terms", map_go_terms)
    builder.add_node("advance_bp", advance_bp)

    builder.set_entry_point("select_bp")
    builder.add_edge("select_bp", "phase2_research")
    # Add conditional edge for research loop (continues until max iterations reached)
    builder.add_conditional_edges(
        "phase2_research",
        phase2_research_route,
        {"phase2_research": "phase2_research", "phase2_critic": "phase2_critic"},
    )
    builder.add_conditional_edges(
        "phase2_critic",
        phase2_route,
        {"phase2_refine": "phase2_refine", "map_go_terms": "map_go_terms"},
    )
    builder.add_edge("phase2_refine", "phase2_critic")
    builder.add_edge("map_go_terms", "advance_bp")
    builder.add_conditional_edges(
        "advance_bp",
        bp_loop_route,
        {"select_bp": "select_bp", END: END},
    )

    return builder.compile()


def build_workflow() -> StateGraph:
    """Build the top-level workflow graph."""
    builder: StateGraph = StateGraph(ResearchState)
    builder.add_node("phase1", build_phase1_graph())
    builder.add_node("phase2", build_phase2_graph())

    builder.set_entry_point("phase1")
    builder.add_edge("phase1", "phase2")
    builder.add_edge("phase2", END)

    return builder.compile()


def run_workflow(
    initial_state: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run the aging BD gene discovery workflow.

    Args:
        initial_state: Initial state with hallmark_name.
        config: Optional config dict with callbacks and other settings.

    Returns:
        Final state after workflow completion.
    """
    graph = build_workflow()

    if config is None:
        config = {}

    # Invoke graph with config
    result = graph.invoke(initial_state, config=config)

    return result
