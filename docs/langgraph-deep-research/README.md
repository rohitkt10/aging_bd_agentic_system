# LangGraph Deep-Research Orchestration (Project-Specific Guide)

This documentation explains how to replicate a **Deep-Search-style research workflow** using **LangGraph** in *this project* (no ADK). It is tailored to the two-phase design described in `docs/PRD.md` and the current tooling under `src/aging_bd_agentic_system/tools/`.

## Read Order

1. **Architecture Overview** → [`architecture.md`](./architecture.md)
2. **State Schema & Data Contracts** → [`state-schema.md`](./state-schema.md)
3. **Node-by-Node Orchestration** → [`node-orchestration.md`](./node-orchestration.md)
4. **Critique & Refinement Loop** → [`critique-loop.md`](./critique-loop.md)
5. **Tool Integration Patterns** → [`tools-integration.md`](./tools-integration.md)
6. **Context Management & Summarization** → [`context-management.md`](./context-management.md)
7. **Logging, Tracing, and Audit Trail** → [`logging-tracing.md`](./logging-tracing.md)
8. **Execution Runbook** → [`execution-runbook.md`](./execution-runbook.md)
9. **Gap Analysis & Implementation Checklist** → [`gap-analysis.md`](./gap-analysis.md)

## Scope

- Uses **LangGraph** as the orchestrator.
- Builds around **Phase 1** (Biological Process Identification) and **Phase 2** (Gene Research ReAct loop).
- Integrates **existing tools**: `query_vector_db`, `query_pubmed`, `query_genage`, `query_opengenes`, `query_go_terms`.
- Provides concrete node designs, routing rules, and data contracts for a production-grade workflow.

## Source Context

- **PRD**: `docs/PRD.md`
- **Current state schema**: `src/aging_bd_agentic_system/graph/state.py`
- **Tools**: `src/aging_bd_agentic_system/tools/`
- **Literature pipeline**: `src/aging_bd_agentic_system/literature_pipeline/`

If you implement the workflow exactly as described, you will have a LangGraph pipeline that mirrors the deep-research orchestration used in ADK’s deep-search sample, but entirely within this repo’s stack.
