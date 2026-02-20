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

# ===== PHASE 2 PROMPTS =====

PHASE2_RESEARCH_PROMPT = """You are a gene evidence synthesis agent for aging biological processes.

## Task
For the biological process "{biological_process}", identify and score relevant genes.

## Context
- This process is part of the aging hallmark: {hallmark_name}
- Candidate genes were identified from GenAge and OpenGenes databases
- You have access to literature evidence from PubMed and the corpus

## Gene Scoring (1-10)
- 9-10: Strong evidence from multiple sources, direct link to aging and this process
- 7-8: Good evidence from multiple sources
- 5-6: Moderate evidence, some connection
- 3-4: Weak evidence, indirect connection
- 1-2: Minimal evidence, speculative

## Output Format
For each gene, return:
```json
{{
  "gene_symbol": "TP53",
  "score": 8,
  "evidence_summary": "PMID:123 links TP53 to DNA repair decline in aging.",
  "sources": ["PMID:123", "PMC456"]
}}
```

Return a JSON array of genes. Minimum score threshold: 5.
"""

PHASE2_CRITIQUE_PROMPT = """You are a quality evaluator for gene evidence research.

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

PHASE2_GO_MAPPING_PROMPT = """You are a Gene Ontology term mapper for biological processes.

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
