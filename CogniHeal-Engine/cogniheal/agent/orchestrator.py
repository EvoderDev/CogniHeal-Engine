"""Autonomous Self-Healing Agent Orchestrator.

The ``HealingOrchestrator`` is the brain of CogniHeal.  When a new coding
task or prompt arrives, it:

1. **Memory Scan** — queries the episodic memory for semantically similar
   past failures and retrieves active hard-constraint rules.
2. **Code Generation** — constructs a system prompt enriched with
   "Lessons from Past Experience" and "Hard Constraints", then asks the
   LLM to produce code.
3. **Sandbox Execution** — runs the generated code in the secure sandbox.
4. **Self-Heal Loop** — if execution fails, invokes the Reflexion engine
   to analyse the error, proposes a fix, and retries up to *N* times.
5. **Memory Update** — after resolution (success or max retries), writes
   a full episodic record to the hybrid memory store.

"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from cogniheal.config import settings
from cogniheal.engine.ast_analyzer import analyse_source
from cogniheal.engine.rca import perform_rca
from cogniheal.engine.reflection import ReflectionEngine
from cogniheal.memory.episodic_engine import EpisodicMemoryEngine
from cogniheal.memory.models import (
    EpisodicRecord,
    FixRecord,
    HardConstraintRule,
    ReflectionOutput,
    SandboxResult,
)
from cogniheal.sandbox.executor import execute_code

logger = logging.getLogger(__name__)


# ── Callback protocol ─────────────────────────────────────────────────────

@dataclass
class HealCycleEvent:
    """Event emitted at each stage of the self-heal loop.

    The CLI or any other consumer can subscribe to these events via
    the ``on_event`` callback to render live progress.
    """

    stage: str  # e.g. "memory_scan", "execute", "reflect", "fix", "success", "exhausted"
    iteration: int
    message: str
    data: dict[str, Any] = field(default_factory=dict)


EventCallback = Callable[[HealCycleEvent], None]


def _noop_callback(event: HealCycleEvent) -> None:
    """Default no-op event callback."""
    pass


# ── Code-generation prompt ─────────────────────────────────────────────────

_CODEGEN_SYSTEM = """\
You are **CogniHeal Code Generator** — an expert Python programmer.
Generate clean, correct, production-quality Python code that solves the
user's task.

IMPORTANT RULES:
{constraints}

LESSONS FROM PAST EXPERIENCE:
{lessons}

Return ONLY the Python code — no markdown fences, no explanations.
"""


# ── Orchestrator ───────────────────────────────────────────────────────────

class HealingOrchestrator:
    """Autonomous self-healing agent orchestrator.

    Usage::

        memory = EpisodicMemoryEngine()
        memory.initialise()
        orch = HealingOrchestrator(memory_engine=memory)
        result = orch.run("Write a function that sorts a list of dicts by 'age'.")
    """

    def __init__(
        self,
        memory_engine: EpisodicMemoryEngine,
        max_iterations: int | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self.memory = memory_engine
        self.max_iterations = max_iterations or settings.max_heal_iterations
        self.on_event = on_event or _noop_callback
        self.reflection_engine = ReflectionEngine()

    # ── public API ────────────────────────────────────────────────────

    def run(
        self,
        task_prompt: str,
        initial_code: str | None = None,
        context: str | None = None,
    ) -> OrchestratorResult:
        """Execute the full self-healing pipeline for a task.

        Args:
            task_prompt: Natural-language description of the coding task.
            initial_code: Optional pre-written code to execute directly
                          (skips LLM code generation on iteration 1).
            context: Optional prior session context or previous code history
                     to preserve multi-turn agent memory.

        Returns:
            An ``OrchestratorResult`` summarising the entire run.
        """
        start_time = time.perf_counter()

        # Step 1 — Memory scan
        self.on_event(HealCycleEvent(
            stage="memory_scan", iteration=0,
            message="Querying episodic memory for similar past failures…",
        ))
        past_episodes = self.memory.query(task_prompt)
        constraints = self.memory.get_all_constraints()
        constraint_texts = [c["description"] for c in constraints]

        self.on_event(HealCycleEvent(
            stage="memory_scan", iteration=0,
            message=f"Found {len(past_episodes)} relevant memories, {len(constraints)} active constraints.",
            data={"memories": len(past_episodes), "constraints": len(constraints)},
        ))

        # Step 2 — Prepare initial code
        if initial_code:
            current_code = initial_code
        else:
            current_code = self._generate_code(
                task_prompt, past_episodes, constraint_texts, context=context
            )

        all_attempts: list[AttemptRecord] = []
        final_result: SandboxResult | None = None
        final_reflection: ReflectionOutput | None = None
        success = False

        for iteration in range(1, self.max_iterations + 1):
            self.on_event(HealCycleEvent(
                stage="execute", iteration=iteration,
                message=f"Executing code (attempt {iteration}/{self.max_iterations})…",
            ))

            # Step 3 — Execute in sandbox
            result = execute_code(current_code)
            final_result = result

            attempt = AttemptRecord(
                iteration=iteration,
                code=current_code,
                result=result,
            )

            if result.success:
                self.on_event(HealCycleEvent(
                    stage="success", iteration=iteration,
                    message=f"✅ Code executed successfully on attempt {iteration}!",
                    data={"stdout": result.stdout[:500]},
                ))
                success = True
                all_attempts.append(attempt)
                break

            # Step 4 — Reflection & self-heal
            self.on_event(HealCycleEvent(
                stage="reflect", iteration=iteration,
                message=f"❌ Execution failed. Running Reflexion analysis…",
                data={"stderr": result.stderr[:1000]},
            ))

            ast_report = analyse_source(current_code)
            ast_insights = [ins.message for ins in ast_report.insights]

            reflection = self.reflection_engine.reflect(
                code=current_code,
                error=result.stderr,
                task_prompt=task_prompt,
                iteration=iteration,
                memory_context=past_episodes,
                constraints=constraint_texts,
                ast_insights=ast_insights,
            )
            final_reflection = reflection
            attempt.reflection = reflection
            all_attempts.append(attempt)

            self.on_event(HealCycleEvent(
                stage="fix", iteration=iteration,
                message=(
                    f"🔧 Applying fix (confidence: {reflection.confidence:.0%})\n"
                    f"   Constraint: {reflection.hard_constraint}"
                ),
                data={
                    "confidence": reflection.confidence,
                    "constraint": reflection.hard_constraint,
                },
            ))

            # Apply the fix
            current_code = reflection.proposed_fix if reflection.proposed_fix.strip() else current_code

            # Add the new constraint immediately
            if reflection.hard_constraint:
                constraint_texts.append(reflection.hard_constraint)

        if not success:
            self.on_event(HealCycleEvent(
                stage="exhausted", iteration=self.max_iterations,
                message=f"💀 Max iterations ({self.max_iterations}) exhausted. Could not self-heal.",
            ))

        # Step 5 — Persist to memory
        elapsed = time.perf_counter() - start_time
        self._persist_episode(
            task_prompt=task_prompt,
            attempts=all_attempts,
            success=success,
            final_result=final_result,
            final_reflection=final_reflection,
        )

        return OrchestratorResult(
            task_prompt=task_prompt,
            success=success,
            total_iterations=len(all_attempts),
            final_code=current_code,
            final_result=final_result,
            attempts=all_attempts,
            elapsed_seconds=elapsed,
        )

    # ── code generation ───────────────────────────────────────────────

    def _generate_code(
        self,
        task_prompt: str,
        memories: list[EpisodicRecord],
        constraints: list[str],
        context: str | None = None,
    ) -> str:
        """Ask the LLM to generate initial code for the task."""
        lessons = "\n".join(
            rec.to_prompt_injection() for rec in memories
        ) if memories else "(No past lessons available.)"
        constraint_block = "\n".join(
            f"- {c}" for c in constraints
        ) if constraints else "- (No special constraints.)"

        system = _CODEGEN_SYSTEM.format(
            constraints=constraint_block,
            lessons=lessons,
        )

        user_content = task_prompt
        if context:
            user_content = (
                f"### Active Session Context & Prior Code State:\n{context}\n\n"
                f"### Current Task Instruction:\n{task_prompt}"
            )

        if not settings.openai_api_key:
            return f"# CogniHeal: No API key — cannot generate code for: {task_prompt}\nraise NotImplementedError('API key required for code generation')"

        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        )
        code = resp.choices[0].message.content or ""
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    # ── memory persistence ────────────────────────────────────────────

    def _persist_episode(
        self,
        task_prompt: str,
        attempts: list[AttemptRecord],
        success: bool,
        final_result: SandboxResult | None,
        final_reflection: ReflectionOutput | None,
    ) -> None:
        """Write the completed self-heal episode to the memory engine."""
        if not attempts:
            return

        first_attempt = attempts[0]
        last_attempt = attempts[-1]
        error_text = first_attempt.result.stderr if first_attempt.result else ""

        # Build RCA
        rca_data, frames, _ = perform_rca(
            first_attempt.code, error_text, use_llm=False,
        )
        if final_reflection and final_reflection.root_cause:
            rca_data = final_reflection.root_cause

        # Build fix record
        fix = FixRecord(
            description=(
                final_reflection.self_critique
                if final_reflection
                else "No reflection available."
            ),
            fixed_code=last_attempt.code,
            iteration=len(attempts),
        )

        # Build hard constraint
        constraint = HardConstraintRule(
            description=(
                final_reflection.hard_constraint
                if final_reflection
                else "Review code carefully before execution."
            ),
        )

        record = EpisodicRecord(
            original_code=first_attempt.code,
            task_prompt=task_prompt,
            raw_error=error_text,
            stack_frames=list(frames) if frames else [],
            rca=rca_data,
            reflection_reasoning=(
                final_reflection.chain_of_thought if final_reflection else ""
            ),
            fix=fix,
            hard_constraint=constraint,
            tags=[rca_data.category.value, rca_data.severity.value],
            success=success,
            total_iterations=len(attempts),
        )

        try:
            self.memory.upsert(record)
            logger.info("Persisted episode %s (success=%s)", record.episode_id, success)
        except Exception as exc:
            logger.error("Failed to persist episode: %s", exc)


# ── Supporting data classes ────────────────────────────────────────────────

@dataclass
class AttemptRecord:
    """Record of a single execution attempt within the self-heal loop."""

    iteration: int
    code: str
    result: SandboxResult | None = None
    reflection: ReflectionOutput | None = None


@dataclass
class OrchestratorResult:
    """Final result of a complete orchestrator run."""

    task_prompt: str
    success: bool
    total_iterations: int
    final_code: str
    final_result: SandboxResult | None
    attempts: list[AttemptRecord] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def summary(self) -> str:
        """Human-readable one-line summary."""
        status = "✅ SUCCESS" if self.success else "❌ FAILED"
        return (
            f"{status} | Iterations: {self.total_iterations}/{len(self.attempts)} | "
            f"Time: {self.elapsed_seconds:.1f}s"
        )
