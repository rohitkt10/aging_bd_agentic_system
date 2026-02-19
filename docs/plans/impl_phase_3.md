# Phase 3 — Outputs + Quality Gates (Detailed Implementation)

**Goal:** Convert raw graph state into deterministic, validated outputs and enforce PRD constraints. This phase makes results reproducible, auditable, and consumable downstream.

---

## 3.0 Scope and Responsibilities

Phase 3 is responsible for:

1. **Aggregation:** Deduplicate and sort gene and GO-term outputs deterministically.
2. **Validation:** Enforce PRD constraints and report issues without crashing.
3. **Context control:** Summarize state when exceeding token budgets.
4. **Output writing:** Persist canonical TSV artifacts.

Non‑goals:
- Do not alter Phase 1/2 research logic.
- Do not change tool interfaces.
- Do not add new dependencies without updating `pyproject.toml`.

---

## 3.1 Files to Create

```
src/aging_bd_agentic_system/utils/validation.py
src/aging_bd_agentic_system/utils/aggregation.py
src/aging_bd_agentic_system/utils/context_manager.py
```

If `main.py` already writes outputs, update it to call these utilities.

---

## 3.2 Validation Module — `utils/validation.py`

### 3.2.1 Function: `validate_phase1(biological_processes) -> dict`

**Input contract:** list of dicts with keys:
- `rank: int`
- `process_name: str`
- `evidence_score: int`
- `evidence_summary: str`
- `sources: list[str]`

**Checks:**
- Count in [10, 15]
- Each entry has all required keys
- `evidence_score` is int in [1, 10]
- `sources` length >= 1
- `evidence_summary` is non‑empty
- `process_name` is non‑empty

**Return:**
```python
{"passed": bool, "issues": list[str]}
```

**Issue examples:**
- `"expected 10–15 processes, got 7"`
- `"process[3] missing sources"`
- `"process[4] evidence_score not in 1–10"`

---

### 3.2.2 Function: `validate_phase2(genes, go_terms) -> dict`

**Input contracts:**
- **genes** entries require:
  - `gene_symbol: str`
  - `score: int`
  - `biological_process: str`
  - `evidence_summary: str`
  - `sources: list[str]`
- **go_terms** entries require:
  - `go_id: str`
  - `go_label: str`
  - `definition: str`
  - `biological_process: str | list[str]`

**Checks (genes):**
- 300–500 genes (overall total)
- `score` in [1, 10]
- `evidence_summary` not empty
- `sources` length >= 1

**Checks (GO terms):**
- 50–80 GO terms (overall total)
- `go_id` starts with `GO:`
- `go_label` and `definition` non‑empty

**Return:**
```python
{"passed": bool, "issues": list[str]}
```

---

### 3.2.3 Function: `validate_all(bps, genes, go_terms) -> dict`

- Calls `validate_phase1` and `validate_phase2`.
- Returns a single dict with `passed` and a **flattened** `issues` list.
- `passed` is true only if both validators pass.

**Non‑fatal requirement:**
- Validation **must not** crash the run; issues are logged and outputs still written.

**Pseudo‑implementation:**
```python
issues = []
issues += validate_phase1(bps)["issues"]
issues += validate_phase2(genes, go_terms)["issues"]
return {"passed": len(issues) == 0, "issues": issues}
```

---

## 3.3 Aggregation Module — `utils/aggregation.py`

### 3.3.1 Function: `dedupe_genes(genes) -> list`

**Rules:**
- Deduplicate by `gene_symbol`.
- Keep entry with highest `score`.
- If scores equal, keep the entry with the longer `evidence_summary`.
- Preserve the `biological_process` of the retained entry (do not merge BPs here).

**Rationale:**
- The evidence score is the primary ranking signal.
- Longer summary usually contains more citations.

---

### 3.3.2 Function: `merge_go_terms(go_terms) -> list`

**Rules:**
- Deduplicate by `go_id`.
- Preserve all `biological_process` values in a list if term repeats.
- Keep the longest `definition` when merging duplicates.

**Example merge:**
```python
{
  "go_id": "GO:0006915",
  "go_label": "apoptotic process",
  "definition": "...",
  "biological_process": ["DNA damage", "cell death"]
}
```

---

### 3.3.3 Function: `sort_genes(genes) -> list`

- Sort by `score` desc, then `gene_symbol` asc.
- Sorting must be stable to keep deterministic ordering.

---

### 3.3.4 Function: `aggregate_outputs(genes, go_terms) -> tuple`

- Returns `(genes_deduped_sorted, go_terms_deduped)`.
- Apply `dedupe_genes` → `sort_genes` for genes.
- Apply `merge_go_terms` for GO terms.

---

## 3.4 Context Manager — `utils/context_manager.py`

### 3.4.1 Function: `estimate_tokens(text) -> int`
- Approximate: `len(text.split())`.

### 3.4.2 Function: `summarize_if_needed(state, max_tokens=50000) -> dict`

**Steps:**
1. Build a single text blob from:
   - `tool_call_history`
   - `reasoning_trace`
   - `research_scratchpad`
2. Estimate tokens.
3. If tokens <= max_tokens, return `{}`.
4. Else summarize via LLM (short summary of evidence + decisions).
5. Return:
```python
{
  "context_summary": summary,
  "tool_call_history": [],
  "reasoning_trace": [],
  "research_scratchpad": ""
}
```

**Persistence requirement:**
- Raw tool evidence must still be persisted in log files (Phase 4), even if removed from state.

**Trigger points (recommended):**
- After each Phase 2 BP loop.
- After each critique/refine cycle.
- Before final aggregation.

---

## 3.5 Output Writers (Add to `main.py` or new `utils/output_writer.py`)

### 3.5.1 Processes TSV

**File:** `outputs/{hallmark}/processes.tsv`
**Columns (tab‑separated):**
```
rankprocess_nameevidence_scoreevidence_summarysources
```

**Rules:**
- `rank` is 1‑indexed after sorting by evidence score.
- `sources` serialized as `;`‑joined strings.
- Always write header row.

---

### 3.5.2 Genes TSV

**File:** `outputs/{hallmark}/genes.tsv`
**Columns (tab‑separated):**
```
rankgene_symbolscorebiological_processevidence_summarysources
```

**Rules:**
- `rank` assigned after sorting/deduping.
- `biological_process` is the BP label used when the gene was scored.
- `sources` serialized as `;`‑joined strings.

---

### 3.5.3 GO Terms TSV

**File:** `outputs/{hallmark}/go_terms.tsv`
**Columns (tab‑separated):**
```
go_idgo_labelbiological_processdefinitionsources
```

**Rules:**
- If `biological_process` is a list, serialize with `;`.
- `sources` serialized as `;`‑joined strings.

---

### 3.5.4 Writer Utilities (Optional)

If output writing becomes large, add helpers:
- `ensure_output_dir(hallmark_name)`
- `serialize_sources(sources: list[str]) -> str`
- `write_tsv(path, header, rows)`

---

## 3.6 Wire Validation into Workflow

After graph execution:
1. Call `aggregate_outputs(genes_found, go_terms_found)`.
2. Run `validate_all(bps, genes, go_terms)`.
3. If `passed == False`, log issues and still write outputs.

**Ordering matters:**
- Always aggregate before validating and writing to ensure deterministic outputs.

---

## 3.7 Edge Cases and Handling

- **Empty outputs:** validation should report a clear issue and still write TSV headers.
- **Duplicate genes across BPs:** dedupe retains highest score.
- **Duplicate GO terms across BPs:** merge with BP list.
- **Invalid scores:** report in validation, do not coerce silently.

---

## 3.8 Acceptance Criteria

- TSV outputs are generated for one hallmark.
- Validation reports are produced and logged.
- Aggregation + dedupe are deterministic.
- Output schema matches PRD requirements.
