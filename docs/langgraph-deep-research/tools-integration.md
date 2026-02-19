# Tool Integration Patterns

This project’s deep research workflow must use your existing tool functions. LangGraph does not provide tool calling automatically; you must implement a **tool router** or a **tool execution node**.

## Available Tools

- `query_vector_db` → literature corpus chunks
- `query_pubmed` → PubMed abstracts
- `query_genage` → GenAge CSV
- `query_opengenes` → Open Genes API
- `query_go_terms` → GO terms

## Tool Router Pattern (Recommended)

Create a node that takes a tool request from the model and executes it.

```python
def tool_router(state):
    request = state["pending_tool_request"]
    tool_name = request["tool"]
    args = request["args"]

    if tool_name == "query_vector_db":
        result = query_vector_db(**args)
    elif tool_name == "query_pubmed":
        result = query_pubmed(**args)
    # ... etc

    state["tool_call_history"].append({
        "tool": tool_name,
        "args": args,
        "result": result,
    })

    return {"last_tool_result": result}
```

## Tool Usage in Researcher Nodes

### Phase 1 (BP identification)

- First call `query_vector_db(hallmark)`.
- Extract BPs from results.
- Then call `query_pubmed` for each candidate BP.

### Phase 2 (Gene research)

- Use `query_genage` + `query_opengenes` to seed candidates.
- Use `query_vector_db` and `query_pubmed` for evidence and score updates.
- Use `query_go_terms` to map GO BP terms.

## Tool Evidence Format

Standardize tool outputs into a common format so you can attach citations in final outputs:

```python
{
  "source_type": "pubmed" | "corpus" | "genage" | "opengenes" | "go",
  "source_id": "PMID:..." | "PMC..." | "GO:...",
  "snippet": "short excerpt",
  "metadata": {...}
}
```

## Error Handling

- Validate tool args before calls.
- Catch network errors for PubMed/OpenGenes and record failures in `warnings`.
- If a tool fails, do not crash the graph; add a warning and continue.
