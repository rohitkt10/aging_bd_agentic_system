# Codebase Component Descriptions

## src/aging_bd_agentic_system/tools/
**Purpose:** Tool definitions that agents can call during research

**vector_db.py**
- Queries FAISS index in data/corpus/index/
- Takes search query string, returns relevant paper chunks with metadata
- Uses lookup.jsonl to map index results to source papers

**pubmed.py**
- Searches PubMed API for papers
- Takes query string + optional filters (date range, max results)
- Returns titles, abstracts, PMIDs, publication info

**genage.py**
- Queries GenAge CSV (data/databases/genage.csv)
- Takes gene name or biological process keywords
- Returns matching aging-related genes with annotations

**opengenes.py**
- Queries Open Genes CSV (data/databases/opengenes.csv)
- Takes gene name or process keywords
- Returns longevity genes with associated pathways/functions

**go_terms.py**
- Queries go-basic.json (data/go-basic.json)
- Searches by definition text (meta.definition.val field)
- Filters for biological_process type only
- Returns GO ID and label for matching terms

## src/aging_bd_agentic_system/agents/
**Purpose:** Agent logic and behavior definitions

**phase1_bp_identifier.py**
- Agent that identifies biological processes for a hallmark
- Loads Lopez-Otin paper as context
- Uses vector_db and pubmed tools to research the hallmark
- Synthesizes 10-15 processes with evidence scores
- Returns structured data for processes.tsv output

**phase2_gene_researcher.py**
- ReAct agent that researches genes for each biological process
- Autonomously decides which tools to call and when
- Maintains research scratchpad in state
- Scores genes 1-10 based on evidence
- Maps genes to GO BP terms
- Handles context summarization when token limit approached
- Returns gene lists and GO terms per BP

## src/aging_bd_agentic_system/graph/
**Purpose:** LangGraph workflow orchestration

**state.py**
- Defines state schema for the entire workflow
- State includes: current hallmark, current BP, identified processes, genes found (with scores/sources), GO terms collected, research scratchpad, context summary
- Defines state update/merge logic

**workflow.py**
- Main LangGraph workflow that orchestrates everything
- Nodes: Phase1 BP identification → Phase2 gene research loop → aggregation → output generation
- Edges: Control flow between phases
- Handles checkpointing for resume capability
- Manages state transitions

## src/aging_bd_agentic_system/prompts/
**Purpose:** System prompts and instructions for agents

**phase1.py**
- System prompt for BP identification agent
- Instructions on: how to use Lopez-Otin paper, how to search literature, how to synthesize processes, evidence scoring criteria (1-10), output format requirements

**phase2.py**
- System prompt for gene research agent
- Instructions on: ReAct pattern usage, when to use which tool, gene scoring criteria, GO term mapping requirements, when to stop researching a BP, how to maintain scratchpad

## src/aging_bd_agentic_system/utils/
**Purpose:** Helper functions and utilities

**validation.py**
- Validates outputs meet requirements
- Checks: gene count 300-500, GO term count 50-80, all scores in 1-10 range, all entries have citations, only genes with score >5
- Returns validation report with pass/fail and issues found

**aggregation.py**
- Aggregates results across all BPs after Phase 2 completes
- Deduplicates genes (keeps max score when gene appears in multiple BPs)
- Merges GO term lists
- Re-ranks final gene list
- Prepares data for TSV output

**context_manager.py**
- Monitors token usage during agent execution
- When context exceeds ~50K tokens, summarizes older tool results and reasoning
- Keeps recent context + scratchpad + gene list intact
- Returns condensed context for continued execution

## src/aging_bd_agentic_system/main.py
**Purpose:** Entry point for running the system

- CLI interface: takes hallmark name as input
- Initializes Gemini 3 client (Vertex AI)
- Loads data sources (Lopez-Otin paper, database connections)
- Instantiates LangGraph workflow
- Runs workflow for specified hallmark
- Saves outputs to outputs/{hallmark_name}/
- Logs all agent traces to logs/agent_traces/

## scripts/run_curation.py
**Purpose:** Convenience script to run curation

- Wrapper around main.py
- Can run multiple hallmarks in batch
- Handles error recovery and retries
- Generates summary reports

## tests/
**Purpose:** Unit tests

**test_tools.py**
- Tests each tool in isolation
- Validates query/response formats
- Checks error handling

**test_agents.py**
- Tests agent logic with mocked tools
- Validates output formats
- Tests state transitions

## data/ (existing structure)
**lopez-otin-22.md** - Reference paper loaded as context for Phase 1
**corpus/** - Indexed literature corpus for vector DB queries
**databases/** - CSV files queried by tools
**go-basic.json** - GO ontology for term mapping (to be added)

## outputs/ (generated)
**{hallmark_name}/processes.tsv** - Phase 1 output
**{hallmark_name}/genes.tsv** - Phase 2 output (genes)
**{hallmark_name}/go_terms.tsv** - Phase 2 output (GO terms)

## logs/ (generated)
**agent_traces/** - Full execution logs with tool calls, reasoning, decisions for auditability