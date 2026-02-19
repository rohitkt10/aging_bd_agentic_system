# Runbook

## Environment Setup
1. Install dependencies:
   ```bash
   make sync
   ```
2. Set required environment variables in `.env`:
   - `NCBI_EMAIL` (required for PubMed access)
   - `NCBI_API_KEY` (optional)

## Build Literature Corpus (if needed)
```bash
python scripts/fetch_pmc.py --n 500
python scripts/build_chunks.py
python scripts/build_index.py
```

## Run the Workflow
```bash
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"
```

## Outputs
Outputs are written to `outputs/{hallmark}/`:
- `processes.tsv`
- `genes.tsv`
- `go_terms.tsv`

## Logs
Audit logs are written to `logs/agent_traces/{hallmark}.jsonl`.

## Troubleshooting
- Missing `NCBI_EMAIL`: PubMed queries will fail.
- Missing FAISS index: run the corpus build steps above.
- Validation failures: run completes and reports issues without stopping.
