# Phase 3 — Observability

**Goal:** Integrate LangGraph callback-based tracing for automatic LLM and tool call capture with unified logging directory.

**Note:** Phase 3 is complete. This plan documents the final unified logging structure.

---

## 3.1 Logging Architecture

**Unified Directory Structure:**
```
<project_root>/
├── logs/
│   └── {hallmark}/                      # e.g., "epigenetic_alterations"
│       ├── trace_{timestamp}.jsonl      # Tier 1: Per-call traces
│       ├── trace_{timestamp}.json       # Tier 1: Complete summary
│       └── audit.jsonl                  # Tier 2: Major events
├── outputs/                             # Unchanged
│   └── {hallmark}/
│       ├── biological_processes.tsv
│       ├── curated_genes.tsv
│       ├── curated_go_terms.tsv
│       └── full_state.json
```

**Two-Tier Logging:**
- **Tier 1:** `TracingCallbackHandler` captures every LLM call, tool call, node transition
- **Tier 2:** `audit_logger` captures BP completion, workflow completion, scratchpad dumps

**Benefits:**
- All logs for a hallmark in one directory
- Easy to find/analyze logs for specific hallmark
- Separate files for easy filtering by granularity
- Can trace full execution by sorting both JSONL files by timestamp

---

## 3.2 Tracing Module (Implemented)

**File:** `src/aging_bd_agentic_system/observability/tracing.py`

**Status:** ✅ Complete

**What it provides:**
- `TracingCallbackHandler` - LangGraph callback handler (accepts `hallmark_name`)
- `create_tracing_callback(log_dir, hallmark_name)` - Factory function
- `setup_logging(level)` - Application logging configuration

**What it logs:**
- Every LLM call (start/end, model, prompt preview, response preview)
- Every tool call (start/end, tool name, args, results)
- Chain/node execution (start/end)
- Errors

**Where logs go:** `logs/{hallmark}/trace_{timestamp}.jsonl` (incremental) + `trace_{timestamp}.json` (summary)

---

## 3.3 Audit Logger (Implemented)

**File:** `src/aging_bd_agentic_system/utils/audit_logger.py`

**Status:** ✅ Complete

**What it logs:**
- `bp_research_complete` - BP completion with scratchpad snapshot
- `workflow_complete` - Workflow completion with summary

**Where logs go:** `logs/{hallmark}/audit.jsonl`

**Integration:** ✅ Complete
- Called in `advance_bp()` at BP completion (phase2_gene_researcher.py:539-546)
- Called in `main.py` at workflow completion (main.py:88-96)

---

## 3.4 Main Entry Point (Implemented)

**File:** `src/aging_bd_agentic_system/main.py`

**Status:** ✅ Complete

**Key integration:**
```python
# Create tracing callback with hallmark name
tracing_handler = create_tracing_callback(hallmark_name=args.hallmark)

# Invoke workflow with tracing callback
result = graph.invoke(state, config={"callbacks": [tracing_handler]})
```

**Also does:**
- Writes full state to `outputs/{hallmark}/full_state.json` (lines 83-85)
- Logs workflow completion via audit_logger (lines 88-96)
- Writes TSV deliverables (lines 77-80)

---

## 3.5 Verify Tracing Works

**Quick test:** Run a hallmark and check trace files are created

```bash
# Run workflow
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"

# Check unified log directory
ls -la logs/epigenetic_alterations/

# Check trace content
head -20 logs/epigenetic_alterations/trace_*.jsonl

# Check audit content
cat logs/epigenetic_alterations/audit.jsonl | jq -r '.event_type'
```

**Expected output:**
```
logs/epigenetic_alterations/
├── trace_20250219_120000.jsonl    # Per-call traces
├── trace_20250219_120000.json     # Complete summary
└── audit.jsonl                    # Major events
```

---

## Phase 3 Completion Checklist

- [x] `observability/tracing.py` exists with `TracingCallbackHandler` ✅
- [x] `TracingCallbackHandler` accepts `hallmark_name` parameter ✅
- [x] `create_tracing_callback()` accepts `hallmark_name` parameter ✅
- [x] `utils/audit_logger.py` uses `logs/{hallmark}/audit.jsonl` ✅
- [x] Two-tier logging in unified directory ✅
  - [x] Per-call traces in `logs/{hallmark}/trace_{timestamp}.jsonl`
  - [x] Major events in `logs/{hallmark}/audit.jsonl`
- [x] `advance_bp()` calls audit_logger at BP completion ✅
- [x] `main.py` calls audit_logger at workflow completion ✅
- [x] `main.py` writes full state to `outputs/{hallmark}/full_state.json` ✅
- [x] `main.py` passes hallmark_name to tracing callback ✅
- [x] Deliverables written to `outputs/{hallmark}/*.tsv` ✅
- [x] All tests passing ✅

---

## Trace File Format

**Tier 1 (trace) events:**
```json
{"timestamp": "2025-02-19T14:30:23.123456", "event_type": "llm_start", "run_id": "...", "model": "gemini-2.0-flash-...", "prompt_preview": "...", "current_node": "phase1_research"}
```

**Tier 2 (audit) events:**
```json
{"timestamp": "2025-02-19T14:35:12", "hallmark": "epigenetic_alterations", "event_type": "bp_research_complete", "bp_name": "DNA methylation", "genes_count": 25, "research_scratchpad": "..."}
```

**Event types captured:**
- `chain_start` / `chain_end` / `chain_error` - Graph execution
- `llm_start` / `llm_end` / `llm_error` - LLM calls
- `tool_start` / `tool_end` / `tool_error` - Tool calls
- `bp_research_complete` - BP completion
- `workflow_complete` - Workflow completion

---

## How to Trace Execution Sequence

**All logs in one place:** `logs/{hallmark}/`

1. **Per-call traces** (Tier 1): `logs/{hallmark}/trace_{timestamp}.jsonl`
   - Every LLM call with timing
   - Every tool call with timing
   - Node transitions

2. **Major events** (Tier 2): `logs/{hallmark}/audit.jsonl`
   - BP research completion events
   - Workflow completion event

3. **Full state**: `outputs/{hallmark}/full_state.json`
   - Complete workflow state
   - All genes, GO terms, biological processes

**To trace full execution:**
```bash
# Combine both logs and sort by timestamp
jq -s 'sort_by(.timestamp)' logs/{hallmark}/*.jsonl
```

---

## Next Phase

After Phase 3 complete, proceed to **Phase 4 — Integration & Validation**, where we'll run end-to-end tests and validate the complete workflow.
