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
    phase2_research,
    select_bp,
)
from aging_bd_agentic_system.agents.phase2_critic import phase2_critic
from aging_bd_agentic_system.agents.phase2_refine import phase2_refine
from aging_bd_agentic_system.graph.state import ResearchState


def phase1_critic_refine_route(state: dict[str, Any]) -> str:
    """Route Phase 1 critique results to refine or finalize."""
    recommendations = state.get("phase1_critic_recommendations", {})
    grade = recommendations.get("grade", "fail")
    if grade == "pass":
        return "phase1_finalize"
    
    # continue research
    iteration = state.get("phase1_iteration", 0)
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase1", {}).get("max_iterations", 2)

    if iteration < max_iterations:
        return "phase1_refine"
    return "phase1_finalize"

def phase1_refine_finalize_route(state: dict[str, Any]) -> str:
    """After refining, go to critic only if budget remains, else finalize."""
    iteration = state.get("phase1_iteration", 0)
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase1", {}).get("max_iterations", 2)

    if iteration >= max_iterations:
        return "phase1_finalize"
    return "phase1_critic"

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
                            phase1_critic_refine_route,
                            {"phase1_refine": "phase1_refine", "phase1_finalize": "phase1_finalize"},
                        )
    builder.add_conditional_edges(     
                        "phase1_refine",
                        phase1_refine_finalize_route,
                        {
                            "phase1_critic":   "phase1_critic",
                            "phase1_finalize": "phase1_finalize",
                        },
                    )

    return builder.compile()



def phase2_research_critic_route(state: dict[str, Any]) -> str:
    """Route Phase 2 research results: continue loop or go to critic."""
    iteration = state.get("phase2_research_iteration", 0)
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase2", {}).get("max_research_iterations", 7)

    # If we haven't reached max iterations, continue research loop
    if iteration > max_iterations:
        return "phase2_critic"
    return "phase2_research"

def phase2_critic_refine_route(state: dict[str, Any]) -> str:
    """Route Phase 2 critic results for critic-refine-only workflow.

    - If critic passes -> END
    - If critic fails -> phase2_refine
    """
    critic_review = state.get("critic_review", {})
    grade = critic_review.get("grade", "fail")
    if grade == "pass":
        return END
    return "phase2_refine"

def phase2_refine_critic_route(state: dict[str, Any]) -> str:
    """Check if there is still budget to do critic/refinement and route accordingly"""
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase2", {}).get("max_critic_iterations", 2)
    current_iteration = state.get("critic_iteration", 0)
    if current_iteration >= max_iterations:
        return END
    return "phase2_critic"

def build_phase2_isolated_graph() -> StateGraph:
    """Build a graph for Phase 2 seeding, research, review and refinement."""
    builder: StateGraph = StateGraph(ResearchState)
    builder.add_node("phase2_research", phase2_research)
    builder.add_node("phase2_critic", phase2_critic)
    builder.add_node("phase2_refine", phase2_refine)
    builder.set_entry_point("phase2_research")
    builder.add_conditional_edges("phase2_research",phase2_research_critic_route,
    {"phase2_research": "phase2_research", "phase2_critic": "phase2_critic"},)

    builder.add_conditional_edges("phase2_critic",phase2_critic_refine_route,
    {END:END, "phase2_refine": "phase2_refine"},)

    builder.add_conditional_edges("phase2_refine",phase2_refine_critic_route,
    {END:END,"phase2_critic": "phase2_critic"},)

    return builder.compile()




def phase2_route(state: dict[str, Any]) -> str:
    """Route Phase 2 critique results to refine or GO term mapping.

    New logic (manuscript review cycle):
    - If critic passes, -> map_go_terms (no further work needed)
    - If critic fails" -> phase2_refine (address reviewer feedback)

    Note: Budget exhaustion is handled by should_continue_critic_refine after refinement.
    """
    critic_review = state.get("critic_review", {})
    grade = critic_review.get("grade", "fail")

    if grade == "pass":
        return "map_go_terms"  # No further work needed

    return "phase2_refine"  # Address reviewer feedback

def bp_loop_route(state: dict[str, Any]) -> str:
    """Loop over BPs or exit when the queue is exhausted."""
    index = state.get("current_bp_index", 0)
    queue = state.get("bp_queue", [])
    if index >= len(queue):
        return END
    return "select_bp"


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
    # Critic routes: pass -> map_go_terms, fail -> phase2_refine
    builder.add_conditional_edges(
        "phase2_critic",
        phase2_route,
        {"phase2_refine": "phase2_refine", "map_go_terms": "map_go_terms"},
    )
    # Refine routes: budget exhausted -> map_go_terms. otherwise -> phase2_critic
    builder.add_conditional_edges(
        "phase2_refine",
        should_continue_critic_refine,
        {"phase2_critic": "phase2_critic", "map_go_terms": "map_go_terms"},
    )
    builder.add_edge("map_go_terms", "advance_bp")
    builder.add_conditional_edges(
        "advance_bp",
        bp_loop_route,
        {"select_bp": "select_bp", END: END},
    )

    return builder.compile()


def phase2_seeding_route(state: dict[str, Any]) -> str:
    """Route for seeding-only graph: end after seeding completes.

    Seeding sets phase2_research_iteration to 1 when done.
    """
    iteration = state.get("phase2_research_iteration", 0)
    if iteration >= 1:
        return END
    return "phase2_research"


def build_phase2_seeding_graph() -> StateGraph:
    """Build Phase 2 graph that only does seeding (iteration 0).

    This graph:
    1. Selects BP
    2. Runs phase2_research at iteration 0 (which triggers seeding)
    3. Ends after seeding completes (iteration becomes 1)
    """
    builder: StateGraph = StateGraph(ResearchState)
    builder.add_node("select_bp", select_bp)
    builder.add_node("phase2_research", phase2_research)

    builder.set_entry_point("select_bp")
    builder.add_edge("select_bp", "phase2_research")
    builder.add_conditional_edges(
        "phase2_research",
        phase2_seeding_route,
        {"phase2_research": "phase2_research", END: END},
    )

    return builder.compile()


def phase2_research_only_route(state: dict[str, Any]) -> str:
    """Route for research-only graph: continue loop or end."""
    iteration = state.get("phase2_research_iteration", 0)
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase2", {}).get("max_research_iterations", 7)

    if iteration > 0 and iteration <= max_iterations:
        return "phase2_research"
    return END


def build_phase2_research_only_graph() -> StateGraph:
    """Build Phase 2 graph that stops after initial research (no critic/refine/go_mapping)."""
    builder: StateGraph = StateGraph(ResearchState)
    builder.add_node("select_bp", select_bp)
    builder.add_node("phase2_research", phase2_research)

    builder.set_entry_point("select_bp")
    builder.add_edge("select_bp", "phase2_research")
    builder.add_conditional_edges(
        "phase2_research",
        phase2_research_only_route,
        {"phase2_research": "phase2_research", END: END},
    )

    return builder.compile()




def phase2_refine_continue_route(state: dict[str, Any]) -> str:
    """Route after refinement for critic-refine-only workflow.

    - If budget exhausted -> END
    - Otherwise -> phase2_critic
    """
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase2", {}).get("max_critic_iterations", 2)
    current_iteration = state.get("critic_iteration", 0)
    if current_iteration >= max_iterations:
        return END
    return "phase2_critic"


def build_phase2_critic_refine_graph() -> StateGraph:
    """Build Phase 2 subgraph for critic-refine loop only."""
    builder: StateGraph = StateGraph(ResearchState)
    builder.add_node("phase2_critic", phase2_critic)
    builder.add_node("phase2_refine", phase2_refine)

    builder.set_entry_point("phase2_critic")
    # Critic routes: pass -> END, fail -> phase2_refine
    builder.add_conditional_edges(
        "phase2_critic",
        phase2_critic_refine_route,
        {"phase2_refine": "phase2_refine", END: END},
    )
    # Refine routes: budget exhausted -> END, otherwise -> phase2_critic
    builder.add_conditional_edges(
        "phase2_refine",
        phase2_refine_continue_route,
        {"phase2_critic": "phase2_critic", END: END},
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
