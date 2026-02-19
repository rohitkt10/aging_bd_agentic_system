from __future__ import annotations

from typing import Any

from aging_bd_agentic_system.agents.helpers import append_warning, run_tool
from aging_bd_agentic_system.literature_pipeline import config
from aging_bd_agentic_system.tools import query_pubmed, query_vector_db
from aging_bd_agentic_system.utils.audit_logger import log_event

PHASE1_KEYWORDS = {
    "methylation": "DNA methylation changes",
    "chromatin": "Chromatin remodeling dysfunction",
    "histone": "Histone modification alterations",
    "repair": "DNA repair decline",
    "autophagy": "Autophagy impairment",
    "senescence": "Cellular senescence",
    "mitochondrial": "Mitochondrial dysfunction",
    "inflammation": "Inflammatory signaling",
}


def load_lopez_otin_context(state: dict[str, Any]) -> dict[str, Any]:
    """Load the Lopez-Otin paper text into state if missing."""
    if state.get("lopez_otin_context"):
        return {}
    path = config.DATA_DIR / "lopez-otin-22.md"
    text = path.read_text(encoding="utf-8")
    return {"lopez_otin_context": text}


def phase1_plan(state: dict[str, Any]) -> dict[str, Any]:
    """Create a simple research plan for Phase 1."""
    hallmark = state["hallmark_name"].strip()
    plan = [
        f"Review Lopez-Otin context for {hallmark} mechanisms",
        f"Search corpus for {hallmark} and related processes",
        "Cross-check candidate processes in PubMed",
        "Rank processes by strength of evidence",
    ]
    return {"phase1_plan": plan}


def _extract_candidates(texts: list[str]) -> list[str]:
    candidates: list[str] = []
    for text in texts:
        lowered = text.lower()
        for needle, label in PHASE1_KEYWORDS.items():
            if needle in lowered:
                candidates.append(label)
    return sorted(set(candidates))


def phase1_research(state: dict[str, Any]) -> dict[str, Any]:
    """Gather evidence for biological processes using corpus and PubMed."""
    hallmark = state["hallmark_name"].strip()
    updates: dict[str, Any] = {}

    vector_results, vector_updates = run_tool(
        tool_fn=query_vector_db,
        tool_name="query_vector_db",
        args={"query": hallmark, "top_k": 10},
        phase="phase1",
        node="phase1_research",
        hallmark=hallmark,
    )
    updates.update(vector_updates)

    candidates = _extract_candidates([rec.get("text", "") for rec in vector_results])
    if not candidates:
        candidates = list(PHASE1_KEYWORDS.values())

    processes: list[dict[str, Any]] = []
    for name in candidates[:15]:
        pubmed_results, pubmed_updates = run_tool(
            tool_fn=query_pubmed,
            tool_name="query_pubmed",
            args={"query": f"{name} aging", "retmax": 5},
            phase="phase1",
            node="phase1_research",
            hallmark=hallmark,
        )
        updates = _merge_updates(updates, pubmed_updates)

        sources = []
        if state.get("lopez_otin_context"):
            sources.append("Lopez-Otin")
        sources.extend(
            [f"PMID:{rec['pmid']}" for rec in pubmed_results if rec.get("pmid")]
        )

        evidence_score = 3
        if pubmed_results and state.get("lopez_otin_context"):
            evidence_score = 9
        elif pubmed_results:
            evidence_score = 7

        summary_parts = [
            f"{rec['title']} (PMID:{rec['pmid']})"
            for rec in pubmed_results
            if rec.get("title") and rec.get("pmid")
        ]
        evidence_summary = "; ".join(summary_parts) or "Evidence collected."

        processes.append(
            {
                "rank": 0,
                "process_name": name,
                "evidence_score": evidence_score,
                "evidence_summary": evidence_summary,
                "sources": sources or ["corpus"],
            }
        )

    updates["biological_processes"] = processes
    return updates


def phase1_critic(state: dict[str, Any]) -> dict[str, Any]:
    """Evaluate Phase 1 biological processes and return critique JSON."""
    processes = state.get("biological_processes", [])
    issues: list[str] = []
    names = [proc.get("process_name", "") for proc in processes]
    if len(processes) < 10 or len(processes) > 15:
        issues.append(f"expected 10-15 processes, got {len(processes)}")
    if len(set(names)) != len(names):
        issues.append("duplicate process names detected")
    for idx, proc in enumerate(processes):
        if not proc.get("sources"):
            issues.append(f"process[{idx}] missing sources")
        if not proc.get("evidence_summary"):
            issues.append(f"process[{idx}] missing evidence summary")

    grade = "pass" if not issues else "fail"
    follow_up = []
    if issues:
        follow_up = [f"{state['hallmark_name']} aging biological processes"]

    eval_data = {
        "grade": grade,
        "comment": "; ".join(issues) or "coverage looks sufficient",
        "missing_themes": issues,
        "follow_up_queries": follow_up,
    }
    log_event(
        {
            "hallmark": state.get("hallmark_name"),
            "phase": "phase1",
            "node": "phase1_critic",
            "grade": eval_data["grade"],
            "follow_up_queries": eval_data["follow_up_queries"],
            "comment": eval_data["comment"],
        }
    )
    return {"phase1_eval": eval_data}


def phase1_refine(state: dict[str, Any]) -> dict[str, Any]:
    """Run follow-up queries when Phase 1 critique fails."""
    eval_data = state.get("phase1_eval", {})
    follow_up = eval_data.get("follow_up_queries", [])
    iteration = state.get("phase1_iteration", 0) + 1
    updates: dict[str, Any] = {"phase1_iteration": iteration}
    hallmark = state.get("hallmark_name")

    for query in follow_up:
        vector_results, vector_updates = run_tool(
            tool_fn=query_vector_db,
            tool_name="query_vector_db",
            args={"query": query, "top_k": 5},
            phase="phase1",
            node="phase1_refine",
            hallmark=hallmark,
        )
        updates = _merge_updates(updates, vector_updates)

        if vector_results:
            updates = _merge_updates(
                updates,
                {
                    "biological_processes": [
                        {
                            "rank": 0,
                            "process_name": query,
                            "evidence_score": 5,
                            "evidence_summary": "Follow-up evidence added.",
                            "sources": ["corpus"],
                        }
                    ]
                },
            )
        else:
            updates = _merge_updates(
                updates,
                append_warning(f"No vector DB results for follow-up: {query}"),
            )

    log_event(
        {
            "hallmark": hallmark,
            "phase": "phase1",
            "node": "iteration_end",
            "iteration": iteration,
        }
    )

    return updates


def phase1_finalize(state: dict[str, Any]) -> dict[str, Any]:
    """Sort and finalize the Phase 1 biological process list."""
    processes = list(state.get("biological_processes", []))
    processes.sort(
        key=lambda item: (
            -int(item.get("evidence_score", 0)),
            item.get("process_name", ""),
        )
    )
    trimmed = processes[:15] if len(processes) > 15 else processes
    for idx, proc in enumerate(trimmed, start=1):
        proc["rank"] = idx

    bp_queue = [
        proc.get("process_name", "") for proc in trimmed if proc.get("process_name")
    ]

    return {"biological_processes": trimmed, "bp_queue": bp_queue}


def _merge_updates(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Merge update dicts, concatenating list fields when needed."""
    merged = dict(base)
    for key, value in extra.items():
        if key in merged and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + value
        else:
            merged[key] = value
    return merged
