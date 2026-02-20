# Implementation Plan: LLM-Powered Deep Research System

**Status:** Literature pipeline and tools are complete. This plan focuses on building an autonomous intelligent research system.

## What's Locked (Do Not Touch)

✅ Literature pipeline (`src/aging_bd_agentic_system/literature_pipeline/`)
✅ FAISS index and chunks in `data/corpus/`
✅ All 5 tools (`src/aging_bd_agentic_system/tools/`) — may need later review
✅ Data files in `data/` (databases, Lopez-Otin paper, GO terms)

## What's Being Built (From Scratch or Refresh)

🔨 **LLM Integration** — Vertex AI Gemini with modular provider abstraction
🔨 **Agents** — LLM-powered reasoning (replace Copilot's deterministic logic)
🔨 **Graph/Workflow** — Verify or rebuild per `docs/langgraph-deep-research/` spec
🔨 **Observability** — LangGraph callback-based tracing
🔨 **Utils** — Verify validation, aggregation, output writers against spec

## Reference Architecture

See `/home/rohitpc/projects/aging_bd_agentic_system/docs/langgraph-deep-research/` for the ADK deep-research pattern we're replicating.

## Read Order

1. **Phase 1 — LLM Foundation** → [`impl_phase_1.md`](./impl_phase_1.md)
2. **Phase 2 — Agent Intelligence** → [`impl_phase_2.md`](./impl_phase_2.md)
3. **Phase 3 — Observability** → [`impl_phase_3.md`](./impl_phase_3.md)
4. **Phase 4 — Integration & Validation** → [`impl_phase_4.md`](./impl_phase_4.md)

## MVP Definition

MVP is achieved when:
1. LangGraph workflow runs end-to-end for one hallmark
2. Agents use LLMs for plan → research → critique → refine loops
3. Outputs match the sample prompt workflow (10-15 BPs, 300-500 genes, 50-80 GO terms)
4. All traces logged locally with timestamps
5. System produces results comparable to Gemini Deep Research web UI

## Phase Dependencies

- Phase 1 (LLM Foundation) → required by Phase 2
- Phase 2 (Agent Intelligence) → required by Phase 4
- Phase 3 (Observability) → independent, can parallelize
- Phase 4 (Integration) → depends on Phases 1-3
