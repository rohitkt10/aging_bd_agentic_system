# Phase 1 Research Context Optimization

**Date:** 2025-02-24
**Status:** Design decision - implementation pending

## Problem Statement

In `phase1_plan`, the LLM generates research goals with unconstrained search terms. In practice, this produces excessive terms per goal, leading to context explosion before the identification LLM call.

### Example (actual generated plan)

```
Goal 1: 11 vector_db_terms + 6 pubmed_terms = 17 queries
Goal 2: 7 vector_db_terms + 6 pubmed_terms = 13 queries
Goal 3: 7 vector_db_terms + 5 pubmed_terms = 12 queries
Total: 42 queries
```

With default limits (`vector_db_top_k=20`, `pubmed_retmax=10`):
- Vector DB: 25 × 20 = 500 results
- PubMed: 17 × 10 = 170 results
- **Total: ~670 results → 352,587 characters → ~88,000 tokens**

### Why This Is Problematic

1. **Low signal-to-noise ratio**: Each vector DB hit is a ~300 word chunk. The actual relevant information for biological process identification might be 2-3 sentences per chunk. The rest is methodology, background, hedging.

2. **Redundancy**: Overlapping searches ("DNA damage aging", "DNA repair aging", "double-strand break aging") return overlapping chunks from the same papers. The same fact may appear in 5+ chunks.

3. **Model attention degradation**: At 88k+ tokens, LLMs can lose information buried in long contexts, even with large context windows.

4. **Unpredictable behavior**: No bounds on search terms means context size varies wildly between runs.

---

## Approaches Considered

### Option 1: Constrain Search Terms

Add `minItems` and `maxItems` constraints to the schema (2-3 terms per goal per tool).

**Pros:**
- Simple implementation
- Bounded, predictable behavior
- Fewer queries = faster

**Cons:**
- Trades thoroughness for efficiency
- Relies on planner LLM to pick the "right" terms
- Critique loop must recover missed signal (recovery vs. refinement)

**Best for:** Real-time or latency-sensitive use cases

### Option 2: Summarize After Aggregation

Aggregate all results, then summarize corpus and PubMed sections separately.

**Pros:**
- Fewer LLM calls (2 summarizer calls)
- Can identify cross-cutting themes

**Cons:**
- Large summarization context (still 88k tokens)
- Loses connection between results and the goal that prompted them
- One goal with many results can dominate summarization

### Option 3: Per-Goal Summarization (CHOSEN)

Summarize corpus and PubMed results separately for each research goal, then aggregate.

**Pros:**
- Smaller chunks per summarizer call (~15k tokens vs ~90k)
- Goal context preserved (summarizer knows "these results are about DNA repair")
- Natural organization for identification LLM
- Each goal gets equal representation regardless of result count

**Cons:**
- More LLM calls (6 goals × 2 tools = 12 calls vs 2)
- More code complexity

**Why this is acceptable:**
- Batch HPC use case - latency irrelevant
- Total tokens processed is similar
- Summarizer calls are simple extraction tasks, low failure probability

---

## Chosen Design: Per-Goal Summarization with Inline Citations

### Architecture

```
for each research goal:
    1. Execute vector_db queries → raw corpus results
    2. Execute pubmed queries → raw pubmed results
    3. Summarize corpus results → corpus_summary (with inline citations)
    4. Summarize pubmed results → pubmed_summary (with inline citations)
    5. Store: {goal, corpus_summary, pubmed_summary}

Aggregate all goal summaries → formatted context for identification LLM
```

### Citation Format: Inline [PMID:xxx]

**Chosen format:**
```
[PMID:12345] TP53 activity decreases 40% in aged fibroblasts.
[PMID:67890] DNA repair efficiency declines with age due to reduced expression of repair enzymes.
```

**Why inline, not reference list:**
1. **Traceability preserved**: Each claim tied to its source. Identification LLM can cite accurately in output.
2. **Implicit fact-checking**: Summarizer can only make claims it can cite.
3. **No parsing needed**: Direct PMID extraction from summaries.
4. **Natural for LLMs**: Trained on academic text with citations.

**Rejected alternative - PMID list in schema:**
```json
{
  "summary": "TP53 shows reduced activity...",
  "pmids": ["PMID:12345", "PMID:67890", ...]
}
```
This loses the fact-source connection. Identification LLM cannot accurately cite - must guess or dump all PMIDs for every claim.

### Schema for Summarized Output

```python
GOAL_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "corpus_summary": {"type": "string"},
        "pubmed_summary": {"type": "string"},
    },
    "required": ["goal", "corpus_summary", "pubmed_summary"],
}
```

### Summarization Prompt Guidelines

The summarizer should be instructed to:
1. Extract only relevant biological process information
2. Include specific gene names, mechanisms, and experimental findings
3. Cite each claim with inline [PMID:xxx] or [Corpus:PMID:xxx]
4. Deduplicate redundant information across chunks
5. Preserve quantitative findings where available
6. Be conservative - include borderline-relevant information rather than risk missing signal

---

## Cost Analysis

| Approach | Input Tokens | Output Tokens | Notes |
|----------|-------------|---------------|-------|
| Direct (no summarization) | ~88k | ~2k | One massive call |
| Aggregate summarization | ~88k + ~10k | ~5k + ~2k | Two calls, second is smaller |
| Per-goal summarization | ~88k total across 12 calls + ~10k | ~12k total + ~2k | More calls, but each is small |

For batch processing, total cost is similar. Per-goal gives better quality for similar cost.

---

## Implementation Checklist

- [ ] Create `PHASE1_SUMMARY_PROMPT` in `llm/prompts.py`
- [ ] Create `GOAL_SUMMARY_SCHEMA` in `agents/phase1_bp_identifier.py`
- [ ] Add `_summarize_goal_results()` helper function
- [ ] Modify `phase1_research()` to call summarizer per goal
- [ ] Aggregate summarized outputs for identification LLM
- [ ] Test with actual hallmark run
- [ ] Verify citation extraction works correctly

---

## Future Considerations

1. **Hybrid approach**: If context is under threshold (e.g., 30k tokens), skip summarization. Only summarize when needed.

2. **Cross-goal synthesis**: After per-goal summarization, an optional synthesis step could identify cross-cutting themes. Probably unnecessary for current use case.

3. **Summarization quality metrics**: Log summarization compression ratio (input tokens / output tokens) to detect over-compression.

4. **Fallback on summarization failure**: If summarizer fails, fall back to truncated raw results rather than failing the entire run.

---

## Related Files

- `src/aging_bd_agentic_system/agents/phase1_bp_identifier.py` - Main implementation
- `src/aging_bd_agentic_system/llm/prompts.py` - Prompt templates
- `docs/plans/impl_phase_2.md` - Phase 1 agent documentation
