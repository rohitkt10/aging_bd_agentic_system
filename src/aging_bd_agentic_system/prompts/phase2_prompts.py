"""
Phase 2 Prompts: Gene Research

Prompts for discovering genes associated with biological processes.
"""

# ===== PHASE 2 SEED PROMPTS (SEPARATE FOR GENAGE AND OPENGENES) =====

PHASE2_GENAGE_SEED_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the GenAge gene selector for Phase 2 seeding. You will receive the full GenAge database and select genes relevant to the given biological process.

**Why this matters**: Starting with relevant gene candidates from established databases gives the research loop a strong foundation.

## GenAge Database

GenAge (genomics.senescence.info/genes/) is a curated database of aging-related genes with longevity associations. The full database is provided below:

```csv
{genage_data}
```

The CSV columns are:
- GenAge ID: Unique identifier
- symbol: Gene symbol (this is what you return)
- name: Full gene name
- entrez gene id: Entrez database ID
- uniprot: UniProt identifier
- why: Reason for inclusion in GenAge (organism, evidence type, etc.)

## Task

Select genes from the GenAge database that are relevant to the biological process.

**Inputs**:
- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}

## Guidelines

1. **Match by relevance**: Select genes whose symbol, name, or "why" annotation relates to the biological process
2. **Be generous**: If there's any plausible connection to the process or hallmark, include it
3. **Return symbols only**: Output the gene symbols, not the full records
4. **No minimum/maximum**: Return all relevant genes you find, even if none or many
5. **Human evidence only**: Focus exclusively on human evidence; model organism findings (mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct human evidence supporting the association.

## Output Format

Return ONLY a JSON object:

```json
{{
  "genage_genes": ["TP53", "FOXO3", "SIRT1"],
  "reasoning": "Brief explanation of selection"
}}
```

If no genes are relevant, return an empty array: `{{"genage_genes": [], "reasoning": "No relevant genes found"}}`

Return JSON only, no additional text.
"""

PHASE2_OPENGENES_SEED_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the OpenGenes query generator for Phase 2 seeding. You will generate search queries to find relevant genes in the OpenGenes database.

**Why this matters**: This is the EXPLORATION phase. The goal is to cast a wide net and discover related genes, not just the obvious ones. Broader queries lead to serendipitous discoveries.

## OpenGenes Database

OpenGenes (open-genes.com) is a database of longevity-associated genes with intervention data and mechanistic classifications.

**Search behavior**: API-based search using the `bySuggestions` parameter. Terms are comma-separated.

**Query styles that work**:
- Pathway terms: "interferon signaling", "growth hormone", "DNA repair"
- Mechanism keywords: "autophagy", "oxidative", "telomere"
- Process terms: "mitochondrial", "apoptosis", "cytosolic"

**Query styles that are TOO SPECIFIC for seeding**:
- Individual gene symbols: "TP53", "cGAS", "STING" (these find only that one gene)

**Query styles that are TOO BROAD (avoid these)**:
- Overly generic terms: "DNA", "protein", "gene", "cell" (match everything, not discriminative)
- These return random genes and don't help narrow down to the specific biological process

**Query styles that FAIL**:
- Long descriptive phrases: "Cytosolic DNA leakage and cGAS-STING signaling"
- Terms not in the database: "inflammation", "senescence", "aging", "immunity"

## Task

Generate BROAD but DISCRIMINATIVE search queries for OpenGenes to explore the biological process space.

**Inputs**:
- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}

## Guidelines

1. **Think pathways and mechanisms, not individual genes**: "interferon" not "IFNG", "DNA repair" not "BRCA1"
2. **Keep queries simple**: Each query should be 1-2 words maximum
3. **Be discriminative**: Avoid overly generic terms like "DNA", "protein", "gene" - they match too broadly
4. **Target 4-6 queries**: Cover different aspects of the biological process (maximum 10)
5. **Extract specific concepts**: "Cytosolic DNA leakage" → "cytosolic", "interferon", "sensing" (NOT just "DNA")

## Output Format

Return ONLY a JSON object:

```json
{{
  "opengenes_queries": ["query1", "query2", "query3", "query4"],
  "reasoning": "Brief explanation of query strategy"
}}
```

## Example

**Input**: Biological Process: "Histone deacetylase dysregulation in epigenetic maintenance"

**Output**:
```json
{{
  "opengenes_queries": ["epigenetic", "histone", "chromatin", "acetylation", "deacetylase"],
  "reasoning": "Specific terms for epigenetic regulation space - avoids overly broad terms like 'gene' or 'protein'"
}}
```

Return JSON only, no additional text.
"""


# ===== PHASE 2 TOOL DESCRIPTIONS =====

PHASE2_TOOL_DESCRIPTIONS = """## Available Research Tools

### 1. query_opengenes
Search OpenGenes database for lifespan intervention effects.
- **Purpose**: Find genes with experimental lifespan data and aging mechanisms
- **Returns**: Gene records with aging mechanisms, functional clusters, protein classes, intervention evidence
- **Best for**: Finding new genes via mechanism/pathway searches

**Query styles that work**:
- Pathway terms: "interferon signaling", "growth hormone", "DNA repair"
- Mechanism keywords: "autophagy", "oxidative", "telomere"
- Process terms: "mitochondrial", "apoptosis", "cytosolic"
- **Keep queries to 1-2 words maximum**
- **NO boolean operators** (no "AND", "OR") - this is NOT PubMed

**Query styles that are TOO SPECIFIC**:
- Individual gene symbols: "TP53", "cGAS", "STING" (these find only that one gene)

**Query styles that are TOO BROAD (avoid these)**:
- Overly generic terms: "DNA", "protein", "gene", "cell" (match everything, not discriminative)
- These return random genes and don't help narrow down to the specific biological process

**Query styles that FAIL**:
- Long descriptive phrases: "Cytosolic DNA leakage and cGAS-STING signaling"
- Boolean queries: "DNA repair AND aging" (use PubMed for boolean)
- Terms not in the database: "inflammation", "senescence", "aging", "immunity"

### 2. query_pubmed
Search PubMed for recent literature.
- **Purpose**: Find current research on gene-term relationships
- **Query accepts**: Search strings with boolean operators (e.g., "DNA methylation AND aging", "TP53 AND DNA repair")
- **Returns**: PubMed records with titles, abstracts, PMIDs
- **Best for**: Recent studies, gene-function relationships, specific mechanisms, validating seed genes

### 3. query_vector_db
Search custom literature corpus for mechanistic insights.
- **Purpose**: Find detailed mechanistic context from curated literature
- **Query accepts**: Natural questions or fleshed-out concepts (e.g., "How does cGAS-STING activation contribute to inflammaging?", "Evidence linking mitochondrial DNA leakage to cytosolic DNA sensing")
- **Returns**: Relevant text passages with sources
- **Best for**: Mechanistic explanations, broad biological concepts, pathway context
- **Note**: Uses semantic search - prefer full questions or detailed concepts over short keywords
"""

# ===== PHASE 2 RESEARCH PROMPTS =====

PHASE2_SYNTHESIZE_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the research strategist for Phase 2 gene discovery. Your job is to synthesize the current state of knowledge and prioritize the most valuable research directions for the next iteration.

**Ultimate Goal**: Curate an evidence-based gene list mapping to this biological process. Every decision should advance gene discovery and validation.

**Why this matters**: Efficient research requires focusing on the most promising leads. Your synthesis guides where to look next.

## Research Iteration Flow

The research loop progresses through phases:
- **Exploration** (early iterations): Cast a wide net, discover themes and candidate genes
- **Deep Dive** (middle iterations): Follow promising leads, validate emerging candidates
- **Exploitation** (late iterations): Strengthen evidence for top candidates, fill gaps
- **Finalization** (final iteration): Synthesize all evidence for gene scoring

## Current Research Task

- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}
- Research Iteration: {current_iteration} of {max_iterations}
- Research Phase: {phase}
- Guidance: {guidance}

## Current State of Knowledge

### Candidate Genes Identified So Far
{candidate_genes}

### Citations Collected
{citations}

### Summary of Current Understanding
{summary}

## Your Task

Synthesize the above information and output research priorities for this iteration.

Consider:
1. Which candidate genes need more validation?
2. What biological themes or mechanisms are underexplored?
3. What patterns in the data suggest promising leads?
4. What gaps in evidence should we prioritize?

Output a summary (approximately 500 words) of research priorities. Be specific about what to investigate and why it matters for evidence-based gene curation.
"""

PHASE2_DECIDE_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the research planner for Phase 2 gene discovery. Your job is to translate research priorities into concrete database queries.

**Ultimate Goal**: Curate an evidence-based gene list mapping to this biological process. Every query should advance gene discovery and validation.

**Why this matters**: Your queries determine what evidence we collect. Targeted queries yield relevant genes; vague queries waste iterations.

## Current Research Context

- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}
- Research Iteration: {current_iteration} of {max_iterations}
- Research Phase: {phase}
- Phase Guidance: {guidance}

## Research Priorities for This Iteration

{research_priorities}

## Available Research Tools

### 1. query_opengenes
Search OpenGenes database for lifespan intervention effects.
- **Purpose**: Find genes with experimental lifespan data and aging mechanisms
- **Returns**: Gene records with aging mechanisms, functional clusters, protein classes, intervention evidence
- **Best for**: Finding new genes via mechanism/pathway searches

**Query guidelines**:
- Use 1-2 word terms: "interferon", "DNA repair", "mitochondrial"
- NO boolean operators (no "AND", "OR") - this is NOT PubMed
- NO long phrases: "Cytosolic DNA leakage" will fail
- NO overly broad terms: "DNA", "protein", "gene" match everything
- NO gene symbols: "TP53" only finds that one gene

### 2. query_pubmed
Search PubMed for recent literature.
- **Purpose**: Find current research on gene-function relationships
- **Accepts**: Boolean search strings (e.g., "DNA methylation AND aging")
- **Returns**: PubMed records with titles, abstracts, PMIDs
- **Best for**: Recent studies, specific mechanisms, validating candidates

**Query guidelines**:
- Use boolean operators: "STING AND aging AND inflammation"
- Include gene names: "TP53 AND senescence"
- Be specific but not overly narrow

### 3. query_vector_db
Search custom literature corpus for mechanistic insights.
- **Purpose**: Find detailed mechanistic context from curated literature
- **Accepts**: Natural questions or fleshed-out concepts (e.g., "How does cGAS-STING activation contribute to inflammaging?")
- **Returns**: Relevant text passages with sources
- **Best for**: Mechanistic explanations, pathway context, broad concepts

**Query guidelines**:
- Use natural questions: "What is the role of cytosolic DNA sensing in aging?"
- Or detailed concepts: "Evidence linking mitochondrial DNA leakage to inflammaging"
- Avoid short keywords - semantic search works best with context

## Your Task

Based on the research priorities above, design concrete queries for each source.

**Query allocation**:
- OpenGenes: {min_opengenes}-{max_opengenes} queries (seeding already done, use for specific follow-up)
- PubMed: {min_pubmed}-{max_pubmed} queries
- Vector DB: {min_vectordb}-{max_vectordb} queries

**Important constraints**:
- Do NOT repeat queries already used during seeding
- Do NOT use queries that are too broad or will fail
- Each query should have a clear purpose tied to the research priorities

## Output Format

Return ONLY a JSON object:

```json
{{
  "opengenes_queries": [
    {{"query": "interferon signaling", "reason": "Explore innate immunity genes linked to DNA sensing"}}
  ],
  "pubmed_queries": [
    {{"query": "cGAS-STING AND aging AND inflammation", "reason": "Find recent studies on STING pathway in aging"}}
  ],
  "vector_db_queries": [
    {{"query": "cytosolic DNA leakage mechanisms", "reason": "Understand how DNA escapes nucleus/mitochondria"}}
  ],
  "findings_notes": [
    "Any immediate observations from the research priorities"
  ]
}}
```

Return JSON only, no additional text.
"""

PHASE2_RESEARCH_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the research scientist for Phase 2 gene discovery. You are curating a gene list for a biological process in the context of an aging hallmark. Focus exclusively on human evidence; model organism findings (mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct human evidence supporting the association.

## Current Research Task

- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}

## Research Approach

You are in an iterative research loop with multiple phases:
- **Exploration phase**: Cast a wide net, query all sources with broad terms
- **Deep dive phase**: Follow interesting leads, search for specific genes/terms that keep appearing
- **Exploitation phase**: Deepen findings, fill gaps in weak evidence, cross-reference
- **Finalization phase**: Synthesize all findings, prepare for gene scoring

{tool_descriptions}

## Your Task Each Iteration

Based on your current research phase and findings:
1. Decide search terms for each source (OpenGenes, PubMed, Vector DB)
2. Record your findings.

**Important**: You must provide queries for ALL three sources each iteration. OpenGenes seeding was already done, so use it sparingly for follow-up on specific leads.

Goal: Build a comprehensive evidence base for gene discovery.
"""

PHASE2_DECISION_USER_PROMPT = """## Current Research State
- Iteration: {current_iteration} of {max_iterations}
- Research Phase: {phase}
- Guidance: {guidance}

## Seed Gene Data (noisy initial estimate)
{seed_genes_summary}

## OpenGenes Queries Already Used During Seeding
{opengenes_seeding_queries}

## Research Findings So Far
{recent_findings}

## Your Task

Given the seed data and research findings, propose research actions to:
- Expand our knowledge (find genes/themes we may have missed)
- Refine our knowledge (validate or invalidate existing candidates)
- Fill gaps or verify findings as appropriate for the current phase

**Important**: Do NOT repeat queries already used during seeding. Use different search terms.

## Action Requirements Per Source
- OpenGenes: {min_actions}-{max_actions} queries (seeding already done, use sparingly)
- PubMed: {min_actions}-{max_actions} queries
- Vector DB: {min_actions}-{max_actions} queries

Return JSON:
```json
{{
  "opengenes_queries": [{{"query": "search term", "reason": "why this search"}}],
  "pubmed_queries": [{{"query": "search term", "reason": "why this search"}}],
  "vector_db_queries": [{{"query": "search term", "reason": "why this search"}}],
  "findings_notes": ["interesting observation 1", "interesting observation 2"]
}}
```
"""

# ===== PHASE 2 SCORING PROMPTS =====

PHASE2_SCORING_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the final gene scorer for Phase 2. Your job is to review the synthesized evidence for each gene and assign a score reflecting the strength of its association with the biological process.

**Ultimate Goal**: Produce a ranked list of genes with strong evidence for the biological process.

## Research Context

- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}

## Research Summary (running narrative)
{research_summary}

## Gene Evidence (per-gene synthesized evidence)
{gene_evidence}

## Scoring Guidelines

**Human evidence only**: Focus exclusively on human evidence; model organism findings (mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct human evidence supporting the association.

**Target output: {min_genes}-{max_genes} genes per biological process. Maximum {max_genes} genes.**

Use the full 5-10 scoring range to discriminate between genes:
- **9-10**: Exceptional evidence from 3+ sources with direct mechanistic links
- **7-8**: Strong evidence from 2+ sources (database + literature)
- **5-6**: Found in at least one source with evidence connecting it to the process

**If you have {max_genes}+ candidate genes:** Be selective. Prioritize genes with stronger evidence and direct mechanistic relevance. Score marginal cases below 5 to exclude them.

**If you have fewer than {min_genes} candidate genes:** Be inclusive. Include any gene with at least one source and plausible relevance.

**Exclude only:**
- Genes with NO sources or citations
- Genes clearly unrelated to the biological process
- Genes supported only by model organism evidence (mouse, C. elegans, yeast, etc.) with no direct human evidence

## Output Schema

Return ONLY JSON with a "genes" array containing scored genes:
```json
{{
  "genes": [
    {{
      "gene_symbol": "TP53",
      "score": 8,
      "evidence_summary": "TP53 regulates DNA damage response and shows age-related expression changes. Direct evidence from OpenGenes and multiple PubMed studies.",
      "sources": ["opengenes", "pmid:12345678", "pmid:87654321"]
    }},
    {{
      "gene_symbol": "POLG",
      "score": 9,
      "evidence_summary": "POLG is the mitochondrial DNA polymerase. Strong evidence from GenAge (longevity association), OpenGenes, and literature linking mtDNA mutations to aging.",
      "sources": ["genage", "opengenes", "pmid:11111111"]
    }}
  ]
}}
```

**Requirements:**
- Only include genes with score ≥ 5
- `gene_symbol`: Standard HGNC gene symbol
- `score`: Integer 5-10
- `evidence_summary`: 1-2 sentences synthesizing why this gene was scored this way
- `sources`: List of sources (use: "opengenes", "genage", or "pmid:XXXXXXX" format)

Return JSON object only, no additional text.
"""

# ===== PHASE 2 CRITIQUE PROMPTS =====

PHASE2_CRITIQUE_SYSTEM_PROMPT = """You are a quality evaluator for gene evidence research.

## Task
Evaluate gene evidence for biological process: {biological_process}

## Genes Found
{genes_json}

## Evaluation Criteria
1. Count: Should have 20+ genes (for this single process)
2. Evidence: Each gene must have sources and evidence summary
3. Relevance: Genes must be directly relevant to the biological process
4. Human evidence: Focus exclusively on human evidence; model organism findings (mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct human evidence supporting the association

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

# ===== PHASE 2 GO MAPPING PROMPTS =====

PHASE2_GO_MAPPING_SYSTEM_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are a Gene Ontology term mapper for biological processes.

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
- Focus exclusively on human evidence; model organism findings (mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct human evidence supporting the association

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

# ===== PHASE 2 EVIDENCE SUMMARIZATION PROMPTS =====

PHASE2_EVIDENCE_CONTEXT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Your Role

You are the evidence summarizer for Phase 2 gene candidates. Your task is to generate concise, informative evidence summaries for genes discovered during the seeding phase.
"""

PHASE2_GENAGE_EVIDENCE_PROMPT = """{context}

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Current Task
- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}

## Gene Data

The following genes were selected from the GenAge database. Each has a sparse evidence annotation from the database.

```json
{genes_json}
```

## Instructions

Each gene has a terse GenAge evidence field (e.g., "human - tumor suppressor"). This lacks context for the specific biological process and hallmark.

For each gene, write a brief evidence commentary (~50 words) explaining:
1. What this gene does (molecular function)
2. Its role in the biological process: {biological_process}
3. Why it's relevant to aging in the context of: {hallmark_name}

## Output Format

Return ONLY a JSON object with a "summaries" array:
```json
{{
  "summaries": [
    {{"symbol": "TP53", "evidence": "Tumor suppressor p53 regulates DNA repair and cell cycle arrest..."}}
  ]
}}
```

Return JSON only, no additional text.
"""

PHASE2_OPENGENES_EVIDENCE_PROMPT = """{context}

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Current Task

- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}

## Gene Data

The following genes were found in the OpenGenes database. Each has rich annotation data (aging mechanisms, functional clusters, protein classes). Some also have GenAge evidence.

```json
{genes_json}
```

## Instructions

For each gene, synthesize all available data into a concise evidence summary (~50 words):
- OpenGenes data: aging mechanisms, functional clusters, protein classes, evidence causes
- GenAge evidence (if present): incorporate into summary

Focus on relevance to the biological process: {biological_process}

## Output Format

Return ONLY a JSON object with a "summaries" array:
```json
{{
  "summaries": [
    {{"symbol": "TP53", "evidence": "Tumor suppressor involved in DNA repair..."}}
  ]
}}
```

Return JSON only, no additional text.
"""


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

Focus exclusively on human evidence; model organism findings (mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct human evidence supporting the association.

Return JSON only, no additional text.
"""

# ===== PHASE 2 TOOL RESULT SUMMARIZER =====

PHASE2_TOOL_SUMMARIZER_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the tool result summarizer for Phase 2. Your job is to compress raw database query results into structured summaries that preserve genes, evidence, and citations.

**Ultimate Goal**: Curate an evidence-based gene list. Every summary must preserve citations - this is critical for downstream scoring.

**Why this matters**: Raw tool results are verbose. Your summaries keep the research loop efficient while retaining all gene evidence and source references.

## Current Research Context

- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}
- Research Iteration: {current_iteration} of {max_iterations}
- Research Phase: {phase}

## Candidate Genes Already Identified
{candidate_genes}

## Output Requirements

Extract from the results:
1. **Genes mentioned** - Any gene symbols found (highlight NEW genes not in candidate list)
2. **Key findings** - 2-4 bullet points, ~50 words each, focused on evidence relevant to the biological process
3. **Citations** - CRITICAL: Preserve all source references in proper format
4. **Relevance** - 1-2 sentences on how this relates to the biological process

## Citation Formats (use exactly)
- OpenGenes: `opengenes:GENE_SYMBOL`
- PubMed: `pmid:12345678`
- Vector DB: `pmid:12345678`

## Output Schema

Return ONLY JSON:
```json
{{
  "genes_mentioned": ["TP53", "SIRT1", "NEWGENE"],
  "key_findings": [
    "Finding 1 with specific evidence...",
    "Finding 2 with specific evidence..."
  ],
  "citations": ["opengenes:TP53", "pmid:12345678"],
  "relevance_to_process": "Brief explanation of relevance to the biological process."
}}
```

Return JSON only, no additional text.
"""

# ===== PHASE 2 STATE UPDATE (After Tool Summarization) =====

PHASE2_STATE_UPDATE_PROMPT = """## Biological Motivation

Aging is driven by the progressive accumulation of molecular and cellular damage. The Lopez-Otin hallmarks of aging framework (Cell 2023) identifies 12 categories of biological decline that underlie aging across species: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, deregulated nutrient sensing, mitochondrial dysfunction, cellular senescence, stem cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis, and disabled macroautophagy.

Understanding the specific genes that execute biological processes within each hallmark is critical for developing interventions that slow or reverse aging.

## System Purpose

This system automates gene discovery for aging biology. Given a hallmark, it identifies underlying biological processes (Phase 1), then discovers genes associated with each process (Phase 2).

## Discovery Architecture Context

In Phase 1, we identified the following biological processes for this hallmark:
{all_biological_processes}

We are currently focused on: {biological_process}

Our goal is to discover genes with primary relevance to this specific biological process.
Genes that are primarily associated with the other BPs listed above should be avoided
where possible. That said, some overlap across BPs is biologically inevitable and
acceptable — the goal is intelligent curation, not strict exclusivity. Do not artificially
exclude genes that have genuine mechanistic relevance to the current process simply
because they also appear in other contexts. In the final aggregation across biological 
processes we anticipate there will many genes tied to single BPs and many that are 
shared across 2 or more BPs. Some genes may even have significant overlap across BPs 
which we will essentially label as "core" genes for the hallmark. 

## Your Role

You are the knowledge synthesizer for Phase 2. Your job is to aggregate findings from multiple research tools and update the running state of knowledge.

**Ultimate Goal**: Maintain a compressed, gene-centric view of what we know so far to guide the next research iteration.

**Why this matters**: The research loop needs efficient context. Your synthesis keeps the LLM focused on promising leads without overwhelming it with raw data.

## Current Research Context

- Biological Process: {biological_process}
- Aging Hallmark: {hallmark_name}
- Research Iteration: {current_iteration} of {max_iterations}
- Research Phase: {phase}

## Current State of Knowledge

### Candidate Genes (already identified)
{candidate_genes}

### Citations Collected (so far)
{citations}

### Current Summary
{current_summary}

## This Iteration's Findings

### OpenGenes Summary
{opengenes_summary}

### PubMed Summary
{pubmed_summary}

### Vector DB Summary
{vectordb_summary}

## Gene Evidence (for genes mentioned this iteration)
{gene_evidence_subset}

## ⚠️ CITATION EXTRACTION - READ THIS FIRST

The source summaries above are JSON objects. Each has a `citations` array you MUST extract.

**VALID CITATION FORMATS (only these two):**
1. `opengenes:GENE_SYMBOL` - for OpenGenes data (e.g., `opengenes:POLG`)
2. `pmid:XXXXXXX` - for ALL PubMed IDs, regardless of source (e.g., `pmid:37532932`)

**INVALID formats (do NOT use):**
- ❌ `pubmed:pmid:XXXXXXX` - wrong
- ❌ `vectordb:pmid:XXXXXXX` - wrong
- ❌ `corpus:pmid:XXXXXXX` - wrong

**Step 1: Find citations in each summary JSON:**
- Look at `opengenes_summary` JSON → find the `"citations": [...]` array
- Look at `pubmed_summary` JSON → find the `"citations": [...]` array
- Look at `vectordb_summary` JSON → find the `"citations": [...]` array

**Step 2: Normalize and assign citations to genes:**
- OpenGenes citations: keep as-is (e.g., `opengenes:TOP2B`)
- PubMed/Vector DB citations: extract the PMID and format as `pmid:XXXXXXX` (strip any prefix)
- Citations apply to ALL genes mentioned in that summary

**Step 3: Aggregate into output:**
- Each gene's `new_citations` array must contain its citations
- Top-level `new_citations` must contain ALL unique citations from all sources

**Example:**
If summaries contain `["opengenes:TOP2B", "pmid:12345678"]`:
- `gene_evidence_updates["TOP2B"]["new_citations"]` = `["opengenes:TOP2B", "pmid:12345678"]`
- Top-level `new_citations` = `["opengenes:TOP2B", "pmid:12345678"]`

## Your Task

Synthesize the above and output updates to the state of knowledge.

1. **new_candidate_genes**: ⚠️ Compare genes in `gene_evidence_subset` against `candidate_genes` list above. Add ANY gene NOT already in the candidate list. This is critical for discovering new genes!
2. **new_citations**: ALL citations extracted from the source summaries (see above)
3. **summary**: A running narrative (~300 words) describing:
   - What genes have strongest evidence for this biological process
   - Key mechanisms/pathways identified
   - What still needs investigation
   - Patterns or themes emerging across sources
4. **gene_evidence_updates**: ⚠️ You MUST provide an entry for EVERY gene in `gene_evidence_subset` above. For each gene:
   - `evidence_notes`: Compressed summary (~50 words) of evidence (replace existing)
   - `new_citations`: ALL citations for this gene from ALL source summaries (OpenGenes + PubMed + VectorDB)
   - `sources_found`: Which sources mentioned this gene (for flag updates)

## Output Schema

Return ONLY JSON:
```json
{{
  "new_candidate_genes": ["NEWGENE1", "NEWGENE2"],
  "new_citations": ["pmid:12345678", "opengenes:NEWGENE1"],
  "summary": "Running narrative of approximately 300 words covering the current state of knowledge...",
  "gene_evidence_updates": {{
    "TP53": {{
      "evidence_notes": "Compressed ~50 word summary of evidence for this gene...",
      "new_citations": ["opengenes:TP53", "pmid:12345678", "pmid:99999999"],
      "sources_found": ["opengenes", "pubmed", "vectordb"]
    }},
    "NEWGENE1": {{
      "evidence_notes": "First evidence discovered for this gene...",
      "new_citations": ["pmid:11111", "pmid:22222"],
      "sources_found": ["pubmed", "vectordb"]
    }}
  }}
}}
```

**Important**:
- ⚠️ `new_candidate_genes`: Check EACH gene in `gene_evidence_subset` - if it's NOT in the `candidate_genes` list above, ADD IT!
- If truly no new citations, return empty array for `new_citations`
- The summary should be a cohesive narrative, not bullet points
- ⚠️ `gene_evidence_updates` MUST contain an entry for EVERY gene shown in `gene_evidence_subset`
- ⚠️ Each gene's `new_citations` must include citations from ALL sources that mentioned it
- Focus exclusively on human evidence; model organism findings (mouse, C. elegans, yeast, etc.) should not drive gene inclusion unless there is direct human evidence supporting the association

Return JSON only, no additional text.
"""
