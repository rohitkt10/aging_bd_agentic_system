"""
Phase 1 Agent: Biological Process Identification

Uses LLM-powered reasoning to identify biological processes for aging hallmarks.
"""

from __future__ import annotations

import json
from typing import Any

from aging_bd_agentic_system.llm import get_llm
from aging_bd_agentic_system.llm.prompts import PHASE1_CRITIQUE_PROMPT, PHASE1_SYSTEM_PROMPT
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

    # Step 2: Build user context for LLM
    user_context = f"""## Reference Context

### Lopez-Otin Hallmarks Paper
{lopez_context[:3000]}

### Relevant Literature from Corpus
{chr(10).join([f"Document: {rec.get('pmcid', 'unknown')}{chr(10)}{rec.get('text', '')[:500]}" for rec in vector_results[:10]])}

### PubMed Search Results
{chr(10).join([f"PMID:{rec.get('pmid')} - {rec.get('title', '')}{chr(10)}{rec.get('abstract', '')[:300]}" for rec in pubmed_results[:5]])}

Based on this context, identify the biological processes.
"""

    # Step 3: Format system prompt with hallmark name
    system_prompt = PHASE1_SYSTEM_PROMPT.format(hallmark_name=hallmark)

    llm = get_llm()

    # Try structured output first
    try:
        # Define schema for biological processes
        schema = {
            "title": "biological_processes",
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

        processes = llm.invoke_structured(
            user_context,
            schema=schema,
            system_prompt=system_prompt
        )

    except Exception as e:
        # Fallback: parse JSON from text response
        print(f"Structured output failed ({e}), falling back to JSON parsing")
        response = llm.invoke(user_context, system_prompt=system_prompt)

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

    # Serialize processes for LLM (user message)
    user_context = json.dumps(processes, indent=2)

    # Format system prompt with variables
    system_prompt = PHASE1_CRITIQUE_PROMPT.format(
        hallmark_name=hallmark,
        processes_json="{PROCESSES_JSON}"  # Placeholder, will be in user message
    )

    # Remove the processes_json from system prompt since it's now in user message
    system_prompt = system_prompt.replace("{processes_json}", "See the processes in the user message.")

    llm = get_llm()

    try:
        # Try structured output with split/merge fields
        schema = {
            "title": "phase1_evaluation",
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

        eval_result = llm.invoke_structured(
            user_context,
            schema=schema,
            system_prompt=system_prompt
        )

    except Exception:
        # Fallback to JSON parsing
        response = llm.invoke(user_context, system_prompt=system_prompt)
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
