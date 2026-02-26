# Plan: Phase 1 Audit Trail & Citation Management

## Goal
Add comprehensive audit trailing for Phase 1 to track all tool calls, LLM interactions, and citations for verification and reproducibility.

## Current State
- `tool_call_history` field exists in state schema but is never populated
- Tools (`query_vector_db`, `query_pubmed`) return rich data with PMIDs but results are lost after summarization
- No LLM call logging (prompts/responses not saved)
- Final `full_state.json` has empty audit fields

## Implementation Plan

### 1. Create Audit Helper Functions
**File**: `src/aging_bd_agentic_system/utils/audit_logger.py` (already exists, extend it)

Add helper to log tool calls to state:
```python
def log_tool_call(
    state: dict,
    tool_name: str,
    query: str,
    params: dict,
    results: list[dict],
    result_count: int
) -> dict:
    """Append tool call record to tool_call_history."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "phase": "phase1",
        "tool": tool_name,
        "query": query,
        "params": params,
        "result_count": result_count,
        "pmids": [r.get("pmid") for r in results if r.get("pmid")],
        "pmcids": [r.get("pmcid") for r in results if r.get("pmcid")],
    }
    return {"tool_call_history": [entry]}
```

### 2. Instrument Tool Calls in `phase1_research()`
**File**: `src/aging_bd_agentic_system/agents/phase1_bp_identifier.py`

Wrap each tool call to log to `tool_call_history`:

**Initial research path (iteration 0)**:
```python
# Vector DB searches
for term in goal.get("vector_db_terms", []):
    results = query_vector_db(query=term, top_k=vector_db_top_k)
    goal_corpus_results.extend(results)
    # LOG IT
    tool_logs.extend([{
        "tool": "vector_db", "query": term, "top_k": vector_db_top_k,
        "result_count": len(results), "pmids": extract_pmids(results)
    }])

# PubMed searches
for term in goal.get("pubmed_terms", []):
    results = query_pubmed(query=term, retmax=pubmed_retmax)
    goal_pubmed_results.extend(results)
    # LOG IT
    tool_logs.extend([{
        "tool": "pubmed", "query": term, "retmax": pubmed_retmax,
        "result_count": len(results), "pmids": extract_pmids(results)
    }])
```

**Refinement research path (iteration > 0)**:
Same logging for critic-recommended queries.

### 3. Add Citation Aggregation to `phase1_finalize()`
**File**: `src/aging_bd_agentic_system/agents/phase1_bp_identifier.py`

At end of Phase 1, aggregate all unique citations:
```python
def aggregate_phase1_citations(state: dict) -> dict:
    """Extract all unique PMIDs/PMCID from tool_call_history."""
    tool_history = state.get("tool_call_history", [])
    all_pmids = set()
    all_pmcids = set()

    for call in tool_history:
        all_pmids.update(call.get("pmids", []))
        all_pmcids.update(call.get("pmcids", []))

    return {
        "phase1_citations": {
            "pmids": sorted(list(all_pmids)),
            "pmcids": sorted(list(all_pmcids)),
            "total_unique": len(all_pmids) + len(all_pmcids),
            "total_queries": len(tool_history),
        }
    }
```

Call this in `phase1_finalize()` and add to return dict.

### 4. Add LLM Call Logging
**File**: `src/aging_bd_agentic_system/llm/client.py`

Add logging to `invoke()` and `invoke_structured()`:
- Log full prompt and system prompt
- Log response (structured output as JSON)
- Log timestamp and model info
- Store in `llm_call_history` list in state

```python
class LLMClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        # ... existing init ...
        self.call_history: list[dict] = []

    def _log_call(self, prompt: str, response: Any, system_prompt: str | None = None) -> None:
        """Log LLM call for audit trail."""
        self.call_history.append({
            "timestamp": datetime.now().isoformat(),
            "model": self.config.model,
            "system_prompt": system_prompt,
            "prompt": prompt,
            "response": response if isinstance(response, dict) else str(response)[:5000],
        })

    def invoke(self, prompt: str, *, system_prompt: str | None = None, **kwargs) -> str:
        response = self.provider.invoke(prompt, system_prompt=system_prompt, **kwargs)
        self._log_call(prompt, response, system_prompt)
        return response

    def invoke_structured(self, prompt: str, schema: dict, *, system_prompt: str | None = None, **kwargs) -> dict:
        response = self.provider.invoke_structured(prompt, schema, system_prompt=system_prompt, **kwargs)
        self._log_call(prompt, response, system_prompt)
        return response
```

Add `llm_call_history` to state schema and aggregate in `phase1_finalize()`.

### 5. Output Changes
**File**: `src/aging_bd_agentic_system/main.py`

After Phase 1 completes, write audit files:
```python
# In addition to full_state.json
audit_file = out_dir / "phase1_audit.json"
with audit_file.open("w") as f:
    json.dump({
        "tool_call_history": result.get("tool_call_history", []),
        "phase1_citations": result.get("phase1_citations", {}),
    }, f, indent=2)
```

## Files to Modify

1. **`src/aging_bd_agentic_system/llm/client.py`**
   - Add `call_history` list to `LLMClient`
   - Add `_log_call()` helper method
   - Wrap `invoke()` and `invoke_structured()` with logging
   - Add `get_call_history()` method to retrieve logs

2. **`src/aging_bd_agentic_system/agents/phase1_bp_identifier.py`**
   - Add tool call logging in `phase1_research()` (both paths)
   - Add `aggregate_phase1_citations()` helper
   - Call aggregation in `phase1_finalize()`
   - Export LLM call history to state

3. **`src/aging_bd_agentic_system/main.py`**
   - Write `phase1_audit.json` after workflow completes
   - Include both `tool_call_history` and `llm_call_history`

4. **`src/aging_bd_agentic_system/graph/state.py`** (if exists)
   - Add `llm_call_history` to state schema

## Output Artifacts

After Phase 1 completes, `outputs/{hallmark}/` will contain:
- `processes.tsv` - Final biological processes
- `full_state.json` - Complete state including `tool_call_history` and `llm_call_history`
- `phase1_audit.json` - Extracted audit trail:
  - `tool_call_history` - All vector_db and pubmed queries with results
  - `llm_call_history` - All LLM calls with prompts and responses
  - `phase1_citations` - Aggregated unique PMIDs/PMCIDs

## Verification

1. Run Phase 1 on a hallmark: `python -m aging_bd_agentic_system.main --hallmark "genomic instability"`
2. Check `outputs/genomic_instability/phase1_audit.json` contains:
   - Non-empty `tool_call_history` with all vector_db and pubmed queries
   - Non-empty `llm_call_history` with all LLM prompts and responses
   - `phase1_citations` with aggregated PMIDs
3. Verify `full_state.json` has populated `tool_call_history` and `llm_call_history`
4. Cross-reference PMIDs in `processes.tsv` sources with audit
5. Verify LLM call count matches expected (plan, research, critic, refine, finalize)

## Scope Note

This plan is **Phase 1 only**. Phase 2 audit trailing is a separate task - Phase 2 already has partial `tool_call_history` usage but needs similar citation aggregation.
