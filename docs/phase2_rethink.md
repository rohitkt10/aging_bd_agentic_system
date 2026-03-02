# Phase 2 Rethink

## Current Status

Phase 2 works as expected up to iteration 0 (seed generation).

## Problem Statement

Context grows quickly during research iterations. Each iteration conducts multiple searches across:
- Vector DB (local corpus)
- PubMed (online literature)
- OpenGenes (gene database)

Managing this context is the central challenge. Raw findings accumulate and trigger context summarization, but current approaches are inefficient.

## Goals

### High-Level Workflow Goal
Mirror real scientific research: exploration early, exploitation later. Synthesize knowledge progressively. 2-3 rounds of feedback/refinement suffice (like manuscript review).

### Core Task
Curate gene lists that map to hallmarks of aging to further mechanistic understanding of molecular changes during aging.

### Design Principle
The LLM should always be biased toward gene discovery and validation. Every decision should answer: *"Does this help us identify or validate genes for this biological process?"*

---

## Proposed Architecture

### Key Insight: Separate Concerns

| Component | Purpose | Mutability | Token Impact |
|-----------|---------|------------|--------------|
| **Scratchpad** | Audit trail, raw findings | Append-only, never read by LLM | None (not in context) |
| **State of Knowledge** | Working memory for LLM | Rewritten each iteration | Bounded (compressed) |

The scratchpad logs everything for audit. The state of knowledge is continually compressed and propagated forward—shedding redundancy at each step.

### State of Knowledge Schema

```python
{
    "candidate_genes": ["TP53", "FOXO3", "SIRT1", ...],
    "citations": ["PMID:12345", "PMID:67890", "genage:WRN", ...],
    "summary": "2-3 paragraphs covering: what we know, key evidence, and what still needs investigation"
}
```

**Size target**: ~2000-2500 tokens regardless of iteration count.

---

## Workflow

### Iteration 0: Seeding (Already Works)

Generate seed genes from GenAge and OpenGenes. Produce initial `state_of_knowledge_0`.

### Iteration k (k >= 1): Research Loop

**Step 1: Synthesize (Free-form Invoke)**
- Input: `state_of_knowledge_{k-1}` + `candidate_genes`
- Output: Research priorities (free-form text)

**Step 2: Decide (Structured Invoke)**
- Input: Research priorities + `candidate_genes` + iteration context
- Output: Concrete tool calls (opengenes, pubmed, vector_db queries)

**Step 3: Execute Tool Calls**
- Run queries against all sources
- Log raw results to scratchpad (never read again by LLM)

**Step 4: Summarize Results**
- For each source, summarize: `{'summary': ..., 'genes': [...], 'sources': [...]}`
- **CRITICAL**: Preserve citations at every step

**Step 5: Synthesize New State**
- Input: `state_of_knowledge_{k-1}` + all source summaries
- Output: `state_of_knowledge_k` (compressed, rewritten)
- This is a **running summary**—each iteration builds on the previous, not independent

### Data Flow

```
Iteration k:

  state_of_knowledge_{k-1} ──┐
                              ├──> [Synthesize] ──> state_of_knowledge_k ──> Next iteration
  tool_results_k ────────────┘         │
                                        │
                                        └──> Also logged to scratchpad (audit only)
```

---

## Key Properties

1. **Context stays bounded**: Raw tool results never accumulate in LLM context
2. **Citations preserved**: Never lost across compressions
3. **Gene-centric**: `candidate_genes` list always visible to LLM
4. **Progressive refinement**: State of knowledge compounds, doesn't accumulate
5. **Full audit trail**: Scratchpad captures everything for post-hoc analysis
