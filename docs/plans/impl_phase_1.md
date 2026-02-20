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

## 1.6 Environment Configuration

**File:** `.env.example`

**Action:** Create or update with the following:

```bash
# ===========================================
# LLM Configuration (Vertex AI Gemini)
# ===========================================
VERTEX_PROJECT_ID=your-google-cloud-project-id
VERTEX_LOCATION=us-central1
VERTEX_MODEL=gemini-2.0-flash-001

# Optional: Override default LLM parameters
# LLM_TEMPERATURE=0.7
# LLM_MAX_TOKENS=8192

# ===========================================
# Research Loop Configuration
# ===========================================
# Phase 1: Biological Process Identification
# PHASE1_MAX_ITERATIONS=3

# Phase 2: Gene Research (per biological process)
# PHASE2_RESEARCH_MAX_ITERATIONS=7
# PHASE2_REFINE_MAX_ITERATIONS=3

# ===========================================
# PubMed / NCBI Configuration
# ===========================================
NCBI_EMAIL=your-email@example.com
NCBI_API_KEY=optional-api-key-from-ncbi

# ===========================================
# Literature Pipeline (already configured)
# ===========================================
# EMBEDDING_MODEL_ID=BAAI/bge-base-en-v1.5
# CHUNK_SIZE_WORDS=300
# CHUNK_OVERLAP_WORDS=50
```

**Important:** Update your actual `.env` file (not `.env.example`) with your real Google Cloud project ID.

---

## 1.7 Prompt Templates (`llm/prompts.py`)

**Purpose:** Centralize all prompt templates. Migrate from `agents/prompts/` and improve.

**Implementation:**

```python
"""
Prompt templates for the deep research system.

All prompts should be defined here with clear documentation on:
- Expected inputs (variables)
- Expected outputs (structure)
- When to use the prompt
"""

# ===== PHASE 1 PROMPTS =====

PHASE1_SYSTEM_PROMPT = """You are an expert biological process identifier for aging hallmark curation.

## Task
Identify 10-15 biological processes that comprise the hallmark: {hallmark_name}

## Context
- Lopez-Otin hallmarks paper (Cell 2023) is provided as reference
- Use this as your primary source for understanding the hallmark

## Process Criteria
- Each process must be mechanistically distinct (no overlap)
- Focus on molecular/cellular mechanisms, not outcomes
- Examples: "DNA methylation changes", "Histone modification alterations"
- Bad examples: "Cellular aging" (too broad), "Disease" (outcome not mechanism)

## Evidence Scoring (1-10)
- 9-10: Extensively documented, core mechanism in Lopez-Otin + multiple external sources
- 7-8: Well-supported, mentioned in Lopez-Otin or similar reviews
- 5-6: Moderate evidence, multiple studies
- 3-4: Limited evidence, speculative
- 1-2: Minimal evidence, highly speculative

## Output Format
Return ONLY a JSON list of processes:
```json
[
  {{
    "process_name": "DNA methylation changes",
    "evidence_score": 9,
    "evidence_summary": "Supported by Lopez-Otin et al. 2023 and 15 papers on epigenetic clocks.",
    "sources": ["Lopez-Otin", "PMID:12345"]
  }}
]
```

Requirements:
- Exactly 10-15 processes
- Each evidence_summary must cite sources
- Scores are integers 1-10
- Return JSON only, no additional text
"""

PHASE1_CRITIQUE_PROMPT = """You are a quality evaluator for biological process identification.

## Task
Evaluate the following list of biological processes for the hallmark: {hallmark_name}

## Processes to Evaluate
{processes_json}

## Evaluation Criteria
1. Count: Must have 10-15 distinct processes
2. Evidence: Each process must have sources and evidence summary
3. Distinctness: No overlapping or duplicate processes
4. Specificity: Processes are mechanisms, not outcomes

## Count Adjustment (CRITICAL)
- If count < 10: You MUST suggest specific processes to SPLIT into narrower concepts
  - Example: "Split 'DNA methylation changes' into 'DNA hypermethylation' and 'DNA hypomethylation'"
  - Example: "Split 'mitochondrial dysfunction' into 'mitochondrial DNA damage' and 'mitochondrial biogenesis decline'"
- If count > 15: You MUST suggest specific processes to MERGE
  - Example: "Merge 'histone acetylation alterations' and 'histone methylation alterations' into 'histone modification alterations'"
  - Example: "Merge 'autophagy impairment' and 'mitophagy decline' into 'autophagy pathway dysfunction'"

## Output Format
Return ONLY JSON:
```json
{{
  "grade": "pass|fail",
  "comment": "brief explanation",
  "missing_themes": ["theme1", "theme2"],
  "follow_up_queries": ["query1", "query2"],
  "split_instructions": ["Split X into A and B", ...],
  "merge_instructions": ["Merge X and Y into Z", ...]
}}
```

Rules for split_instructions:
- Only provide if count < 10
- Each instruction should clearly state: "Split 'process_name' into 'new_name_1' and 'new_name_2'"
- Choose processes that are conceptually broad enough to split
- Split into biologically meaningful sub-processes

Rules for merge_instructions:
- Only provide if count > 15
- Each instruction should clearly state: "Merge 'process_1' and 'process_2' into 'merged_name'"
- Choose processes that are overlapping or highly related
- The merged name should be inclusive and biologically accurate

Return JSON only, no additional text.
"""

# ===== PHASE 2 PROMPTS =====

PHASE2_RESEARCH_PROMPT = """You are a gene evidence synthesis agent for aging biological processes.

## Task
For the biological process "{biological_process}", identify and score relevant genes.

## Context
- This process is part of the aging hallmark: {hallmark_name}
- Candidate genes were identified from GenAge and OpenGenes databases
- You have access to literature evidence from PubMed and the corpus

## Gene Scoring (1-10)
- 9-10: Strong evidence from multiple sources, direct link to aging and this process
- 7-8: Good evidence from multiple sources
- 5-6: Moderate evidence, some connection
- 3-4: Weak evidence, indirect connection
- 1-2: Minimal evidence, speculative

## Output Format
For each gene, return:
```json
{{
  "gene_symbol": "TP53",
  "score": 8,
  "evidence_summary": "PMID:123 links TP53 to DNA repair decline in aging.",
  "sources": ["PMID:123", "PMC456"]
}}
```

Return a JSON array of genes. Minimum score threshold: 5.
"""

PHASE2_CRITIQUE_PROMPT = """You are a quality evaluator for gene evidence research.

## Task
Evaluate gene evidence for biological process: {biological_process}

## Genes Found
{genes_json}

## Evaluation Criteria
1. Count: Should have 20+ genes (for this single process)
2. Evidence: Each gene must have sources and evidence summary
3. Relevance: Genes must be directly relevant to the biological process

## Output Format
Return ONLY JSON:
```json
{{
  "grade": "pass|fail",
  "comment": "brief explanation",
  "follow_up_queries": ["query1", "query2"]
}}
```

Return JSON only, no additional text.
"""

PHASE2_GO_MAPPING_PROMPT = """You are a Gene Ontology term mapper for biological processes.

## Task
Find GO biological process terms related to: {biological_process}

## Context
- This is part of aging hallmark: {hallmark_name}
- GO terms must have namespace "biological_process"
- Return the most relevant terms (relevance score 6+)

## GO Term Scoring (1-10)
- 9-10: Exact match or core concept
- 7-8: Highly relevant
- 5-6: Moderately relevant
- 1-4: Weakly related

## Output Format
Return JSON array:
```json
{{
  "go_id": "GO:0006915",
  "go_label": "apoptotic process",
  "relevance_score": 8,
  "evidence_summary": "Directly related to programmed cell death in aging."
}}
```

Return JSON only, no additional text.
"""
```

**Notes:**
- These prompts are more detailed than Copilot's versions
- Explicitly request JSON output for structured parsing
- Include clear scoring rubrics
- Document expected input variables (e.g., `{hallmark_name}`, `{processes_json}`)

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

- [ ] Dependencies added to `pyproject.toml` and `uv sync` completed
- [ ] `llm/` module created with all 4 files
- [ ] `.env.example` updated with Vertex AI configuration
- [ ] Actual `.env` file contains your `VERTEX_PROJECT_ID`
- [ ] Test script `scripts/test_llm.py` created and passes
- [ ] Can successfully import and use `get_llm()` from Python

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
