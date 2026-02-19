# Google ADK (Agent Development Kit) - Detailed Mental Model Guide

This documentation is a deep, code-accurate guide to Google’s Agent Development Kit (ADK) based on the `adk-python` source and the `deep-search` sample. The goal is to provide a concrete mental model: what primitives exist, where they live in the codebase, and how they fit together when you build and orchestrate agentic systems.

## How to Navigate

- **Core concepts and runtime model** → [`core-concepts.md`](./core-concepts.md)
- **Agents and orchestration** → [`agents-orchestration.md`](./agents-orchestration.md)
- **Tools and toolsets** → [`tools.md`](./tools.md)
- **Telemetry, tracing, and debugging** → [`telemetry-debugging.md`](./telemetry-debugging.md)
- **Deep Search sample walkthrough** → [`deep-search-walkthrough.md`](./deep-search-walkthrough.md)

## Source References (Primary)

- ADK library: `adk-python/src/google/adk/...`
- Deep Search sample: `adk-samples/python/agents/deep-search/app/agent.py`

If you are implementing your own system, read **Core Concepts** first, then **Agents & Orchestration**, and finally **Tools** and **Telemetry**.
