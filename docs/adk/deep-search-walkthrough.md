# Deep Search Sample (ADK Orchestration Example)

This section documents the `deep-search` sample to show how ADK primitives are used to orchestrate a research system.

**Source:** `adk-samples/python/agents/deep-search/app/agent.py`

## 1) Architectural Overview

The sample builds a multi-stage research pipeline with human approval and iterative refinement:

1. **Plan generation** (interactive, human-in-the-loop)
2. **Section planning** (report outline)
3. **Research and evidence gathering**
4. **Critique + refinement loop**
5. **Final report with citations**

This is a composite workflow built from multiple `LlmAgent`s + `SequentialAgent` + `LoopAgent`.

## 2) Core Agents

### Plan Generator

- `plan_generator` is an `LlmAgent` that emits a structured plan.
- Uses `google_search` only for topic clarification.
- Produces a plan labeled with `[RESEARCH]` and `[DELIVERABLE]` markers.

### Section Planner

- `section_planner` produces a markdown outline for the report.
- Uses the approved plan in state (`research_plan`).

### Section Researcher

- `section_researcher` executes the plan.
- Uses `google_search` extensively.
- Stores findings in `section_research_findings`.
- Attaches `collect_research_sources_callback` to capture grounding metadata.

### Research Evaluator

- `research_evaluator` (critic model) scores research quality.
- Emits a JSON output that includes follow-up queries if research is insufficient.

### Enhanced Search Executor

- `enhanced_search_executor` runs follow-up queries.
- Merges new findings into `section_research_findings`.

### Report Composer

- `report_composer` produces a final cited report.
- Uses a custom citation tag (`<cite source="src-N" />`).
- After-agent callback replaces tags with Markdown links.

## 3) Looping and Escalation

The refinement loop is implemented with `LoopAgent`:

- Sub-agents: `research_evaluator`, `EscalationChecker`, `enhanced_search_executor`
- The loop stops when `EscalationChecker` emits an event with `escalate=True`.

This is a practical example of **quality gating** using a loop agent.

## 4) Sequential Pipeline

The full pipeline is a `SequentialAgent`:

```
section_planner → section_researcher → iterative_refinement_loop → report_composer
```

Because it is sequential, each stage can depend on state outputs from the previous stage.

## 5) Callback-Based Citation System

Two custom callbacks are important:

- **Source collection**: `collect_research_sources_callback` inspects grounding metadata and stores a `sources` map in state.
- **Citation replacement**: `citation_replacement_callback` transforms `<cite source="src-N" />` tags into Markdown links.

This illustrates how callbacks can add post-processing steps without modifying agent logic directly.

## 6) Root Agent Design

The root agent is `interactive_planner_agent`:

- Its only job is to **plan** and **delegate**.
- It invokes `plan_generator` until the user approves.
- Then it delegates to `research_pipeline`.

This pattern (planning agent + execution pipeline) is a canonical ADK orchestration style.
