"""
Configuration system for the aging BD agentic system.

Hierarchy (lowest to highest priority):
1. RunConfig dataclass defaults
2. YAML config file
3. CLI arguments

.env is separate and only for secrets (API keys, project IDs).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Resolve repo root for absolute path defaults:
# <repo>/src/aging_bd_agentic_system/config.py -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Phase1Config:
    """Configuration for Phase 1: Biological Process Identification."""

    min_research_goals: int = 4
    max_research_goals: int = 6
    phase1_vector_db_top_k: int = 20
    phase1_pubmed_retmax: int = 10
    max_iterations: int = 2
    min_processes: int = 10
    max_processes: int = 15
    summary_max_words: int = 300


@dataclass
class Phase2Config:
    """Configuration for Phase 2: Gene Research."""

    # Research loop
    max_research_iterations: int = 7
    max_refine_iterations: int = 3
    min_actions_per_iteration: int = 2
    max_actions_per_iteration: int = 4

    # Seeding
    genage_seed_max_results: int = 50
    opengenes_seed_results_per_query: int = 15

    # Tool limits
    phase2_vector_db_top_k: int = 10
    phase2_pubmed_retmax: int = 10
    opengenes_results_per_query: int = 20
    max_opengenes_items_per_field: int = 5  # Truncate long lists in OpenGenes results

    # Context management
    phase2_summarize_max_tokens: int = 100000

    # Critic-refine loop settings
    max_critic_iterations: int = 2
    refine_opengenes_max_results: int = 15
    refine_pubmed_max_results: int = 10
    refine_vector_db_top_k: int = 10


@dataclass
class LLMConfig:
    """Configuration for LLM client with two-tier model system."""

    provider: str = "vertex"  # "vertex" or "openai"

    # Two-tier model system:
    # - model: Base fallback for both tiers (used if model_low/model_high not set)
    # - model_low: Cheaper/faster model for most tasks (overrides model if set)
    # - model_high: More capable model for complex tasks (defaults to model_low if not set)
    model: str = "gemini-2.5-pro"  # Base model (fallback)
    model_low: str | None = None  # If None, uses model
    model_high: str | None = None  # If None, uses resolved model_low

    temperature: float = 0.7
    max_tokens: int | None = None
    # Vertex-specific
    vertex_location: str = "us-central1"
    # OpenAI-specific
    openai_base_url: str | None = None

    def get_model_low(self) -> str:
        """Get resolved model_low (model_low if set, else model)."""
        return self.model_low if self.model_low else self.model

    def get_model_high(self) -> str:
        """Get resolved model_high (model_high if set, else resolved model_low)."""
        return self.model_high if self.model_high else self.get_model_low()


@dataclass
class LiteraturePipelineConfig:
    """
    Configuration for literature corpus ingestion pipeline.

    NOTE: This is NOT part of RunConfig. The corpus is currently frozen.
    Wire this into the pipeline later if re-indexing is needed.
    """

    embedding_model_id: str = "BAAI/bge-base-en-v1.5"
    chunk_size_words: int = 300
    chunk_overlap_words: int = 50


@dataclass
class RunConfig:
    """Top-level run configuration."""

    hallmark: str = ""
    output_dir: Path = field(default_factory=lambda: REPO_ROOT / "outputs")
    use_llm_summarization: bool = True
    phase1_only: bool = False  # If True, terminate after Phase 1
    llm: LLMConfig = field(default_factory=LLMConfig)
    phase1: Phase1Config = field(default_factory=Phase1Config)
    phase2: Phase2Config = field(default_factory=Phase2Config)

    def to_dict(self) -> dict[str, Any]:
        """Convert to nested dict for state."""
        return {
            "hallmark": self.hallmark,
            "output_dir": str(self.output_dir),
            "use_llm_summarization": self.use_llm_summarization,
            "phase1_only": self.phase1_only,
            "llm": asdict(self.llm),
            "phase1": asdict(self.phase1),
            "phase2": asdict(self.phase2),
        }

    @classmethod
    def from_yaml(cls, path: Path) -> "RunConfig":
        """Load config from YAML file, merging over defaults."""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        config = cls()

        # Merge top-level
        if "hallmark" in data:
            config.hallmark = data["hallmark"]
        if "output_dir" in data:
            config.output_dir = Path(data["output_dir"])
        if "use_llm_summarization" in data:
            config.use_llm_summarization = data["use_llm_summarization"]
        if "phase1_only" in data:
            config.phase1_only = data["phase1_only"]

        # Merge llm
        if "llm" in data:
            for key, value in data["llm"].items():
                if hasattr(config.llm, key):
                    setattr(config.llm, key, value)

        # Merge phase1
        if "phase1" in data:
            for key, value in data["phase1"].items():
                if hasattr(config.phase1, key):
                    setattr(config.phase1, key, value)

        # Merge phase2
        if "phase2" in data:
            for key, value in data["phase2"].items():
                if hasattr(config.phase2, key):
                    setattr(config.phase2, key, value)

        return config

    def merge_cli(self, **kwargs: Any) -> "RunConfig":
        """Override config with non-None CLI arguments."""
        # Top-level
        if kwargs.get("hallmark"):
            self.hallmark = kwargs["hallmark"]
        if kwargs.get("output_dir"):
            self.output_dir = Path(kwargs["output_dir"])
        if kwargs.get("use_llm_summarization") is not None:
            self.use_llm_summarization = kwargs["use_llm_summarization"]
        if kwargs.get("phase1_only") is not None:
            self.phase1_only = kwargs["phase1_only"]

        # LLM
        if kwargs.get("provider"):
            self.llm.provider = kwargs["provider"]
        if kwargs.get("model"):
            self.llm.model = kwargs["model"]
        if kwargs.get("model_low"):
            self.llm.model_low = kwargs["model_low"]
        if kwargs.get("model_high"):
            self.llm.model_high = kwargs["model_high"]
        if kwargs.get("temperature") is not None:
            self.llm.temperature = kwargs["temperature"]
        if kwargs.get("max_tokens") is not None:
            self.llm.max_tokens = kwargs["max_tokens"]
        if kwargs.get("vertex_location"):
            self.llm.vertex_location = kwargs["vertex_location"]
        if kwargs.get("openai_base_url"):
            self.llm.openai_base_url = kwargs["openai_base_url"]

        # Phase 1
        if kwargs.get("min_research_goals") is not None:
            self.phase1.min_research_goals = kwargs["min_research_goals"]
        if kwargs.get("max_research_goals") is not None:
            self.phase1.max_research_goals = kwargs["max_research_goals"]
        if kwargs.get("phase1_vector_db_top_k") is not None:
            self.phase1.phase1_vector_db_top_k = kwargs["phase1_vector_db_top_k"]
        if kwargs.get("phase1_pubmed_retmax") is not None:
            self.phase1.phase1_pubmed_retmax = kwargs["phase1_pubmed_retmax"]
        if kwargs.get("max_iterations") is not None:
            self.phase1.max_iterations = kwargs["max_iterations"]
        if kwargs.get("min_processes") is not None:
            self.phase1.min_processes = kwargs["min_processes"]
        if kwargs.get("max_processes") is not None:
            self.phase1.max_processes = kwargs["max_processes"]
        if kwargs.get("summary_max_words") is not None:
            self.phase1.summary_max_words = kwargs["summary_max_words"]

        # Phase 2
        if kwargs.get("max_research_iterations") is not None:
            self.phase2.max_research_iterations = kwargs["max_research_iterations"]
        if kwargs.get("max_refine_iterations") is not None:
            self.phase2.max_refine_iterations = kwargs["max_refine_iterations"]
        if kwargs.get("min_actions_per_iteration") is not None:
            self.phase2.min_actions_per_iteration = kwargs["min_actions_per_iteration"]
        if kwargs.get("max_actions_per_iteration") is not None:
            self.phase2.max_actions_per_iteration = kwargs["max_actions_per_iteration"]
        if kwargs.get("genage_seed_max_results") is not None:
            self.phase2.genage_seed_max_results = kwargs["genage_seed_max_results"]
        if kwargs.get("opengenes_seed_results_per_query") is not None:
            self.phase2.opengenes_seed_results_per_query = kwargs["opengenes_seed_results_per_query"]
        if kwargs.get("phase2_vector_db_top_k") is not None:
            self.phase2.phase2_vector_db_top_k = kwargs["phase2_vector_db_top_k"]
        if kwargs.get("phase2_pubmed_retmax") is not None:
            self.phase2.phase2_pubmed_retmax = kwargs["phase2_pubmed_retmax"]
        if kwargs.get("opengenes_results_per_query") is not None:
            self.phase2.opengenes_results_per_query = kwargs["opengenes_results_per_query"]
        if kwargs.get("max_opengenes_items_per_field") is not None:
            self.phase2.max_opengenes_items_per_field = kwargs["max_opengenes_items_per_field"]
        if kwargs.get("phase2_summarize_max_tokens") is not None:
            self.phase2.phase2_summarize_max_tokens = kwargs["phase2_summarize_max_tokens"]
        if kwargs.get("max_critic_iterations") is not None:
            self.phase2.max_critic_iterations = kwargs["max_critic_iterations"]
        if kwargs.get("refine_opengenes_max_results") is not None:
            self.phase2.refine_opengenes_max_results = kwargs["refine_opengenes_max_results"]
        if kwargs.get("refine_pubmed_max_results") is not None:
            self.phase2.refine_pubmed_max_results = kwargs["refine_pubmed_max_results"]
        if kwargs.get("refine_vector_db_top_k") is not None:
            self.phase2.refine_vector_db_top_k = kwargs["refine_vector_db_top_k"]

        return self
