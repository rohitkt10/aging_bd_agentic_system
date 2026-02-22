"""
Prompt templates for the deep research system.

All prompts should be defined here with clear documentation on:
- Expected inputs (variables)
- Expected outputs (structure)
- When to use the prompt
"""

# ===== PHASE 1 PROMPTS =====

PHASE1_SYSTEM_PROMPT = """You are an expert biological process identifier for aging hallmark curation.

## Task
Identify 10-15 biological processes that comprise the hallmark: {hallmark_name}

## Context
- Lopez-Otin hallmarks paper (Cell 2023) is provided as reference
- Use this as your primary source for understanding the hallmark

## Process Criteria
- Each process must be mechanistically distinct (no overlap)
- Focus on molecular/cellular mechanisms, not outcomes
- Examples: "DNA methylation changes", "Histone modification alterations"
- Bad examples: "Cellular aging" (too broad), "Disease" (outcome not mechanism)

## Evidence Scoring (1-10)
- 9-10: Extensively documented, core mechanism in Lopez-Otin + multiple external sources
- 7-8: Well-supported, mentioned in Lopez-Otin or similar reviews
- 5-6: Moderate evidence, multiple studies
- 3-4: Limited evidence, speculative
- 1-2: Minimal evidence, highly speculative

## Output Format
Return ONLY a JSON list of processes:
```json
[
  {{
    "process_name": "DNA methylation changes",
    "evidence_score": 9,
    "evidence_summary": "Supported by Lopez-Otin et al. 2023 and 15 papers on epigenetic clocks.",
    "sources": ["Lopez-Otin", "PMID:12345"]
  }}
]
```

Requirements:
- Exactly 10-15 processes
- Each evidence_summary must cite sources
- Scores are integers 1-10
- Return JSON only, no additional text
"""

PHASE1_CRITIQUE_PROMPT = """You are a quality evaluator for biological process identification.

## Task
Evaluate the following list of biological processes for the hallmark: {hallmark_name}

## Processes to Evaluate
{processes_json}

## Evaluation Criteria
1. Count: Must have 10-15 distinct processes
2. Evidence: Each process must have sources and evidence summary
3. Distinctness: No overlapping or duplicate processes
4. Specificity: Processes are mechanisms, not outcomes

## Count Adjustment (CRITICAL)
- If count < 10: You MUST suggest specific processes to SPLIT into narrower concepts
  - Example: "Split 'DNA methylation changes' into 'DNA hypermethylation' and 'DNA hypomethylation'"
  - Example: "Split 'mitochondrial dysfunction' into 'mitochondrial DNA damage' and 'mitochondrial biogenesis decline'"
- If count > 15: You MUST suggest specific processes to MERGE
  - Example: "Merge 'histone acetylation alterations' and 'histone methylation alterations' into 'histone modification alterations'"
  - Example: "Merge 'autophagy impairment' and 'mitophagy decline' into 'autophagy pathway dysfunction'"

## Output Format
Return ONLY JSON:
```json
{{
  "grade": "pass|fail",
  "comment": "brief explanation",
  "missing_themes": ["theme1", "theme2"],
  "follow_up_queries": ["query1", "query2"],
  "split_instructions": ["Split X into A and B", ...],
  "merge_instructions": ["Merge X and Y into Z", ...]
}}
```

Rules for split_instructions:
- Only provide if count < 10
- Each instruction should clearly state: "Split 'process_name' into 'new_name_1' and 'new_name_2'"
- Choose processes that are conceptually broad enough to split
- Split into biologically meaningful sub-processes

Rules for merge_instructions:
- Only provide if count > 15
- Each instruction should clearly state: "Merge 'process_1' and 'process_2' into 'merged_name'"
- Choose processes that are overlapping or highly related
- The merged name should be inclusive and biologically accurate

Return JSON only, no additional text.
"""

# ===== PHASE 1 PLANNING PROMPT =====

PHASE1_PLAN_SYSTEM_PROMPT = """You are an expert research planner for aging biology.

## Task
Create a research plan to identify biological processes for the aging hallmark: {hallmark_name}

## Available Research Tools
You have access to these tools for conducting research:

### 1. query_vector_db
- Searches a curated literature corpus (aging-related papers)
- Good for: mechanistic explanations, broad biological concepts, pathway context
- Query accepts: biological concepts, processes, or phrases (e.g., "autophagy", "DNA methylation")

### 2. query_pubmed
- Searches PubMed for recent scientific literature
- Good for: recent studies, specific mechanisms, gene-function relationships
- Query accepts: search strings with boolean operators (e.g., "DNA methylation AND aging")

## Your Goal
Generate {min_goals}-{max_goals} research goals. For each goal, suggest specific search terms for both tools.

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
      "vector_db_terms": ["DNA methylation aging", "epigenetic clock"],
      "pubmed_terms": ["DNA methylation AND aging AND mechanism"]
    }}
  ]
}}
```

Return JSON only, no additional text.
"""

# ===== PHASE 1 CRITIC PROMPTS (TWO-STEP) =====

PHASE1_CRITIC_UNSTRUCTURED_PROMPT = """You are a quality evaluator reviewing biological processes for the aging hallmark: {hallmark_name}

## Context
- This is iteration {current_iteration} of {max_iterations}
- A "pass" grade means no more refinement is needed
- If this is the last iteration ({max_iterations}), be practical about what can be achieved

## Processes to Review
{processes_json}

## Your Task
Write a brief critique (~100 words) of this list. Consider:
- Are there obvious gaps or missing themes?
- Is there redundancy or overlap?
- Is evidence quality adequate?
- Are these mechanistic processes (not outcomes)?

Be direct and actionable. This is a first pass, so some rough edges are expected.
"""

PHASE1_CRITIC_STRUCTURED_PROMPT = """Based on the following critique of biological processes, extract structured recommendations.

## Critique
{critique_text}

## Processes Being Reviewed
{processes_json}

## Your Task
Parse the critique and output structured tool recommendations for refinement.

## Output Format
Return ONLY JSON:
```json
{{
  "grade": "pass|fail",
  "vector_db_queries": ["query1", "query2"],
  "pubmed_queries": ["query1", "query2"],
  "focus_areas": ["area needing more research", "another area"]
}}
```

Rules:
- grade "pass" if the list is adequate (even if not perfect)
- Only provide queries if grade is "fail"
- Queries should be specific and actionable
- focus_areas describe what needs more research (not search terms)

Return JSON only, no additional text.
"""

# ===== PHASE 2 TOOL DESCRIPTIONS =====

# Detailed tool descriptions for LLM decision-making
PHASE2_TOOL_DESCRIPTIONS = """## Available Research Tools

### 1. query_genage
Search GenAge database for aging-associated genes.
- **Purpose**: Find genes with documented aging associations
- **Query accepts**: Gene symbols (e.g., "TP53", "FOXO3") or keywords (e.g., "DNA repair", "mitophagy")
- **Returns**: Gene records with evidence annotations
- **Best for**: Known aging genes, longevity associations, genetic interventions

### 2. query_opengenes
Search OpenGenes database for lifespan intervention effects.
- **Purpose**: Find genes with experimental lifespan data
- **Query accepts**: Gene symbols (e.g., "GHR", "INS") or keywords (e.g., "insulin signaling", "growth hormone")
- **Returns**: Gene records with aging mechanisms, functional clusters, protein classes, intervention evidence
- **Best for**: Intervention studies, functional classifications, mechanism annotations

### 3. query_pubmed
Search PubMed for recent literature.
- **Purpose**: Find current research on gene-term relationships
- **Query accepts**: Gene names, biological processes, MeSH terms, or search strings (e.g., "TP53 DNA methylation aging", "sirtuans lifespan")
- **Returns**: PubMed records with titles, abstracts, PMIDs
- **Best for**: Recent studies, gene-function relationships, specific mechanisms

### 4. query_vector_db
Search custom literature corpus for mechanistic insights.
- **Purpose**: Find detailed mechanistic context from curated literature
- **Query accepts**: Biological concepts, processes, or phrases (e.g., "autophagy", "cellular senescence", "mitochondrial biogenesis")
- **Returns**: Relevant text passages with sources
- **Best for**: Mechanistic explanations, broad biological concepts, pathway context
"""

# ===== PHASE 2 PROMPTS =====

# PHASE2_RESEARCH_SYSTEM_PROMPT: System prompt for research loop iterations
# Used in phase2_research() to guide the LLM during each iteration
PHASE2_RESEARCH_SYSTEM_PROMPT = """You are a gene research scientist conducting autonomous research on a biological process related to aging.

## Your Objective
Research and identify genes relevant to: {biological_process}
This is part of the aging hallmark: {hallmark_name}

## Research Approach
You are in an iterative research loop with multiple phases:
- **Exploration phase**: Cast a wide net, query all sources with broad terms
- **Deep dive phase**: Follow interesting leads, search for specific genes/terms that keep appearing
- **Exploitation phase**: Deepen findings, fill gaps in weak evidence, cross-reference
- **Finalization phase**: Synthesize all findings, score genes, return final results

{tool_descriptions}

## Your Task Each Iteration
Based on your current research phase and findings:
1. Decide which tool(s) to query
2. Decide what search terms to use
3. Record your findings
4. Build on previous findings (don't repeat the same searches)

Focus on discovering genes with strong evidence for relevance to {biological_process} in the context of aging.
"""

# PHASE2_DECISION_USER_PROMPT: User prompt for getting LLM decisions on what to research
# Used in phase2_research() to get structured decisions from LLM
PHASE2_DECISION_USER_PROMPT = """## Current Research State
- Iteration: {current_iteration} of {max_iterations}
- Research Phase: {phase}
- Guidance: {guidance}

## Candidates Identified So Far
{candidates_summary}

## Recent Findings
{recent_findings}

## Your Task
Based on the current research phase ({phase}), decide what to research next.

Return JSON:
```json
{{
  "actions": [
    {{"source": "genage|opengenes|pubmed|vector_db", "query": "search term", "reason": "why this search"}}
  ],
  "findings_notes": ["interesting observation 1", "interesting observation 2"]
}}
```

Be specific with your queries. Use {min_actions}-{max_actions} actions per iteration.
"""

# PHASE2_SCORING_SYSTEM_PROMPT: System prompt for final gene scoring
# Used in phase2_research() final iteration to score genes based on research findings
PHASE2_SCORING_SYSTEM_PROMPT = """You are a gene research scientist finalizing evidence synthesis for an aging biological process.

## Task
Analyze research findings and identify genes with strong evidence for the biological process: {biological_process}

This process is part of the aging hallmark: {hallmark_name}

## Research Context
You have completed an autonomous research loop querying:
- GenAge database (longevity associations)
- OpenGenes database (intervention effects)
- PubMed literature (recent studies)
- Custom literature corpus (mechanistic insights)

## Gene Scoring Rubric (1-10)
- 9-10: Strong evidence from multiple sources, direct link to aging and this process
- 7-8: Good evidence from multiple sources
- 5-6: Moderate evidence, some connection
- 3-4: Weak evidence, indirect connection
- 1-2: Minimal evidence, speculative

## Output Requirements
Return ONLY a JSON array of genes with score 5+:
```json
[
  {{
    "gene_symbol": "TP53",
    "score": 8,
    "evidence_summary": "PMID:123 links TP53 to DNA repair decline in aging.",
    "sources": ["PMID:123", "GenAge"]
  }}
]
```

Each gene must include:
- gene_symbol: Standard gene symbol
- score: Integer 1-10 (only include genes with score 5+)
- evidence_summary: 2-3 sentences synthesizing evidence
- sources: List of PMIDs, database names, or corpus references
"""

# PHASE2_CRITIQUE_SYSTEM_PROMPT: System prompt for evaluating gene research quality
# Used in phase2_critic() to evaluate if sufficient genes were found
PHASE2_CRITIQUE_SYSTEM_PROMPT = """You are a quality evaluator for gene evidence research.

## Task
Evaluate gene evidence for biological process: {biological_process}

## Genes Found
{genes_json}

## Evaluation Criteria
1. Count: Should have 20+ genes (for this single process)
2. Evidence: Each gene must have sources and evidence summary
3. Relevance: Genes must be directly relevant to the biological process

## Output Format
Return ONLY JSON:
```json
{{
  "grade": "pass|fail",
  "comment": "brief explanation",
  "follow_up_queries": ["query1", "query2"]
}}
```

Return JSON only, no additional text.
"""

# PHASE2_GO_MAPPING_SYSTEM_PROMPT: System prompt for mapping GO terms to biological processes
# Used in map_go_terms() to score relevance of GO terms
PHASE2_GO_MAPPING_SYSTEM_PROMPT = """You are a Gene Ontology term mapper for biological processes.

## Task
Find GO biological process terms related to: {biological_process}

## Context
- This is part of aging hallmark: {hallmark_name}
- GO terms must have namespace "biological_process"
- Return the most relevant terms (relevance score 6+)

## GO Term Scoring (1-10)
- 9-10: Exact match or core concept
- 7-8: Highly relevant
- 5-6: Moderately relevant
- 1-4: Weakly related

## Output Format
Return JSON array:
```json
{{
  "go_id": "GO:0006915",
  "go_label": "apoptotic process",
  "relevance_score": 8,
  "evidence_summary": "Directly related to programmed cell death in aging."
}}
```

Return JSON only, no additional text.
"""

# ===== PHASE 2 CONTEXT SUMMARIZATION PROMPTS =====

# PHASE2_ACTIONABILITY_SUMMARY_PROMPT: User prompt for mid-loop context summarization
# Used in summarize_for_actionability() to create focused view for "what to research next"
PHASE2_ACTIONABILITY_SUMMARY_PROMPT = """You are a research context analyzer for an autonomous gene discovery system.

## Task
Summarize the research data to help the LLM decide what to research NEXT.

## Research Data
{research_data_json}

## Your Goal
Create an actionability-focused summary that identifies:
1. Top 10-15 most promising candidate genes (ranked by confidence)
2. Top 20-30 high-value findings (scored by actionability)
3. Research gaps (genes/themes mentioned but not deeply explored)
4. Covered topics (what has been well-researched)

## Ranking Criteria
- **Confidence 9-10**: Genes from GenAge/OpenGenes seeds + multiple corroborating findings
- **Confidence 7-8**: Genes from seeds OR multiple mentions in findings
- **Confidence 5-6**: Genes with 2-3 supporting findings
- **Confidence 1-4**: Genes with single/weak findings

- **Value Score 9-10**: Critical mechanistic insights, direct links to aging
- **Value Score 7-8**: Strong supporting evidence, clear relevance
- **Value Score 5-6**: Moderate evidence, somewhat relevant
- **Value Score 1-4**: Weak or tangential findings

## Output Format
Return ONLY JSON:
```json
{{
  "top_candidates": [
    {{"symbol": "TP53", "source": "genage", "confidence": 8, "key_evidence": "DNA repair, longevity association"}}
  ],
  "high_value_findings": [
    {{"gene": "TP53", "source": "pubmed", "finding": "Direct link to DNA repair pathway", "value_score": 9}}
  ],
  "research_gaps": ["Mitochondrial mechanisms not explored"],
  "covered_topics": ["DNA repair", "Cell cycle"],
  "iteration_state": {{
    "current_iteration": 3,
    "total_candidates": 45,
    "total_findings": 234
  }}
}}
```

Return JSON only, no additional text.
"""

# PHASE2_SCORING_SUMMARY_PROMPT: User prompt for pre-scoring evidence aggregation
# Used in summarize_for_scoring() to aggregate ALL evidence for comprehensive ranking
PHASE2_SCORING_SUMMARY_PROMPT = """You are an evidence synthesis specialist for gene research.

## Task
Synthesize ALL research findings into a comprehensive evidence summary for gene scoring.

## Biological Process
{biological_process}

## Research Data
{research_data_json}

## Your Goal
Aggregate ALL evidence for each candidate gene, including:
1. All supporting evidence from all sources (GenAge, OpenGenes, PubMed, Vector DB)
2. Evidence strength classification (strong/moderate/weak)
3. Cross-source corroboration (mentioned in 2+ sources?)
4. Contradicting evidence (don't hide negative findings)
5. Aggregate evidence strength score (1-10)

## Evidence Strength Classification
- **Strong**: Direct experimental evidence, multiple studies, clear mechanistic link
- **Moderate**: Correlational evidence, single study, indirect link
- **Weak**: Speculative, tangential, minimal data

## Aggregate Scoring (1-10)
- **9-10**: Strong multi-source evidence, direct mechanistic link
- **7-8**: Strong single-source OR moderate multi-source evidence
- **5-6**: Moderate single-source evidence
- **3-4**: Weak single-source evidence
- **1-2**: Minimal/speculative evidence

## Output Format
Return ONLY JSON:
```json
{{
  "candidate_evidence": [
    {{
      "gene_symbol": "TP53",
      "supporting_evidence": [
        {{"source": "genage", "finding": "Longevity association", "strength": "strong", "pmid_or_ref": "GenAge entry"}},
        {{"source": "pubmed", "finding": "Direct link to DNA repair", "strength": "strong", "pmid_or_ref": "PMID:12345"}}
      ],
      "contradicting_evidence": [],
      "cross_source_corroboration": true,
      "evidence_strength_score": 9
    }}
  ],
  "evidence_summary": "Found 15 genes with strong multi-source evidence.",
  "total_genes_with_evidence": 15,
  "total_sources_queried": 4
}}
```

IMPORTANT: Process ALL findings. Do not truncate or limit.

Return JSON only, no additional text.
"""
