"""Reflexion-based self-reflection and critique engine.

Implements the *Reflexion* architecture (Shinn et al., 2023) adapted for
autonomous code debugging.  The pipeline:

1. **Observe** — receive the failed code, its error and any past memories.
2. **Reflect** — generate structured chain-of-thought reasoning about
   the failure, critique the previous attempt, and identify the root cause.
3. **Propose** — output a concrete fix and a hard-constraint rule.

All reflection outputs are validated through Pydantic ``ReflectionOutput``
models and returned as structured JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from cogniheal.config import settings
from cogniheal.memory.models import (
    EpisodicRecord,
    ReflectionOutput,
    RootCauseAnalysis,
)

logger = logging.getLogger(__name__)

# ── Prompt templates ───────────────────────────────────────────────────────

_REFLECTION_SYSTEM = """\
You are **CogniHeal Reflection Engine** — an expert Python debugger that
practises disciplined *self-reflection*.  You follow the Reflexion
framework:

1. **Chain-of-Thought** — reason step-by-step about what went wrong.
2. **Self-Critique** — honestly assess what the previous code attempt
   got wrong and why.
3. **Root Cause** — identify the precise root cause (not symptoms).
4. **Proposed Fix** — provide the complete corrected Python code.
5. **Hard Constraint** — state one concise rule that must *never* be
   violated again to prevent recurrence.

Return your analysis as a JSON object with exactly these keys:
{
  "chain_of_thought": "<step-by-step reasoning>",
  "self_critique": "<what went wrong in the previous attempt>",
  "root_cause": {
    "summary": "<one-paragraph root cause>",
    "category": "<syntax_error|type_error|runtime_error|import_error|logic_error|concurrency_error|resource_error|dependency_error|unknown>",
    "severity": "<low|medium|high|critical>",
    "root_cause_chain": ["<step1>", "<step2>", ...],
    "affected_symbols": ["<symbol1>", ...]
  },
  "proposed_fix": "<complete corrected Python code>",
  "hard_constraint": "<one-sentence rule>",
  "confidence": <float 0-1>
}

Do NOT wrap the JSON in markdown code fences.  Return raw JSON only.
"""

_REFLECTION_USER_TEMPLATE = """\
### Task / Prompt
{task_prompt}

### Failed Code (Attempt #{iteration})
```python
{code}
```

### Runtime Error / Traceback
```
{error}
```

### AST Insights
{ast_insights}

### Past Lessons from Memory
{memory_context}

### Active Hard Constraints
{constraints}

Analyse the failure using the Reflexion framework and return the JSON.
"""


# ── Reflection engine ──────────────────────────────────────────────────────

class ReflectionEngine:
    """Reflexion-based analysis engine.

    Wraps the LLM call, prompt construction and output parsing into a
    single coherent interface.

    Usage::

        engine = ReflectionEngine()
        output = engine.reflect(
            code=source,
            error=traceback_text,
            task_prompt="Sort a list of dicts by key 'age'",
            iteration=2,
            memory_context=[past_episode_1, past_episode_2],
            constraints=["Never use bare 'except:'"],
            ast_insights=["mutable default on line 12"],
        )
    """

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialise the OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    # ── public API ────────────────────────────────────────────────────

    def reflect(
        self,
        code: str,
        error: str,
        task_prompt: str = "",
        iteration: int = 1,
        memory_context: list[EpisodicRecord] | None = None,
        constraints: list[str] | None = None,
        ast_insights: list[str] | None = None,
    ) -> ReflectionOutput:
        """Run a full Reflexion cycle and return structured output.

        Args:
            code: The Python source that failed.
            error: The stderr / traceback output.
            task_prompt: The original task description.
            iteration: Current self-heal loop iteration number.
            memory_context: Relevant past episodic memories.
            constraints: Currently active hard-constraint descriptions.
            ast_insights: Observations from AST static analysis.

        Returns:
            A validated ``ReflectionOutput`` model.
        """
        memory_text = self._format_memories(memory_context or [])
        constraints_text = self._format_constraints(constraints or [])
        insights_text = self._format_insights(ast_insights or [])

        user_message = _REFLECTION_USER_TEMPLATE.format(
            task_prompt=task_prompt or "(not provided)",
            iteration=iteration,
            code=code,
            error=error,
            ast_insights=insights_text,
            memory_context=memory_text,
            constraints=constraints_text,
        )

        if settings.openai_api_key:
            return self._reflect_via_llm(user_message)
        return self._reflect_heuristic(code, error, task_prompt)

    # ── LLM path ──────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _reflect_via_llm(self, user_message: str) -> ReflectionOutput:
        """Call the LLM and parse the structured JSON response."""
        client = self._get_client()
        resp = client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            messages=[
                {"role": "system", "content": _REFLECTION_SYSTEM},
                {"role": "user", "content": user_message},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]

        data = json.loads(raw)
        return ReflectionOutput(
            chain_of_thought=data.get("chain_of_thought", ""),
            self_critique=data.get("self_critique", ""),
            root_cause=RootCauseAnalysis(**data.get("root_cause", {
                "summary": "Unable to determine",
                "category": "unknown",
                "severity": "medium",
            })),
            proposed_fix=data.get("proposed_fix", ""),
            hard_constraint=data.get("hard_constraint", "Review code carefully."),
            confidence=float(data.get("confidence", 0.5)),
        )

    # ── Heuristic fallback ────────────────────────────────────────────

    def _reflect_heuristic(
        self,
        code: str,
        error: str,
        task_prompt: str,
    ) -> ReflectionOutput:
        """Produce a basic reflection without an LLM.

        Uses pattern matching on the error text to generate a best-effort
        fix suggestion.  This allows the system to function (albeit with
        lower quality) when no API key is configured.
        """
        from cogniheal.engine.rca import perform_rca

        rca, frames, ast_report = perform_rca(code, error, use_llm=False)

        critique = (
            f"The code failed with {rca.category.value}. "
            f"The error occurred in: {', '.join(rca.affected_symbols) or 'unknown location'}."
        )

        chain_of_thought = (
            f"1. The code was executed and raised {rca.summary}.\n"
            f"2. Stack trace shows {len(frames)} frame(s).\n"
            f"3. AST analysis found {len(ast_report.insights)} insight(s).\n"
            f"4. The root cause is: {' -> '.join(rca.root_cause_chain)}.\n"
        )

        # Attempt a simple auto-fix for common cases
        proposed_fix = self._auto_fix_common(code, error, rca)

        return ReflectionOutput(
            chain_of_thought=chain_of_thought,
            self_critique=critique,
            root_cause=rca,
            proposed_fix=proposed_fix,
            hard_constraint=f"Always handle {rca.category.value} errors explicitly.",
            confidence=0.3,
        )

    def _auto_fix_common(self, code: str, error: str, rca: RootCauseAnalysis) -> str:
        """Attempt rule-based auto-fixes for frequent error patterns.

        Handles:
        - Missing imports (adds ``import`` statements).
        - NameError for undefined variables.
        - TypeError for wrong argument counts.
        - IndentationError cleanup.

        Returns the (possibly) corrected code.
        """
        import re

        lines = code.splitlines()

        # Fix: ModuleNotFoundError / ImportError — comment out the bad import
        if rca.category.value == "import_error":
            match = re.search(r"No module named '([^']+)'", error)
            if match:
                bad_module = match.group(1).split(".")[0]
                new_lines: list[str] = []
                for line in lines:
                    stripped = line.strip()
                    if (
                        stripped.startswith("import ") or stripped.startswith("from ")
                    ) and bad_module in stripped:
                        new_lines.append(f"# REMOVED (missing): {line}")
                    else:
                        new_lines.append(line)
                return "\n".join(new_lines)

        # Fix: NameError — add a placeholder definition
        if "NameError" in error:
            match = re.search(r"name '([^']+)' is not defined", error)
            if match:
                var_name = match.group(1)
                return f"{var_name} = None  # auto-fix: define missing name\n" + code

        # Fix: TypeError with argument counts
        if "TypeError" in error and "argument" in error:
            return f"# AUTO-FIX NOTE: Check function signatures for argument count mismatches.\n{code}"

        # Fix: IndentationError
        if "IndentationError" in error or "TabError" in error:
            import textwrap
            return textwrap.dedent(code)

        return code

    # ── formatting helpers ────────────────────────────────────────────

    @staticmethod
    def _format_memories(records: list[EpisodicRecord]) -> str:
        """Format episodic records into a prompt-injectable string."""
        if not records:
            return "(No relevant past experiences found.)"
        parts: list[str] = []
        for i, rec in enumerate(records, 1):
            parts.append(f"{i}. {rec.to_prompt_injection()}")
        return "\n".join(parts)

    @staticmethod
    def _format_constraints(constraints: list[str]) -> str:
        """Format active constraint rules."""
        if not constraints:
            return "(No active constraints.)"
        return "\n".join(f"🚫 {c}" for c in constraints)

    @staticmethod
    def _format_insights(insights: list[str]) -> str:
        """Format AST insights."""
        if not insights:
            return "(No AST issues detected.)"
        return "\n".join(f"⚡ {ins}" for ins in insights)
