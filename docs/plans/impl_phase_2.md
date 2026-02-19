# Phase 2 — Deep-Research Orchestration (MVP Core)

**Goal:** Build the LangGraph deep‑research workflow with explicit **Plan → Research → Critique → Refine** loops for both Phase 1 and Phase 2. This phase defines files, node logic, routing, data contracts, logging hooks, and error handling in operational detail.

---

## 2.1 Files to Create

```
src/aging_bd_agentic_system/agents/phase1_bp_identifier.py
src/aging_bd_agentic_system/agents/phase2_gene_researcher.py
src/aging_bd_agentic_system/prompts/phase1.py
src/aging_bd_agentic_system/prompts/phase2.py
src/aging_bd_agentic_system/graph/workflow.py
src/aging_bd_agentic_system/main.py
```

---

## 2.2 Extend State Schema (Required)

Update `graph/state.py` to include all fields below (if missing):

```python
class ResearchState(TypedDict):
    hallmark_name: str

    # Audit
    tool_call_history: Annotated[list[dict[str, Any]], operator.add]
    reasoning_trace: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]

    # Context
    lopez_otin_context: str
    context_summary: str | None
    token_count: int
    research_scratchpad: str

    # Phase 1
    phase1_plan: list[str]
    phase1_iteration: int
    phase1_eval: dict[str, Any]
    biological_processes: list[dict[str, Any]]
    bp_queue: list[str]

    # Phase 2 control
    current_bp_index: int
    current_bp_name: str
    phase2_iteration: int
    phase2_eval: dict[str, Any]

    # Phase 2 outputs
    genes_found: Annotated[list[dict[str, Any]], operator.add]
    go_terms_found: Annotated[list[dict[str, Any]], operator.add]
```

### Reducer Fields (Must Use `operator.add`)
- `tool_call_history`, `reasoning_trace`, `genes_found`, `go_terms_found`.

### Initialization Requirements (in `main.py`)
- Lists: `[]`
- Counters: `0`
- Strings: `""`
- Optional summary: `None`
- Include `warnings: []` for non‑fatal tool errors.

---

## 2.3 Prompts (Explicit Requirements)

### `prompts/phase1.py`
**Purpose:** Generate Phase 1 research plan and critique JSON.

**Must include:**
1. Task definition (BP identification for hallmark).
2. Output schema for plan list (Python list, no prose).
3. Output schema for critique JSON.
4. Criteria: count range, evidence requirements, overlap detection, missing themes.

**Required outputs:**
- `phase1_plan`: list of 4–6 strings (goals).
- `phase1_eval` JSON:
  ```json
  {"grade":"pass|fail","comment":"...","follow_up_queries":["..."],"missing_themes":["..."]}
  ```

### `prompts/phase2.py`
**Purpose:** Gene evidence synthesis + critique JSON per BP.

**Must include:**
1. Task definition (gene evidence + GO terms for current BP).
2. Output schema for gene entries and critique JSON.
3. Criteria: minimum genes per BP, evidence completeness, citations.

**Required outputs:**
- Gene evidence fields: `gene_symbol`, `score`, `evidence_summary`, `sources`.
- `phase2_eval` JSON:
  ```json
  {"grade":"pass|fail","comment":"...","follow_up_queries":["..."],"min_genes_expected":20}
  ```

---

## 2.4 Phase 1 Agent — `agents/phase1_bp_identifier.py`

### Node A — `load_lopez_otin_context(state)`
**Inputs:** `hallmark_name`, `lopez_otin_context`
**Outputs:** `{ "lopez_otin_context": file_text }` (only if missing)
**Notes:** Read from `data/lopez-otin-22.md`.

### Node B — `phase1_plan(state)`
**Inputs:** `hallmark_name`, `lopez_otin_context`
**Outputs:** `{ "phase1_plan": goals }`
**Notes:** Use prompt from `prompts/phase1.py`; return only the list.

### Node C — `phase1_research(state)`
**Inputs:** `hallmark_name`, `phase1_plan`, `lopez_otin_context`
**Process:**
1. `query_vector_db(hallmark_name, top_k=10)`.
2. Extract candidate BPs by scanning chunk text for:
   `methylation`, `chromatin`, `repair`, `autophagy`, `senescence`, `mitochondrial`, `inflammation`.
3. Deduplicate; keep top 15–20 candidates.
4. For each BP: `query_pubmed(f"{bp} aging", retmax=5)`.
5. Score evidence:
   - 9–10 if Lopez‑Otin + ≥2 PubMed hits
   - 6–8 if ≥1 PubMed hit
   - 3–5 if corpus‑only
6. Build `evidence_summary` from titles/abstracts; include PMIDs.

**Output format:**
```python
{
  "biological_processes": [
    {
      "rank": 1,
      "process_name": "DNA methylation changes",
      "evidence_score": 9,
      "evidence_summary": "Lopez-Otin highlights methylation drift. PMID:123 shows epigenetic clocks.",
      "sources": ["Lopez-Otin", "PMID:123", "PMC456"]
    }
  ]
}
```

**Audit trail:** append a record per tool call:
```python
{
  "phase": "phase1",
  "node": "phase1_research",
  "tool": "query_pubmed",
  "args": {"query": "...", "retmax": 5},
  "result_count": 5
}
```

### Node D — `phase1_critic(state)`
**Inputs:** `biological_processes`
**Outputs:** `{ "phase1_eval": eval_json }`
**Fail if:**
- count <10 or >15
- missing sources or evidence summaries
- overlapping/duplicate processes

### Node E — `phase1_refine(state)`
**Inputs:** `phase1_eval.follow_up_queries`
**Process:**
- For each query: `query_vector_db(query, top_k=5)` and `query_pubmed(query, retmax=5)`.
- Merge new evidence into BP list.
- Increment `phase1_iteration`.

### Node F — `phase1_finalize(state)`
**Outputs:**
- Sort by `evidence_score` desc.
- Trim to 10–15.
- Create `bp_queue` from `process_name`.

---

## 2.5 Phase 2 Agent — `agents/phase2_gene_researcher.py`

### Node A — `select_bp(state)`
**Outputs:**
- Set `current_bp_name` from `bp_queue`.
- If `current_bp_index >= len(bp_queue)`, return `{}` and route to END.

### Node B — `seed_gene_candidates(state)`
**Process:**
- `query_genage(current_bp_name, max_results=50)`.
- `query_opengenes(current_bp_name, max_results=50)`.
- Extract `symbol` fields; dedupe.
- Store candidates in `research_scratchpad` (serialized list).

### Node C — `phase2_research(state)`
**Process:**
- For each candidate gene (limit ~30 per BP):
  - `query_pubmed(f"{gene} {current_bp_name} aging", retmax=3)`.
  - `query_vector_db(f"{gene} {current_bp_name} aging", top_k=3)`.
- Score evidence:
  - 8–10 if ≥2 sources
  - 5–7 if 1 source
  - <5 excluded
- Append entries to `genes_found` with sources/summary.

**Gene output schema:**
```python
{
  "gene_symbol": "TP53",
  "score": 8,
  "biological_process": "DNA damage response",
  "evidence_summary": "PMID:123 links TP53 to aging DNA repair decline.",
  "sources": ["PMID:123", "PMC456"]
}
```

### Node D — `phase2_critic(state)`
**Outputs:** `{ "phase2_eval": eval_json }`
**Fail if:** gene count < `min_genes_expected` or evidence missing.

### Node E — `phase2_refine(state)`
- Execute follow‑up queries and add candidates.
- Increment `phase2_iteration`.

### Node F — `map_go_terms(state)`
- `query_go_terms(current_bp_name, max_results=10)`.
- Produce entries with `go_id`, `go_label`, `definition`, `biological_process`.

### Node G — `advance_bp(state)`
- Increment `current_bp_index` and loop back to `select_bp`.

---

## 2.6 LangGraph Wiring — `graph/workflow.py`

### Phase 1 Subgraph
```
load_context → phase1_plan → phase1_research → phase1_critic
  → (phase1_refine → phase1_critic) loop
  → phase1_finalize
```
**Routing:**
```
if phase1_eval["grade"] == "fail" and phase1_iteration < 3:
    route to phase1_refine
else:
    route to phase1_finalize
```

### Phase 2 Subgraph
```
select_bp → seed_gene_candidates → phase2_research → phase2_critic
  → (phase2_refine → phase2_critic) loop
  → map_go_terms → advance_bp → select_bp
```
**Routing:**
```
if phase2_eval["grade"] == "fail" and phase2_iteration < 3:
    route to phase2_refine
else:
    route to map_go_terms
```

### Top‑Level Graph
```
phase1_subgraph → phase2_subgraph → END
```

---

## 2.7 Entry Point — `main.py`

- Parse `--hallmark` from CLI.
- Initialize state with empty lists and counters for all reducers.
- Call `graph.invoke(state)`.
- Persist outputs (Phase 3 defines writers).

---

## 2.8 Error Handling & Warnings

- Tool call failures append a warning to `warnings` and continue.
- Critique failures do not crash the run; they route to refine.
- Missing data assets raise a clear error before graph execution.

---

## Phase 2 Exit Criteria

- Phase 1: 10–15 BPs with evidence + sources.
- Phase 2: genes + GO terms produced for each BP.
- Critique/refine loops executed at least once.
- Tool calls recorded in `tool_call_history`.
