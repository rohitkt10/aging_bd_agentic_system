# Phase 1 — Foundations (Already Done)

**Status:** Done

This phase documents what is already implemented so later phases do not rework it.
Use this as a verification checklist rather than a to‑do list.

---

## 1) Literature Pipeline (Implemented)

**Location:** `src/aging_bd_agentic_system/literature_pipeline/`

### Files + Responsibilities
- **ingestion.py**: PubMed → PMCID → PMC XML downloads (input validation, retry handling).
- **chunking.py**: XML → structured sections → `chunks.jsonl`.
- **embedding.py**: SentenceTransformer embeddings (consistent model + device).
- **indexing.py**: embeddings → FAISS + `lookup.jsonl` + `index.meta.json`.
- **config.py**: paths, corpus limits, model settings, index params.

### Expected Outputs
- `data/corpus/raw/` — PMC XML
- `data/corpus/chunks/` — chunk JSONL
- `data/corpus/index/` — FAISS index + metadata

### Done When
- Scripts run end‑to‑end and create outputs above.
- Index is queryable via `query_vector_db`.
- Errors are surfaced clearly (no silent failures).

### Verification Steps
- Run `python scripts/fetch_pmc.py --n 10`.
- Run `python scripts/build_chunks.py`.
- Run `python scripts/build_index.py`.
- Confirm `data/corpus/index/lookup.jsonl` exists and is non‑empty.

---

## 2) Tools (Implemented)

**Location:** `src/aging_bd_agentic_system/tools/`

### Required Tools
- `query_vector_db` (FAISS corpus search)
- `query_pubmed` (PubMed API query)
- `query_genage` (GenAge CSV search)
- `query_opengenes` (OpenGenes database search)
- `query_go_terms` (GO term lookup)

### Required Behaviors
- Validate inputs (non‑empty query, positive limits).
- Return structured dicts with required keys.
- Surface errors via exceptions (no silent failure).

### Done When
- Tools are importable from `aging_bd_agentic_system.tools`.
- Tool tests pass (success + invalid args).

---

## 3) Data Assets (Implemented)

**Paths:**
- `data/lopez-otin-22.md`
- `data/go-basic.json`
- `data/databases/genage_human.csv`
- `data/databases/opengenes.db`

### Done When
- Files exist and are readable by tools/utilities.
- Any format assumptions are codified in tool modules.
- A missing file causes a clear error message.

---

## 4) State Schema (Implemented)

**Location:** `src/aging_bd_agentic_system/graph/state.py`

### Required Fields (Base)
- hallmark input
- tool call history
- Phase 1 outputs (BP list)
- Phase 2 progress (current BP index/name)
- Phase 2 outputs (genes + GO terms)
- working memory (scratchpad, context summary)

### Done When
- TypedDict fields exist and match plan docs.
- Reducer fields use `Annotated[..., operator.add]`.

---

## 5) Scripts + Tests (Implemented)

**Scripts:** `scripts/`
- `fetch_pmc.py`, `build_chunks.py`, `build_index.py`

**Tests:** `tests/`
- `test_vector_db.py`, `test_pubmed.py`, `test_genage.py`, `test_opengenes.py`, `test_go_terms.py`

### Done When
- `make test` passes in the repo environment.
- Tests cover success + invalid input handling.
- PubMed tests are gated on `NCBI_EMAIL`.

---

## Phase 1 Exit Criteria

- Literature pipeline produces a queryable FAISS index.
- All tool tests pass.
- Data assets are present and correctly referenced.
- State schema provides the base fields used by Phase 2.
