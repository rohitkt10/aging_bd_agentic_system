# Logging, Tracing, and Audit Trail

This system must produce a complete audit trail of tool calls and reasoning.

## Required Log Channels

1. **Tool call history** (in state)
2. **Execution logs** (file-based)
3. **Final outputs** (TSV + summary)

## Recommended Logging Structure

Write JSONL logs to `logs/agent_traces/{hallmark_name}.jsonl`:

```json
{
  "timestamp": "...",
  "phase": "phase1" | "phase2",
  "bp": "...",
  "node": "...",
  "tool": "query_pubmed",
  "args": {...},
  "result_count": 5,
  "notes": "..."
}
```

## State-Based Audit Trail

Maintain `tool_call_history` in state for in-graph debugging. At the end of the run, persist it as an artifact or JSONL file.

## Evidence Requirements

Every gene/GO term output should include:

- At least one evidence source (PMID, PMC, or tool reference)
- A short evidence summary

## Validation Hooks

Use `utils/validation.py` to enforce:

- Gene count (300–500)
- GO term count (50–80)
- Score ranges (1–10)
- Non-empty evidence summaries
