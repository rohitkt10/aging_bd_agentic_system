# Phase 4 — Integration & Validation

**Goal:** Wire everything together, run end-to-end tests, verify outputs match expectations.

---

## 4.1 Verify Workflow Graph

**File to verify:** `src/aging_bd_agentic_system/graph/workflow.py`

**What should exist:**
- `build_phase1_graph()` - Returns compiled StateGraph with all Phase 1 nodes
- `build_phase2_graph()` - Returns compiled StateGraph with all Phase 2 nodes (including ReAct loop)
- `build_workflow()` - Returns top-level graph connecting Phase 1 → Phase 2

---

### Phase 2 Routing Logic (ReAct Loop)

**The Phase 2 subgraph needs a routing function to handle the autonomous ReAct research loop:**

```python
def phase2_research_route(state: dict[str, Any]) -> str:
    """
    Route within the Phase 2 research loop.

    Routes back to phase2_research until max iterations reached,
    then routes to phase2_critic for quality review.
    """
    import os

    max_iterations = int(os.environ.get("PHASE2_RESEARCH_MAX_ITERATIONS", "7"))
    current_iteration = state.get("phase2_research_iteration", 0)

    if current_iteration < max_iterations:
        return "phase2_research"  # Continue research loop
    else:
        return "phase2_critic"  # Research complete, review quality


def phase2_critique_route(state: dict[str, Any]) -> str:
    """
    Route after critique determines if refinement is needed.
    """
    import os

    eval_data = state.get("phase2_eval", {})
    grade = eval_data.get("grade", "fail")
    iteration = state.get("phase2_iteration", 0)
    max_refine = int(os.environ.get("PHASE2_REFINE_MAX_ITERATIONS", "3"))

    if grade == "fail" and iteration < max_refine:
        return "phase2_refine"  # Try to fix issues
    else:
        return "map_go_terms"  # Good enough, proceed
```

---

### Expected Nodes in Phase 1:
1. `load_context` → Loads Lopez-Otin paper
2. `phase1_plan` → LLM generates research plan
3. `phase1_research` → LLM extracts biological processes
4. `phase1_critic` → LLM evaluates quality AND count (suggests splits/merges)
5. `phase1_refine` → Executes splits, merges, or follow-up searches (conditional)
6. `phase1_finalize` → Sorts and creates BP queue

### Expected Nodes in Phase 2 (with ReAct loop):
1. `select_bp` → Selects current BP from queue
2. `seed_gene_candidates` → Queries GenAge/OpenGenes to seed research
3. `phase2_research` → **ReAct loop** (autonomous research across multiple iterations)
4. `phase2_critic` → Reviews research quality
5. `phase2_refine` → Focused refinement if critic says fail (conditional)
6. `map_go_terms` → LLM maps GO terms
7. `advance_bp` → Moves to next BP

**Key difference from Copilot's version:**
- Phase 2 now uses an autonomous ReAct research loop instead of single-pass evidence gathering
- `phase2_research` routes to itself multiple times before going to critic
- All iteration counts are configurable via environment variables

**If Copilot's version is good:** Keep it
**If Copilot's version has issues:** Rebuild per the node list above

---

## 4.2 Verify State Schema

**File to verify:** `src/aging_bd_agentic_system/graph/state.py`

**Required fields:**
- `hallmark_name: str`
- `tool_call_history: Annotated[list[dict], operator.add]`
- `reasoning_trace: Annotated[list[str], operator.add]`
- `warnings: Annotated[list[str], operator.add]`
- `lopez_otin_context: str`
- `context_summary: str | None`
- `token_count: int`
- `research_scratchpad: str`
- `phase1_plan: list[str]`
- `phase1_iteration: int`
- `phase1_eval: dict[str, Any]`
- `biological_processes: list[dict[str, Any]]`
- `bp_queue: list[str]`
- `current_bp_index: int`
- `current_bp_name: str`
- `phase2_iteration: int` (for refine loop)
- `phase2_research_iteration: int` (for ReAct research loop)
- `phase2_eval: dict[str, Any]`
- `genes_found: Annotated[list[dict[str, Any]], operator.add]`
- `go_terms_found: Annotated[list[dict[str, Any]], operator.add]`

**If Copilot's version matches:** Keep it
**If fields are missing:** Add them

---

## 4.3 Verify Utilities

**Files to verify:**
- `utils/validation.py` - Phase 1 and Phase 2 validation
- `utils/aggregation.py` - Gene deduplication, GO term merging
- `utils/output_writer.py` - TSV output writers
- `utils/context_manager.py` - Token estimation and summarization

**These should be fine if Copilot implemented them per the old Phase 3 plan.**

**Quick checks:**
1. `validate_all()` returns `{"passed": bool, "issues": list[str]}`
2. `aggregate_outputs()` returns `(genes, go_terms)` tuples
3. `write_processes_tsv()`, `write_genes_tsv()`, `write_go_terms_tsv()` exist
4. `summarize_if_needed()` exists (may not be needed for MVP)

---

## 4.4 End-to-End Test

**Test hallmark:** Use a simple, well-defined hallmark

```bash
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"
```

**Expected behavior:**
1. Phase 1 runs, produces 10-15 biological processes
2. Phase 2 loops through each BP
3. For each BP:
   - Seeds gene candidates from databases
   - LLM scores genes
   - LLM critiques results
   - Maps GO terms
4. Outputs written to `outputs/epigenetic_alterations/`
5. Trace written to `logs/traces/`

**What to monitor:**
- LLM calls completing successfully
- Tools returning results
- Graph progressing through nodes
- Final state has all expected fields

---

## 4.5 Verify Outputs

**Check output files:**

```bash
ls -la outputs/epigenetic_alterations/
```

**Should have:**
- `processes.tsv` - 10-15 rows
- `genes.tsv` - 300-500 rows
- `go_terms.tsv` - 50-80 rows

**Verify content quality:**
- Processes have meaningful names (not "methylation" as a standalone)
- Evidence summaries reference sources (PMID, Lopez-Otin)
- Scores are in range 1-10
- No duplicate genes or GO terms

---

## 4.6 Check Trace File

**Find the trace:**
```bash
ls -la logs/traces/*.jsonl | tail -1
```

**Examine events:**
```bash
cat logs/traces/epigenetic_alterations_*.jsonl | head -50
```

**Look for:**
- `run_start` event
- `llm_start` / `llm_end` pairs
- `node_start` / `node_end` pairs (not `tool_` - tools aren't called via callbacks in LangGraph)
- No `error` events

---

## 4.7 Validation Check

**After run completes:** Check validation output

```bash
python -c "
from pathlib import Path
import json

output_dir = Path('outputs/epigenetic_alterations')
processes = json.loads(output_dir / 'processes.json') if (output_dir / 'processes.json').exists() else []
genes = json.loads(output_dir / 'genes.json') if (output_dir / 'genes.json').exists() else []
go_terms = json.loads(output_dir / 'go_terms.json') if (output_dir / 'go_terms.json').exists() else []

from aging_bd_agentic_system.utils.validation import validate_all
result = validate_all(processes, genes, go_terms)

print(f'Passed: {result[\"passed\"]}')
print(f'Issues: {result[\"issues\"]}')
"
```

**Expected:** Some issues may exist (gene count targets), but no critical errors

---

## 4.8 Troubleshooting Common Issues

### Issue: "VERTEX_PROJECT_ID not set"
**Fix:** Add to `.env`:
```bash
VERTEX_PROJECT_ID=your-project-id
```

### Issue: "No biological processes identified"
**Possible causes:**
1. LLM not returning valid JSON
2. Prompt not clear enough
3. Context too short

**Debug:**
- Check trace file for LLM errors
- Add print statement to see LLM response
- Try simpler prompt

### Issue: "Gene list is empty"
**Possible causes:**
1. GenAge/OpenGenes returning no results
2. LLM filtering out all genes (scores < 5)
3. Structured output parsing failed

**Debug:**
- Check `research_scratchpad` state before phase2_research
- Check LLM response in trace
- Try lowering score threshold to 3

### Issue: "Too few GO terms"
**Possible causes:**
1. GO query returning no results
2. LLM being too strict (score < 6)

**Debug:**
- Check GO tool results directly
- Lower relevance threshold in prompt

### Issue: "Graph hangs or loops forever"
**Possible causes:**
1. Critique always returns "fail"
2. Max iteration not enforced

**Fix:**
- Verify routing functions check iteration count
- Add logging to routing logic

---

## 4.9 Performance Tuning (Optional)

**If runs are too slow:**

1. **Reduce LLM calls:**
   - Limit `gene_limit` in `phase2_research` (try 15 instead of 30)
   - Skip `phase1_plan` LLM call (use hardcoded plan)
   - Reduce `top_k` in tool queries

2. **Use faster model:**
   - Change `VERTEX_MODEL` to `gemini-2.0-flash-001` (already default)
   - Avoid `gemini-2.5-pro` for MVP

3. **Batch operations:**
   - Process multiple genes in single LLM call (already doing this)

---

## 4.10 Compare to Gemini Deep Research

**Manual comparison:**

1. Run your system for "epigenetic alterations"
2. Compare outputs to your boss's Gemini Deep Research results
3. Look for:
   - Process name quality
   - Evidence summary depth
   - Gene relevance
   - GO term mapping

**Your system should:**
- ✅ Produce similar quality outputs
- ✅ Have better source attribution (explicit PMIDs)
- ✅ Be more controllable (adjustable parameters)
- ✅ Have full audit trail (trace files)

**If quality is lower:**
- Improve prompts (add more examples)
- Increase `top_k` for tool queries
- Adjust temperature for more/less creativity
- Add a second critique pass

---

## Phase 4 Completion Checklist

- [ ] Workflow graph verified (all nodes present)
- [ ] State schema verified (all fields present)
- [ ] End-to-end test completes without crashing
- [ ] Output files generated (3 TSV files)
- [ ] Trace file generated with LLM and node events
- [ ] Validation runs (issues logged but not fatal)
- [ ] Outputs are reasonable quality (human review)

---

## Final Verification Command

**One-command test:**

```bash
# Run hallmark
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"

# Check outputs
echo "=== Process Count ==="
wc -l outputs/epigenetic_alterations/processes.tsv

echo "=== Gene Count ==="
wc -l outputs/epigenetic_alterations/genes.tsv

echo "=== GO Term Count ==="
wc -l outputs/epigenetic_alterations/go_terms.tsv

# Check trace
echo "=== Trace Summary ==="
python -c "
from aging_bd_agentic_system.utils.tracing import get_trace_files, summarize_trace
import sys

traces = get_trace_files('epigenetic_alterations')
if traces:
    summary = summarize_trace(traces[-1])
    for k, v in summary.items():
        print(f'{k}: {v}')
else:
    print('No trace files found')
    sys.exit(1)
"
```

**Expected output:**
```
=== Process Count ===
16 outputs/epigenetic_alterations/processes.tsv  (15 + header)

=== Gene Count ===
350 outputs/epigenetic_alterations/genes.tsv  (within 300-500 range)

=== GO Term Count ===
65 outputs/epigenetic_alterations/go_terms.tsv  (within 50-80 range)

=== Trace Summary ===
trace_file: logs/traces/epigenetic_alterations_20250219_143022.jsonl
total_events: 250
llm_calls: 45
tool_calls: 0
errors: 0
start_time: 2025-02-19T14:30:22
end_time: 2025-02-19T15:15:48
```

---

## What If Something Doesn't Work?

**Strategy:**
1. Check trace file for error events
2. Add print statements to isolate the issue
3. Test components individually:
   - LLM integration: `python scripts/test_llm.py`
   - Tools: Import and call directly
   - Single agent node: Call the function directly

**Common fixes:**
- Structured output failing → Use fallback JSON parsing
- Tools returning empty → Check query strings, increase limits
- State not updating → Check reducer annotations (`operator.add`)
- Graph not progressing → Check routing logic

---

## Success Criteria

**MVP is complete when:**
1. ✅ End-to-end run succeeds for one hallmark
2. ✅ Outputs match target ranges (10-15 BPs, 300-500 genes, 50-80 GO terms)
3. ✅ All traces captured with timestamps
4. ✅ Quality is comparable to Gemini Deep Research
5. ✅ System can be rerun with different hallmark

**At that point:** You have replaced Gemini Deep Research with a controllable, local, auditable system.
