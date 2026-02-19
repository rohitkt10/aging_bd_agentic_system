# Core Concepts and Runtime Model

This section explains the foundational pieces of ADK and how they relate to each other during a run. The mental model is: **App → Runner → Session → Invocation → Agent Tree → Events**.

## 1) App: Top-Level Container

**Code location:** `google/adk/apps/app.py`

An `App` bundles the root agent and global configuration:

- **`root_agent`**: The root of the agent tree (the single entry point).
- **`plugins`**: App-wide plugins that can intercept callbacks and augment behavior.
- **`events_compaction_config`**: Controls compaction of session event history.
- **`context_cache_config`**: Controls LLM context caching settings.
- **`resumability_config`**: Enables pause/resume for long-running tools.

The `App` is not the runtime itself; it is the **definition** of an agentic system.

## 2) Runner: Execution Engine

**Code location:** `google/adk/runners.py`

The `Runner` is the execution orchestrator. It binds together:

- `app_name` and root `agent`
- services (session, memory, artifact, credentials)
- plugins

When you run an agent, the `Runner` is responsible for:

1. **Loading/creating sessions**
2. **Creating an InvocationContext**
3. **Invoking the root agent**
4. **Streaming or yielding events**

The runner enforces app/agent alignment and provides the operational boundary for execution.

### Runner Services (what they do)

- **Session service**: persists events and state; required for every run.
- **Memory service**: optional long-term memory store used by agents.
- **Artifact service**: stores files and media attached to the session.
- **Credential service**: supports auth flows for tool access.

These services are exposed to tools and callbacks through the `Context` APIs.

## 3) Session: Persistent Conversation and State

**Code location:** `google/adk/sessions/*`, `google/adk/sessions/session.py`

A `Session` is the persisted container for:

- **Events** (conversation history, tool calls, tool responses)
- **State** (shared key-value store across agent tree)
- **Artifacts** (files or media attached to a session)

Sessions are keyed by `app_name`, `user_id`, and `session_id`.

### Session State and Compaction

Sessions can grow large. ADK supports **event compaction** (summarization of older events) via `EventsCompactionConfig`, configured on `App`. Compaction can be triggered by invocation count or token thresholds, while keeping a window of recent raw events to preserve context.

## 4) Invocation: One User Request / One Run

**Code location:** `google/adk/agents/invocation_context.py`

An **invocation** is the runtime lifecycle for a single user input until a final response. The InvocationContext describes:

- The **current agent**
- The **current session**
- The **user content** that started the invocation
- **agent_states** and **end_of_agents** flags for resumability
- **branch** (isolation between parallel sub-agents)

Key rules:

- An invocation may involve **multiple agents** (transfers or workflow agents).
- An invocation can be **paused** if a long-running tool is called and resumability is enabled.

### Branching and Isolation

Parallel sub-agents run under different **branches**. Branching isolates each agent’s view of the conversation, avoiding cross-talk between peers while preserving a unified event log.

## 5) Events: The Canonical Trace

**Code location:** `google/adk/events/event.py`, `google/adk/events/event_actions.py`

All observable outputs from ADK are **Events**. Each event includes:

- `author` (agent name or `user`)
- `content` (text, tool calls, tool responses, code results)
- `actions` (state deltas, transfer markers, escalation flags)
- `id`, `timestamp`, `invocation_id`, `branch`

### EventActions (why it matters)

`EventActions` expresses side effects and control signals:

- **`state_delta`**: Updates session state incrementally.
- **`artifact_delta`**: Records new/updated artifacts.
- **`transfer_to_agent`**: Signals control transfer to another agent.
- **`escalate`**: Signals loop agents to stop.
- **`requested_tool_confirmations` / `requested_auth_configs`**: Signals user confirmation or auth requests.
- **`end_of_agent` / `agent_state`**: Used for resumability checkpoints.

ADK is **event-first**: everything that happens (LLM calls, tool calls, state updates) is represented by events or their actions.

## 6) Context and State

**Code location:** `google/adk/agents/context.py`, `google/adk/agents/readonly_context.py`

There are two key context objects:

- **`ReadonlyContext`**: Used when you should not mutate state.
- **`Context`**: Used by tools/callbacks to mutate state and record actions.

The `Context.state` object is delta-aware:

- Writes go to `state_delta`, not directly to the session.
- On event emission, the delta is applied to the session.

This pattern ensures agent runs remain deterministic and traceable.

## 7) State and Artifacts

Context gives you APIs to:

- `ctx.state["key"] = value` → persistent state update
- `ctx.save_artifact(...)` → stores artifacts and records in `artifact_delta`
- `ctx.load_artifact(...)` / `ctx.list_artifacts()`

Artifacts are stored by the configured artifact service; the default for local runs is typically in-memory or filesystem-backed.

## 8) Memory and Credential Handling

Context APIs also expose memory and credential workflows:

- **Memory**: `ctx.add_session_to_memory()`, `ctx.search_memory(query)`, `ctx.add_memory(...)`.
- **Credentials**: `ctx.request_credential(auth_config)` (tool-time), and `ctx.save_credential(...)` / `ctx.load_credential(...)` (callback-time).

This allows tools to request OAuth or API keys and persist them for later use.

## 9) Plugins and Cross-Cutting Concerns

Plugins are registered on the `App` and executed through the Runner’s `PluginManager`. They can intercept callbacks (before/after agent or model) and apply shared behavior such as logging, policy checks, or instrumentation.

## 10) Context Caching

`ContextCacheConfig` (App-level) governs how model requests are cached. `LlmAgent.static_instruction` is designed to maximize cache reuse: static content is sent first, dynamic instruction follows, and the model can reuse cached context.

## 11) Resumability and Long-Running Tools

Resumability is configured at the `App` level with `ResumabilityConfig`.

When a tool is marked **long-running** and invoked:

1. The tool call event is emitted with `long_running_tool_ids`.
2. The invocation is **paused**.
3. The event stream ends without end-of-agent markers.
4. A future resume can continue from the last checkpoint.

Loop and sequential agents also store agent state to support resuming mid-workflow.

## 12) Live / Streaming Mode

Agents can run in **live** mode (`run_live`) with audio/video streams and transcription handling. In live mode, SequentialAgent injects a `task_completed()` tool so agents can signal completion and hand off to subsequent steps.
