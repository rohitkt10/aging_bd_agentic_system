# Agents and Orchestration

This section covers all ADK agent types and how they orchestrate work. The core mental model is **agent trees**: a root agent with sub-agents; parent agents can delegate work, and workflow agents can orchestrate sequences, loops, or parallel execution.

## 1) BaseAgent: The Universal Interface

**Code location:** `google/adk/agents/base_agent.py`

All agents inherit from `BaseAgent`. Key responsibilities:

- **`run_async()`** / **`run_live()`**: Entry points used by the Runner.
- **Callbacks**: `before_agent_callback`, `after_agent_callback` to intercept run.
- **Agent tree**: `sub_agents`, `parent_agent`, `find_agent()`.
- **Resumability support**: loads and writes agent state events.

### Callbacks (Agent-level)

- `before_agent_callback`: can short-circuit execution by returning content.
- `after_agent_callback`: can post-process results or append a final event.

These callbacks operate on `CallbackContext`, which provides read/write access to state and event actions.

## 2) LlmAgent: Primary LLM-backed Agent

**Code location:** `google/adk/agents/llm_agent.py`

`LlmAgent` is the most common agent type. It adds LLM and tool semantics.

### Key Fields

- **`model`**: Gemini model name or a BaseLlm instance.
- **`instruction`**: Core prompt template (can be dynamic).
- **`static_instruction`**: Static content for caching.
- **`tools`**: List of tools or toolsets.
- **`planner`**: Optional planner for “thinking” configurations.
- **`code_executor`**: Optional code execution support.
- **`input_schema` / `output_schema`**: Structured inputs/outputs.
- **`output_key`**: Save final response to session state.
- **`include_contents`**: Controls whether prior conversation history is included.

### Input/Output Schemas

- `input_schema`: Used when the agent is wrapped as a tool (via `AgentTool`).
- `output_schema`: If set, the agent must return structured output and **cannot** use tools.

### Flow Selection

`LlmAgent` chooses its execution flow via `_llm_flow`:

- **`SingleFlow`**: If transfer is disallowed and no sub-agents.
- **`AutoFlow`**: Default; enables transfer logic and tool orchestration.

### LLM Flow Stages (SingleFlow / AutoFlow)

LLM flows are responsible for constructing the request, calling the model, handling tool calls, and producing events. The high-level stages are:

1. **Build LlmRequest** (system + user content + tools + configs).
2. **Run before-model callbacks** (plugins then agent callbacks).
3. **Call model** and emit response event.
4. **Execute tools** if function calls exist.
5. **Summarize tool results** via a follow-up model call.
6. **Run after-model callbacks** and emit final response.

This is why a single user message can result in multiple model calls and multiple events.

## 3) SequentialAgent

**Code location:** `google/adk/agents/sequential_agent.py`

A workflow agent that runs sub-agents **in order**.

- Records progress in `SequentialAgentState`.
- Resumability works by storing which sub-agent is next.
- Emits end-of-agent event after all sub-agents run.

Use when you want deterministic, linear pipelines (plan → research → summarize → report).

## 4) ParallelAgent

**Code location:** `google/adk/agents/parallel_agent.py`

Runs sub-agents **concurrently**.

- Each sub-agent gets its own **branch**.
- Events are merged in a controlled interleaving to preserve order per agent.
- Once all sub-agents finish, it marks end-of-agent.

Use when you want multiple perspectives or redundant attempts in parallel.

## 5) LoopAgent

**Code location:** `google/adk/agents/loop_agent.py`

Repeatedly runs its sub-agents until:

- A sub-agent emits `EventActions(escalate=True)`, or
- `max_iterations` is reached.

Looping is stateful and resumable. This is ideal for **“refine until good”** loops (e.g., research → critique → refine).

## 6) Agent Transfer (AutoFlow)

**Code locations:**

- `google/adk/flows/llm_flows/auto_flow.py`
- `google/adk/tools/transfer_to_agent_tool.py`

`AutoFlow` enables LLM-controlled transfer between agents in a tree. Transfer happens when:

- A tool call returns `transfer_to_agent`, setting `EventActions.transfer_to_agent`.

Rules:

- Parent → child allowed.
- Child → parent allowed.
- Child → peer allowed only if parent is an `LlmAgent` and `disallow_transfer_to_peers` is False.

Transfers can be constrained via `TransferToAgentTool`, which adds an enum of valid agent names.

## 7) Planners and Thinking

**Code location:** `google/adk/planners/built_in_planner.py`

A planner can inject configuration (e.g., thinking config) into LLM requests. The built-in planner primarily attaches a `ThinkingConfig` to a request. It is **not** an external planning agent; it is a request-level configuration.

## 8) Code Execution

**Code location:** `google/adk/code_executors/*`

`code_executor` allows LLMs to produce and execute code blocks, with results recorded as events. If code execution is enabled, events can include `executable_code` and `code_execution_result` parts.

## 9) Model and Tool Callbacks

LlmAgent supports callbacks at multiple levels:

- **Before/After model callbacks**: Intercept or override LLM requests/responses.
- **On-model-error callbacks**: Provide fallback responses for model failures.
- **Before/After tool callbacks**: Inspect or override tool calls and responses.
- **On-tool-error callbacks**: Provide fallback tool results.
All callbacks run after plugin callbacks, so plugins can enforce policy or logging globally.

## 10) Canonical Execution Path (Mental Model)

When an LlmAgent runs:

1. **Instruction resolution** (static + dynamic).
2. **LLM call** via flow.
3. **Tool calls** if model outputs function calls.
4. **Tool responses** are appended as events.
5. **Summarization** of tool responses (another LLM call).
6. **Final response** emitted as a new event.

Every stage creates events, enabling full traceability.
