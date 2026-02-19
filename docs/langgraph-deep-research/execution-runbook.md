# Execution Runbook

This runbook describes how to run the end-to-end workflow once implemented.

## 1) Environment Setup

```bash
make sync
```

Set required environment variables in `.env`:

- `NCBI_EMAIL` (required for PubMed)
- `NCBI_API_KEY` (optional)
- `EMBEDDING_MODEL_ID` (optional override)

## 2) Build Literature Corpus (if needed)

```bash
python scripts/fetch_pmc.py --n 500
python scripts/build_chunks.py
python scripts/build_index.py
```

## 3) Run the Workflow

Once `graph/workflow.py` and agents are implemented:

```bash
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"
```

## 4) Verify Outputs

Check `outputs/{hallmark}/`:

- `processes.tsv`
- `genes.tsv`
- `go_terms.tsv`

## 5) Inspect Logs

Check `logs/agent_traces/` for JSONL traces and tool call history.
