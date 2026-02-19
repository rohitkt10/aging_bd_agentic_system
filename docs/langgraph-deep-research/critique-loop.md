# Critique & Refinement Loop

Deep research requires explicit quality gates. This is the core concept borrowed from ADK’s deep-search: **research → critique → refine**.

## Phase 1 Critique (Biological Processes)

### Input
- Draft list of BPs + evidence summaries

### Output (Critic)
```json
{
  "grade": "pass" | "fail",
  "comment": "why",
  "missing": ["missing aspect 1", "missing aspect 2"],
  "follow_up_queries": ["search query 1", "query 2"]
}
```

### Pass Criteria
- 10–15 distinct processes
- Each has evidence from Lopez-Otin + at least one external source
- No overlapping or duplicate processes

## Phase 2 Critique (Genes)

### Input
- Current BP’s gene set and evidence

### Output (Critic)
```json
{
  "grade": "pass" | "fail",
  "comment": "why",
  "missing": ["missing mechanism", "insufficient evidence"],
  "follow_up_queries": ["gene X aging evidence", "BP Y related gene"]
}
```

### Pass Criteria
- BP has sufficient gene coverage
- Scores are justified by multiple sources
- Evidence summaries include citations

## Implementation Details

### Critic Node

Use an LLM prompt with strict JSON output. Store result in `phase1_eval` or `phase2_eval`.

### Refinement Node

If the critic returns `follow_up_queries`, execute them with:

- `query_pubmed`
- `query_vector_db`

Then merge evidence into the scratchpad and regenerate outputs.

### Loop Budget

Set max iterations to avoid infinite loops (e.g., `max_iter = 3`).

### Deterministic Stop

Use explicit routing based on `grade` + iteration count. Do not rely on free-form model output to stop the loop.
