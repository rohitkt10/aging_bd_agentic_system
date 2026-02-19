# Architecture Overview (Deep Research with LangGraph)

This project’s goal is a **two-phase deep research workflow** that produces:

- 10–15 biological processes per hallmark
- 300–500 genes with evidence scores
- 50–80 GO biological process terms
- a full audit trail of evidence and tool calls

To achieve this, the LangGraph orchestration should mirror a deep-search pipeline with **planning, research, critique, refinement, and synthesis**. The core architecture is:

```
User Input (hallmark)
    ↓
Phase 1 Subgraph
  - Context load
  - Research plan
  - Evidence gathering
  - Critique/refine loop
  - BP list output
    ↓
Phase 2 Subgraph (per BP)
  - Candidate gene expansion
  - Evidence gathering loop
  - Critique/refine loop
  - GO term mapping
  - Aggregation + validation
    ↓
Final outputs + full audit trail
```

## Why This Mirrors Deep-Search

Deep-search-style systems are defined by **iterative refinement loops** with explicit quality gates. That pattern maps cleanly to LangGraph:

- **Planner node** → defines explicit research goals
- **Researcher node** → runs tools and collects evidence
- **Critic node** → evaluates gaps and requests follow-up
- **Refiner node** → executes follow-up searches
- **Composer node** → synthesizes final results

## Recommended Graph Topology

- **Top-level graph**: handles Phase 1, then loops Phase 2 over each BP.
- **Phase 1 subgraph**: single hallmark → BPs list.
- **Phase 2 subgraph**: loop over BPs, each with its own research loop and GO term mapping.

## Key Design Principles

1. **Explicit state contracts**: every node reads/writes a well-defined subset of state.
2. **Deterministic routing**: loop continuations depend on evaluator outputs, not implicit model behavior.
3. **Tool grounding**: all outputs must include source evidence.
4. **Context budget control**: auto-summarize when token thresholds are exceeded.
5. **Auditability**: every tool call and reasoning step is logged.

## Phase 1 vs Phase 2 Roles

**Phase 1** (BP Identification):
- Goal: 10–15 processes with evidence scoring
- Tools: vector DB + PubMed
- Output: ranked BPs with evidence summaries

**Phase 2** (Gene Research):
- Goal: 300–500 genes + 50–80 GO terms
- Tools: GenAge, OpenGenes, PubMed, vector DB, GO terms
- Output: gene list and GO mappings with evidence

## Suggested Files (Implementation Targets)

- `src/aging_bd_agentic_system/agents/phase1_bp_identifier.py`
- `src/aging_bd_agentic_system/agents/phase2_gene_researcher.py`
- `src/aging_bd_agentic_system/graph/workflow.py`
- `src/aging_bd_agentic_system/utils/context_manager.py`
- `src/aging_bd_agentic_system/utils/validation.py`
- `src/aging_bd_agentic_system/utils/aggregation.py`

These files are referenced in existing docs but not yet present; this guide defines how they should work.
