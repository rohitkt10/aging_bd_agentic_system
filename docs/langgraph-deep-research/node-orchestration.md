# Node-by-Node Orchestration (LangGraph)

This section describes how to implement the full workflow as a LangGraph `StateGraph`, including the core nodes and routing rules.

## Top-Level Graph

You should build a top-level graph that orchestrates two subgraphs:

1. **Phase 1 graph** → outputs `biological_processes` and `bp_queue`.
2. **Phase 2 graph** → loops over each BP and accumulates genes/GO terms.

### Pseudocode Skeleton

```python
from langgraph.graph import StateGraph, END

builder = StateGraph(ResearchState)

builder.add_node("phase1", phase1_subgraph)
builder.add_node("phase2", phase2_subgraph)

builder.set_entry_point("phase1")
builder.add_edge("phase1", "phase2")
builder.add_edge("phase2", END)

graph = builder.compile()
```

## Phase 1 Subgraph (BP Identification)

### Node Roles

1. **Load Context**
   - Loads `data/lopez-otin-22.md` into `lopez_otin_context`.
2. **Plan BP Research**
   - Generates 4–6 research goals (topics, search angles).
3. **Research BPs**
   - Uses `query_vector_db` and `query_pubmed` to gather evidence.
4. **Critique Phase 1**
   - Evaluates coverage: are BPs distinct? evidence sufficient?
5. **Refine Phase 1**
   - Adds follow-up searches if critique fails.
6. **Finalize BP List**
   - Ranks and writes `biological_processes` + `bp_queue`.

### Routing Logic

- After **Critique**, route to **Refine** if `grade == fail` and iteration < max.
- Otherwise route to **Finalize**.

### Pseudocode Routing

```python
def phase1_route(state):
    if state["phase1_eval"]["grade"] == "fail" and state["phase1_iteration"] < 3:
        return "phase1_refine"
    return "phase1_finalize"
```

## Phase 2 Subgraph (Per-BP Research Loop)

### Node Roles

1. **Select BP**
   - Reads `bp_queue` and sets `current_bp_name`.
2. **Expand Candidates**
   - Queries GenAge + OpenGenes for initial gene candidates.
3. **Evidence Research Loop**
   - Uses vector DB + PubMed to collect evidence for candidates.
4. **Critique Gene Evidence**
   - Checks gene count, coverage, and evidence strength.
5. **Refine Genes**
   - Fills gaps: add missing genes or evidence.
6. **Map GO Terms**
   - Uses `query_go_terms` to map BP-specific terms.
7. **Accumulate Outputs**
   - Adds results to `genes_found`, `go_terms_found`.
8. **Advance BP**
   - Moves to next BP or exits loop.

### Routing Logic

- Critique fail → refine.
- Critique pass → map GO terms → accumulate → advance BP.

## Orchestrating Multiple BPs

Use a **while-style loop** by routing back to `select_bp` until `current_bp_index` reaches the end of `bp_queue`.

```python
def bp_loop_route(state):
    if state["current_bp_index"] >= len(state["bp_queue"]):
        return END
    return "select_bp"
```

## Where to Implement

- `graph/workflow.py`: top-level graph and subgraphs.
- `agents/phase1_bp_identifier.py`: nodes for Phase 1.
- `agents/phase2_gene_researcher.py`: nodes for Phase 2.
- `utils/context_manager.py`: summary logic.
- `utils/validation.py`: end-of-pipeline checks.

This gives you a complete, ADK-style deep-research workflow in LangGraph form.
