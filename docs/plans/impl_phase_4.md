# Phase 4 — Stability + Runbook + Traceability (Detailed)

**Goal:** Make the system repeatable, debuggable, and fully auditable. This phase adds logging, runbook, and (optional) smoke testing.

---

## 4.0 Scope and Responsibilities

Phase 4 is responsible for:

1. **Audit logging** of tool calls, critic results, and loop iterations.
2. **Operational runbook** for setup and execution.
3. **Optional smoke test** to validate minimal end‑to‑end flow.

Non‑goals:
- Do not change model prompts or research logic.
- Do not add new external dependencies without updating `pyproject.toml`.

---

## 4.1 Logging & Audit Trail (Implement in Code)

### 4.1.1 File: `utils/audit_logger.py`

```python
import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs/agent_traces")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def log_event(record: dict) -> None:
    record["timestamp"] = datetime.now().isoformat(timespec="seconds")
    path = LOG_DIR / f"{record.get('hallmark','run')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

### 4.1.2 Required Record Shapes

**Tool call record:**
```json
{
  "hallmark": "epigenetic alterations",
  "phase": "phase1",
  "bp": "DNA methylation changes",
  "node": "phase1_research",
  "tool": "query_pubmed",
  "args": {"query": "DNA methylation changes aging", "retmax": 5},
  "result_count": 5
}
```

**Critique record:**
```json
{
  "hallmark": "epigenetic alterations",
  "phase": "phase2",
  "bp": "chromatin remodeling",
  "node": "phase2_critic",
  "grade": "fail",
  "follow_up_queries": ["chromatin remodeling aging genes"],
  "comment": "insufficient gene coverage"
}
```

**Iteration boundary record:**
```json
{
  "hallmark": "epigenetic alterations",
  "phase": "phase2",
  "bp": "chromatin remodeling",
  "node": "iteration_end",
  "iteration": 2
}
```

### 4.1.3 Usage Requirements

- Log **every tool call** (name, args, result_count).
- Log **every critic output** (grade + follow‑up queries + comment).
- Log **each loop iteration** start/end.
- Use consistent `phase` values: `phase1` or `phase2`.

---

## 4.2 Integrate Logging into Nodes

### Phase 1 Nodes
- `phase1_research`: log each `query_vector_db` and `query_pubmed` call.
- `phase1_critic`: log critic JSON.
- `phase1_refine`: log follow‑up tool calls.

### Phase 2 Nodes
- `phase2_research`: log per‑gene tool calls.
- `phase2_critic`: log critic JSON.
- `phase2_refine`: log follow‑up tool calls.
- `map_go_terms`: log GO term count and query.

**Note:** Logging is additive and should not mutate business logic.

---

## 4.3 Runbook (Implement as `docs/RUNBOOK.md`)

Runbook must include:

1. **Environment setup**
   - `make sync`
   - Required env vars: `NCBI_EMAIL`, optional `NCBI_API_KEY`

2. **Corpus build steps**
   - `python scripts/fetch_pmc.py --n 500`
   - `python scripts/build_chunks.py`
   - `python scripts/build_index.py`

3. **Running a hallmark**
   - `python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"`

4. **Output locations**
   - `outputs/{hallmark}/processes.tsv`
   - `outputs/{hallmark}/genes.tsv`
   - `outputs/{hallmark}/go_terms.tsv`

5. **Log locations**
   - `logs/agent_traces/{hallmark}.jsonl`

6. **Troubleshooting**
   - Missing PubMed env vars
   - Empty vector DB index
   - Validation failures (non‑fatal)

---

## 4.4 Optional Smoke Test

**File:** `tests/test_workflow_smoke.py`

**Purpose:** Verify that Phase 1 can run with tiny limits and produces a non‑empty BP list.

**Guidance:**
- Limit calls: `top_k=2`, `retmax=2`.
- Skip test if `NCBI_EMAIL` is not set.
- Assert `biological_processes` length > 0.
- Do not require external LLM calls in smoke test.

---

## 4.5 Acceptance Criteria

- Logs are produced in `logs/agent_traces/` with expected record shapes.
- Runbook exists and enables a new engineer to execute the workflow.
- Smoke test passes (if enabled).
