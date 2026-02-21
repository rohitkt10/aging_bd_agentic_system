# Project Structure

```
aging_bd_agentic_system/
├── src/
│   └── aging_bd_agentic_system/
│       ├── __init__.py
│       ├── main.py                         # CLI entry point
│       │
│       ├── agents/                         # Agent node implementations
│       │   ├── __init__.py
│       │   ├── phase1_bp_identifier.py     # Phase 1: BP planning, research, critique, refine
│       │   ├── phase2_gene_researcher.py   # Phase 2: ReAct research loop, critique, GO mapping
│       │   └── helpers.py                  # Shared utilities (unique_non_empty)
│       │
│       ├── graph/                          # LangGraph workflow orchestration
│       │   ├── __init__.py
│       │   ├── state.py                    # ResearchState TypedDict with reducer annotations
│       │   └── workflow.py                 # build_phase1_graph, build_phase2_graph, build_workflow
│       │
│       ├── llm/                            # LLM client and prompts
│       │   ├── __init__.py                 # Exports get_llm, reset_llm
│       │   ├── client.py                   # LLMClient singleton with invoke/invoke_structured
│       │   ├── providers.py                # VertexGeminiProvider implementation
│       │   ├── prompts.py                  # All system/user prompts for Phase 1 & 2
│       │   └── testing.py                  # FakeLLMProvider for unit tests
│       │
│       ├── tools/                          # Research tools (evidence sources)
│       │   ├── __init__.py
│       │   ├── genage.py                   # GenAge longevity genes database
│       │   ├── opengenes.py                # OpenGenes intervention database
│       │   ├── pubmed.py                   # PubMed/Entrez literature search
│       │   ├── vector_db.py                # FAISS corpus search
│       │   └── go_terms.py                 # Gene Ontology term lookup
│       │
│       ├── observability/                  # Logging and tracing
│       │   ├── __init__.py
│       │   └── tracing.py                  # TracingCallbackHandler for LLM/tool/chain events
│       │
│       ├── utils/                          # Utility functions
│       │   ├── __init__.py
│       │   ├── validation.py               # validate_phase1, validate_phase2, validate_all
│       │   ├── aggregation.py              # dedupe_genes, merge_go_terms, sort_genes
│       │   ├── output_writer.py            # TSV writers for processes/genes/go_terms
│       │   ├── context_manager.py          # Token estimation, LLM-based summarization
│       │   └── audit_logger.py             # Structured event logging to audit.jsonl
│       │
│       └── literature_pipeline/            # Corpus ingestion (pre-processing)
│           ├── __init__.py
│           ├── config.py                   # Pipeline configuration
│           ├── ingestion.py                # PMC paper download
│           ├── chunking.py                 # Text chunking
│           ├── embedding.py                # BGE embedding generation
│           └── indexing.py                 # FAISS index building
│
├── data/
│   ├── lopez-otin-22.md                    # Reference paper (hallmark definitions)
│   ├── go-basic.json                       # GO ontology database
│   ├── sample_prompt.txt                   # Example prompt for testing
│   │
│   ├── corpus/                             # Literature corpus
│   │   ├── raw/                            # Downloaded XML from PMC
│   │   ├── chunks/                         # Chunked text files
│   │   └── index/                          # FAISS index + metadata
│   │       ├── index.faiss
│   │       ├── index.metadata.json
│   │       └── lookup.jsonl
│   │
│   ├── databases/                          # Local database files
│   │   ├── genage.csv                      # GenAge longevity genes
│   │   └── opengenes.csv                   # OpenGenes interventions
│   │
│   └── logs/                               # Runtime logs (moved from project root)
│
├── logs/                                   # Execution logs per hallmark
│   └── {hallmark}/                         # Sanitized hallmark name
│       ├── trace_{timestamp}.jsonl         # Tier 1: Per-call traces
│       ├── trace_{timestamp}.json          # Tier 1: Complete trace summary
│       └── audit.jsonl                     # Tier 2: Major events (BP/workflow completion)
│
├── outputs/                                # Generated outputs per hallmark
│   └── {hallmark}/
│       ├── processes.tsv                   # Biological processes (10-15 rows)
│       ├── genes.tsv                       # Curated genes (300-500 rows)
│       ├── go_terms.tsv                    # GO term mappings (50-80 rows)
│       └── full_state.json                 # Complete workflow state for audit
│
├── tests/                                  # Unit and integration tests
│   ├── test_genage.py                      # GenAge tool tests
│   ├── test_opengenes.py                   # OpenGenes tool tests
│   ├── test_pubmed.py                      # PubMed tool tests
│   ├── test_vector_db.py                   # FAISS tool tests
│   ├── test_go_terms.py                    # GO terms tool tests
│   ├── test_llm.py                         # LLM client and prompts tests
│   ├── test_tracing.py                     # Tracing callback tests
│   ├── test_audit_logger.py                # Audit logger tests
│   ├── test_workflow.py                    # Workflow graph tests
│   ├── test_workflow_smoke.py              # Smoke tests (require credentials)
│   ├── test_phase2_nodes.py                # Phase 2 node tests
│   ├── test_phase3_utils.py                # Utilities tests
│   └── test_phase4_integration.py          # Comprehensive Phase 4 tests
│
├── docs/                                   # Documentation
│   ├── PRD.md                              # Product requirements
│   ├── RUNBOOK.md                          # Operations runbook
│   ├── codebase-desc.md                    # Codebase description
│   ├── implementation_flow.md              # Implementation phases
│   ├── issues-and-fixes.md                 # Known issues and fixes
│   ├── project-structure.md                # This file
│   │
│   ├── plans/                              # Implementation plans
│   │   ├── README.md                       # Plans overview
│   │   ├── impl_phase_1.md                 # Phase 1: LLM foundation
│   │   ├── impl_phase_2.md                 # Phase 2: Agent intelligence
│   │   ├── impl_phase_3.md                 # Phase 3: Observability
│   │   └── impl_phase_4.md                 # Phase 4: Integration & validation
│   │
│   ├── adk/                                # ADK reference docs
│   └── langgraph-deep-research/            # LangGraph reference docs
│
├── scripts/                                # Utility scripts
│   ├── fetch_pmc.py                        # Download papers from PMC
│   ├── build_chunks.py                     # Chunk downloaded papers
│   ├── build_index.py                      # Build FAISS index
│   ├── test_llm.py                         # Test LLM connectivity
│   └── test_opengenes_api.py               # Test OpenGenes API
│
├── .env.example                            # Environment variable template
├── pyproject.toml                          # Project dependencies (uv)
├── README.md                               # Project overview
└── CHANGELOG_INTERNAL.md                   # Internal change log
```

## Key Files

### Entry Points

| File | Purpose |
|------|---------|
| `src/aging_bd_agentic_system/main.py` | CLI entry point: `python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"` |
| `scripts/*.py` | Corpus ingestion scripts |

### Core Components

| Directory | Purpose |
|-----------|---------|
| `agents/` | Node implementations for Phase 1 (BP identification) and Phase 2 (gene research) |
| `graph/` | LangGraph StateGraph definitions and routing functions |
| `llm/` | Vertex AI Gemini integration with structured output support |
| `tools/` | 5 evidence sources: GenAge, OpenGenes, PubMed, Vector DB, GO Terms |
| `observability/` | Two-tier logging: per-call traces + audit events |
| `utils/` | Validation, aggregation, output writing, context management |

### Configuration

| File | Purpose |
|------|---------|
| `.env` | Environment variables (VERTEX_PROJECT_ID, NCBI_EMAIL, etc.) |
| `.env.example` | Template with all available options |
| `pyproject.toml` | Dependencies and project metadata |

### Output Structure

```
outputs/{hallmark}/
├── processes.tsv       # rank, process_name, evidence_score, evidence_summary, sources
├── genes.tsv           # rank, gene_symbol, score, biological_process, evidence_summary, sources
├── go_terms.tsv        # go_id, go_label, biological_process, definition, sources
└── full_state.json     # Complete workflow state

logs/{hallmark}/
├── trace_{ts}.jsonl    # Per-call LLM/tool/chain events
├── trace_{ts}.json     # Complete trace summary
└── audit.jsonl         # BP completion, workflow completion events
```

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VERTEX_PROJECT_ID` | Yes | - | Google Cloud project ID |
| `VERTEX_LOCATION` | No | `us-central1` | GCP region |
| `VERTEX_MODEL` | No | `gemini-2.0-flash-exp-01-21` | Gemini model |
| `NCBI_EMAIL` | Yes | - | For PubMed API |
| `NCBI_API_KEY` | No | - | Increases PubMed rate limits |
| `PHASE1_MAX_ITERATIONS` | No | `3` | Phase 1 refine loop limit |
| `PHASE2_RESEARCH_MAX_ITERATIONS` | No | `7` | Research loop iterations |
| `PHASE2_REFINE_MAX_ITERATIONS` | No | `3` | Phase 2 refine loop limit |
| `USE_LLM_SUMMARIZATION` | No | `true` | Toggle LLM vs rule-based summarization |
