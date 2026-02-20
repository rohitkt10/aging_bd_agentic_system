# Phase 2 — Agent Intelligence

**Goal:** Rewrite agent nodes to use LLM-powered reasoning instead of deterministic keyword extraction.

**Reference:** `/home/rohitpc/projects/aging_bd_agentic_system/docs/langgraph-deep-research/` for ADK deep-research patterns

---

## 2.1 Understand What Needs To Change

**Current (Copilot's implementation):**
- `phase1_research`: Uses hardcoded `PHASE1_KEYWORDS` dict for keyword matching
- `phase1_critic`: Rule-based validation (count checks, field existence)
- `phase2_research`: Iterates through candidates, counts PubMed hits for scoring
- `phase2_critic`: Rule-based validation (gene count thresholds)

**Target (LLM-powered):**
- `phase1_research`: LLM analyzes corpus results + Lopez-Otin context to extract processes
- `phase1_critic`: LLM evaluates quality, coverage, distinctness of processes
- `phase2_research`: LLM synthesizes evidence from multiple sources for each gene
- `phase2_critic`: LLM judges if sufficient gene evidence was collected

---

## 2.2 Phase 1 Agent Rewrite

**File to completely rewrite:** `src/aging_bd_agentic_system/agents/phase1_bp_identifier.py`

### 2.2.1 New `phase1_research` Node

**Old approach:**
- Scan vector DB results for keywords like "methylation", "chromatin"
- Use keyword dictionary to map to process names
- Score by counting PubMed hits

**New approach:**
1. Call vector DB to get relevant literature chunks
2. Pass chunks + Lopez-Otin context + hallmark to LLM
3. LLM extracts biological processes with evidence summaries and scores
4. Return structured list of processes

**Implementation:**

```python
"""
Phase 1 Agent: Biological Process Identification

Uses LLM-powered reasoning to identify biological processes for aging hallmarks.
"""

from __future__ import annotations

import json
from typing import Any

from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.llm.prompts import PHASE1_SYSTEM_PROMPT
from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.tools import query_pubmed, query_vector_db


def load_lopez_otin_context(state: dict[str, Any]) -> dict[str, Any]:
    """Load the Lopez-Otin paper text into state if missing."""
    if state.get("lopez_otin_context"):
        return {}
    path = config.DATA_DIR / "lopez-otin-22.md"
    text = path.read_text(encoding="utf-8")
    return {"lopez_otin_context": text}


def phase1_plan(state: dict[str, Any]) -> dict[str, Any]:
    """Create a research plan for Phase 1 using LLM."""
    hallmark = state["hallmark_name"].strip()
    lopez_context = state.get("lopez_otin_context", "")

    prompt = f"""Based on the hallmark "{hallmark}", create a research plan to identify biological processes.

Context from Lopez-Otin paper:
{lopez_context[:2000]}...

Output a JSON list of 4-6 research goals:
```json
["goal 1", "goal 2", ...]
```
"""

    llm = get_llm()
    response = llm.invoke(prompt)

    # Parse JSON response
    try:
        # Extract JSON from response (in case LLM adds extra text)
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            plan = json.loads(json_str)
        else:
            # Fallback to default plan
            plan = [
                f"Review Lopez-Otin context for {hallmark} mechanisms",
                f"Search corpus for {hallmark} and related processes",
                "Cross-check candidate processes in PubMed",
                "Rank processes by strength of evidence",
            ]
    except json.JSONDecodeError:
        # Fallback to default plan
        plan = [
            f"Review Lopez-Otin context for {hallmark} mechanisms",
            f"Search corpus for {hallmark} and related processes",
            "Cross-check candidate processes in PubMed",
            "Rank processes by strength of evidence",
        ]

    return {"phase1_plan": plan}


def phase1_research(state: dict[str, Any]) -> dict[str, Any]:
    """
    Use LLM to identify biological processes from corpus and context.

    Process:
    1. Query vector DB for relevant literature
    2. Query Lopez-Otin paper
    3. Pass evidence to LLM with structured prompt
    4. LLM returns list of biological processes with evidence
    """
    hallmark = state["hallmark_name"].strip()
    lopez_context = state.get("lopez_otin_context", "")

    # Step 1: Gather evidence from tools
    vector_results = query_vector_db(query=hallmark, top_k=15)

    # Get sample PubMed results for context (not for every process yet)
    pubmed_results = query_pubmed(query=f"{hallmark} aging biological processes", retmax=10)

    # Step 2: Build context for LLM
    corpus_snippets = "\n\n".join([
        f"Document: {rec.get('pmcid', 'unknown')}\n{rec.get('text', '')[:500]}"
        for rec in vector_results[:10]
    ])

    pubmed_snippets = "\n\n".join([
        f"PMID:{rec.get('pmid')} - {rec.get('title', '')}\n{rec.get('abstract', '')[:300]}"
        for rec in pubmed_results[:5]
    ])

    # Step 3: Call LLM with prompt
    prompt = PHASE1_SYSTEM_PROMPT.format(
        hallmark_name=hallmark
    )

    # Add context to prompt
    full_prompt = f"""{prompt}

## Reference Context

### Lopez-Otin Hallmarks Paper
{lopez_context[:3000]}

### Relevant Literature from Corpus
{corpus_snippets}

### PubMed Search Results
{pubmed_snippets}

Based on this context, identify the biological processes.
"""

    llm = get_llm()

    # Try structured output first
    try:
        # Define schema for biological processes
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "process_name": {"type": "string"},
                    "evidence_score": {"type": "integer"},
                    "evidence_summary": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["process_name", "evidence_score", "evidence_summary", "sources"],
            },
        }

        processes = llm.invoke_structured(full_prompt, schema=schema)

    except Exception as e:
        # Fallback: parse JSON from text response
        print(f"Structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(full_prompt)

        # Extract JSON from response
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            processes = json.loads(json_str)
        else:
            raise ValueError("LLM did not return valid JSON array of processes")

    # Step 4: Validate and return
    if not processes:
        raise ValueError("LLM returned empty process list")

    # Add rank field
    for idx, proc in enumerate(processes, start=1):
        proc["rank"] = idx

    return {"biological_processes": processes}


def phase1_critic(state: dict[str, Any]) -> dict[str, Any]:
    """
    Use LLM to critique the quality of identified biological processes.

    LLM evaluates:
    - Count (10-15 processes?)
    - Evidence quality
    - Distinctness (no duplicates/overlap)
    - Specificity (mechanisms, not outcomes)

    If count is off, LLM suggests specific splits/merges to adjust.
    """
    hallmark = state["hallmark_name"]
    processes = state.get("biological_processes", [])

    if not processes:
        return {
            "phase1_eval": {
                "grade": "fail",
                "comment": "No biological processes identified",
                "missing_themes": ["all"],
                "follow_up_queries": [f"{hallmark} aging biological processes mechanisms"],
                "split_instructions": [],
                "merge_instructions": [],
            }
        }

    # Serialize processes for LLM
    processes_json = json.dumps(processes, indent=2)

    prompt = PHASE1_CRITIQUE_PROMPT.format(
        hallmark_name=hallmark,
        processes_json=processes_json
    )

    llm = get_llm()

    try:
        # Try structured output with split/merge fields
        schema = {
            "type": "object",
            "properties": {
                "grade": {"type": "string", "enum": ["pass", "fail"]},
                "comment": {"type": "string"},
                "missing_themes": {"type": "array", "items": {"type": "string"}},
                "follow_up_queries": {"type": "array", "items": {"type": "string"}},
                "split_instructions": {"type": "array", "items": {"type": "string"}},
                "merge_instructions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["grade", "comment", "missing_themes", "follow_up_queries", "split_instructions", "merge_instructions"],
        }

        eval_result = llm.invoke_structured(prompt, schema=schema)

    except Exception:
        # Fallback to JSON parsing
        response = llm.invoke(prompt)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            eval_result = json.loads(json_str)
        else:
            raise ValueError("LLM did not return valid JSON for evaluation")

    return {"phase1_eval": eval_result}


def phase1_refine(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run refinement operations when Phase 1 critique fails or count is off.

    Handles three types of operations from the critic:
    1. follow_up_queries - Search for more literature
    2. split_instructions - Split broad processes into narrower ones
    3. merge_instructions - Merge narrow processes into broader ones
    """
    eval_data = state.get("phase1_eval", {})
    follow_up = eval_data.get("follow_up_queries", [])
    split_instructions = eval_data.get("split_instructions", [])
    merge_instructions = eval_data.get("merge_instructions", [])
    iteration = state.get("phase1_iteration", 0) + 1

    hallmark = state.get("hallmark_name")
    updates: dict[str, Any] = {"phase1_iteration": iteration}

    processes = list(state.get("biological_processes", []))

    # === HANDLE SPLITS ===
    if split_instructions:
        for instruction in split_instructions:
            # Use LLM to execute the split
            split_prompt = f"""Execute this split instruction on the biological processes list:

Instruction: {instruction}

Current processes:
{json.dumps([p['process_name'] for p in processes], indent=2)}

Return a JSON array showing how to split. Format:
```json
[
  {{
    "original": "DNA methylation changes",
    "split_into": ["DNA hypermethylation", "DNA hypomethylation"]
  }}
]
```
"""

            llm = get_llm()
            response = llm.invoke(split_prompt)

            try:
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    split_plan = json.loads(json_str)

                    # Execute the splits
                    for split in split_plan:
                        original = split.get("original")
                        split_into = split.get("split_into", [])

                        # Find the original process
                        for i, proc in enumerate(processes):
                            if proc["process_name"] == original:
                                # Remove original, add split versions
                                processes.pop(i)
                                for new_name in split_into:
                                    processes.append({
                                        "rank": 0,
                                        "process_name": new_name,
                                        "evidence_score": proc["evidence_score"],  # Inherit score
                                        "evidence_summary": f"Split from {original}. {proc.get('evidence_summary', '')}",
                                        "sources": proc.get("sources", []),
                                    })
                                break
            except json.JSONDecodeError:
                pass  # Skip if split fails

    # === HANDLE MERGES ===
    if merge_instructions:
        for instruction in merge_instructions:
            # Use LLM to execute the merge
            merge_prompt = f"""Execute this merge instruction on the biological processes list:

Instruction: {instruction}

Current processes:
{json.dumps([p['process_name'] for p in processes], indent=2)}

Return a JSON array showing how to merge. Format:
```json
[
  {{
    "merge": ["histone acetylation alterations", "histone methylation alterations"],
    "into": "histone modification alterations",
    "keep_highest_score": true
  }}
]
```
"""

            llm = get_llm()
            response = llm.invoke(merge_prompt)

            try:
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    merge_plan = json.loads(json_str)

                    # Execute the merges
                    for merge in merge_plan:
                        to_merge = merge.get("merge", [])
                        into_name = merge.get("into")
                        keep_highest = merge.get("keep_highest_score", True)

                        # Find the processes to merge
                        to_remove = []
                        merged_proc = None
                        best_score = 0

                        for proc_name in to_merge:
                            for i, proc in enumerate(processes):
                                if proc["process_name"] == proc_name:
                                    if keep_highest and proc["evidence_score"] > best_score:
                                        best_score = proc["evidence_score"]
                                        merged_proc = proc.copy()
                                    else:
                                        to_remove.append(proc)
                                    break

                        if merged_proc and into_name:
                            merged_proc["process_name"] = into_name
                            # Remove merged processes
                            for proc in to_remove:
                                if proc in processes:
                                    processes.remove(proc)
                            # Add the merged process
                            processes.append(merged_proc)
            except json.JSONDecodeError:
                pass  # Skip if merge fails

    # === HANDLE FOLLOW-UP SEARCHES (existing behavior) ===
    if follow_up:
        new_processes = []

        for query in follow_up[:3]:  # Limit to 3 follow-up queries
            # Query vector DB
            vector_results = query_vector_db(query=query, top_k=5)

            # Query PubMed
            pubmed_results = query_pubmed(query=f"{query}", retmax=3)

            # Use LLM to extract any NEW processes from this evidence
            existing_processes = {p["process_name"] for p in processes}

            corpus_snippets = "\n\n".join([
                rec.get('text', '')[:300] for rec in vector_results
            ])

            pubmed_snippets = "\n\n".join([
                f"PMID:{rec.get('pmid')} - {rec.get('title', '')}"
                for rec in pubmed_results
            ])

            extract_prompt = f"""Extract biological processes related to "{hallmark}" from the following evidence.

Corpus:
{corpus_snippets}

PubMed:
{pubmed_snippets}

Already identified: {', '.join(existing_processes)}

Return ONLY a JSON list of NEW processes not already identified:
```json
[
  {{
    "process_name": "name",
    "evidence_score": 7,
    "evidence_summary": "...",
    "sources": ["PMID:xxx"]
  }}
]
```
"""

            llm = get_llm()
            response = llm.invoke(extract_prompt)

            try:
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    extracted = json.loads(json_str)
                    new_processes.extend(extracted)
            except json.JSONDecodeError:
                pass  # Skip if extraction fails

        if new_processes:
            processes.extend(new_processes)

    # Update the biological processes with all changes
    updates["biological_processes"] = processes

    return updates


def phase1_finalize(state: dict[str, Any]) -> dict[str, Any]:
    """
    Finalize Phase 1 by sorting processes and creating BP queue.
    """
    processes = list(state.get("biological_processes", []))

    # Sort by evidence score desc, then by process name
    processes.sort(
        key=lambda p: (-p.get("evidence_score", 0), p.get("process_name", ""))
    )

    # Trim to 10-15
    processes = processes[:15]

    # Re-rank
    for idx, proc in enumerate(processes, start=1):
        proc["rank"] = idx

    # Create queue
    bp_queue = [p["process_name"] for p in processes if p.get("process_name")]

    return {"biological_processes": processes, "bp_queue": bp_queue}
```

### 2.2.2 Verify Phase 1 Workflow

**Nodes in order:**
1. `load_context` → Load Lopez-Otin paper
2. `phase1_plan` → LLM generates research plan
3. `phase1_research` → LLM extracts processes from evidence
4. `phase1_critic` → LLM evaluates quality AND count (suggests splits/merges if needed)
5. `phase1_refine` (if needed) → Executes splits, merges, or follow-up searches
6. `phase1_finalize` → Sort and create queue

**Critique → Refine Loop:**
- If grade="fail" OR count < 10 OR count > 15 → route to refine
- Refine handles:
  - **Split operations**: LLM breaks broad processes into narrower ones
  - **Merge operations**: LLM combines narrow/overlapping processes
  - **Follow-up searches**: Query literature for missing themes
- After refine → route back to critic for re-evaluation
- Max 3 iterations, then proceed to finalize

**Key changes from Copilot's version:**
- ✅ LLM extracts processes (not keyword extraction)
- ✅ LLM critiques quality (not rule-based checks)
- ✅ Evidence summaries synthesized by LLM
- ✅ Scoring based on LLM judgment (not hit counts)
- ✅ Autonomous count adjustment via split/merge (NEW)

---

## 2.3 Phase 2 Agent Rewrite - Autonomous ReAct Loop

**File to completely rewrite:** `src/aging_bd_agentic_system/agents/phase2_gene_researcher.py`

### 2.3.1 Research Pattern: Autonomous ReAct Loop

**Instead of a single research call, Phase 2 uses an autonomous ReAct loop:**

```
For each biological process:
│
├─ ReAct Research Loop (configurable, default: 7 iterations)
│  • Iteration 1-2: Wide exploration (all sources, broad queries)
│  • Iteration 3-4: Follow rabbit holes (explore interesting leads)
│  • Iteration 5-6: Balance + exploitation (deepen findings, fill gaps)
│  • Iteration 7: Final summary (synthesize, score, finalize)
│
├─ Critic (reviews research output)
│  • Grades: pass/fail
│  • Provides feedback on gaps
│
└─ If fail → Refine (2-3 iterations, focused on critic feedback)
   └─ Re-criticize → pass → Next BP
```

**Configuration:**
- `PHASE2_RESEARCH_MAX_ITERATIONS` - Default 7 (from `.env`)
- `PHASE2_REFINE_MAX_ITERATIONS` - Default 3 (from `.env`)

**Key change from Copilot's version:**
- Copilot: Single call to gather evidence, then score
- New: Autonomous agent explores all 4 sources intelligently over multiple iterations

### 2.3.2 ReAct Research Node

**Old approach:**
- Iterate through candidate genes
- Count PubMed + vector DB hits
- Score by hit count (8 if both, 6 if one)

**New approach:**
- LLM scientist agent with tool-calling capability
- Queries all 4 sources (GenAge, OpenGenes, PubMed, Vector DB)
- Decides what to search for based on findings
- Shifts from exploration → exploitation over iterations

**Implementation:**

```python
"""
Phase 2 Agent: Gene Research and GO Term Mapping

Uses LLM-powered reasoning to identify genes and GO terms for biological processes.
"""

from __future__ import annotations

import json
from typing import Any

from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.llm.prompts import (
    PHASE2_GO_MAPPING_PROMPT,
    PHASE2_RESEARCH_PROMPT,
)
from aging_bd_agentic_system.tools import (
    query_genage,
    query_go_terms,
    query_opengenes,
    query_pubmed,
    query_vector_db,
)


def select_bp(state: dict[str, Any]) -> dict[str, Any]:
    """Select the current biological process from the queue."""
    bp_queue = state.get("bp_queue", [])
    index = state.get("current_bp_index", 0)

    if index >= len(bp_queue):
        return {}  # Signal to exit loop

    return {"current_bp_name": bp_queue[index]}


def seed_gene_candidates(state: dict[str, Any]) -> dict[str, Any]:
    """
    Seed candidate genes using GenAge and OpenGenes databases.

    Unlike Copilot's version, we store the actual gene data (not just symbols)
    so the LLM has more context to work with.
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")

    # Query databases
    genage_results = query_genage(query=bp_name, max_results=50)
    opengenes_results = query_opengenes(query=bp_name, max_results=50)

    # Combine and dedupe
    seen = set()
    candidates = []

    for rec in genage_results:
        symbol = rec.get("symbol")
        if symbol and symbol not in seen:
            seen.add(symbol)
            candidates.append({
                "symbol": symbol,
                "source": "genage",
                "name": rec.get("name", ""),
            })

    for rec in opengenes_results:
        symbol = rec.get("symbol")
        if symbol and symbol not in seen:
            seen.add(symbol)
            candidates.append({
                "symbol": symbol,
                "source": "opengenes",
                "name": rec.get("name", ""),
            })

    # Store as JSON in scratchpad
    return {"research_scratchpad": json.dumps(candidates)}


def phase2_research(
    state: dict[str, Any],
    genage_seed_max_results: int = 50,
    opengenes_seed_max_results: int = 50,
    max_opengenes_items_per_field: int = -1,
    min_actions_per_iteration: int = 1,
    max_actions_per_iteration: int = 3,
    pubmed_max_results: int = 5,
    vector_db_max_results: int = 5,
) -> dict[str, Any]:
    """
    Autonomous ReAct research loop for gene discovery.

    This function runs a multi-iteration research loop where the LLM scientist agent:
    1. Queries all 4 sources (GenAge, OpenGenes, PubMed, Vector DB)
    2. Decides what to search for based on findings
    3. Shifts from exploration → exploitation over iterations
    4. Synthesizes and scores genes at the end

    Args:
        genage_seed_max_results: Maximum GenAge results to fetch during seeding (default 50)
        opengenes_seed_max_results: Maximum OpenGenes results to fetch during seeding (default 50)
        max_opengenes_items_per_field: Maximum items per OpenGenes field to include.
            -1 (default): Include all items (no truncation)
            0+: Truncate to first N items per field
        min_actions_per_iteration: Minimum research actions per iteration (default 1)
        max_actions_per_iteration: Maximum research actions per iteration (default 3)
        pubmed_max_results: Maximum PubMed results to process per action (default 5)
        vector_db_max_results: Maximum vector DB results to process per action (default 5)

    Iterations (configurable via PHASE2_RESEARCH_MAX_ITERATIONS):
    - Iteration 1-2: Wide exploration (all sources, broad queries)
    - Iteration 3-4: Follow rabbit holes (explore interesting leads)
    - Iteration 5-6: Balance + exploitation (deepen findings, fill gaps)
    - Iteration 7: Final summary (synthesize, score, finalize)

    Returns:
        Genes with scores (5+ only) and evidence summaries
    """
    import os
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")
    max_iterations = int(os.environ.get("PHASE2_RESEARCH_MAX_ITERATIONS", "7"))

    # Get current iteration
    current_iteration = state.get("phase2_research_iteration", 0)

    # Initialize scratchpad if first iteration
    if current_iteration == 0:
        # Seed with candidates from databases
        genage_results = query_genage(query=bp_name, max_results=50)
        opengenes_results = query_opengenes(query=bp_name, max_results=50)

        # Combine and dedupe
        seen = set()
        candidates = []

        for rec in genage_results:
            symbol = rec.get("symbol")
            if symbol and symbol not in seen:
                seen.add(symbol)
                candidates.append({
                    "symbol": symbol,
                    "name": rec.get("name", ""),
                    "source": "genage",
                    "longevity_score": rec.get("longevity_effect", ""),
                })

        for rec in opengenes_results:
            symbol = rec.get("symbol")
            if symbol and symbol not in seen:
                seen.add(symbol)
                candidates.append({
                    "symbol": symbol,
                    "name": rec.get("name", ""),
                    "source": "opengenes",
                    "intervention": rec.get("intervention", ""),
                })

        # Store in scratchpad as structured JSON
        research_data = {
            "initial_database_genes": candidates,
            "research_findings": [],  # Accumulated findings from iterations
        }
        return {
            "research_scratchpad": json.dumps(research_data, default=str),
            "phase2_research_iteration": 1
        }

    # Load current research state
    try:
        research_data = json.loads(state.get("research_scratchpad", "{}"))
    except json.JSONDecodeError:
        research_data = {"initial_database_genes": [], "research_findings": []}

    llm = get_llm()

    # Determine research phase based on iteration
    if current_iteration <= 2:
        phase = "exploration"
        guidance = "Cast a wide net. Query all 4 sources with broad terms. Note what looks interesting."
    elif current_iteration <= 4:
        phase = "rabbit_hole"
        guidance = "Follow interesting leads you found. Search for specific genes or terms that keep appearing."
    elif current_iteration < max_iterations:
        phase = "exploitation"
        guidance = "Deepen your findings. Fill gaps in weak evidence. Cross-reference."
    else:
        phase = "finalization"
        guidance = "Synthesize all findings. Score genes 1-10. Return only genes with score 5+."

    # Build research summary for LLM
    findings_summary = json.dumps(research_data.get("research_findings", [])[:10], indent=2)
    candidates_summary = json.dumps([c["symbol"] for c in research_data.get("initial_database_genes", [])[:20]], indent=2)

    # Create system prompt for this iteration
    research_prompt = f"""You are a gene research scientist studying "{bp_name}" as part of aging hallmark "{hallmark}".

## Research Phase: {phase.upper()}
{guidance}

## Current State
- Iteration: {current_iteration} of {max_iterations}
- Candidates identified so far: {candidates_summary}
- Key findings from previous iterations: {findings_summary}

## Available Tools
1. query_genage - Search GenAge database for longevity genes
2. query_opengenes - Search OpenGenes database for intervention effects
3. query_pubmed - Search PubMed for literature
4. query_vector_db - Search local literature corpus

## Your Task
Based on the phase and current findings:
1. Decide which source(s) to query
2. Decide what search terms to use
3. Call the appropriate tools
4. Record your findings

## Tools Information
- GenAge: Contains genes with longevity associations and scores
- OpenGenes: Contains genes with lifespan intervention data
- PubMed: Use for recent literature and specific gene-term associations
- Corpus: Use for broad contextual information and mechanistic insights

If this is the final iteration (iteration {max_iterations}), output a FINAL_SUMMARY with scored genes.
"""

    # Call LLM with tool-calling capability
    # For now, we'll implement a simplified version where the LLM outputs what to search for
    # In full implementation, this would use LangChain's agent framework with actual tool calling

    # Prompt LLM to decide what to research
    decision_prompt = f"""{research_prompt}

Based on the current phase ({phase}), what should you search for?

Return JSON:
```json
{{
  "actions": [
    {{"source": "genage|opengenes|pubmed|vector_db", "query": "search term", "reason": "why"}}
  ],
  "findings_notes": ["interesting observation 1", "interesting observation 2"]
}}
```

Be specific with your queries. Use 1-3 actions per iteration.
"""

    response = llm.invoke(decision_prompt)

    # Parse LLM's research decisions
    try:
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            decisions = json.loads(json_str)
        else:
            decisions = {"actions": [], "findings_notes": []}
    except json.JSONDecodeError:
        decisions = {"actions": [], "findings_notes": []}

    # Execute the research actions
    new_findings = []

    for action in decisions.get("actions", []):
        source = action.get("source")
        query = action.get("query")

        if source == "genage":
            results = query_genage(query=query, max_results=20)
            for rec in results[:5]:
                new_findings.append({
                    "source": "genage",
                    "gene": rec.get("symbol"),
                    "query": query,
                    "finding": f"Longevity association: {rec.get('longevity_effect', 'N/A')}"
                })

        elif source == "opengenes":
            results = query_opengenes(query=query, max_results=20)
            for rec in results[:5]:
                new_findings.append({
                    "source": "opengenes",
                    "gene": rec.get("symbol"),
                    "query": query,
                    "finding": f"Intervention: {rec.get('intervention', 'N/A')}"
                })

        elif source == "pubmed":
            results = query_pubmed(query=query, retmax=10)
            for rec in results[:5]:
                new_findings.append({
                    "source": "pubmed",
                    "gene": None,  # May or may not mention a gene
                    "query": query,
                    "finding": f"{rec.get('title', '')}: {rec.get('abstract', '')[:200]}"
                })

        elif source == "vector_db":
            results = query_vector_db(query=query, top_k=10)
            for rec in results[:5]:
                new_findings.append({
                    "source": "corpus",
                    "gene": None,
                    "query": query,
                    "finding": rec.get("text", "")[:300]
                })

    # Update research data
    research_data["research_findings"].extend(new_findings)
    research_data["research_findings"].extend(decisions.get("findings_notes", []))

    # If final iteration, synthesize and score genes
    if current_iteration >= max_iterations:
        # Prepare final summary for scoring
        all_findings = research_data.get("research_findings", [])
        all_candidates = research_data.get("initial_database_genes", [])

        scoring_prompt = f"""You are finalizing gene research for "{bp_name}" (part of "{hallmark}").

## All Candidates
{json.dumps([c['symbol'] for c in all_candidates], indent=2)}

## Research Findings
{json.dumps(all_findings[:50], indent=2)}

## Your Task
1. Synthesize all evidence
2. Score each gene 1-10 (only genes with score 5+)
3. Write 2-3 sentence evidence summaries
4. List sources (PMIDs, database names)

Return JSON array:
```json
[
  {{
    "gene_symbol": "TP53",
    "score": 8,
    "evidence_summary": "PMID:123 shows...",
    "sources": ["PMID:123", "GenAge"]
  }}
]
```
"""

        llm_response = llm.invoke(scoring_prompt)

        try:
            json_start = llm_response.find("[")
            json_end = llm_response.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                scored_genes = json.loads(json_str)
            else:
                scored_genes = []
        except json.JSONDecodeError:
            scored_genes = []

        # Add biological_process field
        for gene in scored_genes:
            gene["biological_process"] = bp_name

        return {
            "genes_found": scored_genes,
            "phase2_research_iteration": 0  # Reset for next BP
        }

    # Not final iteration - continue research loop
    return {
        "research_scratchpad": json.dumps(research_data, default=str),
        "phase2_research_iteration": current_iteration + 1
    }


def phase2_critic(state: dict[str, Any], min_genes_expected: int = 20) -> dict[str, Any]:
    """
    Use LLM to evaluate gene evidence coverage for the current BP.

    LLM judges:
    - Are there enough genes?
    - Is evidence strong?
    - Are genes relevant to the BP?
    """
    bp_name = state.get("current_bp_name", "")

    # Get genes for this BP only
    all_genes = state.get("genes_found", [])
    bp_genes = [g for g in all_genes if g.get("biological_process") == bp_name]

    if not bp_genes:
        return {
            "phase2_eval": {
                "grade": "fail",
                "comment": f"No genes found for {bp_name}",
                "follow_up_queries": [f"{bp_name} genes aging mechanisms"],
            }
        }

    genes_json = json.dumps(bp_genes, indent=2)

    prompt = PHASE2_CRITIQUE_PROMPT.format(
        biological_process=bp_name,
        genes_json=genes_json
    )

    llm = get_llm()

    try:
        schema = {
            "type": "object",
            "properties": {
                "grade": {"type": "string", "enum": ["pass", "fail"]},
                "comment": {"type": "string"},
                "follow_up_queries": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["grade", "comment", "follow_up_queries"],
        }

        eval_result = llm.invoke_structured(prompt, schema=schema)

    except Exception:
        # Fallback
        response = llm.invoke(prompt)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            eval_result = json.loads(json_str)
        else:
            eval_result = {
                "grade": "pass" if len(bp_genes) >= min_genes_expected else "fail",
                "comment": f"Found {len(bp_genes)} genes",
                "follow_up_queries": [],
            }

    eval_result["min_genes_expected"] = min_genes_expected
    return {"phase2_eval": eval_result}


def phase2_refine(
    state: dict[str, Any],
    max_follow_up_queries: int = 2,
    refine_vector_db_results: int = 5,
    refine_pubmed_results: int = 3,
    max_genes_per_query: int = 5,
) -> dict[str, Any]:
    """
    Run follow-up queries when Phase 2 critique fails.

    Args:
        max_follow_up_queries: Maximum follow-up queries to execute (default 2)
        refine_vector_db_results: Max vector DB results per query (default 5)
        refine_pubmed_results: Max PubMed results per query (default 3)
        max_genes_per_query: Max genes to extract per query (default 5)
    """
    eval_data = state.get("phase2_eval", {})
    follow_up = eval_data.get("follow_up_queries", [])
    iteration = state.get("phase2_critic_iteration", 0) + 1

    bp_name = state.get("current_bp_name", "")
    updates: dict[str, Any] = {"phase2_critic_iteration": iteration}

    # Refinement: query tools and extract genes using LLM
    for query in follow_up[:max_follow_up_queries]:
        # Use the query to find more genes
        vector_results = query_vector_db(query=query, top_k=refine_vector_db_results)
        pubmed_results = query_pubmed(query=query, retmax=refine_pubmed_results)

        # Collect text for LLM extraction
        extraction_context = []
        for vec in vector_results:
            extraction_context.append(f"Corpus: {vec.get('text', '')[:500]}")

        for pub in pubmed_results:
            title = pub.get('title', '')
            abstract = pub.get('abstract', '')
            extraction_context.append(f"PubMed: {title}\\n{abstract[:400]}")

        if not extraction_context:
            continue

        # Use LLM to extract actual gene symbols
        llm = get_llm()

        extraction_prompt = f"""## Text from Literature Search

        Query: {query}

        {" ".join(extraction_context)}

        ## Task
        Extract gene symbols mentioned in the text above that are relevant to: {bp_name}

        Return ONLY a JSON array of gene symbols (e.g., ["TP53", "FOXO3"]).
        """

        extraction_schema = {
            "title": "gene_symbols",
            "type": "array",
            "items": {"type": "string"},
        }

        try:
            extracted_genes = llm.invoke_structured(
                extraction_prompt,
                schema=extraction_schema,
                system_prompt="You are a gene symbol extractor. Return only standard gene symbols."
            )

            # Create gene entries
            new_genes = [
                {
                    "gene_symbol": gene,
                    "score": 6,
                    "biological_process": bp_name,
                    "evidence_summary": f"Found via follow-up query: {query}",
                    "sources": ["refinement"],
                }
                for gene in extracted_genes[:max_genes_per_query]
            ]

            if new_genes:
                updates["genes_found"] = new_genes

        except Exception:
            # Fallback: skip gene extraction on failure
            pass

    return updates


def map_go_terms(state: dict[str, Any], max_results: int = 10) -> dict[str, Any]:
    """
    Map GO biological process terms using LLM for relevance scoring.

    Process:
    1. Query GO database for terms
    2. Pass results to LLM
    3. LLM scores relevance and filters
    """
    bp_name = state.get("current_bp_name", "").strip()
    hallmark = state.get("hallmark_name")

    # Query GO terms
    go_results = query_go_terms(query=bp_name, max_results=20)

    if not go_results:
        return {"go_terms_found": []}

    # Format for LLM
    go_json = json.dumps(go_results, indent=2)

    prompt = PHASE2_GO_MAPPING_PROMPT.format(
        biological_process=bp_name,
        hallmark_name=hallmark
    )

    full_prompt = f"""{prompt}

## GO Terms to Evaluate

{go_json}

For each GO term, provide:
- go_id (exactly as provided)
- go_label (exactly as provided)
- relevance_score (1-10, only include terms with score 6+)
- evidence_summary (1-2 sentences explaining relevance)

Return a JSON array.
"""

    llm = get_llm()

    try:
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "go_id": {"type": "string"},
                    "go_label": {"type": "string"},
                    "relevance_score": {"type": "integer"},
                    "evidence_summary": {"type": "string"},
                },
                "required": ["go_id", "go_label", "relevance_score", "evidence_summary"],
            },
        }

        scored_terms = llm.invoke_structured(full_prompt, schema=schema)

    except Exception:
        # Fallback to JSON parsing
        response = llm.invoke(full_prompt)
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            scored_terms = json.loads(json_str)
        else:
            scored_terms = []

    # Add definition and biological_process
    for term in scored_terms:
        # Find original definition
        go_id = term.get("go_id", "")
        original = next((g for g in go_results if g.get("go_id") == go_id), {})
        term["definition"] = original.get("definition", "")
        term["biological_process"] = bp_name
        term["sources"] = [go_id]

    return {"go_terms_found": scored_terms}


def advance_bp(state: dict[str, Any]) -> dict[str, Any]:
    """Advance to the next biological process."""
    return {
        "current_bp_index": state.get("current_bp_index", 0) + 1,
        "current_bp_name": "",
        "research_scratchpad": "",
        "phase2_critic_iteration": 0,
        "phase2_research_iteration": 0,  # Also reset research iteration for next BP
    }
```

---

## 2.4 Update Helpers Module

**File:** `src/aging_bd_agentic_system/agents/helpers.py`

**Changes needed:**
- Remove `run_tool()` function (no longer needed with direct tool calls)
- Remove `append_warning()` (warnings can be added directly to state)
- Keep utility functions if useful, otherwise simplify

**Simplified version:**

```python
"""
Helper utilities for agent nodes.
"""

from __future__ import annotations

from typing import Any


def unique_non_empty(items: list[Any]) -> list[Any]:
    """Return unique non-empty items from a list."""
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
```

---

## 2.5 Delete Old Prompt Files

**Files to delete:**
- `src/aging_bd_agentic_system/prompts/phase1.py` (moved to `llm/prompts.py`)
- `src/aging_bd_agentic_system/prompts/phase2.py` (moved to `llm/prompts.py`)

Or keep them for reference but they won't be used.

---

## Phase 2 Completion Checklist

- [ ] `phase1_bp_identifier.py` completely rewritten with LLM calls
- [ ] `phase2_gene_researcher.py` completely rewritten with autonomous ReAct research loop
- [ ] `helpers.py` simplified (removed logging functions)
- [ ] All agent nodes use `get_llm()` from llm module
- [ ] Prompts consolidated in `llm/prompts.py`
- [ ] Structured output with fallback to JSON parsing
- [ ] Error handling for LLM failures
- [ ] Environment variables added for iteration configuration
- [ ] Routing logic implements ReAct loop with configurable max iterations
- [ ] State schema includes `phase2_research_iteration` field
- [ ] **Context management integrated** (context_manager.summarize_if_needed called)
- [ ] **Findings selection fixed** (recent 10 instead of first 10)
- [ ] **System prompts used properly** (SystemMessage + HumanMessage separation)
- [ ] **Persistent logging implemented** (audit_logger for BP/workflow completion)
- [ ] **Full state output** (full_state.json written to outputs/{hallmark}/)

---

## Configuration Summary

**All configurable iteration limits (via `.env`):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHASE1_MAX_ITERATIONS` | 3 | Phase 1 critique/refine loops |
| `PHASE2_RESEARCH_MAX_ITERATIONS` | 7 | Phase 2 autonomous research loop (per BP) |
| `PHASE2_REFINE_MAX_ITERATIONS` | 3 | Phase 2 refinement after critique |

**Total worst-case iterations per hallmark:**
- Phase 1: 3 research cycles
- Phase 2: 15 BPs × (7 research + 3 refine) = 150 iterations
- **Total: ~153 LLM calls per hallmark**

**To adjust for cost/time:**
- Reduce `PHASE2_RESEARCH_MAX_ITERATIONS` to 5 for faster runs
- Reduce `PHASE2_REFINE_MAX_ITERATIONS` to 2 to limit refinement
- These are trade-offs between thoroughness and speed

---

## Testing Strategy

**Manual test:** Run a single hallmark through the workflow

```bash
python -m aging_bd_agentic_system.main --hallmark "epigenetic alterations"
```

**What to verify:**
1. Phase 1 produces 10-15 biological processes
2. Each process has LLM-generated evidence summary
3. Phase 2 produces genes for each process
4. Each gene has LLM-generated evidence summary
5. GO terms are mapped with relevance scores
6. Outputs written to `outputs/{hallmark}/`

**Expected improvement over Copilot's version:**
- Better quality process names (LLM extracts, not keyword matches)
- More nuanced scoring (LLM judgment, not hit counts)
- Richer evidence summaries (LLM synthesizes, not concatenates)
- More adaptive refinement (LLM identifies gaps, not fixed rules)

---

## Next Phase

After completing Phase 2, proceed to **Phase 3 — Observability**, where we'll replace manual JSONL logging with LangGraph callback-based tracing.
