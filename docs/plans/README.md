# Implementation Plan: LLM-Powered Deep Research System

**Status:** ✅ Complete. All phases implemented.

## Implementation Summary

### What's Locked (Do Not Touch)
- ✅ Literature pipeline (`src/aging_bd_agentic_system/literature_pipeline/`)
- ✅ FAISS index and chunks in `data/corpus/`
- ✅ All 5 tools (`src/aging_bd_agentic_system/tools/`)
- ✅ Data files in `data/` (databases, Lopez-Otin paper, GO terms)

### What Was Built
- ✅ **LLM Integration** — Vertex AI Gemini with modular provider abstraction
- ✅ **Configuration System** — `RunConfig` dataclass with YAML + CLI hierarchy
- ✅ **Agents** — LLM-powered reasoning with two-step critic pattern
- ✅ **Graph/Workflow** — LangGraph-based Phase 1 → Phase 2 pipeline
- ✅ **Observability** — Callback-based tracing + audit logging

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

## Read Order

1. **Phase 1 — LLM Foundation** → [`impl_phase_1.md`](./impl_phase_1.md)
2. **Phase 2 — Agent Intelligence** → [`impl_phase_2.md`](./impl_phase_2.md)
3. **Phase 3 — Observability** → [`impl_phase_3.md`](./impl_phase_3.md)
4. **Phase 4 — Integration & Validation** → [`impl_phase_4.md`](./impl_phase_4.md)

## Quick Start

```bash
# Run with defaults
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"

# Run with custom config
python -m aging_bd_agentic_system.main --hallmark "..." --config config/fast.yaml

# Run with CLI overrides
python -m aging_bd_agentic_system.main --hallmark "..." --max-research-iterations 5
```

## Output Locations

- **Outputs:** `outputs/{hallmark}/` (TSV files, full_state.json)
- **Traces:** `logs/{hallmark}/` (trace files, audit.jsonl)
