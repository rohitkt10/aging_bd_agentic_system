# Context Management Lessons

## Problem Diagnosis

The current `research_findings` list + `summarize_if_needed` pattern has three failure modes:

1. **Temporal Bias:** Early high-value evidence gets summarized/truncated as context fills, while recent low-value evidence dominates the active prompt.
2. **Disconnected Facts:** Findings about the same gene from iterations 1 and 5 are not synthesized. LLM must resolve them zero-shot during final scoring, increasing hallucination risk.
3. **Token Wastage:** Dead-end searches consume tokens without contributing to synthesis.

## Solution Analysis

| Pattern | Verdict | Reasoning |
|---------|---------|-----------|
| 3.1 Semantic Memory | ✅ Recommended | Uses existing FAISS, retrieves by relevance not chronology, minimal code change |
| 3.2 Knowledge Graphs | ❌ Skip | Entity normalization is hard, schema complexity, diminishing returns for gene list output |
| 3.3 Hierarchical Memory | ⚠️ Already exists | Per-BP state already implements this pattern |
| 3.4 Reflective Memory | ⚠️ Over-engineered | CRUD tools add LLM complexity and failure points |

## Recommended Approach: Hybrid 3.1 + 3.4 Lite

Combine structured state (from 3.4) with semantic retrieval (from 3.1), but skip the CRUD tool complexity.

### Data Structure

```python
# Instead of flat list:
research_findings = [finding1, finding2, finding3, ...]

# Use gene-centric dict:
evidence_state = {
    "TP53": {"score": 0.8, "evidence": "...", "sources": [...]},
    "mTOR": {"score": 0.6, "evidence": "...", "sources": [...]},
}

# Plus ephemeral vector store for raw findings:
finding_store.add(Document(text=new_finding, metadata={"gene": gene, "source": source}))
```

### How It Works

1. **Raw findings** → ephemeral per-BP vector store (for semantic retrieval)
2. **Structured state** → `evidence_state` dict updated by LLM in structured output (not via CRUD tools)
3. **At decision time** → inject both: current `evidence_state` + top-k relevant raw findings

### What We Skip

- No CRUD tools (`upsert_gene_evidence`, `flag_contradiction`, etc.)
- No separate mutation step
- No knowledge graph / entity normalization
- Keep `research_findings` list for audit trail (dual-write is cheap)

## Implementation Notes

- Per-BP ephemeral FAISS store for findings retrieval
- LLM returns `evidence_state` updates as part of structured output
- At loop end, `evidence_state` IS the output - no separate scoring phase needed

## Key Insight

You don't need CRUD *tools* to have a mutable state. The LLM can update state directly in its structured response. This is "Reflective Memory Lite" - structured state without the tool complexity.
