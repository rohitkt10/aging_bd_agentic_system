# Gap Analysis & Implementation Checklist

This repository already includes tools and data pipelines, but the orchestration layer is incomplete. Below is a concrete checklist of missing components.

## Missing or Incomplete Files

- `src/aging_bd_agentic_system/agents/phase1_bp_identifier.py` (not present)
- `src/aging_bd_agentic_system/agents/phase2_gene_researcher.py` (not present)
- `src/aging_bd_agentic_system/graph/workflow.py` (not present)
- `src/aging_bd_agentic_system/utils/validation.py` (not present)
- `src/aging_bd_agentic_system/utils/aggregation.py` (not present)
- `src/aging_bd_agentic_system/utils/context_manager.py` (not present)
- `src/aging_bd_agentic_system/prompts/phase2.py` (not present)
- `src/aging_bd_agentic_system/main.py` (not present)

## Implementation Checklist

1. **Define Phase 1 agent**
   - Load Lopez-Otin context
   - Use vector DB + PubMed
   - Output 10–15 BPs

2. **Define Phase 2 agent**
   - Seed genes with GenAge + OpenGenes
   - Use literature evidence to score
   - Map GO terms

3. **Build LangGraph workflow**
   - Phase 1 subgraph
   - Phase 2 loop
   - Critique/refinement loops

4. **Add aggregation + validation utilities**

5. **Add context summarization**

6. **Wire main entrypoint + CLI**

Once these are implemented, the system will be production-ready.
