# Deep-Research Implementation Plan (Fully Self-Contained)

These plan files are the **authoritative implementation guides** for the deep-research
system. A new engineer should be able to implement the full pipeline from these docs
alone, without needing external context.

## Read Order (Required)

1. **Phase 1 — Foundations** → [`impl_phase_1.md`](./impl_phase_1.md)
2. **Phase 2 — Deep-Research Orchestration** → [`impl_phase_2.md`](./impl_phase_2.md)
3. **Phase 3 — Outputs + Quality Gates** → [`impl_phase_3.md`](./impl_phase_3.md)
4. **Phase 4 — Stability + Traceability** → [`impl_phase_4.md`](./impl_phase_4.md)

## Phase Dependencies

- **Phase 1** provides the data pipeline + tools that Phase 2 will call.
- **Phase 2** builds the LangGraph workflow, which Phase 3 assumes can run end-to-end.
- **Phase 3** adds deterministic outputs and validation gates for Phase 2 results.
- **Phase 4** adds audit logging, runbook, and optional smoke testing for stability.

If you skip earlier phases, later phases will not function.

## MVP Definition (Non-Negotiable)

MVP is achieved when **all** of the following are true:

1. The LangGraph workflow runs end-to-end for **one hallmark**.
2. Outputs are written to disk:
   - `outputs/{hallmark}/processes.tsv`
   - `outputs/{hallmark}/genes.tsv`
   - `outputs/{hallmark}/go_terms.tsv`
3. Phase 1 and Phase 2 both have **explicit** research → critique → refine loops.
4. Tool calls + reasoning are logged to `logs/agent_traces/`.
5. Validation runs and reports issues without crashing the run.

## Expected Artifacts by Phase

### Phase 1 Artifacts
- Literature pipeline scripts and configs (ingestion → chunking → embedding → indexing).
- Tools for vector DB, PubMed, GenAge, OpenGenes, GO terms.
- Data assets in `data/` and `data/databases/`.
- Tests validating tool behavior.

### Phase 2 Artifacts
- `agents/phase1_bp_identifier.py`
- `agents/phase2_gene_researcher.py`
- `prompts/phase1.py`, `prompts/phase2.py`
- `graph/workflow.py`
- `main.py` entry point

### Phase 3 Artifacts
- `utils/validation.py`
- `utils/aggregation.py`
- `utils/context_manager.py`
- Deterministic TSV writers for `processes.tsv`, `genes.tsv`, `go_terms.tsv`

### Phase 4 Artifacts
- `utils/audit_logger.py`
- `docs/RUNBOOK.md`
- `tests/test_workflow_smoke.py` (optional)

## Conventions

- **Pure node functions:** state in → partial update out.
- **Deterministic routing:** no free-form LLM control flow.
- **Explicit data contracts:** every output has a schema.
- **Auditability:** every tool call is logged.
- **Non-fatal validation:** validation reports issues but does not abort.

## Scope Guardrails

- These plans are about **implementation**, not model tuning.
- Do **not** modify tool interfaces unless required by tests.
- Do **not** add new external dependencies without updating `pyproject.toml`.
