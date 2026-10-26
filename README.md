# Aging BD Agentic System

An LLM-driven deep-research pipeline for curating aging-related gene lists. Given one of
the hallmarks of aging, the system autonomously identifies the relevant biological
processes, researches the genes implicated in each process across multiple evidence
sources, scores those genes against a causal-evidence rubric, and produces a ranked,
fully auditable gene table. It is a controllable, local, reproducible alternative to
manual Deep Research workflows.

## Overview

The pipeline runs in two phases, orchestrated as a LangGraph state machine.

**Phase 1 — Biological process identification.** Starting from a single aging hallmark,
an LLM research agent plans a set of research goals, queries the literature corpus and
PubMed, and synthesizes a ranked list of 10–15 biological processes relevant to that
hallmark. A critic/refine loop iterates until the list meets a quality bar.

**Phase 2 — Gene research per process.** For each biological process, an autonomous
ReAct research loop seeds candidate genes from curated aging databases and then
iteratively queries OpenGenes, PubMed, and the literature corpus to accumulate evidence.
A manuscript-review-style critic grades the result and triggers a refinement loop when
needed. Each gene is scored on a causal-evidence rubric, and the relevant Gene Ontology
terms are mapped to the process.

The per-process results are aggregated into a single hallmark-level gene table, ranked by
evidence score and annotated with how broadly each gene recurs across the hallmark's
processes.

## Method

### Evidence sources

| Source | Access | Role |
|--------|--------|------|
| GenAge | Local curated CSV | Phase 2 seeding |
| OpenGenes | REST API | Seeding and iterative research |
| PubMed | NCBI Entrez (Biopython) | Phase 1 and Phase 2 literature search |
| Literature corpus | FAISS index over PMC full text, `BAAI/bge-base-en-v1.5` embeddings | Semantic retrieval in both phases |
| Gene Ontology | Local `go-basic.json` | GO term mapping per process |

### Scoring rubric

Genes are scored on the strength and nature of **human** evidence, not source count.
Model-organism findings do not drive inclusion without corroborating human evidence.

| Score | Label | Criterion |
|-------|-------|-----------|
| 9–10 | Essential Driver | Direct causal human evidence: loss- or gain-of-function produces aging phenotypes, accelerated age-related disease, or altered lifespan. Mechanism well characterized. |
| 7–8 | Core Mediator | Essential functional role — central to a key complex, pathway, or regulatory mechanism — supported by human functional studies. |
| 5–6 | Supporting Role | Validated but indirect, tissue-specific, or primarily associative involvement (expression changes, GWAS without functional follow-up). |

Evidence is tagged `[CAUSAL]`, `[FUNCTIONAL]`, or `[ASSOCIATIVE]` as it is collected, so
the scorer has a basis for the rubric rather than counting citations.

### Language models

A single client exposes two independent axes:

- **Model tier** — `low` (fast) and `high` (capable), selected per call site.
- **Temperature tier** — `low`, `mid`, `high`, selected independently of the model tier.

Decoupling the axes lets, for example, gene scoring run on the capable model at low
temperature (judgment quality with reproducible output), while strategic synthesis runs
on the capable model at high temperature (exploratory). The default provider is Vertex AI
(`gemini-2.5-pro`); OpenAI is also supported.

## Repository layout

```
src/aging_bd_agentic_system/
  agents/              Phase 1 and Phase 2 node implementations
  graph/               LangGraph state schema and workflow builders
  prompts/             Phase 1, Phase 2, critic, and refine prompt templates
  tools/               The five evidence-source tools
  llm/                 Provider abstraction and the two-axis client
  literature_pipeline/ Corpus ingestion, chunking, embedding, indexing
  utils/               Aggregation, validation, output writing, audit logging
  observability/       Tracing and audit instrumentation
  config.py            RunConfig / LLMConfig / Phase1Config / Phase2Config
  main.py              Unified CLI entry point
config/
  default.yaml         Production defaults
run_scripts/
  run_phase1.py        Phase 1 runner
  run_phase2_bp.py     Phase 2 runner for one biological process
  run_aggregation.py   Hallmark-level aggregation
jobs/                  SLURM submission scripts
scripts/               Corpus-building and integration-check scripts
data/                  Databases, GO ontology, FAISS corpus, reference paper
tests/                 Unit and integration tests
outputs/               Generated results per hallmark
```

## Installation

Requires Python 3.12+ and the [uv](https://docs.astral.sh/uv/) package manager.

```bash
uv venv
uv sync
```

Common development tasks are exposed through the Makefile:

```bash
make sync   # uv sync
make test   # uv run pytest
make lint   # uv run ruff check .
make fmt    # uv run ruff format .
```

### Credentials

Secrets are read from a `.env` file at the repository root; the run scripts load it
automatically.

```bash
VERTEX_PROJECT_ID=your-gcp-project-id   # for the Vertex AI provider
NCBI_EMAIL=your-email@example.org        # required for PubMed access
NCBI_API_KEY=your-ncbi-api-key           # optional; raises the PubMed rate limit
OPENAI_API_KEY=sk-...                    # only if using the OpenAI provider
```

For the Vertex AI provider, authenticate once per machine:

```bash
gcloud auth application-default login
gcloud config set project your-gcp-project-id
```

### Literature corpus

The FAISS index is built once. If `data/corpus/` does not contain an index:

```bash
python scripts/fetch_pmc.py
python scripts/build_chunks.py
python scripts/build_index.py
```

## Configuration

Configuration resolves in three layers, lowest to highest priority:

1. Dataclass defaults in `config.py`.
2. A YAML config file (`RunConfig.from_yaml`), merged field-by-field over the defaults.
3. CLI flags, applied only where a value is provided.

`config/default.yaml` holds the production defaults. Experiment configs typically live
alongside the run and override the parameters of interest. A representative config:

```yaml
hallmark: "genomic instability"
output_dir: "outputs/my_experiment"

llm:
  provider: vertex
  model: gemini-2.5-pro
  vertex_location: us-central1
  temperature: 0.3        # global fallback
  temperature_low: 0.2
  temperature_mid: 0.4
  temperature_high: 0.8

phase1:
  min_processes: 10
  max_processes: 15
  max_iterations: 2

phase2:
  max_research_iterations: 7
  max_critic_iterations: 2
  min_genes: 30
  max_genes: 50
```

Key parameters:

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `phase1.max_processes` | 15 | Upper bound on biological processes per hallmark |
| `phase2.max_research_iterations` | 7 | ReAct research iterations per process |
| `phase2.max_critic_iterations` | 2 | Critic/refine cycles per process |
| `phase2.min_genes` / `max_genes` | 30 / 50 | Target gene count per process |

## Running experiments

The pipeline is designed for SLURM. The standard flow — Phase 1, then a Phase 2 array
with one task per biological process, then aggregation — is orchestrated by a single
submission:

```bash
sbatch jobs/run_test_expt.sh config/my_experiment.yaml
```

This runs Phase 1, reads the process count from `processes.tsv`, submits the Phase 2
array throttled to five concurrent tasks, and submits aggregation with an `afterok`
dependency on the array.

### Replicates

To assess reproducibility, submit N independent replicates of a config, each writing to
its own output directory:

```bash
sh jobs/run_replicates.sh config/my_experiment.yaml 3
```

### Manual and local runs

The individual stages can be run directly, for example on a single process:

```bash
python run_scripts/run_phase1.py --config config/my_experiment.yaml
python run_scripts/run_phase2_bp.py --bp-rank 3 --config config/my_experiment.yaml
python run_scripts/run_aggregation.py --config config/my_experiment.yaml --k-threshold 0.5
```

Phase 2 requires that Phase 1 has completed: it reads the process name for the given
`--bp-rank` (1-indexed) from `processes.tsv` and the Phase 1 state from `full_state.json`.

## Outputs

```
outputs/<hallmark>/
  processes.tsv          Phase 1: ranked biological processes
  full_state.json        Complete Phase 1 state (consumed by Phase 2)
  bp<n>/                 Per-process artifacts
    seed_genes.json
    gene_evidence.json
    state_of_knowledge.json
    critic_review.json
    refinement_history.json
    scored_genes.tsv     Final scored genes for this process
    full_result.json     Complete Phase 2 state for this process
  hallmark_genes.tsv     Aggregated, ranked hallmark-level gene table
```

### `hallmark_genes.tsv`

| Column | Description |
|--------|-------------|
| `rank` | Rank by evidence score |
| `gene_symbol` | HGNC gene symbol |
| `max_score` | Highest score across the processes the gene appears in |
| `mean_score` | Mean score across those processes |
| `bp_count` | Number of biological processes the gene appears in |
| `hallmark_core` | True if the gene recurs in more than `k_threshold` of the processes |
| `biological_processes` | Processes the gene was found in |
| `sources` | Evidence citations |
| `evidence_summary` | Synthesized evidence summary |

## Observability

Each run writes a two-tier audit trail under `logs/<hallmark>/`: per-call traces
(LLM calls, tool calls, chain steps) and higher-level audit events (process completion,
workflow completion). Combined with the per-process JSON snapshots in the output tree,
every result is traceable back to the evidence and model calls that produced it.

## Testing

```bash
make test                          # full suite
uv run pytest tests/test_phase4_integration.py
```

The suite covers the five evidence tools, the LLM client, observability, the aggregation
and validation utilities, and the workflow graph and routing.

## Data sources and acknowledgments

- López-Otín et al. (2022), *Hallmarks of Aging: An Expanding Universe*, Cell.
- GenAge — database of aging-related genes.
- OpenGenes — database of longevity-associated genes.
- Gene Ontology.
- LangGraph for workflow orchestration; Vertex AI for model inference.

## License

MIT. See [LICENSE](LICENSE).
