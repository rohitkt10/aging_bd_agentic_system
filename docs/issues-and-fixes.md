# Issues & Fixes

## Issue 1: Observability/Logging

**Current State:** Manual `log_event()` calls throughout nodes → inconsistent, requires maintenance

**Solution:** Replace with LangGraph callback-based tracing (automatic, local-only)

**Implementation:** Create `utils/tracing.py` with custom callback handler, remove manual logging from nodes, integrate in `main.py`

## Issue 2: No LLM Integration

**Current State:** Agents use only deterministic logic (keyword extraction, hit counting); prompts exist but aren't called by LLMs. No LLM dependencies in `pyproject.toml`. No LLM config in `.env`.

**Solution:**
- Create modular LLM provider interface (`llm/providers.py`)
- Implement Vertex AI Gemini provider (`llm/vertex_gemini.py`)
- Create LLM client wrapper (`llm/client.py`)
- Add dependencies to `pyproject.toml`: `langchain-core`, `google-cloud-aiplatform`
- Add LLM config to `.env`: `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_MODEL`
- Add iteration config to `.env`: `PHASE1_MAX_ITERATIONS`, `PHASE2_RESEARCH_MAX_ITERATIONS`, `PHASE2_REFINE_MAX_ITERATIONS`
- Rewrite agents to use LLMs (replace deterministic logic)
- Phase 2: Implement autonomous ReAct research loop (exploration → exploitation)

**Implementation:** New `llm/` module with provider abstraction; update `pyproject.toml` and `.env`; rewrite agent nodes to use LLMs; implement ReAct loop for Phase 2 research
