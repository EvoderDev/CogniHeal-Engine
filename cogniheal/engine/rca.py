"""Root Cause Analysis (RCA) module.

Combines AST static analysis with LLM-powered reasoning to produce
structured ``RootCauseAnalysis`` verdicts for runtime failures.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from cogniheal.config import settings
from cogniheal.engine.ast_analyzer import (
    ASTReport,
    analyse_source,
    extract_error_type,
    parse_traceback,
)
from cogniheal.memory.models import (
    ErrorCategory,
    ErrorSeverity,
    RootCauseAnalysis,
    StackFrame,
)

logger = logging.getLogger(__name__)

# ── Error-type → category mapping ─────────────────────────────────────────
_CATEGORY_MAP: dict[str, ErrorCategory] = {
    "SyntaxError": ErrorCategory.SYNTAX,
    "IndentationError": ErrorCategory.SYNTAX,
    "TabError": ErrorCategory.SYNTAX,
    "TypeError": ErrorCategory.TYPE,
    "ValueError": ErrorCategory.TYPE,
    "AttributeError": ErrorCategory.TYPE,
    "ImportError": ErrorCategory.IMPORT,
    "ModuleNotFoundError": ErrorCategory.IMPORT,
    "RuntimeError": ErrorCategory.RUNTIME,
    "RecursionError": ErrorCategory.RUNTIME,
    "StopIteration": ErrorCategory.RUNTIME,
    "KeyError": ErrorCategory.RUNTIME,
    "IndexError": ErrorCategory.RUNTIME,
    "FileNotFoundError": ErrorCategory.RESOURCE,
    "PermissionError": ErrorCategory.RESOURCE,
    "OSError": ErrorCategory.RESOURCE,
    "MemoryError": ErrorCategory.RESOURCE,
    "TimeoutError": ErrorCategory.CONCURRENCY,
    "asyncio.TimeoutError": ErrorCategory.CONCURRENCY,
    "CancelledError": ErrorCategory.CONCURRENCY,
    "BrokenPipeError": ErrorCategory.CONCURRENCY,
}


def _classify_category(error_type: str) -> ErrorCategory:
    """Map an exception class name to an ``ErrorCategory``."""
    return _CATEGORY_MAP.get(error_type, ErrorCategory.UNKNOWN)


def _assess_severity(category: ErrorCategory, raw: str) -> ErrorSeverity:
    """Heuristically assess severity from category and traceback depth."""
    depth = raw.count('File "')
    if category in (ErrorCategory.CONCURRENCY, ErrorCategory.RESOURCE):
        return ErrorSeverity.CRITICAL
    if category == ErrorCategory.IMPORT:
        return ErrorSeverity.HIGH
    if depth > 8:
        return ErrorSeverity.HIGH
    if category == ErrorCategory.SYNTAX:
        return ErrorSeverity.MEDIUM
    return ErrorSeverity.MEDIUM


# ── LLM-powered deep RCA ──────────────────────────────────────────────────

_RCA_SYSTEM_PROMPT = """\
You are a world-class Python debugging expert. Analyse the following
runtime error and source code. Return a JSON object (no markdown fences)
with exactly these keys:
  - "summary": one-paragraph root cause explanation
  - "root_cause_chain": ordered list of causal steps (strings)
  - "affected_symbols": list of function/class/variable names involved
  - "category": one of syntax_error|type_error|runtime_error|import_error|logic_error|concurrency_error|resource_error|dependency_error|unknown
  - "severity": one of low|medium|high|critical
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _llm_rca(code: str, error: str) -> dict[str, Any]:
    """Call the LLM to produce a structured RCA JSON."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.1,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _RCA_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"### Source code\n```python\n{code}\n```\n\n### Error\n```\n{error}\n```",
            },
        ],
    )
    text = resp.choices[0].message.content or "{}"
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    return json.loads(text)


def perform_rca(
    code: str,
    raw_error: str,
    use_llm: bool = True,
) -> tuple[RootCauseAnalysis, list[StackFrame], ASTReport]:
    """Run full Root Cause Analysis on a failed code execution.

    The analysis proceeds in three stages:

    1. **Traceback parsing** — structured ``StackFrame`` extraction.
    2. **AST static analysis** — heuristic checks for anti-patterns.
    3. **LLM deep analysis** (optional) — semantic understanding of the
       root cause via an LLM call.

    If the LLM call fails or ``use_llm`` is ``False``, a heuristic-only
    RCA is returned.

    Args:
        code: The Python source that was executed.
        raw_error: The complete stderr / traceback output.
        use_llm: Whether to call the LLM for deep analysis.

    Returns:
        A tuple of ``(RootCauseAnalysis, list[StackFrame], ASTReport)``.
    """
    # Stage 1 — parse traceback
    frames = parse_traceback(raw_error)
    error_type, error_msg = extract_error_type(raw_error)

    # Stage 2 — static analysis
    ast_report = analyse_source(code)

    # Stage 3 — LLM deep analysis (with fallback)
    category = _classify_category(error_type)
    severity = _assess_severity(category, raw_error)

    if use_llm and settings.openai_api_key:
        try:
            llm_result = _llm_rca(code, raw_error)
            rca = RootCauseAnalysis(
                summary=llm_result.get("summary", f"{error_type}: {error_msg}"),
                category=ErrorCategory(llm_result.get("category", category.value)),
                severity=ErrorSeverity(llm_result.get("severity", severity.value)),
                root_cause_chain=llm_result.get("root_cause_chain", [error_msg]),
                affected_symbols=llm_result.get("affected_symbols", []),
            )
            return rca, frames, ast_report
        except Exception as exc:
            logger.warning("LLM RCA failed, falling back to heuristic: %s", exc)

    # Heuristic fallback
    chain = [f"{error_type} raised"]
    if frames:
        chain.append(f"in {frames[-1].function_name} at {frames[-1].filename}:{frames[-1].lineno}")
    chain.append(error_msg)

    affected: list[str] = []
    if frames:
        affected = list({f.function_name for f in frames if f.function_name != "<module>"})

    rca = RootCauseAnalysis(
        summary=f"{error_type}: {error_msg}",
        category=category,
        severity=severity,
        root_cause_chain=chain,
        affected_symbols=affected,
    )
    return rca, frames, ast_report
