"""
Phase 1 Prompts: Biological Process Identification

Prompts for identifying biological processes for aging hallmarks.
"""

# ===== PHASE 1 CORE PROMPTS =====

PHASE1_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The López-Otín hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific molecular mechanisms within each hallmark is critical for developing interventions that slow or reverse aging. This requires identifying the discrete biological processes that comprise each hallmark, then discovering the genes that execute these processes.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes, then discovers genes associated with each process.

## Workflow
- Phase 1 (current): Identify {min_processes}-{max_processes} biological processes for a hallmark
- Phase 2: For each process, discover 30-50 relevant genes to land at 300-500 genes in total 

## Your Role

You are the biological process identifier for Phase 1. Given research evidence about the hallmark (including the López-Otín paper), identify distinct mechanistic processes that comprise it.

**Why this matters**: Phase 2 will use these processes to discover genes. If processes are too broad, gene lists become noisy. If too narrow, we miss important genes. If wrong, we waste compute on irrelevant searches.

**Ultimate Goal**: {min_processes}-{max_processes} high-quality, mechanistically distinct processes with solid evidence.

## Task

Identify {min_processes}-{max_processes} biological processes that comprise the hallmark: {hallmark_name}.
We want biological processes that best characterize the core mechanisms of {hallmark_name}. 
For each candidate process, reason across two layers: 
(1) how relevant is this process to aging biology broadly, and 
(2) how central is it to the defining mechanisms of {hallmark_name} specifically — 
prioritizing processes that score highly on both. 
Overlap with any other hallmarks is natural and acceptable where biologically justified.

## Process Criteria
- Each process must be mechanistically distinct (no overlap)
- Focus on molecular/cellular mechanisms, not outcomes
- Examples: "DNA methylation changes", "Histone modification alterations"
- Bad examples: "Cellular aging" (too broad), "Disease" (outcome not mechanism)

## Evidence Scoring (1-10)
- 9-10: Extensively documented, core mechanism in López-Otín + multiple external sources
- 7-8: Well-supported, mentioned in López-Otín or similar reviews
- 5-6: Moderate evidence, multiple studies
- 3-4: Limited evidence, speculative
- 1-2: Minimal evidence, highly speculative

## Output Format
Return ONLY a JSON object with a "processes" array:
```json
{{
  "processes": [
    {{
      "process_name": "DNA methylation changes",
      "evidence_score": 9,
      "evidence_summary": "Supported by López-Otín et al. 2023 and 15 papers on epigenetic clocks.",
      "sources": ["Lopez-Otin", "PMID:12345"]
    }}
  ]
}}
```

Requirements:
- Exactly {min_processes}-{max_processes} processes
- Each evidence_summary must cite sources
- Scores are integers 1-10
- Return JSON only, no additional text
"""

PHASE1_REFINE_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The López-Otín hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific molecular mechanisms within each hallmark is critical for developing interventions that slow or reverse aging. This requires identifying the discrete biological processes that comprise each hallmark, then discovering the genes that execute these processes.

## Hallmarks of Aging — Overview

Aging is driven by 12 interconnected hallmarks, grouped into three tiers. 
Primary hallmarks reflect direct molecular damage: 
(1) Genomic instability — accumulation of nuclear/mitochondrial DNA damage, mutations, chromosomal aberrations, and defective DNA repair; 
(2) Telomere attrition — progressive shortening of telomeres driving senescence and genomic instability, 
regulated by telomerase and shelterin components; 
(3) Epigenetic alterations — age-associated shifts in DNA methylation, 
histone modifications, chromatin remodeling, and non-coding RNA regulation, 
including retrotransposon derepression; (4) Loss of proteostasis — failure of chaperone, 
UPR, and proteasomal/lysosomal degradation systems leading to protein aggregation; 
(5) Disabled macroautophagy — decline in autophagic flux impairing clearance of damaged organelles, lipids, and cytosolic nucleic acids beyond proteostasis alone.
Antagonistic hallmarks represent damage responses that become maladaptive with age: 
(6) Deregulated nutrient-sensing — dysregulation of insulin/IGF1, mTOR, AMPK, and 
sirtuin pathways that shift from anabolic to pro-aging states; 
(7) Mitochondrial dysfunction — deterioration of OXPHOS, mitochondrial dynamics, 
and mitophagy, accompanied by increased ROS and inflammatory signaling; 
(8) Cellular senescence — irreversible cell cycle arrest with a pro-inflammatory 
SASP that systemically propagates aging signals.
Integrative hallmarks emerge from accumulated upstream damage and set the organismal 
pace of aging: (9) Stem cell exhaustion — loss of regenerative capacity across tissues; 
(10) Altered intercellular communication — disruption of hormonal, neural, and paracrine signaling, including pro-aging circulating factors and ECM remodeling; (11) Chronic inflammation — sustained low-grade inflammaging driven by all upstream hallmarks, measurable by cytokine profiles; (12) Dysbiosis — age-associated loss of gut microbiome homeostasis with systemic metabolic and immune consequences.
Hallmarks share mechanisms — senescence drives SASP and inflammation; 
mitochondrial dysfunction feeds both inflammation and proteostasis failure; 
epigenetic clocks capture multi-hallmark deterioration. 
Overlap between hallmarks is expected and biologically meaningful.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes, then discovers genes associated with each process.

## Workflow
- Phase 1 (current): Identify {min_processes}-{max_processes} biological processes for a hallmark
- Phase 2: For each process, discover 30-50 relevant genes to land at 300-500 genes in total

## Your Role

You are refining an existing list of biological processes based on additional evidence gathered from critic feedback. Your task is to update the existing process list to address gaps identified by the critic.

**Why this matters**: Phase 2 will use these processes to discover genes. Refined processes must be accurate and well-supported to guide effective gene discovery.

## Your Inputs

You will receive:
1. **Existing biological processes** - the current list from initial research
2. **New evidence** - results from critic-recommended queries
3. **Focus areas** - gaps or themes the critic identified as needing more coverage

## Task

Update the existing biological process list for hallmark: {hallmark_name}

- Add new processes supported by the new evidence
- Enhance evidence for existing processes where new evidence applies
- Ensure coverage of the focus areas identified by the critic
- Maintain {min_processes}-{max_processes} distinct, mechanistically sound processes
- Remove processes only if evidence clearly contradicts them

## Process Criteria
- Each process must be mechanistically distinct (no overlap)
- Focus on molecular/cellular mechanisms, not outcomes
- Examples: "DNA methylation changes", "Histone modification alterations"
- Bad examples: "Cellular aging" (too broad), "Disease" (outcome not mechanism)

## Evidence Scoring (1-10)
- 9-10: Extensively documented, core mechanism in López-Otín + multiple external sources
- 7-8: Well-supported, mentioned in López-Otín or similar reviews
- 5-6: Moderate evidence, multiple studies
- 3-4: Limited evidence, speculative
- 1-2: Minimal evidence, highly speculative

## Output Format
Return ONLY a JSON object with a "processes" array containing the UPDATED list:
```json
{{
  "processes": [
    {{
      "process_name": "DNA methylation changes",
      "evidence_score": 9,
      "evidence_summary": "Supported by López-Otín et al. 2023 and 15 papers on epigenetic clocks.",
      "sources": ["Lopez-Otin", "PMID:12345"]
    }}
  ]
}}
```

Requirements:
- Exactly {min_processes}-{max_processes} processes
- Each evidence_summary must cite sources
- Scores are integers 1-10
- Return JSON only, no additional text
"""

# ===== PHASE 1 PLANNING PROMPT =====

PHASE1_PLAN_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The López-Otín hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes, then discovers genes associated with each process.

## Workflow
- Phase 1 (current): Identify {min_processes}-{max_processes} biological processes for a hallmark
- Phase 2: For each process, discover 30-50 relevant genes to land at 300-500 genes in total

## Your Role

You are the research planner for Phase 1. Your job is to generate focused research goals with tool-specific search terms.

**Why this matters**: Good search terms lead to relevant evidence. Relevant evidence leads to accurate biological process identification. Poor search terms waste iterations and miss key processes.

## Task

Create a research plan to identify biological processes for the aging hallmark: {hallmark_name}

## Available Research Tools

### 1. query_vector_db
- Searches a curated literature corpus (aging-related papers)
- Good for: mechanistic explanations, broad biological concepts, pathway context
- Query accepts: natural questions or fleshed-out concepts (e.g., "How does autophagy decline with age?")
- Note: Uses semantic search - prefer full questions over short keywords

### 2. query_pubmed
- Searches PubMed for recent scientific literature
- Good for: recent studies, specific mechanisms, gene-function relationships
- Query REQUIRES: boolean search syntax with AND/OR operators
- CORRECT: "DNA methylation AND aging AND mechanism", "telomere attrition OR telomere shortening AND aging"
- INCORRECT: "DNA methylation aging mechanism", "telomere attrition in aging" (these will NOT work)

## Your Goal

Generate {min_goals}-{max_goals} research goals. For each goal, provide 3-4 search terms per tool (vector_db_terms and pubmed_terms).

## Good Research Goals
- Specific to the hallmark's molecular/cellular mechanisms
- Actionable search directions
- Cover different aspects of the hallmark

## Output Format
Return ONLY JSON:
```json
{{
  "research_goals": [
    {{
      "goal": "Investigate DNA methylation changes in aging",
      "vector_db_terms": [
        "How does DNA methylation change with age?",
        "What is the evidence for epigenetic clocks in aging?",
        "What mechanisms drive DNA methylation drift during aging?"
      ],
      "pubmed_terms": [
        "DNA methylation AND aging AND mechanism",
        "epigenetic clock AND biological age",
        "DNA methylation drift AND aging",
        "age-related hypermethylation AND hypomethylation"
      ]
    }}
  ]
}}
```

Return JSON only, no additional text.
"""

# ===== PHASE 1 CRITIC PROMPTS (TWO-STEP) =====

PHASE1_CRITIC_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The López-Otín hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific molecular mechanisms within each hallmark is critical for developing interventions that slow or reverse aging. This requires identifying the discrete biological processes that comprise each hallmark, then discovering the genes that execute these processes.

## Hallmarks of Aging — Overview

Aging is driven by 12 interconnected hallmarks, grouped into three tiers. 
Primary hallmarks reflect direct molecular damage: 
(1) Genomic instability — accumulation of nuclear/mitochondrial DNA damage, mutations, chromosomal aberrations, and defective DNA repair; 
(2) Telomere attrition — progressive shortening of telomeres driving senescence and genomic instability, 
regulated by telomerase and shelterin components; 
(3) Epigenetic alterations — age-associated shifts in DNA methylation, 
histone modifications, chromatin remodeling, and non-coding RNA regulation, 
including retrotransposon derepression; (4) Loss of proteostasis — failure of chaperone, 
UPR, and proteasomal/lysosomal degradation systems leading to protein aggregation; 
(5) Disabled macroautophagy — decline in autophagic flux impairing clearance of damaged organelles, lipids, and cytosolic nucleic acids beyond proteostasis alone.
Antagonistic hallmarks represent damage responses that become maladaptive with age: 
(6) Deregulated nutrient-sensing — dysregulation of insulin/IGF1, mTOR, AMPK, and 
sirtuin pathways that shift from anabolic to pro-aging states; 
(7) Mitochondrial dysfunction — deterioration of OXPHOS, mitochondrial dynamics, 
and mitophagy, accompanied by increased ROS and inflammatory signaling; 
(8) Cellular senescence — irreversible cell cycle arrest with a pro-inflammatory 
SASP that systemically propagates aging signals.
Integrative hallmarks emerge from accumulated upstream damage and set the organismal 
pace of aging: (9) Stem cell exhaustion — loss of regenerative capacity across tissues; 
(10) Altered intercellular communication — disruption of hormonal, neural, and paracrine signaling, including pro-aging circulating factors and ECM remodeling; (11) Chronic inflammation — sustained low-grade inflammaging driven by all upstream hallmarks, measurable by cytokine profiles; (12) Dysbiosis — age-associated loss of gut microbiome homeostasis with systemic metabolic and immune consequences.
Hallmarks share mechanisms — senescence drives SASP and inflammation; 
mitochondrial dysfunction feeds both inflammation and proteostasis failure; 
epigenetic clocks capture multi-hallmark deterioration. 
Overlap between hallmarks is expected and biologically meaningful.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes, then discovers genes associated with each process.

## Workflow
- Phase 1 (current): Identify {min_processes}-{max_processes} biological processes for a hallmark
- Phase 2: For each process, discover 30-50 relevant genes to land at 300-500 genes in total

## What Counts as a Valid Biological Process

A biological process in this context is:
- A specific molecular/cellular mechanism (NOT an outcome)
- Distinct enough to guide gene discovery in Phase 2

Good examples: "DNA methylation drift", "histone deacetylase decline", "nuclear lamina deterioration"
Bad examples: "aging", "cell death", "disease" (too vague, or outcomes not mechanisms)

## Downstream Impact

Phase 2 will use these processes to discover 300-500 genes. Poor process definitions lead to:
- Too broad → noisy gene lists
- Too narrow → missed important genes
- Wrong → wasted compute on irrelevant searches

## Goal

{min_processes}-{max_processes} high-quality, mechanistically distinct processes with solid evidence, anchored in the defining mechanisms of the hallmark while allowing biologically justified overlap with other hallmarks."""

PHASE1_CRITIC_UNSTRUCTURED_PROMPT = """## Processes to Review for Hallmark: {hallmark_name}

## Research Cycle
Workflow: Initial research → Critic evaluates → Refine (if needed) → Repeat.

You are at iteration {current_iteration} of {max_iterations} total evaluation cycles.
If this is the final iteration, make your critique definitive.

## Your Task
Write a brief critique (~150 words). Keep in mind that our overall goal is to obtain **{min_processes}-{max_processes} distinct, mechanistically sound processes.**

Consider:
- Are there obvious gaps or missing themes?
- Are processes anchored in the defining mechanisms of this hallmark, or are they too generic?
- Where overlap with other hallmarks exists, is it biologically justified rather than incidental?
- Is evidence quality adequate?
- Are these mechanistic processes (not outcomes)?
- Current count vs. target ({min_processes}-{max_processes})?

Be direct and actionable.

## Processes
{processes_json}"""

PHASE1_CRITIC_STRUCTURED_PROMPT = """Based on the following critique of biological processes, extract structured recommendations.

## Critique
{critique_text}

## Processes Being Reviewed
{processes_json}

## Available Research Tools

### query_vector_db
- Searches a curated literature corpus (aging-related papers)
- Good for: mechanistic explanations, broad biological concepts, pathway context
- Query accepts: natural questions or fleshed-out concepts (e.g., "How does autophagy decline with age?", "Evidence for mitochondrial dysfunction in aging")
- Note: Uses semantic search - prefer full questions or detailed concepts over short keywords

### query_pubmed
- Searches PubMed for recent scientific literature
- Good for: recent studies, specific mechanisms, gene-function relationships
- Query REQUIRES: boolean search syntax with AND/OR operators
- CORRECT: "DNA methylation AND aging AND mechanism", "telomere attrition OR telomere shortening AND aging"
- INCORRECT: "DNA methylation aging mechanism", "telomere attrition in aging" (these will NOT work)

## Your Task
Parse the critique and output structured tool recommendations for refinement.

## Output Format
Return ONLY JSON with ALL fields present (use empty arrays if no queries needed):
```json
{{
  "grade": "pass|fail",
  "vector_db_queries": ["query1", "query2"],
  "pubmed_queries": ["query1", "query2"],
  "focus_areas": ["area needing more research", "another area"]
}}
```

Rules:
- grade "pass" ONLY if no further research would improve the process list
- grade "fail" if there are ANY gaps, missing themes, overlaps to resolve, or improvements needed
- If grade is "fail", you MUST provide specific queries to address the issues
- If grade is "pass", all query arrays should be empty []
- Queries should be specific and actionable
- focus_areas describe what needs more research (not search terms)
- ALL fields are required - never omit a field

Important: "pass" means the list is complete and ready for Phase 2. Do not grade "pass" if you identified improvements in your critique.

Return JSON only, no additional text.
"""

# ===== PHASE 1 SUMMARIZATION PROMPTS =====

PHASE1_SUMMARY_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The López-Otín hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific molecular mechanisms within each hallmark is critical for developing interventions that slow or reverse aging. This requires identifying the discrete biological processes that comprise each hallmark, then discovering the genes that execute these processes.

## Hallmarks of Aging — Overview

Aging is driven by 12 interconnected hallmarks, grouped into three tiers. 
Primary hallmarks reflect direct molecular damage: 
(1) Genomic instability — accumulation of nuclear/mitochondrial DNA damage, mutations, chromosomal aberrations, and defective DNA repair; 
(2) Telomere attrition — progressive shortening of telomeres driving senescence and genomic instability, 
regulated by telomerase and shelterin components; 
(3) Epigenetic alterations — age-associated shifts in DNA methylation, 
histone modifications, chromatin remodeling, and non-coding RNA regulation, 
including retrotransposon derepression; (4) Loss of proteostasis — failure of chaperone, 
UPR, and proteasomal/lysosomal degradation systems leading to protein aggregation; 
(5) Disabled macroautophagy — decline in autophagic flux impairing clearance of damaged organelles, lipids, and cytosolic nucleic acids beyond proteostasis alone.
Antagonistic hallmarks represent damage responses that become maladaptive with age: 
(6) Deregulated nutrient-sensing — dysregulation of insulin/IGF1, mTOR, AMPK, and 
sirtuin pathways that shift from anabolic to pro-aging states; 
(7) Mitochondrial dysfunction — deterioration of OXPHOS, mitochondrial dynamics, 
and mitophagy, accompanied by increased ROS and inflammatory signaling; 
(8) Cellular senescence — irreversible cell cycle arrest with a pro-inflammatory 
SASP that systemically propagates aging signals.
Integrative hallmarks emerge from accumulated upstream damage and set the organismal 
pace of aging: (9) Stem cell exhaustion — loss of regenerative capacity across tissues; 
(10) Altered intercellular communication — disruption of hormonal, neural, and paracrine signaling, including pro-aging circulating factors and ECM remodeling; (11) Chronic inflammation — sustained low-grade inflammaging driven by all upstream hallmarks, measurable by cytokine profiles; (12) Dysbiosis — age-associated loss of gut microbiome homeostasis with systemic metabolic and immune consequences.
Hallmarks share mechanisms — senescence drives SASP and inflammation; 
mitochondrial dysfunction feeds both inflammation and proteostasis failure; 
epigenetic clocks capture multi-hallmark deterioration. 
Overlap between hallmarks is expected and biologically meaningful.

## System Overview
This system automates the curation of aging-related gene lists, replacing manual literature review workflows. It is designed to produce comprehensive, well-documented outputs suitable for downstream biological analysis and experimental validation.

## Workflow Context
The system operates in two phases:

**Phase 1 - Biological Process Identification (current phase)**:
- Input: An aging hallmark name
- Output: {min_processes}-{max_processes} biological processes that comprise the hallmark
- A "biological process" is a specific molecular/cellular mechanism, not an outcome
- Examples: "DNA methylation drift", "histone deacetylase decline", "nuclear lamina deterioration"
- Bad examples: "aging", "disease", "cell death" (too vague or are outcomes, not mechanisms)

**Phase 2 - Gene Discovery**:
- For each biological process from Phase 1, discover 300-500 relevant genes
- Map genes to Gene Ontology terms
- Produce curated gene lists with evidence scores

## Your Role
You are summarizing literature search results that will be used by another LLM to identify biological processes. Your summary is critical infrastructure - if you miss relevant information, it will not appear in the final output.

Accurate citations are essential for traceability. Every downstream claim must be traceable to its source.
"""

PHASE1_CORPUS_SUMMARY_PROMPT = """{system_prompt}

## Current Task
Summarize corpus results for this research goal: {goal}

This goal is part of researching the aging hallmark: {hallmark_name}

## Corpus Results (from local literature database)
{results}

## Your Instructions

1. **Extract signal, discard noise**: Focus on biological mechanisms, gene names, pathways, molecular interactions, experimental findings. Ignore methodology details, grant numbers, author affiliations, hedging language, and generic background information.

2. **Deduplicate**: If the same fact appears multiple times from different chunks, state it once with all relevant citations combined.

3. **Cite every claim**: Use inline [PMID:xxx] citations for every factual claim.
   - Single source: [PMID:12345] Claim here.
   - Multiple sources for same claim: [PMID:111][PMID:222] Claim here.

4. **Preserve ALL signal**: Missing information is worse than extra detail. When uncertain about relevance, include it. The downstream identification LLM can filter, but it cannot recover what you omit.

5. **Be concise but complete**: Target approximately {max_words} words. No minimum required - if results are highly redundant, a brief summary is appropriate. Do not pad with unnecessary words.

6. **Preserve quantitative findings**: Include specific numbers, percentages, fold-changes, sample sizes, organism models when available.

7. **Note contradictions**: If sources disagree, mention the conflict with citations.

## Output Format
Return ONLY a JSON object with these two keys:

```json
{{
  "goal": "{goal}",
  "summary": "[PMID:12345] TP53 activity decreases 40% in aged human fibroblasts (n=50). [PMID:67890] DNA repair efficiency declines ~60% with age..."
}}
```

If no results, use empty string: "summary": ""

Return JSON only, no additional text.
"""

PHASE1_PUBMED_SUMMARY_PROMPT = """{system_prompt}

## Current Task
Summarize PubMed results for this research goal: {goal}

This goal is part of researching the aging hallmark: {hallmark_name}

## PubMed Results (from PubMed API)
{results}

## Your Instructions

1. **Extract signal, discard noise**: Focus on biological mechanisms, gene names, pathways, molecular interactions, experimental findings. Ignore methodology details, grant numbers, author affiliations, hedging language, and generic background information.

2. **Deduplicate**: If the same fact appears multiple times from different papers, state it once with all relevant citations combined.

3. **Cite every claim**: Use inline [PMID:xxx] citations for every factual claim.
   - Single source: [PMID:12345] Claim here.
   - Multiple sources for same claim: [PMID:111][PMID:222] Claim here.

4. **Preserve ALL signal**: Missing information is worse than extra detail. When uncertain about relevance, include it. The downstream identification LLM can filter, but it cannot recover what you omit.

5. **Be concise but complete**: Target approximately {max_words} words. No minimum required - if results are highly redundant, a brief summary is appropriate. Do not pad with unnecessary words.

6. **Preserve quantitative findings**: Include specific numbers, percentages, fold-changes, sample sizes, organism models when available.

7. **Note contradictions**: If sources disagree, mention the conflict with citations.

## Output Format
Return ONLY a JSON object with these two keys:

```json
{{
  "goal": "{goal}",
  "summary": "[PMID:11111] Recent study shows SIRT1 overexpression extends lifespan in mice. [PMID:22222] Contradicting findings show no effect..."
}}
```

If no results, use empty string: "summary": ""

Return JSON only, no additional text.
"""
