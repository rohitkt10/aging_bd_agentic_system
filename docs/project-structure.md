# Project Structure

aging_bd_agentic_system/
├── src/
│   └── aging_bd_agentic_system/
│       ├── literature_pipeline/          # Existing: download/chunk/index
│       ├── tools/                        # Tool definitions
│       │   ├── __init__.py
│       │   ├── vector_db.py             # FAISS query tool
│       │   ├── pubmed.py                # PubMed search tool
│       │   ├── go_terms.py              # GO term search tool
│       │   ├── genage.py                # GenAge query tool
│       │   └── opengenes.py             # Open Genes query tool
│       ├── agents/                       # Agent definitions
│       │   ├── __init__.py
│       │   ├── phase1_bp_identifier.py  # BP identification agent
│       │   └── phase2_gene_researcher.py # Gene research ReAct agent
│       ├── graph/                        # LangGraph workflows
│       │   ├── __init__.py
│       │   ├── state.py                 # State schema definitions
│       │   └── workflow.py              # Main graph orchestration
│       ├── prompts/                      # System prompts
│       │   ├── __init__.py
│       │   ├── phase1.py                # BP identification prompts
│       │   └── phase2.py                # Gene research prompts
│       ├── utils/                        # Utilities
│       │   ├── __init__.py
│       │   ├── validation.py            # Output validation
│       │   ├── aggregation.py           # Cross-BP aggregation
│       │   └── context_manager.py       # Context summarization
│       └── main.py                       # Entry point
├── data/
│   ├── lopez-otin-22.md                 # Existing: reference paper
│   ├── corpus/                          # Existing: literature corpus
│   │   ├── raw/                         # XML files from PMC
│   │   ├── chunks/                      # Chunked papers
│   │   └── index/                       # FAISS index + metadata
│   │       ├── index files
│   │       ├── index.meta.json
│   │       └── lookup.jsonl
│   ├── databases/                       # Existing: local databases
│   │   ├── genage.csv
│   │   └── opengenes.csv
│   └── go-basic.json                    # GO ontology (to be added)
├── logs/                                 # Existing: execution logs
│   └── agent_traces/                    # Agent reasoning traces
├── outputs/                              # Generated outputs
│   └── {hallmark_name}/                 # Per-hallmark results
│       ├── processes.tsv
│       ├── genes.tsv
│       └── go_terms.tsv
├── docs/                                 # Existing: documentation
│   └── PRD.md
├── scripts/                              # Existing: utility scripts
│   └── run_curation.py                  # Run curation for a hallmark
├── tests/                                # Unit tests
│   ├── test_tools.py
│   └── test_agents.py
├── pyproject.toml                        # Dependencies
└── README.md