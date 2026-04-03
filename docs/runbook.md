# Experiment Runbook: Running a Hallmark End-to-End

This document covers how to set up, configure, and submit a full experiment for any aging hallmark using Slurm and Vertex AI (or OpenAI).

---

## Prerequisites

### 1. Python environment

The project uses `uv` for dependency management. The virtual environment must exist at `.venv/` in the repo root before any job submission.

```bash
# From repo root
uv venv
uv sync
```

Requires Python >= 3.12.

### 2. Credentials (.env)

A `.env` file must exist at the repo root. It is loaded automatically by both run scripts. Fill in the values for whichever provider you are using:

```bash
# NCBI — required for PubMed queries
NCBI_EMAIL=your@email.org
NCBI_API_KEY=your_ncbi_api_key

# LLM provider selection (informational; actual provider is set in the YAML config)
LLM_PROVIDER=vertex   # or openai

# Vertex AI
VERTEX_PROJECT_ID=your-gcp-project-id

# OpenAI (if using OpenAI provider)
OPENAI_API_KEY=sk-...
```

### 3. Vertex AI authentication (if using Vertex)

Run once per session / machine before submitting jobs:

```bash
gcloud auth application-default login
gcloud config set project your-gcp-project-id
```

### 4. FAISS vector index

The vector DB index must be built before running. If `data/corpus/faiss.index` does not exist, build it:

```bash
python scripts/fetch_pmc.py
python scripts/build_chunks.py
python scripts/build_index.py
```

---

## Step 1: Create a config YAML

Each experiment is driven by a YAML config file. The convention is to keep these inside the experiment directory (e.g., `test_expt_vertex/`).

The config file can live anywhere on the filesystem — its path is passed explicitly to all scripts and is not tied to the experiment directory. A reasonable convention is to keep configs alongside the run scripts, but this is not required.

```bash
cp test_expt_vertex/test_config1.yaml test_expt_vertex/my_hallmark_config.yaml
# or anywhere else, e.g.:
cp test_expt_vertex/test_config1.yaml configs/telomere_attrition.yaml
```

Edit the new file:

```yaml
hallmark: "telomere attrition"         # The aging hallmark to research
output_dir: "outputs/my_experiment"    # Where outputs are written (relative to repo root)

llm:
  provider: vertex                     # "vertex" or "openai"
  model: gemini-3-flash-preview        # Low-tier model (fast, most calls)
  model_high: gemini-3-pro-preview     # High-tier model (complex reasoning tasks)
  temperature: 0.5
  vertex_location: global              # Vertex AI region

phase1:
  min_research_goals: 3
  max_research_goals: 5
  phase1_vector_db_top_k: 5
  phase1_pubmed_retmax: 5
  max_iterations: 2                    # Critic-refine cycles
  min_processes: 10
  max_processes: 15

phase2:
  max_research_iterations: 4          # Research loops per biological process
  min_actions_per_iteration: 5
  max_actions_per_iteration: 7
  genage_seed_max_results: 10
  opengenes_seed_results_per_query: 15
  phase2_vector_db_top_k: 5
  phase2_pubmed_retmax: 5
  max_critic_iterations: 2
  refine_opengenes_max_results: 3
  refine_pubmed_max_results: 7
  refine_vector_db_top_k: 7
```

### Supported hallmarks

Any string is accepted, but the system is designed and tested around these:

- `genomic instability`
- `telomere attrition`
- `epigenetic alterations`
- `loss of proteostasis`
- `deregulated nutrient sensing`
- `mitochondrial dysfunction`
- `cellular senescence`
- `stem cell exhaustion`
- `altered intercellular communication`
- `chronic inflammation`
- `dysbiosis`
- `disabled macroautophagy`

---

## Step 2: Submit the experiment

**All `sbatch` commands must be run from the repo root.** The job scripts use `$SLURM_SUBMIT_DIR` as their working directory.

```bash
cd /projects/compsci/karuturi/tripar/aging_bd_agentic_system

sbatch jobs/run_test_expt.sh test_expt_vertex test_expt_vertex/my_hallmark_config.yaml
```

Arguments:
- `$1` — experiment directory (where `run_phase1.py` and `run_phase2_bp.py` live)
- `$2` — path to the YAML config

This single command runs the full pipeline:

1. **Phase 1** runs as a single Slurm job (`-J aging_bd`, 32 GB, 8 h).
2. On completion, it reads `processes.tsv` to count biological processes (`N`).
3. **Phase 2** is submitted as a job array (`--array=1-N%5`), where each task processes one biological process in parallel (throttled to 5 concurrent tasks).

### Submitting multiple hallmarks

Each hallmark is independent. Submit them simultaneously with separate `sbatch` calls:

```bash
sbatch jobs/run_test_expt.sh test_expt_vertex test_expt_vertex/test_config1.yaml  # genomic instability
sbatch jobs/run_test_expt.sh test_expt_vertex test_expt_vertex/test_config2.yaml  # cellular senescence
sbatch jobs/run_test_expt.sh test_expt_vertex test_expt_vertex/test_config3.yaml  # mitochondrial dysfunction
```

---

## Step 3: Monitor jobs

```bash
# All your running/pending jobs
squeue -u $USER

# Phase 1 log (replace JOBID)
tail -f logs/phase1_<JOBID>.out
tail -f logs/phase1_<JOBID>.err

# Phase 2 array logs (%A = array job ID, %a = task index)
tail -f logs/phase2_<ARRAYJOBID>_1.out   # BP rank 1
tail -f logs/phase2_<ARRAYJOBID>_5.err   # BP rank 5 errors
```

---

## Step 4: Re-run a single failed BP

If an individual Phase 2 array task fails, re-run it without resubmitting the whole array:

```bash
sbatch jobs/run_phase2_single.sh <CONFIG_ID> <BP_RANK>
```

`run_phase2_single.sh` is hardcoded to look for configs at `test_expt_vertex/test_config${CONFIG_ID}.yaml`. For example, to re-run BP rank 7 from config 2:

```bash
sbatch jobs/run_phase2_single.sh 2 7
```

Alternatively, run a BP interactively for debugging:

```bash
source .venv/bin/activate
python test_expt_vertex/run_phase2_bp.py \
    --bp-rank 7 \
    --config test_expt_vertex/my_hallmark_config.yaml
```

---

## Output structure

All outputs are written under `output_dir` (as set in the config):

```
outputs/my_experiment/
└── telomere attrition/
    ├── processes.tsv          # Phase 1: ranked biological processes with evidence scores
    ├── full_state.json        # Phase 1: complete LangGraph state (loaded by Phase 2)
    ├── bp1/
    │   ├── seed_genes.json          # Initial genes seeded from GenAge + OpenGenes
    │   ├── seeding_queries.json     # OpenGenes queries used during seeding
    │   ├── research_scratchpad.json # Full intermediate research data
    │   ├── state_of_knowledge.json  # Compressed research summary
    │   ├── gene_evidence.json       # Per-gene source accumulator
    │   ├── tool_call_history.json   # All tool invocations
    │   ├── reasoning_trace.json     # LLM reasoning steps
    │   ├── critic_review.json       # Final critic grade + feedback
    │   ├── refinement_history.json  # Refinement cycles applied
    │   ├── warnings.json
    │   ├── scored_genes.tsv         # Final gene list (gene_symbol, score, evidence, sources)
    │   └── full_result.json         # Complete Phase 2 LangGraph state
    ├── bp2/
    │   └── ...
    └── bp15/
        └── ...
```

### processes.tsv columns

| rank | process_name | evidence_score | evidence_summary | sources |
|------|-------------|---------------|-----------------|---------|

### scored_genes.tsv columns (per BP)

| gene_symbol | score | evidence_summary | sources | biological_process |
|-------------|-------|-----------------|---------|-------------------|

---

## Running phases manually (without Slurm)

Useful for local testing or debugging individual phases.

### Phase 1 only

```bash
source .venv/bin/activate
python test_expt_vertex/run_phase1.py --config test_expt_vertex/my_hallmark_config.yaml
```

Outputs `processes.tsv` and `full_state.json` to `output_dir/hallmark/`.

### Phase 2 for a single BP

Phase 1 must have completed first (needs `full_state.json` and `processes.tsv`).

```bash
source .venv/bin/activate
python test_expt_vertex/run_phase2_bp.py \
    --bp-rank 1 \
    --config test_expt_vertex/my_hallmark_config.yaml
```

---

## Slurm resource summary

| Job | Script | Nodes | CPUs | Memory | Walltime | Queue |
|-----|--------|-------|------|--------|----------|-------|
| Phase 1 | `run_test_expt.sh` | 1 | 1 | 32 GB | 8 h | batch |
| Phase 2 (per task) | `phase2.sh` | 1 | 1 | 32 GB | 8 h | batch |

Phase 2 array is throttled to **5 concurrent tasks** (`%5`). With 15 BPs this means 3 rounds of 5, completing in roughly 3× the per-BP runtime.

---

## Common failure modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `.venv/bin/activate: No such file or directory` | Virtual env not set up | Run `uv venv && uv sync` from repo root |
| `Phase 1 data not found: .../full_state.json` | Phase 2 submitted before Phase 1 finished | Wait for Phase 1 to complete; `run_test_expt.sh` handles this automatically |
| `Config file not found` | Wrong working directory or path | Ensure `sbatch` is run from repo root |
| `conda deactivate` error in logs | Conda not initialised in the shell | Safe to ignore — scripts use `conda deactivate || true` in newer versions |
| Phase 2 task times out | BP research ran long | Reduce `max_research_iterations` or `max_actions_per_iteration` in config |
| PubMed rate limit errors | Too many concurrent PubMed queries | Reduce `phase2_pubmed_retmax`; NCBI_API_KEY in `.env` raises the rate limit |
