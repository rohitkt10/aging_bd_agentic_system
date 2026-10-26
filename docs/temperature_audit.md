# LLM Call Site Audit — Model Tier / Temp Tier Assignments

2 model tiers: **low** (flash), **high** (pro)  
3 temp tiers: **low**, **mid**, **high**  
Config: `temperature_low`, `temperature_mid`, `temperature_high` — all user-definable, fallback to `temperature`

---

## Call site table (sequential execution order)

| Call | Task type | Model tier | Temp tier | Justification |
|------|-----------|------------|-----------|---------------|
| **PHASE 1** |
| `phase1_plan` — generate research plan with goals + search terms | Strategic planning | high | high | Most generative call in the pipeline. Needs to explore diverse research angles for the hallmark. Too low = same obvious goals every run. |
| `_summarize_goal_results` corpus — summarize vector DB chunks per goal (×N goals) | Evidence summarization | low | low | Pure extraction from retrieved text. Answer is in the source. Temperature adds noise. |
| `_summarize_goal_results` pubmed — summarize PubMed abstracts per goal (×N goals) | Evidence summarization | low | low | Same as above. |
| `phase1_research` synthesis — produce ranked biological process list from all goal summaries | Structured synthesis | high | mid | Cross-goal integration and judgment. Needs the capable model. Not purely extractive but output is a grounded ranked list — mid keeps it anchored. |
| `phase1_critic` unstructured — free-form critique of the process list | Analytical critique | low | mid | Needs to notice genuine weaknesses, not just pattern-match. Some temperature helps surface varied critique angles. But not creative — keep it restrained. |
| `phase1_critic` structured — extract grade + query recommendations from critique text | Structured extraction | low | low | Extracting structure from text that already exists. Near-deterministic. |
| `phase1_refine` → `_summarize_goal_results` corpus — summarize corpus results from critic queries | Evidence summarization | low | low | Same as initial summarization calls. |
| `phase1_refine` → `_summarize_goal_results` pubmed — summarize PubMed results from critic queries | Evidence summarization | low | low | Same as above. |
| `phase1_refine` synthesis — update BP list with new evidence + focus areas | Structured synthesis | high | mid | Same as initial synthesis — integration task, grounded output. |
| **PHASE 2 — SEEDING (iteration 0, once per BP)** |
| `select_genage_seed_genes` — select relevant genes from GenAge CSV | Relevance filtering | low | low | Recall task against known database. Not creative. Consistency matters — same BP should produce stable seed set. |
| `generate_opengenes_seed_queries` — generate search queries for OpenGenes | Query generation | low | low | Short formulaic queries. Some diversity is fine but this is constrained enough that low is sufficient. |
| `_summarize_evidence_batch` GenAge — expand GenAge "why" fields into evidence summaries | Evidence summarization | low | low | Expanding sparse structured data into prose. Factual. |
| `_summarize_evidence_batch` OpenGenes — summarize raw OpenGenes mechanism/cluster data per gene | Evidence summarization | low | low | Same as above. |
| **PHASE 2 — RESEARCH LOOP (iterations 1–N, per iteration)** |
| `phase2_research` synthesize — synthesize current state of knowledge into research priorities | Strategic synthesis | high | high | The "thinking" step of the ReAct loop. Explicitly phased (exploration → exploitation). Needs genuine variability to surface different leads across iterations. Low temp here = repetitive research directions. |
| `phase2_research` decide — structured tool call decision (which queries to run) | Structured decision | low | low | Translates the synthesize output into a query list. Should faithfully follow what synthesize decided. Low. |
| `phase2_research` OpenGenes summarizer — extract genes + findings from OpenGenes results | Evidence summarization | low | low | Extraction from tool results. |
| `phase2_research` PubMed summarizer — extract genes + findings from PubMed results | Evidence summarization | low | low | Extraction from tool results. |
| `phase2_research` vector DB summarizer — extract genes + findings from corpus passages | Evidence summarization | low | low | Extraction from tool results. |
| `phase2_research` state update — integrate new findings into running state of knowledge | Knowledge consolidation | high | low | Needs the capable model to correctly synthesize across growing evidence. But this is consolidation of what the pipeline has already established — not generation of new ideas. Mid or higher risks subtle drift in the state representation that compounds across iterations. Low. |
| **PHASE 2 — FINAL RESEARCH ITERATION ONLY** |
| `phase2_research` gene scoring — score all candidate genes 5–10 with evidence summaries | Scoring | high | low | Needs the capable model for judgment quality. But scores feed directly into output filtering — variance is undesirable. This is the canonical case that motivated decoupling model tier from temp tier. High model, low temp. |
| **PHASE 2 — CRITIC** |
| `phase2_critic` — manuscript-style review, grade pass/fail, strengths/weaknesses, query recommendations | Analytical critique | low | mid | Needs to notice genuine problems, not just pattern-match. Some temperature helps. If critic starts hallucinating issues that don't exist, drop to low. |
| **PHASE 2 — REFINE (if critic grades fail)** |
| `phase2_refine` assessment — evaluate reviewer feedback, plan rebuttal + tool calls | Rebuttal planning | low | mid | Judgment call on which reviewer suggestions to accept and which queries to run. More generative than pure extraction but constrained by reviewer input. |
| `phase2_refine` OpenGenes summarizer | Evidence summarization | low | low | Same as research loop summarizers. |
| `phase2_refine` PubMed summarizer | Evidence summarization | low | low | Same. |
| `phase2_refine` vector DB summarizer | Evidence summarization | low | low | Same. |
| `phase2_refine` state update — integrate refine findings + reviewer context into state | Knowledge consolidation | high | low | Same reasoning as research loop state update. Consolidation, not generation. Low. |
| `phase2_refine` gene re-scoring — re-score all genes post-refinement | Scoring | high | low | Same as final iteration scoring. High model, low temp. |
| **PHASE 2 — GO MAPPING** |
| `map_go_terms` — score relevance of GO terms to the BP (1–10), filter to ≥6 | Relevance scoring | low | low | Judgment against a fixed ontology. Should be consistent across BPs. |

---

## Notes

### Why 3 temp tiers not 2

The scoring calls (`phase2_research` final iteration, `phase2_refine` re-scoring) need **high model + low temp** simultaneously. Any scheme that couples temperature to model tier cannot express this — it's the canonical case that motivated decoupling the two axes. 3 tiers (low / mid / high) give a distinct band for each of: near-deterministic extraction, calibrated judgment/critique, and exploratory generation.

### The two dominant patterns

**high model + low temp** appears at state updates and scoring. These are the calls where you need the capable model's judgment but want stable, reproducible outputs. State updates are consolidation, not creation. Scores are used to filter outputs downstream.

**low model + low temp** is the majority of calls by count — all summarizers, structured extraction, tool decisions, seeding. These are mechanical and should be near-deterministic.

### Mid temp is narrow

Mid only appears at synthesis calls (BP list production, process list update) and critique calls (phase1 critic unstructured, phase2 critic, refine assessment). These are the calls that require real analytical judgment or cross-source integration, where the output isn't purely grounded in source text but also isn't free generation. If experiments show these are drifting or hallucinating, drop to low. If they're repetitive and narrow, nudge toward high.

### State update calls — follow Claude's second opinion

The second opinion recommended moving state updates from mid to low. Agreed — state updates are compressive consolidation of what the pipeline has already found. Mid temperature risks the model reframing established findings in each iteration, which accumulates. Low keeps the representation stable and faithful.

### Suggested starting values for experiments

```yaml
llm:
  temperature: 0.3        # global fallback
  temperature_low: 0.2
  temperature_mid: 0.4
  temperature_high: 0.8
```
