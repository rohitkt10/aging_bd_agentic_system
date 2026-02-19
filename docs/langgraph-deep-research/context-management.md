# Context Management & Summarization

Deep research workflows quickly exceed context limits. You must explicitly manage context size.

## Context Budget Strategy

1. Track `token_count` (approximate by word count or external tokenizer).
2. If tokens > threshold (e.g., 50k), summarize older evidence.
3. Preserve:
   - Current BP
   - Current gene list and scores
   - Most recent tool results

## Summarization Node

Create a node (or utility) that:

- Takes `tool_call_history` and `reasoning_trace`
- Produces a condensed `context_summary`
- Clears older entries from raw logs if needed

```python
def summarize_context(state):
    summary = llm_summarize(state["tool_call_history"], state["reasoning_trace"])
    return {
        "context_summary": summary,
        "tool_call_history": [],
        "reasoning_trace": [],
    }
```

## Where to Trigger Summaries

- After each Phase 2 BP loop
- After a critique/refinement cycle
- Before final aggregation

## Practical Notes

- Always keep raw evidence in persistent logs (disk) even if removed from state.
- Summaries should be appended to the final report or audit trail.
