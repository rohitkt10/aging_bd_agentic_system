# Operations Runbook

This runbook covers day-to-day operations for the Aging BD Agentic System.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Configuration](#configuration)
4. [Building the Literature Corpus](#building-the-literature-corpus)
5. [Running the Workflow](#running-the-workflow)
6. [Understanding Outputs](#understanding-outputs)
7. [Monitoring & Logging](#monitoring--logging)
8. [Troubleshooting](#troubleshooting)
9. [Performance Tuning](#performance-tuning)
10. [Testing](#testing)

---

## Prerequisites

### Required

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud account with Vertex AI enabled
- Google Cloud Application Default Credentials (ADC)

### Optional

- NCBI API key (increases PubMed rate limits from 3 to 10 requests/second)

---

## Environment Setup

### 1. Install Dependencies

```bash
# Clone the repository
git clone <repo-url>
cd aging_bd_agentic_system

# Install dependencies with uv
uv sync
```

### 2. Set Up Google Cloud Credentials

```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Authenticate with Google Cloud
gcloud auth application-default login

# Set your default project
gcloud config set project YOUR_PROJECT_ID
```

### 3. Create Environment File

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env
```

**Minimum required `.env`:**
```bash
VERTEX_PROJECT_ID=your-google-cloud-project-id
NCBI_EMAIL=your-email@example.com
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VERTEX_PROJECT_ID` | **Yes** | - | Google Cloud project ID |
| `VERTEX_LOCATION` | No | `us-central1` | GCP region for Vertex AI |
| `VERTEX_MODEL` | No | `gemini-2.0-flash-exp-01-21` | Gemini model to use |
| `LLM_TEMPERATURE` | No | `0.7` | Response creativity (0.0-1.0) |
| `NCBI_EMAIL` | **Yes** | - | Your email for PubMed API |
| `NCBI_API_KEY` | No | - | NCBI API key for higher rate limits |
| `PHASE1_MAX_ITERATIONS` | No | `3` | Phase 1 refine loop limit |
| `PHASE2_RESEARCH_MAX_ITERATIONS` | No | `7` | Research iterations per BP |
| `PHASE2_REFINE_MAX_ITERATIONS` | No | `3` | Phase 2 refine loop limit |
| `USE_LLM_SUMMARIZATION` | No | `true` | Use LLM for context summarization |

### Recommended Production Settings

```bash
# .env for production
VERTEX_PROJECT_ID=prod-project-id
VERTEX_LOCATION=us-central1
VERTEX_MODEL=gemini-2.0-flash-exp-01-21
LLM_TEMPERATURE=0.5

NCBI_EMAIL=data-team@company.com
NCBI_API_KEY=your-api-key-here

PHASE1_MAX_ITERATIONS=3
PHASE2_RESEARCH_MAX_ITERATIONS=7
PHASE2_REFINE_MAX_ITERATIONS=3
USE_LLM_SUMMARIZATION=true
```

---

## Building the Literature Corpus

The literature corpus must be built before running the workflow. This is a one-time setup.

### Step 1: Download Papers from PMC

```bash
# Download 500 aging-related papers (takes ~30 minutes)
python scripts/fetch_pmc.py --n 500

# Papers are saved to data/corpus/raw/
```

### Step 2: Chunk Papers

```bash
# Split papers into ~300 word chunks
python scripts/build_chunks.py

# Chunks are saved to data/corpus/chunks/
```

### Step 3: Build FAISS Index

```bash
# Generate embeddings and build FAISS index
python scripts/build_index.py

# Index is saved to data/corpus/index/
```

### Verify Corpus

```bash
# Check index files exist
ls -la data/corpus/index/
# Should show: index.faiss, index.metadata.json, lookup.jsonl
```

---

## Running the Workflow

### Basic Run

```bash
# Activate virtual environment
source .venv/bin/activate

# Run for a hallmark
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"
```

### Available Hallmarks

The 9 aging hallmarks from López-Otín et al.:

1. `genomic instability`
2. `telomere attrition`
3. `epigenetic alterations`
4. `loss of proteostasis`
5. `deregulated nutrient sensing`
6. `mitochondrial dysfunction`
7. `cellular senescence`
8. `stem cell exhaustion`
9. `altered intercellular communication`

### Output Directory

```bash
# Specify custom output directory
python -m aging_bd_agentic_system.main \
    --hallmark "epigenetic alterations" \
    --output-dir /path/to/outputs
```

### Expected Runtime

| Hallmark | Estimated Time | LLM Calls |
|----------|----------------|-----------|
| Simple (e.g., telomere attrition) | 30-45 min | ~40-60 |
| Complex (e.g., genomic instability) | 60-90 min | ~80-120 |

---

## Understanding Outputs

### Output Directory Structure

```
outputs/epigenetic_alterations/
├── processes.tsv           # 10-15 biological processes
├── genes.tsv               # 300-500 curated genes
├── go_terms.tsv            # 50-80 GO term mappings
└── full_state.json         # Complete workflow state
```

### File Formats

**processes.tsv:**
```
rank    process_name           evidence_score    evidence_summary    sources
1       DNA methylation        9                 Summary text...     PMID:123;GenAge
2       Histone modification   8                 Summary text...     PMID:456
```

**genes.tsv:**
```
rank    gene_symbol    score    biological_process    evidence_summary    sources
1       DNMT1          9        DNA methylation       Summary text...     PMID:123
2       TET2           8        DNA methylation       Summary text...     GenAge
```

**go_terms.tsv:**
```
go_id           go_label                  biological_process    definition    sources
GO:0006306      DNA methylation           DNA methylation       Def text...   GO:0006306
```

### Validation

After a run completes, check the validation output:

```
Completed hallmark 'epigenetic alterations'. BPs=12, genes=347, GO terms=67.
```

If validation issues are reported:
```
Validation issues:
- expected 300-500 genes, got 287
- gene[42] score not in 1-10
```

---

## Monitoring & Logging

### Log Directory Structure

```
logs/epigenetic_alterations/
├── trace_20250220_143022.jsonl    # Per-call traces (LLM, tools, chains)
├── trace_20250220_143022.json     # Complete trace summary
└── audit.jsonl                    # Major events (BP completion, workflow end)
```

### Trace Files (Tier 1)

**JSONL format - one event per line:**
```json
{"timestamp": "2025-02-20T14:30:23.123456", "event_type": "llm_start", "model": "gemini-2.0-flash", "run_id": "..."}
{"timestamp": "2025-02-20T14:30:25.234567", "event_type": "llm_end", "response_preview": "...", "run_id": "..."}
{"timestamp": "2025-02-20T14:30:26.345678", "event_type": "tool_start", "tool": "query_genage", "input": "DNA repair"}
{"timestamp": "2025-02-20T14:30:27.456789", "event_type": "tool_end", "output_preview": "..."}
```

**Event types:**
- `llm_start`, `llm_end`, `llm_error`
- `tool_start`, `tool_end`, `tool_error`
- `chain_start`, `chain_end`, `chain_error`

### Audit Log (Tier 2)

**audit.jsonl - major workflow events:**
```json
{"timestamp": "2025-02-20T14:35:12", "event_type": "bp_research_complete", "bp_name": "DNA methylation", "genes_count": 25}
{"timestamp": "2025-02-20T15:15:48", "event_type": "workflow_complete", "biological_processes_count": 12, "genes_count": 347, "go_terms_count": 67}
```

### Checking Logs

```bash
# View recent trace events
tail -50 logs/epigenetic_alterations/trace_*.jsonl | jq .

# Check for errors
grep "error" logs/epigenetic_alterations/trace_*.jsonl | jq .

# View audit events
cat logs/epigenetic_alterations/audit.jsonl | jq .
```

---

## Troubleshooting

### Common Issues

#### 1. "VERTEX_PROJECT_ID not set"

**Cause:** Missing required environment variable.

**Fix:**
```bash
# Add to .env
echo "VERTEX_PROJECT_ID=your-project-id" >> .env

# Or export directly
export VERTEX_PROJECT_ID=your-project-id
```

#### 2. "Your default credentials were not found"

**Cause:** Google Cloud ADC not configured.

**Fix:**
```bash
gcloud auth application-default login
```

#### 3. "No biological processes identified"

**Possible causes:**
- LLM not returning valid JSON
- Prompt too vague
- Context too short

**Debug:**
```bash
# Check trace for LLM errors
grep "llm_error" logs/*/trace_*.jsonl

# Check LLM responses
grep "llm_end" logs/*/trace_*.jsonl | jq '.response_preview'
```

#### 4. "Gene list is empty"

**Possible causes:**
- GenAge/OpenGenes returning no results
- LLM filtering out all genes
- Structured output parsing failed

**Debug:**
```bash
# Check tool results
grep "tool_end" logs/*/trace_*.jsonl | jq 'select(.tool | contains("genage") or contains("opengenes"))'

# Check full state
cat outputs/*/full_state.json | jq '.genes_found'
```

#### 5. "Too few GO terms"

**Possible causes:**
- GO database not loaded
- LLM being too strict

**Debug:**
```bash
# Verify GO database exists
ls -la data/go-basic.json

# Check GO tool results
grep "tool_end" logs/*/trace_*.jsonl | jq 'select(.tool | contains("go"))'
```

#### 6. "Graph hangs or loops forever"

**Possible causes:**
- Critic always returns "fail"
- Max iteration not enforced

**Debug:**
```bash
# Check iteration counts in state
cat outputs/*/full_state.json | jq '{phase1_iteration, phase2_critic_iteration, phase2_research_iteration}'

# Check critic responses
grep "llm_end" logs/*/trace_*.jsonl | jq 'select(.current_node | contains("critic"))'
```

#### 7. PubMed Rate Limited

**Cause:** Too many requests without API key.

**Fix:**
```bash
# Get NCBI API key from https://www.ncbi.nlm.nih.gov/account/settings/apikeys/
echo "NCBI_API_KEY=your-key" >> .env
```

---

## Performance Tuning

### Faster Runs (Lower Quality)

```bash
# Reduce research iterations
export PHASE2_RESEARCH_MAX_ITERATIONS=5

# Reduce refinement iterations
export PHASE1_MAX_ITERATIONS=2
export PHASE2_REFINE_MAX_ITERATIONS=2
```

### Higher Quality (Slower)

```bash
# More research iterations
export PHASE2_RESEARCH_MAX_ITERATIONS=10

# More refinement iterations
export PHASE1_MAX_ITERATIONS=5
export PHASE2_REFINE_MAX_ITERATIONS=5

# Lower temperature for more focused responses
export LLM_TEMPERATURE=0.3
```

### Reduce LLM Costs

```bash
# Use faster/cheaper model
export VERTEX_MODEL=gemini-2.0-flash-001

# Disable LLM summarization (use rule-based fallback)
export USE_LLM_SUMMARIZATION=false
```

---

## Testing

### Run All Tests

```bash
# Run all unit tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_phase4_integration.py -v

# Run with coverage
python -m pytest tests/ -v --cov=src/aging_bd_agentic_system
```

### Test Categories

| Test File | What It Tests |
|-----------|---------------|
| `test_genage.py` | GenAge database queries |
| `test_opengenes.py` | OpenGenes database queries |
| `test_pubmed.py` | PubMed API integration |
| `test_vector_db.py` | FAISS corpus search |
| `test_go_terms.py` | GO term lookup |
| `test_llm.py` | LLM client and prompts |
| `test_tracing.py` | Observability/tracing |
| `test_phase3_utils.py` | Validation, aggregation, output writers |
| `test_phase4_integration.py` | Workflow graph, routing, state schema |

### Test LLM Connectivity

```bash
# Quick test of LLM connection
python scripts/test_llm.py
```

---

## Support

### Useful Commands

```bash
# Check project structure
find src/ -name "*.py" | head -20

# Count genes in output
wc -l outputs/*/genes.tsv

# View last run summary
cat logs/*/audit.jsonl | jq 'select(.event_type == "workflow_complete")'

# Extract all gene symbols
cut -f2 outputs/*/genes.tsv | tail -n +2 | sort | uniq
```

### Health Check

```bash
# Quick health check script
#!/bin/bash
echo "=== Environment ==="
test -f .env && echo ".env: OK" || echo ".env: MISSING"
grep -q VERTEX_PROJECT_ID .env && echo "VERTEX_PROJECT_ID: OK" || echo "VERTEX_PROJECT_ID: MISSING"
grep -q NCBI_EMAIL .env && echo "NCBI_EMAIL: OK" || echo "NCBI_EMAIL: MISSING"

echo -e "\n=== Corpus ==="
test -f data/corpus/index/index.faiss && echo "FAISS index: OK" || echo "FAISS index: MISSING"
test -f data/go-basic.json && echo "GO database: OK" || echo "GO database: MISSING"

echo -e "\n=== Databases ==="
test -f data/databases/genage.csv && echo "GenAge: OK" || echo "GenAge: MISSING"
test -f data/databases/opengenes.csv && echo "OpenGenes: OK" || echo "OpenGenes: MISSING"

echo -e "\n=== Credentials ==="
gcloud auth application-default print-access-token > /dev/null 2>&1 && echo "GCP ADC: OK" || echo "GCP ADC: NOT CONFIGURED"
```
