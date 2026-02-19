# Tools and Toolsets

This section describes ADK’s tool system, which is the primary mechanism for giving agents external capabilities (search, databases, APIs, custom functions, or other agents).

## 1) BaseTool

**Code location:** `google/adk/tools/base_tool.py`

`BaseTool` defines the interface for all tools:

- **`name` / `description`**: Declared to the model.
- **`run_async(args, tool_context)`**: Executes the tool.
- **`process_llm_request(tool_context, llm_request)`**: Adds tool declarations to the request.
- **`_get_declaration()`**: Returns an OpenAPI-style function declaration.

Tools can be **client-side** (executed in your process) or **model-native** (e.g., Google Search).

## 2) FunctionTool

**Code location:** `google/adk/tools/function_tool.py`

Wraps a Python callable into a tool:

- Automatically generates a function declaration from the signature.
- Converts JSON args into Pydantic models if annotated.
- Supports **confirmation workflows** (HITL) via `require_confirmation`.

### Confirmation Flow

If confirmation is required:

1. Tool returns a request confirmation action.
2. The user must send a response confirming or rejecting.
3. The tool runs only if confirmation is approved.

## 3) Tool Configuration (Config-Driven Agents)

**Code location:** `google/adk/tools/tool_configs.py`

ADK supports declarative tool configuration via `ToolConfig`:

- Built-in tools: `name: google_search`
- Custom tool instance: `name: my_package.my_module.my_tool`
- Tool class + args: `name: my_package.MyTool` with `args:`
- Tool factory function: `name: my_package.create_tool` with `args:`

This allows agents to be defined from config files and loaded dynamically.

## 4) Toolset

**Code location:** `google/adk/tools/base_toolset.py`

A **toolset** is a collection of tools that can be filtered or prefixed. Use it when:

- You want to expose a group of tools together.
- You need dynamic tool generation based on context.
- You want to share auth configuration across tools.

Toolsets can implement `get_auth_config()` to request credentials and support OAuth or other auth flows.

### Toolset Auth Flow (High-Level)

1. Toolset advertises `AuthConfig` via `get_auth_config()`.
2. Runner resolves or requests credentials before tool listing.
3. If no credential exists, ADK emits an auth request event and pauses.
4. Once provided, the credential is injected into the toolset.

This prevents tools from executing without valid credentials.

## 5) Built-In Tools

**Code locations:** `google/adk/tools/*`

Key built-in tools include:

- **`google_search`**: Built-in Gemini search tool.
- **`transfer_to_agent` / `TransferToAgentTool`**: Controlled delegation.
- **Memory and artifact tools** (`load_artifacts`, `load_memory`, etc.).

### Multi-tool limitation (important)

In some Gemini models, `google_search` cannot be combined with other tools directly. ADK handles this by wrapping search as an `AgentTool` when multiple tools are present.

## 6) AgentTool (Agent-as-Tool)

**Code location:** `google/adk/tools/agent_tool.py`

`AgentTool` wraps an agent so it can be called like a tool:

- Uses the agent’s `input_schema` to define tool arguments.
- Returns structured output if the agent has `output_schema`.
- Runs the agent in a child `Runner`, forwarding state deltas.

This is a powerful pattern for building modular systems: a parent agent can invoke a specialist agent with strict input/output contracts.

## 7) Tool Context (Context)

**Code location:** `google/adk/agents/context.py` and `google/adk/tools/tool_context.py`

Tool execution receives a `Context` object that enables:

- State updates (`ctx.state`)
- Auth requests (`ctx.request_credential`)
- Confirmation requests (`ctx.request_confirmation`)
- Artifact access

Tools should use this context instead of touching global state directly.

## 8) Long-Running Tools

A tool can be marked as `is_long_running`. This causes:

- Tool calls to include `long_running_tool_ids` in events.
- The invocation to pause if resumability is enabled.
- The system to resume later based on checkpoints.

This is critical for integrations with async workflows (batch jobs, external pipelines).
