# Phase 2 Critic-Refinement Refactor Specification

## Overview

This document specifies the refactor of the critic-refinement loop in Phase 2 gene research. The new design models the workflow after a scientific manuscript submission/review/rebuttal cycle.

## Scope and Constraints

### DO NOT TOUCH (Smoke-tested and working)

The following components are verified working and must not be modified:

1. **Phase 1: Biological Process Identification** - Entire workflow
2. **Phase 2 Seeding** - `phase2_seeding()` function
3. **Phase 2 Initial Research Loop** - `phase2_research()` function (iterations 1 through K)
4. **Gene scoring at end of research** - Initial scoring logic in `phase2_research()`
5. **Existing prompts for research** - All prompts in `phase2_prompts.py` related to research loop

### WHAT TO IMPLEMENT

1. New `phase2_critic()` function - Complete rewrite
2. New `phase2_refine()` function - Complete rewrite (handles finalization internally)
3. New prompts for critic and refinement agents
4. Updated graph workflow for critic-refine loop

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXISTING (DO NOT MODIFY)                         │
│                                                                          │
│   Phase 1: BP Identification                                            │
│        │                                                                 │
│        ▼                                                                 │
│   Phase 2: Seeding (iteration 0)                                        │
│        │                                                                 │
│        ▼                                                                 │
│   Phase 2: Research Loop (iterations 1 to K, default K=7)               │
│        │                                                                 │
│        ▼                                                                 │
│   Phase 2: Initial Gene Scoring                                         │
│        │                                                                 │
└────────┼─────────────────────────────────────────────────────────────────┘
         │
         │ Output: scored_genes[], gene_evidence{}, state_of_knowledge{}
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         NEW IMPLEMENTATION                               │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                  CRITIC-REFINE LOOP                               │  │
│   │                                                                   │  │
│   │   while critic_iteration < max_critic_iterations:                │  │
│   │       review = critic(draft)                                     │  │
│   │       if review.grade == "pass":                                 │  │
│   │           break  # done, no further work needed                  │  │
│   │       draft = refinement(draft, review)  # always finalizes      │  │
│   │       critic_iteration += 1                                      │  │
│   │                                                                   │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│   GO Term Mapping (isolated, skip for now but keep code)                │
│        │                                                                 │
│        ▼                                                                 │
│   advance_bp()                                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Orchestration Logic

```python
def run_critic_refine_loop(state: dict) -> dict:
    """
    Orchestration function for critic-refine loop.

    This function is called after initial research completes.
    It manages the iteration count and termination conditions.
    """
    max_critic_iterations = state.get("config", {}).get("phase2", {}).get("max_critic_iterations", 2)
    current_iteration = state.get("critic_iteration", 0)

    # no more work is allowed
    if current_iteration == max_critic_iterations:
        return state

    # do a review - phase2_critic returns state update with "critic_review" key
    state.update(phase2_critic(state))
    if state["critic_review"]["grade"] == "pass":
        return state  # no further action is required

    state.update(phase2_refine(state))
    state["critic_iteration"] = current_iteration + 1
    return state
```

---

## Contracts

### Critic Input Contract

```python
critic_input = {
    # Context
    "biological_process": str,      # Current BP being researched
    "hallmark_name": str,           # Parent aging hallmark

    # Draft to review (produced by research loop or refinement)
    "scored_genes": [               # List of scored genes
        {
            "gene_symbol": str,
            "score": int,           # 5-10
            "evidence_summary": str,
            "sources": list[str],   # e.g., ["opengenes", "pmid:12345"]
            "biological_process": str
        }
    ],
    "gene_evidence": dict,          # gene_symbol -> {evidence_notes, citations, opengenes, genage}
    "state_of_knowledge": dict,     # {candidate_genes, citations, summary}

    # Research context
    "research_scratchpad": str,     # JSON string of research data
}
```

### Critic Output Contract

```python
critic_output = {
    "grade": Literal["pass", "fail"],
    "review": {
        "summary": str,             # Overall assessment (2-3 sentences)
        "strengths": list[str],     # What's good about the draft
        "weaknesses": list[str],    # What's lacking or problematic
    },
    "recommendations": {
        "opengenes_queries": [
            {"query": str, "reason": str}
        ],
        "pubmed_queries": [
            {"query": str, "reason": str}
        ],
        "vector_db_queries": [
            {"query": str, "reason": str}
        ]
    }
}
```

### Refinement Input Contract

```python
refinement_input = {
    # Context
    "biological_process": str,
    "hallmark_name": str,

    # Current draft
    "scored_genes": list,
    "gene_evidence": dict,
    "state_of_knowledge": dict,

    # The review to address
    "critic_review": dict,          # Full critic output (as defined above)

    # Config for research tools
    "config": dict,
}
```

### Refinement Output Contract

```python
refinement_output = {
    "response_to_reviewer": str,    # Free-form narrative response

    "reviewer_feedback_addressed": [
        {
            "concern": str,         # What concern from the review
            "action_taken": str,    # What was done (or "rejected")
            "outcome": str          # Result of the action
        }
    ],

    "research_performed": [
        {
            "source": str,          # "opengenes" | "pubmed" | "vector_db"
            "query": str,
            "reason": str           # Why this query was made
        }
    ],

    "research_summary": str,        # Free-form synthesis of research findings

    # Updated draft (patches to state)
    "updated_scored_genes": list,   # Complete updated list
    "updated_gene_evidence": dict,  # Complete updated dict
    "updated_state_of_knowledge": dict,  # Complete updated dict
}
```

---

## Agent Behaviors

### Critic Agent

**Role**: Manuscript reviewer - detached quality assessment

**Mindset**:
- Review the draft objectively
- Assess quality, coverage, and evidence strength
- Provide actionable recommendations
- Give a pass/fail grade
- DO NOT concern yourself with iteration context or research history

**Evaluation Criteria**:
1. **Quantity**: Is the gene count reasonable for this biological process? (Target: 30-50)
2. **Relevance**: Are genes actually relevant to the biological process?
3. **Evidence Quality**: Are scores justified by evidence?
4. **Coverage**: Are major pathways/mechanisms represented?
5. **Red Flags**: Any suspicious high scores? Genes that don't belong?

**Grade Guidelines**:
- **Pass**: Draft is good enough. Minor issues acceptable. Ready for finalization.
- **Fail**: Significant issues that warrant revision. Missing genes, weak evidence, coverage gaps.

### Refinement Agent

**Role**: Researcher responding to manuscript review, always producing a final product

**Mindset**:
- Read the review critically
- Accept or reject suggestions based on judgment
- Execute additional research as needed
- Synthesize findings and update the draft
- Write a response explaining actions taken
- Always aim to produce a draft that will pass
- Always produce a complete, finalized gene list (30-50 genes)
- DO NOT blindly accept reviewer suggestions
- DO NOT concern yourself with iteration context
- Treat each refinement as if it's the final output

**Process**:
1. Read the critic's review
2. Evaluate each recommendation - accept, modify, or reject
3. Decide on queries to execute (reviewer suggestions + own judgment)
4. Execute queries using research tools
5. Summarize research findings
6. Update gene_evidence with new findings
7. Update state_of_knowledge
8. Adjust scored_genes (add/remove/re-score as needed)
9. Ensure final gene count is within target (30-50)
10. Write response to reviewer

**Incremental Scoring**:
- Do NOT run full re-scoring
- Adjust scores based on new evidence:
  - Strengthen scores for genes with new corroborating evidence
  - Lower scores for genes where evidence was found lacking
  - Add new genes discovered with appropriate initial scores
  - Remove genes that are clearly irrelevant

---

## Prompts to Write

### 1. CRITIC_SYSTEM_PROMPT

Location: `src/aging_bd_agentic_system/prompts/phase2_critic_prompts.py`

**Purpose**: System prompt for the critic agent

**Content should include**:
- Role definition (manuscript reviewer)
- Evaluation criteria (quantity, relevance, evidence, coverage, red flags)
- Grade guidelines (pass vs fail)
- Output schema specification
- Emphasis on being thorough but fair
- Target gene count: 30-50 genes per biological process

**Key instructions**:
- You are reviewing a curated gene list for a biological process
- Assess whether the list is comprehensive and well-evidenced
- Provide specific, actionable recommendations
- Structure queries by source type
- Be constructive - your goal is to help improve the draft

### 2. CRITIC_USER_PROMPT_TEMPLATE

Location: `src/aging_bd_agentic_system/prompts/phase2_critic_prompts.py`

**Purpose**: User prompt template that formats the draft for review

**Template variables**:
- `{biological_process}`
- `{hallmark_name}`
- `{gene_count}`
- `{scored_genes_json}`
- `{gene_evidence_json}`
- `{state_of_knowledge_json}`

### 3. REFINEMENT_SYSTEM_PROMPT

Location: `src/aging_bd_agentic_system/prompts/phase2_refine_prompts.py`

**Purpose**: System prompt for the refinement agent

**Content should include**:
- Role definition (researcher responding to review, always producing final product)
- Process overview (read, judge, research, synthesize, respond, finalize)
- Emphasis on exercising judgment
- Instructions for incremental scoring
- Output schema specification
- Finalization requirement: always produce 30-50 genes

**Key instructions**:
- Read the review critically
- Accept suggestions that make sense, reject those that don't
- You may add your own queries beyond reviewer recommendations
- Synthesize research findings before updating the draft
- Adjust scores incrementally based on new evidence
- Write a thoughtful response explaining your decisions
- Always produce a finalized gene list (30-50 genes) - treat this as your final output

### 4. REFINEMENT_USER_PROMPT_TEMPLATE

Location: `src/aging_bd_agentic_system/prompts/phase2_refine_prompts.py`

**Purpose**: User prompt template that formats the review and draft

**Template variables**:
- `{biological_process}`
- `{hallmark_name}`
- `{gene_count}`
- `{critic_review_json}`
- `{scored_genes_json}`
- `{gene_evidence_json}`
- `{state_of_knowledge_json}`

### 5. REFINEMENT_RESEARCH_SUMMARIZER_PROMPT

Location: `src/aging_bd_agentic_system/prompts/phase2_refine_prompts.py`

**Purpose**: Summarize research findings during refinement

**Note**: Similar to `PHASE2_TOOL_SUMMARIZER_PROMPT` but optimized for refinement context.

---

## Code to Write

### 1. New `phase2_critic()` Function

Location: `src/aging_bd_agentic_system/agents/phase2_gene_researcher.py`

**Signature**:
```python
def phase2_critic(state: dict[str, Any]) -> dict[str, Any]:
    """
    Review the current draft and provide feedback.

    This function acts as a manuscript reviewer, evaluating the quality
    of the gene list and providing actionable recommendations.

    Args:
        state: Current workflow state containing scored_genes, gene_evidence,
               state_of_knowledge, and context.

    Returns:
        Dict with "critic_review" key containing the review output.
    """
```

**Implementation steps**:
1. Extract inputs from state (biological_process, hallmark, scored_genes, gene_evidence, state_of_knowledge)
2. Format user prompt with draft data
3. Invoke LLM with structured output schema
4. Return critic_review in state update

**Error handling**:
- If LLM fails, default to "fail" grade with generic recommendations
- Log errors appropriately

### 2. New `phase2_refine()` Function

Location: `src/aging_bd_agentic_system/agents/phase2_gene_researcher.py`

**Signature**:
```python
def phase2_refine(state: dict[str, Any]) -> dict[str, Any]:
    """
    Respond to critic review by performing additional research and updates.

    This function acts as a researcher responding to manuscript review,
    exercising judgment on reviewer suggestions and updating the draft.
    Always produces a finalized gene list (30-50 genes) as output.

    Args:
        state: Current workflow state containing the draft and critic_review.

    Returns:
        Dict with updated scored_genes, gene_evidence, state_of_knowledge,
        and refinement metadata. The output is always a finalized draft.
    """
```

**Implementation steps**:
1. Extract inputs from state (draft + critic_review)
2. Invoke LLM to get refinement plan (queries to execute, feedback to address)
3. Execute queries using existing tools:
   - `query_opengenes()`
   - `query_pubmed()`
   - `query_vector_db()` or `query_vector_db_batch()`
4. Summarize results using existing summarization prompts
5. Invoke LLM to synthesize findings and update draft
6. Ensure final gene count is within target (30-50) - trim if needed
7. Return updated state (scored_genes, gene_evidence, state_of_knowledge)

**Note**: This is a multi-step function with several LLM invocations:
- Step 1: Read review, decide on actions (structured output)
- Step 2: Execute queries (tool calls)
- Step 3: Summarize results (can reuse existing prompts)
- Step 4: Update draft (structured output)
- Step 5: Finalize gene list to meet target constraints

**Error handling**:
- If query execution fails, log and continue with available results
- If LLM fails, preserve existing draft and log error

### 3. Updated Graph Workflow

Location: `src/aging_bd_agentic_system/graph/workflow.py`

**Changes needed**:
1. Add nodes for `phase2_critic` and `phase2_refine`
2. Add edges for critic-refine loop
3. Update routing logic:
   - After initial research → critic
   - After critic → refine (if fail) or next phase (if pass)
   - After refine → back to critic (if iterations remain) or next phase (if budget exhausted)

**Routing logic**:
```python
def should_continue_critic_refine(state: dict) -> str:
    """Route after refinement."""
    max_iter = state.get("config", {}).get("phase2", {}).get("max_critic_iterations", 2)
    current_iter = state.get("critic_iteration", 0)

    if current_iter == max_iter:
        return "next_phase"  # GO mapping or BP advance

    return "critic"

def route_after_critic(state: dict) -> str:
    """Route after critic review."""
    review = state.get("critic_review", {})
    grade = review.get("grade", "fail")

    if grade == "pass":
        return "next_phase"  # GO mapping or BP advance

    return "refine"
```

### 4. Configuration Updates

Location: `src/aging_bd_agentic_system/config.py` and `config/default.yaml`

**Add new config options**:
```yaml
phase2:
  # ... existing config ...

  # Critic-refine loop settings
  max_critic_iterations: 2        # Maximum critic-refine cycles

  # Refinement research settings
  refine_opengenes_max_results: 15
  refine_pubmed_max_results: 10
  refine_vector_db_top_k: 10
```

---

## State Schema Updates

### New State Fields

```python
# Add to state schema in graph/state.py or similar

critic_iteration: int = 0           # Current critic-refine iteration
critic_review: dict = {}            # Latest critic review output
refinement_history: list = []       # List of refinement outputs (for audit)
```

### State Flow

```
Initial state (from research loop):
  - scored_genes: [...]
  - gene_evidence: {...}
  - state_of_knowledge: {...}
  - critic_iteration: 0
  - critic_review: {}
  - refinement_history: []

After critic:
  - critic_review: {grade, review, recommendations}

After refinement:
  - scored_genes: [...] (updated)
  - gene_evidence: {...} (updated)
  - state_of_knowledge: {...} (updated)
  - critic_iteration: n+1
  - refinement_history: [..., refinement_output]
```

---

## GO Term Mapping

**Status**: Isolated, not part of this refactor

**Action**:
- Keep `map_go_terms()` function as-is
- Keep it in the graph but as an optional/disabled step
- Can be re-enabled later by updating graph routing

---

## Implementation Order

1. **Prompts**: Write all new prompts in `phase2_prompts.py`
2. **Critic function**: Implement `phase2_critic()`
3. **Refinement function**: Implement `phase2_refine()` (most complex, handles finalization)
4. **Graph updates**: Update workflow and routing
5. **Config**: Add new config options

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/aging_bd_agentic_system/prompts/phase2_critic_prompts.py` | Create new file with critic prompts |
| `src/aging_bd_agentic_system/prompts/phase2_refine_prompts.py` | Create new file with refinement prompts |
| `src/aging_bd_agentic_system/agents/phase2_gene_researcher.py` | Rewrite `phase2_critic()`, `phase2_refine()` |
| `src/aging_bd_agentic_system/graph/workflow.py` | Update graph with critic-refine loop |
| `src/aging_bd_agentic_system/config.py` | Add new config fields |
| `config/default.yaml` | Add new config values |

---

## Notes

- The critic and refinement agents are deliberately kept unaware of iteration context
- Orchestration (graph) handles iteration counting and termination
- Refinement uses same research tools and summarization as main research loop
- Refinement always produces a finalized gene list (30-50 genes) - no separate finalization step
- GO mapping is kept but disabled for now
- All new code should follow existing patterns in the codebase
