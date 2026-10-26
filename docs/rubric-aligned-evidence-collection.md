# Feature: Rubric-Aligned Evidence Collection

## Motivation

The current scoring rubric in `PHASE2_SCORING_SYSTEM_PROMPT` is source-count based:
- 9–10: 3+ sources
- 7–8: 2+ sources
- 5–6: 1 source

This conflates evidence **quantity** with evidence **quality**. A gene mentioned in three
associative studies can outscore one with a single well-characterized causal LOF result.

The proposed rubric, originally developed for epigenetic regulation and generalized here for
any BP + human-only context, is function/causality-based:

| Score | Label | Criteria |
|-------|-------|----------|
| 9–10 | Essential Driver | Direct causal evidence in humans — LOF or GOF studies directly result in aging phenotypes, accelerated age-related disease, or extended lifespan. Mechanistic link is well-characterized. |
| 7–8 | Core Mediator | Essential functional role in the biological process; central to a key complex, pathway, or regulatory mechanism. Supported by human functional studies, not just association. |
| 5–6 | Supporting Role | Validated involvement in the process but effects are indirect, tissue-specific, or primarily associative (expression changes, GWAS hits without strong functional follow-up). |

Human evidence only throughout. Model organism findings do not count unless backed by
direct human evidence.

---

## Problem: Rubric Requires Upstream Evidence

The scorer only sees `gene_evidence` (per-gene notes) and the `state_of_knowledge` summary.
If those were built by prompts that never asked for causal/functional/associative
classification, the scorer has no basis for the new rubric — it can only count sources.

**The fix is not just changing the scoring prompt.** Every upstream prompt that shapes what
evidence gets collected and how it gets compressed must be aligned with the rubric's
evidence hierarchy.

---

## Audit: Prompts That Need Changes

Full audit trace is in the conversation that produced this doc. Below is the prioritized
change list.

### Priority 1 — Scoring (immediate, highest impact)

**`PHASE2_SCORING_SYSTEM_PROMPT`** — `src/.../prompts/phase2_prompts.py:576–594`

Replace the `## Scoring Guidelines` block. Used in two places:
- `phase2_gene_researcher.py:718` (end of research loop)
- `phase2_refine.py:414` (end of refine step)

New rubric text (replace the current block):

```
## Scoring Guidelines

**Human evidence only**: Focus exclusively on human evidence; model organism findings
(mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct
human evidence supporting the association.

**Target output: {min_genes}-{max_genes} genes per biological process. Maximum {max_genes} genes.**

Score based on the nature and strength of human evidence:

- **9–10 (Essential Driver)**: Direct causal evidence — loss-of-function or gain-of-function
  studies in humans directly result in aging phenotypes, accelerated age-related disease,
  or extended lifespan. Mechanistic link is well-characterized.

- **7–8 (Core Mediator)**: Essential functional role — central to a key complex, pathway,
  or regulatory mechanism. Supported by human functional studies (not just association).
  Well-characterized role even if direct aging LOF/GOF is lacking.

- **5–6 (Supporting Role)**: Validated involvement — participates in the process but effects
  are indirect, tissue-specific, or primarily associative (expression changes, GWAS hits
  without strong functional follow-up).

**If you have {max_genes}+ candidate genes:** Be selective. Prefer Essential Drivers and
Core Mediators. Downgrade Supporting Role genes below 5 to exclude them unless coverage
would otherwise be too thin.

**If you have fewer than {min_genes} candidate genes:** Be inclusive. Include any gene
with at least one source and plausible functional relevance.

**Exclude only:**
- Genes with NO sources or citations
- Genes clearly unrelated to the biological process
- Genes supported only by model organism evidence with no direct human evidence
```

Also update the incremental scoring in `REFINEMENT_SYSTEM_PROMPT`
(`phase2_refine_prompts.py:25–31`) — new genes added during refinement should default
to 5–6 (Supporting), not 5–7, to match the new floor.

**Note**: `REFINEMENT_SYSTEM_PROMPT` and `REFINEMENT_USER_PROMPT_TEMPLATE` are currently
dead code (not imported by `phase2_refine.py`). Update the text anyway so if they are
re-activated they are consistent.

---

### Priority 2 — Synthesize Prompt (strategic planning step)

**`PHASE2_SYNTHESIZE_PROMPT`** — `phase2_prompts.py:298–308`

This is the highest-leverage collection prompt. It drives what the LLM decides to look
for in the next iteration. Currently it asks generic questions: "which genes need
validation?", "what mechanisms are underexplored?".

Replace the `## Your Task` section's `Consider:` block with rubric-aware guidance:

```
Consider:
1. Which candidate genes have only associative evidence so far — do we have any functional
   or causal studies to look for?
2. Which genes might be Essential Drivers (LOF/GOF aging phenotypes in humans) — are we
   specifically searching for that kind of evidence?
3. What biological mechanisms or complexes are central to this process but underrepresented?
4. What gaps in functional evidence (vs. associative evidence) should we prioritize?

Prioritize research directions that could elevate genes from Supporting → Core Mediator
or Core Mediator → Essential Driver, rather than adding more associative hits for genes
already in the list.
```

---

### Priority 3 — Decide Prompt (query generation)

**`PHASE2_DECIDE_PROMPT`** — `phase2_prompts.py:396–409`

The PubMed and Vector DB query guidelines should nudge toward functional/causal queries.
Add to the PubMed section:

```
**Prefer queries that find functional evidence:**
- "GENE AND loss-of-function AND aging"
- "GENE AND gain-of-function AND lifespan"
- "GENE AND knockout AND aging phenotype"
- "PATHWAY AND mechanism AND human"
Associative queries (expression, GWAS) are lower priority if we already have them.
```

Add to the Vector DB section:

```
**Prefer mechanistic questions:**
- "What is the causal role of GENE in PROCESS?"
- "Loss-of-function mutations in GENE and aging"
- "Direct evidence for GENE in human PROCESS"
```

---

### Priority 4 — Tool Summarizer (evidence classification)

**`PHASE2_TOOL_SUMMARIZER_PROMPT`** — `phase2_prompts.py:1003–1029`
**`REFINEMENT_RESEARCH_SUMMARIZER_PROMPT`** — `phase2_refine_prompts.py:298–322`

Both prompts produce `key_findings` arrays. Add a classification requirement to the
Output Requirements section:

```
2. **Key findings** - 2-4 bullet points, ~50 words each. For each finding, prefix with
   the evidence type in brackets:
   - [CAUSAL]: Direct LOF/GOF studies, disease mutations, lifespan intervention
   - [FUNCTIONAL]: Essential pathway role, complex membership, enzymatic function
   - [ASSOCIATIVE]: Expression changes, GWAS hits, correlational studies
   Example: "[CAUSAL] TP53 germline mutations accelerate aging phenotypes in Li-Fraumeni
   syndrome patients (pmid:12345)."
```

---

### Priority 5 — State Update (evidence_notes classification)

**`PHASE2_STATE_UPDATE_PROMPT`** — `phase2_prompts.py:1141–1149`
**`REFINEMENT_STATE_UPDATE_PROMPT`** — `phase2_refine_prompts.py:441–445`

The `evidence_notes` field (~50 words per gene) is fed directly to the scorer. Add to
the `gene_evidence_updates` instructions:

```
- `evidence_notes`: Compressed ~50 word summary. Begin with the strongest evidence type
  for this gene in brackets: [CAUSAL], [FUNCTIONAL], or [ASSOCIATIVE]. This classification
  is used by the downstream scorer.
  Example: "[FUNCTIONAL] BRCA1 is essential for homologous recombination DSB repair,
  forming a core complex with BARD1. Strong human functional evidence from cell lines
  and BRCA1-mutant patient studies."
```

---

### Priority 6 — Critic (rubric-aware evaluation)

**`CRITIC_SYSTEM_PROMPT`** — `phase2_critic_prompts.py:27–29`

Evaluation criterion #3 currently says "Are scores justified by the evidence provided?"
with no rubric to judge against. Replace criterion #3:

```
3. **Evidence Quality**: Are scores justified by the rubric?
   - 9–10 (Essential Driver): Must have direct causal human evidence (LOF/GOF → aging phenotype)
   - 7–8 (Core Mediator): Must have functional human evidence (central pathway/complex role)
   - 5–6 (Supporting Role): Associative evidence acceptable (expression, GWAS, indirect)
   Flag any gene scored 9–10 without causal evidence, or 7–8 without functional evidence.
```

---

### Priority 7 — Seeding evidence summaries (low priority)

**`PHASE2_GENAGE_EVIDENCE_PROMPT`** — `phase2_prompts.py:818–826`
**`PHASE2_OPENGENES_EVIDENCE_PROMPT`** — `phase2_prompts.py:874–880`

Seeding is intentionally a wide net so no major change here. Optionally add to the
instructions: "If the GenAge/OpenGenes data indicates a causal or functional role
(e.g., LOF mutations, longevity intervention), note this explicitly."

---

## Dead Code — No Action Needed

These prompts are defined but not called anywhere:
- `PHASE2_RESEARCH_SYSTEM_PROMPT` + `PHASE2_DECISION_USER_PROMPT` (old ReAct flow)
- `PHASE2_TOOL_DESCRIPTIONS` (imported but unused)
- `PHASE2_ACTIONABILITY_SUMMARY_PROMPT` + `PHASE2_SCORING_SUMMARY_PROMPT` (commented-out flow)
- `PHASE2_CRITIQUE_SYSTEM_PROMPT` in `phase2_prompts.py` (superseded by `phase2_critic_prompts.py`)
- `REFINEMENT_SYSTEM_PROMPT` + `REFINEMENT_USER_PROMPT_TEMPLATE` (not imported by refine agent)

---

## Implementation Order

1. `PHASE2_SCORING_SYSTEM_PROMPT` — change the rubric block
2. `REFINEMENT_SYSTEM_PROMPT` — update incremental scoring guidance (even though dead, for consistency)
3. `PHASE2_SYNTHESIZE_PROMPT` — add rubric-aware Consider block
4. `PHASE2_DECIDE_PROMPT` — add functional/causal query guidance
5. `PHASE2_TOOL_SUMMARIZER_PROMPT` + `REFINEMENT_RESEARCH_SUMMARIZER_PROMPT` — add [CAUSAL/FUNCTIONAL/ASSOCIATIVE] tagging
6. `PHASE2_STATE_UPDATE_PROMPT` + `REFINEMENT_STATE_UPDATE_PROMPT` — add classification prefix to evidence_notes
7. `CRITIC_SYSTEM_PROMPT` — replace criterion #3 with rubric-aware version
8. (Optional) `PHASE2_GENAGE_EVIDENCE_PROMPT` + `PHASE2_OPENGENES_EVIDENCE_PROMPT` — minor note about evidence type

## Testing

Run a single BP with `max_research_iterations: 2` and `max_critic_iterations: 1` using
`test_gene_count_config.yaml`. Inspect `bp1/research_result.json`:
- `gene_evidence` entries should have evidence_notes starting with [CAUSAL/FUNCTIONAL/ASSOCIATIVE]
- `genes_found` scores should reflect causality, not just source count
- High-scoring genes (9–10) should have explicit causal evidence in their evidence_summary
