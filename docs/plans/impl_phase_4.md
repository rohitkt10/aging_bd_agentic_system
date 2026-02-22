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

**The Phase 2 subgraph uses routing functions that read from `state["config"]`:**

```python
def phase2_research_route(state: dict[str, Any]) -> str:
    """
    Route within the Phase 2 research loop.
    Reads max_iterations from state["config"]["phase2"].
    """
    cfg = state.get("config", {})
    max_iterations = cfg.get("phase2", {}).get("max_research_iterations", 7)
    current_iteration = state.get("phase2_research_iteration", 0)

    if current_iteration < max_iterations:
        return "phase2_research"  # Continue research loop
    else:
        return "phase2_critic"  # Research complete, review quality


def phase2_route(state: dict[str, Any]) -> str:
    """
    Route after critique determines if refinement is needed.
    Reads max_refine_iterations from state["config"]["phase2"].
    """
    cfg = state.get("config", {})
    max_refine = cfg.get("phase2", {}).get("max_refine_iterations", 3)

    eval_data = state.get("phase2_eval", {})
    iteration = state.get("phase2_critic_iteration", 0)

    if eval_data.get("grade") == "fail" and iteration < max_refine:
        return "phase2_refine"
    return "map_go_terms"
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

**File:** `src/aging_bd_agentic_system/graph/state.py`

**Required fields:**
- `hallmark_name: str`
- `config: Dict[str, Any]` — Configuration traveling through workflow
- `tool_call_history: Annotated[list[dict], operator.add]`
- `reasoning_trace: Annotated[list[str], operator.add]`
- `warnings: Annotated[list[str], operator.add]`
- `lopez_otin_context: str`
- `context_summary: str | None`
- `token_count: int`
- `research_scratchpad: str`
- `phase1_plan: Dict[str, Any]` — Contains research_goals with search terms
- `phase1_iteration: int`
- `phase1_critique: Optional[str]` — Unstructured critique text
- `phase1_critic_recommendations: Optional[Dict[str, Any]]` — Structured recommendations
- `biological_processes: List[Dict[str, Any]]`
- `bp_queue: List[str]`
- `current_bp_index: int`
- `current_bp_name: str`
- `phase2_critic_iteration: int` (for refine loop)
- `phase2_research_iteration: int` (for ReAct research loop)
- `phase2_eval: Dict[str, Any]`
- `genes_found: Annotated[List[Dict[str, Any]], operator.add]`
- `go_terms_found: Annotated[List[Dict[str, Any]], operator.add]`

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

- [x] Workflow graph verified (all nodes present)
- [x] State schema verified (all fields present including `config`)
- [x] Configuration travels through `state["config"]`
- [x] End-to-end test completes without crashing
- [x] Output files generated (3 TSV files)
- [x] Trace file generated with LLM and node events
- [x] Validation runs (issues logged but not fatal)
- [x] Outputs written to `outputs/{hallmark}/`
- [x] Full state written to `outputs/{hallmark}/full_state.json`

---

## Final Verification Command

**One-command test:**

```bash
# Run hallmark
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"

# Check outputs
echo "=== Process Count ==="
wc -l outputs/epigenetic_alterations/biological_processes.tsv

echo "=== Gene Count ==="
wc -l outputs/epigenetic_alterations/curated_genes.tsv

echo "=== GO Term Count ==="
wc -l outputs/epigenetic_alterations/curated_go_terms.tsv

# Check logs
echo "=== Log Files ==="
ls -la logs/epigenetic_alterations/
```

---

## What If Something Doesn't Work?

**Strategy:**
1. Check trace file for error events: `logs/{hallmark}/trace_*.jsonl`
2. Check audit log: `logs/{hallmark}/audit.jsonl`
3. Check full state: `outputs/{hallmark}/full_state.json`
4. Test components individually:
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
