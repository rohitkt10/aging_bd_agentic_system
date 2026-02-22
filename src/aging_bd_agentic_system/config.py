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


@dataclass
class Phase1Config:
    """Configuration for Phase 1: Biological Process Identification."""

    min_research_goals: int = 4
    max_research_goals: int = 6
    vector_db_top_k: int = 20
    pubmed_retmax: int = 10
    max_iterations: int = 2
    max_processes: int = 15


@dataclass
class Phase2Config:
    """Configuration for Phase 2: Gene Research."""

    max_research_iterations: int = 7
    max_refine_iterations: int = 3
    genage_seed_max_results: int = 50
    opengenes_seed_max_results: int = 50
    pubmed_max_results: int = 5
    vector_db_max_results: int = 5


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
    output_dir: Path = field(default_factory=lambda: Path("outputs"))
    use_llm_summarization: bool = True
    phase1: Phase1Config = field(default_factory=Phase1Config)
    phase2: Phase2Config = field(default_factory=Phase2Config)

    def to_dict(self) -> dict[str, Any]:
        """Convert to nested dict for state."""
        return {
            "hallmark": self.hallmark,
            "output_dir": str(self.output_dir),
            "use_llm_summarization": self.use_llm_summarization,
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
        if "output_dir" in data:
            config.output_dir = Path(data["output_dir"])
        if "use_llm_summarization" in data:
            config.use_llm_summarization = data["use_llm_summarization"]

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

        # Phase 1
        if kwargs.get("min_research_goals") is not None:
            self.phase1.min_research_goals = kwargs["min_research_goals"]
        if kwargs.get("max_research_goals") is not None:
            self.phase1.max_research_goals = kwargs["max_research_goals"]
        if kwargs.get("vector_db_top_k") is not None:
            self.phase1.vector_db_top_k = kwargs["vector_db_top_k"]
        if kwargs.get("pubmed_retmax") is not None:
            self.phase1.pubmed_retmax = kwargs["pubmed_retmax"]
        if kwargs.get("max_iterations") is not None:
            self.phase1.max_iterations = kwargs["max_iterations"]
        if kwargs.get("max_processes") is not None:
            self.phase1.max_processes = kwargs["max_processes"]

        # Phase 2
        if kwargs.get("max_research_iterations") is not None:
            self.phase2.max_research_iterations = kwargs["max_research_iterations"]
        if kwargs.get("max_refine_iterations") is not None:
            self.phase2.max_refine_iterations = kwargs["max_refine_iterations"]

        return self
