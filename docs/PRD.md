# PRD: Aging Hallmarks Gene Curation System

## Overview
Automated system to curate gene lists for aging hallmarks using agentic research with full traceability.

## Goals
- Identify 10-15 biological processes per hallmark
- Find 300-500 genes with evidence scores
- Map 50-80 GO biological process terms
- Maintain full audit trail of sources and reasoning

## Architecture

### Phase 1: Biological Process Identification
**Input:** Hallmark name (e.g., "epigenetic alterations")

**Process:**
1. Load Lopez-Otin hallmarks paper as context
2. Query vector DB + PubMed for hallmark-specific literature
3. Synthesize 10-15 biological processes
4. Rank by evidence strength (1-10 scale)

**Output:** `processes.tsv` with columns: rank, process_name, evidence_score, evidence_summary

### Phase 2: Gene Research (ReAct Loop)
**For each BP from Phase 1:**

**Agent:** Gemini 3 with reasoning via Vertex AI

**Tools:**
- `query_vector_db`: Search FAISS index (data/corpus/index)
- `query_pubmed`: Search PubMed API
- `query_genage`: Search GenAge CSV
- `query_opengenes`: Search Open Genes CSV  
- `query_go_terms`: Search go-basic.json for BP terms

**State Tracked:**
- Current BP being researched
- Genes found with scores/sources
- GO terms mapped
- Research scratchpad

**Process per BP:**
1. Query local databases for candidate genes
2. Search literature for evidence
3. Score genes 1-10 based on evidence strength
4. Find matching GO BP terms (filter: meta.basicPropertyValues.val == "biological_process")
5. Document all sources

**Context Management:**
- Summarize when >50K tokens
- Keep recent tool results + scratchpad + gene list

**Aggregation:**
- Merge genes across all BPs
- Deduplicate using max score
- Final list: 300-500 genes, 50-80 GO terms

**Outputs:**
- `genes.tsv`: rank, gene_symbol, score, biological_process, evidence_summary
- `go_terms.tsv`: go_id, go_label, biological_process

## Validation Rules
- Gene count: 300-500
- GO term count: 50-80
- All scores: 1-10 range
- All entries have source citations
- Only genes with score >5 included

## Data Sources

**Local:**
- Lopez-Otin paper: `data/lopez_otin.md`
- Vector DB: `data/corpus/index/` (FAISS + index.meta.json + lookup.jsonl)
- GO terms: `data/go-basic.json`
- GenAge: `data/genage.csv`
- Open Genes: `data/opengenes.csv`

**External:**
- PubMed API

## Implementation Notes
- LangGraph for agent orchestration
- Gemini 3 reasoning for better research decisions
- Full logging of tool calls and reasoning
- Checkpointing for resume capability
- State schema: TBD during implementation

## Success Criteria
- Complete one hallmark end-to-end
- All outputs meet validation rules
- Full audit trail available
- Reproducible results# PRD: Aging Hallmarks Gene Curation System

## Overview
Automated system to curate gene lists for aging hallmarks using agentic research with full traceability.

## Goals
- Identify 10-15 biological processes per hallmark
- Find 300-500 genes with evidence scores
- Map 50-80 GO biological process terms
- Maintain full audit trail of sources and reasoning

## Architecture

### Phase 1: Biological Process Identification
**Input:** Hallmark name (e.g., "epigenetic alterations")

**Process:**
1. Load Lopez-Otin hallmarks paper as context
2. Query vector DB + PubMed for hallmark-specific literature
3. Synthesize 10-15 biological processes
4. Rank by evidence strength (1-10 scale)

**Output:** `processes.tsv` with columns: rank, process_name, evidence_score, evidence_summary

### Phase 2: Gene Research (ReAct Loop)
**For each BP from Phase 1:**

**Agent:** Gemini 3 with reasoning via Vertex AI

**Tools:**
- `query_vector_db`: Search FAISS index (data/corpus/index)
- `query_pubmed`: Search PubMed API
- `query_genage`: Search GenAge CSV
- `query_opengenes`: Search Open Genes CSV  
- `query_go_terms`: Search go-basic.json for BP terms

**State Tracked:**
- Current BP being researched
- Genes found with scores/sources
- GO terms mapped
- Research scratchpad

**Process per BP:**
1. Query local databases for candidate genes
2. Search literature for evidence
3. Score genes 1-10 based on evidence strength
4. Find matching GO BP terms (filter: meta.basicPropertyValues.val == "biological_process")
5. Document all sources

**Context Management:**
- Summarize when >50K tokens
- Keep recent tool results + scratchpad + gene list

**Aggregation:**
- Merge genes across all BPs
- Deduplicate using max score
- Final list: 300-500 genes, 50-80 GO terms

**Outputs:**
- `genes.tsv`: rank, gene_symbol, score, biological_process, evidence_summary
- `go_terms.tsv`: go_id, go_label, biological_process

## Validation Rules
- Gene count: 300-500
- GO term count: 50-80
- All scores: 1-10 range
- All entries have source citations
- Only genes with score >5 included

## Data Sources

**Local:**
- Lopez-Otin paper: `data/lopez_otin.md`
- Vector DB: `data/corpus/index/` (FAISS + index.meta.json + lookup.jsonl)
- GO terms: `data/go-basic.json`
- GenAge: `data/genage.csv`
- Open Genes: `data/opengenes.csv`

**External:**
- PubMed API

## Implementation Notes
- LangGraph for agent orchestration
- Gemini 3 reasoning for better research decisions
- Full logging of tool calls and reasoning
- Checkpointing for resume capability
- State schema: TBD during implementation

## Success Criteria
- Complete one hallmark end-to-end
- All outputs meet validation rules
- Full audit trail available
- Reproducible results