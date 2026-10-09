"""Centralised configuration management for CogniHeal-Engine.

All tunables are defined as environment variables (optionally loaded from a
`.env` file) and validated through Pydantic *Settings*.  Import the singleton
``settings`` object anywhere in the codebase.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings  # type: ignore[assignment]


class CogniHealSettings(BaseSettings):
    """Application-wide settings with sensible defaults."""

    # --- LLM -----------------------------------------------------------------
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key used for reflection & embedding calls.",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="Chat-completion model identifier.",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model identifier.",
    )
    llm_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for reflection calls.",
    )
    llm_max_tokens: int = Field(
        default=4096,
        ge=256,
        description="Maximum tokens for a single LLM response.",
    )

    # --- Self-heal loop ------------------------------------------------------
    max_heal_iterations: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum retry loops before the agent gives up.",
    )
    similarity_threshold: float = Field(
        default=0.78,
        ge=0.0,
        le=1.0,
        description="Cosine-similarity threshold for memory recall.",
    )
    top_k_memories: int = Field(
        default=5,
        ge=1,
        description="Number of episodic memories to inject per prompt.",
    )

    # --- Sandbox -------------------------------------------------------------
    sandbox_mode: Literal["subprocess", "docker"] = Field(
        default="subprocess",
        description="Execution backend for the code sandbox.",
    )
    sandbox_timeout_seconds: int = Field(
        default=30,
        ge=5,
        description="Hard timeout for each sandbox execution.",
    )
    docker_image: str = Field(
        default="python:3.12-slim",
        description="Docker image used when sandbox_mode is 'docker'.",
    )

    # --- Storage -------------------------------------------------------------
    data_dir: Path = Field(
        default=Path("cogniheal_data"),
        description="Root directory for SQLite DB and ChromaDB collection.",
    )
    sqlite_filename: str = Field(
        default="episodic_memory.db",
        description="SQLite database file name inside data_dir.",
    )
    chroma_collection_name: str = Field(
        default="cogniheal_episodes",
        description="ChromaDB collection name.",
    )

    # --- Logging / CLI -------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Console log verbosity.",
    )
    rich_tracebacks: bool = Field(
        default=True,
        description="Use Rich for pretty-printed tracebacks.",
    )

    model_config = {
        "env_prefix": "COGNIHEAL_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    # --- derived helpers -----------------------------------------------------
    @property
    def sqlite_path(self) -> Path:
        """Fully-qualified path to the SQLite database file."""
        return self.data_dir / self.sqlite_filename

    @property
    def chroma_persist_dir(self) -> Path:
        """Directory where ChromaDB persists its data."""
        return self.data_dir / "chroma_db"

    def ensure_dirs(self) -> None:
        """Create data directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
settings = CogniHealSettings()
