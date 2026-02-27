# Aging BD Agentic System

An LLM-powered deep research system for aging biological discovery gene list curation. This system replaces manual Gemini Deep Research workflows with a controllable, local, and fully auditable alternative.

## Overview

This system automates the curation of aging-related gene lists by:

1. **Phase 1:** Identifying 10-15 biological processes relevant to an aging hallmark
2. **Phase 2:** For each biological process, conducting autonomous research to discover 300-500 relevant genes with evidence

The system uses a LangGraph-based workflow with an autonomous ReAct research loop, querying multiple evidence sources (GenAge, OpenGenes, PubMed, literature corpus, Gene Ontology) and leveraging LLM-powered critique and refinement.

## Status

- ✅ **Phase 1 (BP Discovery):** Implemented and tested
- 🔄 **Phase 2 (Gene Research):** Implemented, smoke testing in progress
- ✅ **Multi-provider LLM:** OpenAI and Vertex AI supported
- ✅ **Observability:** Tracing and audit logging

## Features

- **Autonomous Research Loop:** ReAct-style iterative research with configurable iteration limits
- **Multi-Source Evidence:** Queries GenAge, OpenGenes, PubMed, FAISS-indexed literature corpus, and Gene Ontology
- **Multi-Provider LLM Support:** OpenAI GPT-4o/GPT-4o-mini and Vertex AI Gemini models
- **Structured Outputs:** Produces validated TSV files for biological processes, genes, and GO terms
- **Full Observability:** Two-tier logging with per-call traces and audit events
- **Configurable:** YAML config files with CLI overrides; config hierarchy: defaults → YAML → CLI
- **Auditable:** Complete state export and trace files for every run
- **Independent Smoke Tests:** Phase 1 and Phase 2 can be tested independently

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│  PHASE 1: Biological Process Identification                              │
│  ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌─────────┐   ┌────────┐ │
│  │load_ctx  │ → │ plan/     │ → │ research │ → │ critic  │ → │finalize│ │
│  │          │   │ research  │   │  (LLM)   │   │  (LLM)  │   │        │ │
│  └──────────┘   └───────────┘   └──────────┘   └────┬────┘   └────────┘ │
│                                                   ↓ refine (if fail)    │
├─────────────────────────────────────────────────────────────────────────┤
│  PHASE 2: Gene Research (per Biological Process)                        │
│  ┌──────────┐   ┌───────────────────────────────────────────────┐      │
│  │select_bp │ → │ ReAct Research Loop (7 iterations default)    │      │
│  └──────────┘   │  • GenAge  • OpenGenes  • PubMed  • Vector DB │      │
│                 └───────────────┬───────────────────────────────┘      │
│                                 ↓                                        │
│                 ┌──────────────┐   ┌──────────────┐   ┌──────────┐     │
│                 │ critic (LLM) │ → │ refine/map_go│ → │advance_bp│     │
│                 └──────────────┘   └──────────────┘   └──────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd aging_bd_agentic_system
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env with your OPENAI_API_KEY (for OpenAI) or VERTEX_PROJECT_ID (for Vertex AI)

# 3. (Optional) Set up Google Cloud credentials if using Vertex AI
gcloud auth application-default login

# 4. Run for a hallmark
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"

# 5. Check outputs
ls outputs/epigenetic_alterations/
```

### Using Config Files

```bash
# Run with a config file (recommended for reproducibility)
python -m aging_bd_agentic_system.main --config config/test_config.yaml

# Run Phase 1 only (skip gene research)
python -m aging_bd_agentic_system.main --hallmark "genomic instability" --phase1-only true
```

### Smoke Tests

Test each phase independently:

```bash
# Phase 1 smoke test (BP discovery)
python scripts/phase1_research_smoketest.py

# Phase 2 smoke test (uses saved Phase 1 data)
python scripts/phase2_research_smoketest.py --hallmark "genomic instability" --bp-index 0
```

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud account with Vertex AI enabled
- Google Cloud Application Default Credentials

### Setup

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Authenticate with Google Cloud
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### Build Literature Corpus (One-time)

```bash
python scripts/fetch_pmc.py --n 500
python scripts/build_chunks.py
python scripts/build_index.py
```

## Configuration

Configuration follows a priority hierarchy: **defaults → YAML file → CLI arguments**

### Environment Variables (.env)

Secrets only (API keys, project IDs):

```bash
# OpenAI (default provider)
OPENAI_API_KEY=your-openai-api-key

# Vertex AI (alternative provider)
VERTEX_PROJECT_ID=your-google-cloud-project-id
VERTEX_LOCATION=us-central1

# Required for both providers
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=optional-ncbi-api-key  # Faster PubMed queries
```

### YAML Config File

Create a config file for reproducible runs:

```yaml
# config/test_config.yaml
hallmark: "genomic instability"
output_dir: "outputs"
phase1_only: true  # Set to false to run Phase 2

llm:
  provider: openai  # or "vertex"
  model: gpt-4o     # or "gemini-2.0-flash-exp-01-21"
  temperature: 0.7

phase1:
  max_iterations: 2
  max_processes: 15

phase2:
  max_research_iterations: 7
  max_refine_iterations: 3
```

### CLI Overrides

All config options can be overridden via CLI:

```bash
python -m aging_bd_agentic_system.main \
    --config config/test_config.yaml \
    --provider openai \
    --model gpt-4o-mini \
    --max-research-iterations 3
```

See [.env.example](.env.example) for all available options.

## Usage

### Basic Usage

```bash
# Run with defaults (OpenAI gpt-4o)
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"

# Run with Vertex AI
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations" --provider vertex --model gemini-2.0-flash-exp-01-21
```

### Available Hallmarks

The 9 aging hallmarks from López-Otín et al.:

| Hallmark | Description |
|----------|-------------|
| `genomic instability` | DNA damage accumulation |
| `telomere attrition` | Telomere shortening |
| `epigenetic alterations` | DNA methylation, histone changes |
| `loss of proteostasis` | Protein folding/maintenance |
| `deregulated nutrient sensing` | IGF-1, mTOR, AMPK pathways |
| `mitochondrial dysfunction` | Mitochondrial efficiency decline |
| `cellular senescence` | Cell cycle arrest |
| `stem cell exhaustion` | Stem cell depletion |
| `altered intercellular communication` | Inflammation, signaling changes |

### Custom Output Directory

```bash
python -m aging_bd_agentic_system.main \
    --hallmark "epigenetic alterations" \
    --output-dir /path/to/outputs
```

## Output Format

```
outputs/epigenetic_alterations/
├── processes.tsv           # 10-15 biological processes
├── genes.tsv               # 300-500 curated genes
├── go_terms.tsv            # 50-80 GO term mappings
└── full_state.json         # Complete workflow state
```

### processes.tsv

| Column | Description |
|--------|-------------|
| rank | Process priority (1-15) |
| process_name | Biological process name |
| evidence_score | Quality score (1-10) |
| evidence_summary | Summary of evidence |
| sources | Source citations (PMID, GenAge, etc.) |

### genes.tsv

| Column | Description |
|--------|-------------|
| rank | Gene priority (1-500) |
| gene_symbol | HGNC gene symbol |
| score | Relevance score (1-10) |
| biological_process | Associated process |
| evidence_summary | Summary of evidence |
| sources | Source citations |

### go_terms.tsv

| Column | Description |
|--------|-------------|
| go_id | GO identifier (GO:XXXXXXX) |
| go_label | GO term name |
| biological_process | Associated processes |
| definition | GO term definition |
| sources | Source citations |

## Project Structure

```
aging_bd_agentic_system/
├── src/aging_bd_agentic_system/
│   ├── main.py              # CLI entry point
│   ├── agents/              # Phase 1 & 2 node implementations
│   ├── graph/               # LangGraph workflow definitions
│   ├── llm/                 # Vertex AI Gemini integration
│   ├── tools/               # Evidence source tools (5 tools)
│   ├── observability/       # Tracing and logging
│   └── utils/               # Validation, aggregation, output
├── tests/                   # Unit and integration tests
├── scripts/                 # Corpus ingestion scripts
├── data/                    # Databases, corpus, GO ontology
├── logs/                    # Execution logs per hallmark
├── outputs/                 # Generated outputs per hallmark
└── docs/                    # Documentation
```

See [docs/project-structure.md](docs/project-structure.md) for details.

## Observability

### Two-Tier Logging

```
logs/{hallmark}/
├── trace_{timestamp}.jsonl    # Tier 1: Per-call traces (LLM, tools, chains)
├── trace_{timestamp}.json     # Tier 1: Complete trace summary
└── audit.jsonl                # Tier 2: Major events (BP/workflow completion)
```

### Trace Events

- `llm_start`, `llm_end`, `llm_error`
- `tool_start`, `tool_end`, `tool_error`
- `chain_start`, `chain_end`, `chain_error`

### Audit Events

- `bp_research_complete` - When a biological process finishes
- `workflow_complete` - When the entire workflow finishes

## Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_phase4_integration.py -v

# Run with coverage
python -m pytest tests/ -v --cov=src/aging_bd_agentic_system
```

### Test Categories

| Test File | Coverage |
|-----------|----------|
| `test_genage.py` | GenAge database queries |
| `test_opengenes.py` | OpenGenes database queries |
| `test_pubmed.py` | PubMed API integration |
| `test_vector_db.py` | FAISS corpus search |
| `test_go_terms.py` | GO term lookup |
| `test_llm.py` | LLM client and prompts |
| `test_tracing.py` | Observability/tracing |
| `test_phase3_utils.py` | Validation, aggregation, output |
| `test_phase4_integration.py` | Workflow graph, routing, state |

## Documentation

- [PRD.md](docs/PRD.md) - Product requirements
- [RUNBOOK.md](docs/RUNBOOK.md) - Operations runbook
- [project-structure.md](docs/project-structure.md) - Project structure
- [plans/](docs/plans/) - Implementation phase plans
- [ctx_patterns/](docs/ctx_patterns/) - Context management patterns and lessons learned

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `OPENAI_API_KEY not set` | Add to `.env` file |
| `VERTEX_PROJECT_ID not set` | Add to `.env` file (only if using Vertex AI) |
| `Credentials not found` | Run `gcloud auth application-default login` (Vertex AI only) |
| `No biological processes` | Check LLM errors in trace logs |
| `Empty gene list` | Verify GenAge/OpenGenes data files exist |
| `PubMed rate limited` | Add `NCBI_API_KEY` to `.env` |

See [RUNBOOK.md](docs/RUNBOOK.md) for detailed troubleshooting.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`python -m pytest tests/ -v`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [López-Otín et al. (2022)](https://www.cell.com/cell/fulltext/S0092-8674(22)01377-0) - Hallmarks of aging: An expanding universe
- [GenAge](https://genomics.senescence.info/genes/) - Database of aging-related genes
- [OpenGenes](https://open-genes.com/) - Database of longevity-associated genes
- [Gene Ontology](https://geneontology.org/) - GO term definitions and relationships
- [LangGraph](https://github.com/langchain-ai/langgraph) - Workflow orchestration framework
- [Vertex AI](https://cloud.google.com/vertex-ai) - LLM infrastructure
