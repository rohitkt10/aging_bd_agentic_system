# Phase 1 — LLM Foundation

**Goal:** Set up Vertex AI Gemini integration with modular abstraction for future providers.

---

## 1.1 Add Dependencies

**File:** `pyproject.toml`

**Action:** Add the following to the `dependencies` list:

```toml
dependencies = [
    # ... existing dependencies ...
    "langchain-core>=0.3.0",
    "langchain-google-vertexai>=1.0.0",
    "google-cloud-aiplatform>=1.70.0",
]
```

**Why these versions:**
- `langchain-core>=0.3.0`: Core interfaces for LLM integration
- `langchain-google-vertexai>=1.0.0`: Official Vertex AI integration for LangChain
- `google-cloud-aiplatform>=1.70.0`: Google Cloud client library

**After editing:**
```bash
uv sync
```

**Verify:** Check that packages install without errors. Look for `langchain_core` and `langchain_google_vertexai` in the lock file.

---

## 1.2 Create LLM Module Structure

**Directory to create:** `src/aging_bd_agentic_system/llm/`

**Files to create:**
```
src/aging_bd_agentic_system/llm/
├── __init__.py          # Exports LLMClient, get_llm function
├── client.py            # Main LLM client wrapper with singleton pattern
├── providers.py         # Provider interface + Vertex AI implementation
└── prompts.py           # Prompt templates (migrate from agents/prompts/)
```

---

## 1.3 Provider Interface (`llm/providers.py`)

**Purpose:** Abstract LLM provider so we can swap Vertex AI for OpenAI, Anthropic, etc. later.

**Implementation:**

```python
"""
LLM provider abstraction layer.

Allows swapping between different LLM providers (Vertex AI, OpenAI, etc.)
without changing agent code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """
        Invoke the LLM with a text prompt.

        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Additional provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            The LLM response as a string
        """
        pass

    @abstractmethod
    def invoke_structured(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """
        Invoke the LLM with structured output expectations.

        Args:
            prompt: The prompt to send to the LLM
            schema: The expected output schema (for structured output)
            **kwargs: Additional provider-specific parameters

        Returns:
            The LLM response as a dict matching the schema
        """
        pass


class VertexGeminiProvider(LLMProvider):
    """Vertex AI Gemini implementation of LLMProvider."""

    def __init__(
        self,
        project_id: str,
        location: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        """
        Initialize Vertex AI Gemini provider.

        Args:
            project_id: Google Cloud project ID
            location: Vertex AI region (e.g., "us-central1")
            model: Model name (e.g., "gemini-2.0-flash-001")
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response (None for default)
        """
        from langchain_google_vertexai import ChatVertexAI

        self.llm = ChatVertexAI(
            project=project_id,
            location=location,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """Invoke LLM with text prompt, return response text."""
        from langchain_core.messages import HumanMessage

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def invoke_structured(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """
        Invoke LLM with structured output schema.

        Note: Uses LangChain's with_structured_output() which works with
        models that support tool/function calling (Gemini does).
        """
        from langchain_core.messages import HumanMessage

        # Wrap the LLM with structured output
        llm_structured = self.llm.with_structured_output(schema)
        response = llm_structured.invoke([HumanMessage(content=prompt)])
        return response
```

**Notes:**
- The `invoke_structured` method relies on Gemini's function calling capabilities
- If structured output fails, you may need to fall back to JSON parsing with explicit instructions in the prompt
- Temperature defaults to 0.7 for creative reasoning; you may want lower (0.3-0.5) for more deterministic outputs

---

## 1.4 LLM Client (`llm/client.py`)

**Purpose:** Singleton client that agents can import and use.

**Implementation:**

```python
"""
LLM client singleton for agent use.

Usage:
    from aging_bd_agentic_system.llm.client import get_llm

    llm = get_llm()
    response = llm.invoke("What are biological processes?")
"""

from __future__ import annotations

import os
from typing import Any

from .providers import VertexGeminiProvider


class LLMClient:
    """
    Main LLM client that wraps a provider.

    This class provides a simple interface for agents to call LLMs
    without knowing which provider is being used.
    """

    def __init__(self) -> None:
        """Initialize LLM client from environment variables."""
        project_id = os.environ.get("VERTEX_PROJECT_ID")
        if not project_id:
            raise ValueError(
                "VERTEX_PROJECT_ID environment variable must be set. "
                "Add it to your .env file."
            )

        location = os.environ.get("VERTEX_LOCATION", "us-central1")
        model = os.environ.get("VERTEX_MODEL", "gemini-2.0-flash-001")
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        max_tokens = os.environ.get("LLM_MAX_TOKENS")

        self.provider = VertexGeminiProvider(
            project_id=project_id,
            location=location,
            model=model,
            temperature=temperature,
            max_tokens=int(max_tokens) if max_tokens else None,
        )

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """
        Invoke the LLM with a text prompt.

        Args:
            prompt: The prompt to send
            **kwargs: Override parameters (temperature, max_tokens, etc.)

        Returns:
            LLM response text
        """
        return self.provider.invoke(prompt, **kwargs)

    def invoke_structured(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """
        Invoke the LLM with structured output.

        Args:
            prompt: The prompt to send
            schema: Expected output schema (dict with type hints)
            **kwargs: Override parameters

        Returns:
            LLM response as dict matching schema
        """
        return self.provider.invoke_structured(prompt, schema, **kwargs)


# Singleton instance
_global_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """
    Get the global LLM client instance.

    Returns:
        The singleton LLMClient

    Raises:
        ValueError: If VERTEX_PROJECT_ID is not set
    """
    global _global_client
    if _global_client is None:
        _global_client = LLMClient()
    return _global_client


def reset_llm() -> None:
    """
    Reset the global LLM client.

    Useful for testing or when environment variables change.
    """
    global _global_client
    _global_client = None
```

**Why singleton:** Ensures we reuse the same connection/configuration across all agent calls.

---

## 1.5 Module Exports (`llm/__init__.py`)

```python
"""
LLM integration module.

Provides LLM client and provider abstractions for the deep research system.
"""

from .client import LLMClient, get_llm, reset_llm
from .providers import LLMProvider, VertexGeminiProvider

__all__ = ["LLMClient", "get_llm", "reset_llm", "LLMProvider", "VertexGeminiProvider"]
```

---

## 1.6 Configuration System

**Files:** `src/aging_bd_agentic_system/config.py`, `config/default.yaml`, `.env.example`

**Architecture:** Configuration follows a priority hierarchy:
1. `RunConfig` dataclass defaults (lowest priority)
2. YAML config file (`config/default.yaml` or `--config` flag)
3. CLI arguments (highest priority)

**`.env` is ONLY for secrets** (API keys, project IDs). Non-secret configuration goes through the config system.

### Config Dataclasses

```python
@dataclass
class Phase1Config:
    min_research_goals: int = 4
    max_research_goals: int = 6
    vector_db_top_k: int = 20
    pubmed_retmax: int = 10
    max_iterations: int = 2
    max_processes: int = 15

@dataclass
class RunConfig:
    hallmark: str = ""
    output_dir: Path = Path("outputs")
    use_llm_summarization: bool = True
    phase1: Phase1Config = field(default_factory=Phase1Config)
    phase2: Phase2Config = field(default_factory=Phase2Config)
```

**Config travels through state:** All agents read from `state["config"]` instead of environment variables.

### Environment Variables (Secrets Only)

```bash
# .env - SECRETS ONLY
VERTEX_PROJECT_ID=your-google-cloud-project-id
VERTEX_LOCATION=us-central1
VERTEX_MODEL=gemini-2.5-pro
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=optional-api-key-from-ncbi
```

**Important:** Update your actual `.env` file with your real Google Cloud project ID.

---

## 1.7 Prompt Templates (`llm/prompts.py`)

**Purpose:** Centralize all prompt templates with clear documentation.

**Key Phase 1 Prompts:**

| Prompt | Purpose | Input Variables | Output |
|--------|---------|-----------------|--------|
| `PHASE1_PLAN_SYSTEM_PROMPT` | Generate research goals with tool-specific search terms | `hallmark_name`, `min_goals`, `max_goals` | JSON with `research_goals` array |
| `PHASE1_SYSTEM_PROMPT` | Identify biological processes from evidence | `hallmark_name` | JSON array of processes |
| `PHASE1_CRITIC_UNSTRUCTURED_PROMPT` | Free-form critique (~100 words) | `hallmark_name`, `current_iteration`, `max_iterations`, `processes_json` | Free-text critique |
| `PHASE1_CRITIC_STRUCTURED_PROMPT` | Extract structured recommendations | `critique_text`, `processes_json` | JSON with `grade`, `vector_db_queries`, `pubmed_queries`, `focus_areas` |

**Key Phase 2 Prompts:**

| Prompt | Purpose | Input Variables | Output |
|--------|---------|-----------------|--------|
| `PHASE2_RESEARCH_SYSTEM_PROMPT` | Guide autonomous research loop | `biological_process`, `hallmark_name`, `tool_descriptions` | - |
| `PHASE2_DECISION_USER_PROMPT` | Get LLM decisions on what to research | `current_iteration`, `max_iterations`, `phase`, `guidance`, `candidates_summary`, `recent_findings` | JSON with `actions`, `findings_notes` |
| `PHASE2_SCORING_SYSTEM_PROMPT` | Final gene scoring | `biological_process`, `hallmark_name` | JSON array of scored genes |
| `PHASE2_CRITIQUE_SYSTEM_PROMPT` | Evaluate gene evidence | `biological_process`, `genes_json` | JSON with `grade`, `comment`, `follow_up_queries` |
| `PHASE2_GO_MAPPING_SYSTEM_PROMPT` | Map GO terms to processes | `biological_process`, `hallmark_name` | JSON array of GO terms |

**Notes:**
- All prompts explicitly request JSON output for structured parsing
- Prompts include clear scoring rubrics
- See `src/aging_bd_agentic_system/llm/prompts.py` for full implementations

---

## 1.8 Test Installation

**Create test script:** `scripts/test_llm.py`

```python
#!/usr/bin/env python3
"""Quick test that LLM integration works."""

import os
import sys

def main():
    # Check environment
    if not os.environ.get("VERTEX_PROJECT_ID"):
        print("Error: VERTEX_PROJECT_ID not set in .env")
        sys.exit(1)

    try:
        from aging_bd_agentic_system.llm.client import get_llm

        llm = get_llm()
        response = llm.invoke(
            "Respond with exactly: 'LLM integration works'. "
            "Do not add any other text."
        )
        print(f"LLM Response: {response}")

        if "works" in response.lower():
            print("\n✅ LLM integration is working!")
            return 0
        else:
            print(f"\n⚠️ Unexpected response: {response}")
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**Run the test:**
```bash
python scripts/test_llm.py
```

**Expected output:**
```
LLM Response: LLM integration works

✅ LLM integration is working!
```

---

## Phase 1 Completion Checklist

- [x] Dependencies added to `pyproject.toml` and `uv sync` completed
- [x] `llm/` module created with all 4 files (`__init__.py`, `client.py`, `providers.py`, `prompts.py`)
- [x] `config/` module with `config.py` containing `RunConfig`, `Phase1Config`, `Phase2Config` dataclasses
- [x] `config/default.yaml` created for default configuration
- [x] `.env.example` updated (secrets only: API keys, project IDs)
- [x] Actual `.env` file contains your `VERTEX_PROJECT_ID`
- [x] Test script `scripts/test_llm.py` created and passes
- [x] Can successfully import and use `get_llm()` from Python
- [x] Config travels through `state["config"]` to all agents

---

## Troubleshooting

**Error: "VERTEX_PROJECT_ID not set"**
- Ensure `.env` file exists in project root
- Ensure `VERTEX_PROJECT_ID=your-project-id` is in `.env`
- Restart your Python environment after updating `.env`

**Error: "Module 'langchain_google_vertexai' not found"**
- Run `uv sync` to install dependencies
- Check Python is using the correct virtual environment (`.venv`)

**Error: "Permission denied" or "403" from Vertex AI**
- Ensure your Google Cloud credentials are set up:
  - `gcloud auth application-default login`
  - Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

**Structured output fails or returns incorrect format**
- Gemini's function calling may need specific schema format
- Fallback: Use `invoke()` with explicit JSON instructions in prompt
- Consider using `pydantic` models for schema definition instead of dicts

---

## Next Phase

After completing Phase 1, proceed to **Phase 2 — Agent Intelligence**, where we'll rewrite the agent nodes to use these LLM capabilities instead of deterministic keyword extraction.
