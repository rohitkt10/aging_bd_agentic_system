# State Schema & Data Contracts

Your LangGraph pipeline must rely on a **single shared state** that tracks both phases and preserves auditability. A structured state prevents hidden coupling between nodes and makes debugging straightforward.

## Base State (Extend Current ResearchState)

Current `ResearchState` in `graph/state.py` is a good starting point, but it needs expansions for deep research.

### Recommended State Fields

```python
class ResearchState(TypedDict):
    # Input
    hallmark_name: str

    # Global audit
    tool_call_history: Annotated[list[dict[str, Any]], operator.add]
    reasoning_trace: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]

    # Phase 1
    lopez_otin_context: str
    phase1_plan: list[str]
    biological_processes: list[dict[str, Any]]
    phase1_iteration: int
    phase1_eval: dict[str, Any]

    # Phase 2 control
    current_bp_index: int
    current_bp_name: str
    bp_queue: list[str]

    # Phase 2 outputs
    genes_found: Annotated[list[dict[str, Any]], operator.add]
    go_terms_found: Annotated[list[dict[str, Any]], operator.add]

    # Working memory
    research_scratchpad: str
    context_summary: str | None
    token_count: int

    # Control flags
    stop_requested: bool
    loop_should_continue: bool
```

## Data Contracts by Phase

### Phase 1 Output Contract (Biological Processes)

Each entry should be:

```python
{
  "rank": int,
  "process_name": str,
  "evidence_score": int,
  "evidence_summary": str,
  "sources": list[str]  # PMIDs, Lopez-Otin refs, or corpus IDs
}
```

### Phase 2 Output Contract (Genes)

```python
{
  "gene_symbol": str,
  "score": int,               # 1–10
  "biological_process": str,
  "evidence_summary": str,
  "sources": list[str]
}
```

### GO Term Output Contract

```python
{
  "go_id": str,
  "go_label": str,
  "biological_process": str,
  "definition": str,
  "sources": list[str]
}
```

## Reducers in LangGraph

Use `Annotated[..., operator.add]` for accumulation fields:

- `tool_call_history`
- `reasoning_trace`
- `genes_found`
- `go_terms_found`

This allows each node to append without manually merging lists.

## Why This Matters

If you want a deep-research workflow, you must:

- Preserve **all evidence** in state.
- Capture **critic feedback** and loop counters.
- Ensure nodes are pure functions that only mutate explicit keys.
