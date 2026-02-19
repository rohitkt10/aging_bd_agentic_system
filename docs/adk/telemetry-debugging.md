# Telemetry, Tracing, and Debugging

ADK provides structured tracing and event-based observability. This section explains how to track model calls, tool calls, and full execution traces.

## 1) Event Stream = Ground Truth

Every invocation produces a stream of `Event` objects. Events contain:

- LLM output
- tool calls / tool responses
- state deltas and control actions

If you need an authoritative execution trace, **inspect events**.

## 2) OpenTelemetry Tracing

**Code location:** `google/adk/telemetry/tracing.py`

ADK emits OpenTelemetry spans to capture agent-level actions:

- `invoke_agent`: created for every agent invocation
- `execute_tool`: created for tool calls

Span attributes include:

- Agent name, description, conversation/session ID
- Tool name/type/description
- Tool call args and tool response (optional)

### Agent invocation tracing

`trace_agent_invocation(...)` adds semantic attributes (agent name/description, conversation ID) to every invocation span. This gives you a structured graph of which agents ran, in what order, inside a single session.

### Content capture controls (PII-safe by default)

Two environment variables control whether request/response content is recorded:

- `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS`
- `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`

If these are disabled, tool args and responses are elided.

### Tool call tracing details

`trace_tool_call(...)` captures:

- tool name/type
- tool call ID
- tool args and responses (if enabled)
- the event ID that produced the tool response

This gives you a complete, structured audit trail of tool behavior.

### Merged tool responses

`trace_merged_tool_calls(...)` records merged tool responses (when multiple tool outputs are combined) so debug UIs can request a unified trace.

## 3) Debug Output

**Code location:** `google/adk/utils/_debug_output.py`

`print_event(event, verbose=True)` prints:

- Agent text output
- Tool calls and responses (verbose mode)
- Code execution outputs and file references

This is a practical, developer-friendly way to inspect event streams during local development.

## 4) Model Call Visibility

Model requests and responses are represented in LLM events. A typical LLM step produces:

- An event with `content` that may include `function_call` parts
- A tool response event
- A summarization step (another model call)
- Final response event

These events are all tied to a single `invocation_id`, so you can reconstruct the entire call sequence.

## 5) How to Build Full Tracebacks

To reconstruct a full execution trace:

1. Collect events for a given `session_id` and `invocation_id`.
2. Sort by timestamp or event order in session.
3. Use event `author` and `branch` to group by agent.
4. For tool calls, match `function_call.id` with tool responses.
5. Combine with OpenTelemetry spans for a system-level timeline.

This yields a precise, multi-agent trace of model calls, tool calls, and state transitions.
