"""Pydantic models for the episodic memory subsystem.

Every captured error episode is stored as an ``EpisodicRecord`` which
contains the raw error, root-cause analysis, fix applied, and a hard
constraint rule that must never be violated again.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class ErrorSeverity(str, Enum):
    """Severity classification of the captured error."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """High-level taxonomy of the error."""

    SYNTAX = "syntax_error"
    TYPE = "type_error"
    RUNTIME = "runtime_error"
    IMPORT = "import_error"
    LOGIC = "logic_error"
    CONCURRENCY = "concurrency_error"
    RESOURCE = "resource_error"
    DEPENDENCY = "dependency_error"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------
class StackFrame(BaseModel):
    """Single frame extracted from a Python traceback."""

    filename: str = Field(..., description="Source file path.")
    lineno: int = Field(..., ge=0, description="Line number (0 if unknown).")
    function_name: str = Field(..., description="Enclosing function / method.")
    code_context: str = Field(default="", description="Source line text.")


class RootCauseAnalysis(BaseModel):
    """Structured output of the root-cause analysis step."""

    summary: str = Field(
        ...,
        description="One-paragraph human-readable summary of the root cause.",
    )
    category: ErrorCategory = Field(
        ...,
        description="Classified error category.",
    )
    severity: ErrorSeverity = Field(
        ...,
        description="Assessed severity.",
    )
    root_cause_chain: list[str] = Field(
        default_factory=list,
        description="Ordered causal chain leading to the failure.",
    )
    affected_symbols: list[str] = Field(
        default_factory=list,
        description="Functions / classes / variables involved.",
    )


class HardConstraintRule(BaseModel):
    """A rule the agent must *never* violate again."""

    rule_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12],
        description="Short unique identifier.",
    )
    description: str = Field(
        ...,
        description="Natural-language statement of the constraint.",
    )
    code_pattern: str = Field(
        default="",
        description="Optional regex / AST pattern that triggers the rule.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class FixRecord(BaseModel):
    """Details of the fix that resolved the error."""

    description: str = Field(
        ...,
        description="What was changed and why.",
    )
    diff: str = Field(
        default="",
        description="Unified diff of the applied code change.",
    )
    fixed_code: str = Field(
        default="",
        description="The corrected full source after the fix.",
    )
    iteration: int = Field(
        default=1,
        ge=1,
        description="At which self-heal iteration the fix was found.",
    )


# ---------------------------------------------------------------------------
# Top-level episodic record
# ---------------------------------------------------------------------------
class EpisodicRecord(BaseModel):
    """Complete episodic memory entry persisted in the hybrid store."""

    episode_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Globally unique episode identifier.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # --- raw context ---------------------------------------------------------
    original_code: str = Field(
        ...,
        description="The code that was executed and failed.",
    )
    task_prompt: str = Field(
        default="",
        description="The task / prompt that led to this code.",
    )
    raw_error: str = Field(
        ...,
        description="Complete stderr / traceback output.",
    )
    stack_frames: list[StackFrame] = Field(
        default_factory=list,
        description="Parsed stack frames.",
    )

    # --- analysis results ----------------------------------------------------
    rca: RootCauseAnalysis = Field(
        ...,
        description="Root Cause Analysis output.",
    )
    reflection_reasoning: str = Field(
        default="",
        description="Free-form chain-of-thought reasoning from Reflexion.",
    )

    # --- fix & constraint ----------------------------------------------------
    fix: FixRecord = Field(
        ...,
        description="Details of the applied fix.",
    )
    hard_constraint: HardConstraintRule = Field(
        ...,
        description="Rule derived to prevent recurrence.",
    )

    # --- metadata ------------------------------------------------------------
    embedding_vector: list[float] = Field(
        default_factory=list,
        description="Semantic embedding of the error signature.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags for filtering.",
    )
    success: bool = Field(
        default=False,
        description="Whether the fix ultimately resolved the error.",
    )
    total_iterations: int = Field(
        default=1,
        ge=1,
        description="How many self-heal loops were needed.",
    )

    def to_semantic_text(self) -> str:
        """Build a single text blob used for embedding generation."""
        parts: list[str] = [
            f"Error: {self.rca.summary}",
            f"Category: {self.rca.category.value}",
            f"Root cause chain: {' -> '.join(self.rca.root_cause_chain)}",
            f"Fix: {self.fix.description}",
            f"Constraint: {self.hard_constraint.description}",
        ]
        return "\n".join(parts)

    def to_prompt_injection(self) -> str:
        """Format the episode as an injectable prompt paragraph."""
        return (
            f"⚠️  PAST LESSON (severity={self.rca.severity.value}):\n"
            f"   Error  : {self.rca.summary}\n"
            f"   Cause  : {' → '.join(self.rca.root_cause_chain)}\n"
            f"   Fix    : {self.fix.description}\n"
            f"   🚫 RULE : {self.hard_constraint.description}\n"
        )


# ---------------------------------------------------------------------------
# Reflection output (structured JSON the LLM must return)
# ---------------------------------------------------------------------------
class ReflectionOutput(BaseModel):
    """Structured output produced by the Reflexion analysis step."""

    chain_of_thought: str = Field(
        ...,
        description="Step-by-step reasoning about the failure.",
    )
    self_critique: str = Field(
        ...,
        description="What went wrong in the previous attempt.",
    )
    root_cause: RootCauseAnalysis = Field(
        ...,
        description="Structured root cause analysis.",
    )
    proposed_fix: str = Field(
        ...,
        description="Concrete code fix to apply.",
    )
    hard_constraint: str = Field(
        ...,
        description="Rule to add to prevent recurrence.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Self-assessed confidence in the fix.",
    )


class SandboxResult(BaseModel):
    """Result of a single sandbox execution."""

    success: bool = Field(..., description="True if exit code was 0.")
    exit_code: int = Field(..., description="Process exit code.")
    stdout: str = Field(default="", description="Captured stdout.")
    stderr: str = Field(default="", description="Captured stderr.")
    duration_ms: int = Field(default=0, ge=0, description="Wall-clock ms.")
    timed_out: bool = Field(default=False, description="Hit timeout?")
