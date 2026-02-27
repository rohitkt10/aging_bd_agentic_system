# Implementation Plan: LLM-Powered Deep Research System

**Status:** ✅ Phase 1 complete. Phase 2 smoke testing in progress.

## Implementation Summary

### What's Locked (Do Not Touch)
- ✅ Literature pipeline (`src/aging_bd_agentic_system/literature_pipeline/`)
- ✅ FAISS index and chunks in `data/corpus/`
- ✅ All 5 tools (`src/aging_bd_agentic_system/tools/`)
- ✅ Data files in `data/` (databases, Lopez-Otin paper, GO terms)

### What Was Built
- ✅ **LLM Integration** — Multi-provider support (Vertex AI Gemini, OpenAI GPT)
- ✅ **Configuration System** — `RunConfig` dataclass with defaults → YAML → CLI hierarchy
- ✅ **Agents** — LLM-powered reasoning with two-step critic pattern
- ✅ **Graph/Workflow** — LangGraph-based Phase 1 → Phase 2 pipeline
- ✅ **Observability** — Callback-based tracing + audit logging
- ✅ **Smoke Tests** — Phase 1 and Phase 2 independent smoke tests

## Architecture

```
main.py
  │
  ├─> RunConfig()                    # defaults
  ├─> RunConfig.from_yaml(path)      # YAML overrides
  ├─> config.merge_cli(**args)       # CLI overrides
  │
  └─> state["config"] = config.to_dict()
        │
        ▼
      LangGraph workflow
        │
        ├─> Phase 1: BP Identification
        │     └─> load_context → plan → research → critic → refine → finalize
        │
        └─> Phase 2: Gene Research (per BP)
              └─> select_bp → research (loop) → critic → refine → map_go → advance
```

## LLM Provider Support

The system supports multiple LLM providers:

| Provider | Models | Config Key |
|----------|--------|------------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo | `openai` |
| Vertex AI | gemini-2.0-flash-exp, gemini-2.5-pro | `vertex` |

Provider selection via config:
```yaml
llm:
  provider: openai  # or vertex
  model: gpt-4o
```

## Smoke Tests

Independent smoke tests for testing each phase:

```bash
# Phase 1 smoke test (BP discovery only)
python scripts/phase1_research_smoketest.py

# Phase 2 smoke test (uses saved Phase 1 data)
python scripts/phase2_research_smoketest.py --hallmark "genomic instability" --bp-index 0
```

## Read Order

1. **Phase 1 — LLM Foundation** → [`impl_phase_1.md`](./impl_phase_1.md)
2. **Phase 2 — Agent Intelligence** → [`impl_phase_2.md`](./impl_phase_2.md)
3. **Phase 3 — Observability** → [`impl_phase_3.md`](./impl_phase_3.md)
4. **Phase 4 — Integration & Validation** → [`impl_phase_4.md`](./impl_phase_4.md)

## Quick Start

```bash
# Run with defaults (uses OpenAI gpt-4o)
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"

# Run with custom config
python -m aging_bd_agentic_system.main --config config/test_config.yaml

# Run Phase 1 only
python -m aging_bd_agentic_system.main --hallmark "genomic instability" --phase1-only true
```

## Output Locations

- **Outputs:** `outputs/{hallmark}/` (TSV files, full_state.json)
- **Traces:** `logs/{hallmark}/` (trace files, audit.jsonl)

## Additional Documentation

- **Context Management Patterns:** [`../ctx_patterns/ctx_management_patterns.md`](../ctx_patterns/ctx_management_patterns.md)
- **Lessons Learned:** [`../ctx_patterns/lessons.md`](../ctx_patterns/lessons.md)
- **Phase 1 Audit Trail:** [`../phase1_audit_trail.md`](../phase1_audit_trail.md)

## Recent Improvements

- Added multi-provider LLM support (OpenAI, Vertex AI)
- Config printing to stdout before workflow starts
- Prettified stdout logging for research goals, critic, and refinement stages
- Fixed `--phase1-only` flag to properly respect YAML config
- Fixed Path type handling in output directory creation
- Added Phase 2 smoke test using saved Phase 1 data
- Created context management patterns documentation
