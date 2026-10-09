"""AST-based static analysis and log parsing utilities.

Provides tools for:
- Parsing Python source into AST and extracting structural information.
- Parsing raw traceback / stderr text into structured ``StackFrame`` lists.
- Detecting common anti-patterns (bare excepts, mutable defaults, etc.).
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from typing import Any

from cogniheal.memory.models import StackFrame


# ── Traceback parsing ──────────────────────────────────────────────────────

_TB_LINE_RE = re.compile(
    r'^\s*File "(?P<file>.+?)",\s*line\s+(?P<line>\d+)'
    r'(?:,\s*in\s+(?P<func>.+))?',
)
_ERROR_LINE_RE = re.compile(r"^(?P<exc>[A-Za-z_][A-Za-z0-9_.]*Error|Exception):\s*(?P<msg>.*)")


def parse_traceback(raw: str) -> list[StackFrame]:
    """Parse a Python traceback string into a list of ``StackFrame`` objects.

    Args:
        raw: The raw traceback text (stderr content).

    Returns:
        An ordered list of ``StackFrame`` entries from outermost to innermost.
    """
    frames: list[StackFrame] = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        match = _TB_LINE_RE.match(lines[i])
        if match:
            code_ctx = ""
            if i + 1 < len(lines) and not _TB_LINE_RE.match(lines[i + 1]):
                code_ctx = lines[i + 1].strip()
                i += 1
            frames.append(
                StackFrame(
                    filename=match.group("file"),
                    lineno=int(match.group("line")),
                    function_name=match.group("func") or "<module>",
                    code_context=code_ctx,
                )
            )
        i += 1
    return frames


def extract_error_type(raw: str) -> tuple[str, str]:
    """Extract the exception class name and message from a traceback.

    Args:
        raw: Raw traceback / stderr text.

    Returns:
        A ``(error_type, error_message)`` tuple.  Falls back to
        ``("UnknownError", <first non-empty line>)`` if parsing fails.
    """
    for line in reversed(raw.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        match = _ERROR_LINE_RE.match(stripped)
        if match:
            return match.group("exc"), match.group("msg")
        if ":" in stripped:
            parts = stripped.split(":", 1)
            return parts[0].strip(), parts[1].strip()
    return "UnknownError", raw.strip()[:200]


# ── AST analysis ───────────────────────────────────────────────────────────

@dataclass
class ASTInsight:
    """A single observation from static AST analysis."""

    category: str
    message: str
    lineno: int = 0
    col_offset: int = 0
    severity: str = "warning"


@dataclass
class ASTReport:
    """Aggregated result of AST analysis on a source string."""

    source: str
    tree: ast.AST | None = None
    parse_error: str | None = None
    insights: list[ASTInsight] = field(default_factory=list)
    defined_functions: list[str] = field(default_factory=list)
    defined_classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def analyse_source(source: str) -> ASTReport:
    """Perform static AST analysis on Python source code.

    This function parses the source, collects structural metadata
    (functions, classes, imports) and runs a battery of heuristic
    checks to surface common anti-patterns.

    Args:
        source: Python source code string.

    Returns:
        An ``ASTReport`` containing the parsed tree (if successful),
        structural metadata and any detected insights.
    """
    report = ASTReport(source=source)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        report.parse_error = f"{exc.msg} (line {exc.lineno})"
        return report

    report.tree = tree

    for node in ast.walk(tree):
        # Collect structure
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            report.defined_functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            report.defined_classes.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                report.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                report.imports.append(node.module)

        # Heuristic checks
        _check_bare_except(node, report)
        _check_mutable_default(node, report)
        _check_global_usage(node, report)
        _check_star_import(node, report)

    return report


def _check_bare_except(node: ast.AST, report: ASTReport) -> None:
    """Flag bare ``except:`` clauses."""
    if isinstance(node, ast.ExceptHandler) and node.type is None:
        report.insights.append(
            ASTInsight(
                category="bare_except",
                message="Bare 'except:' clause swallows all exceptions including KeyboardInterrupt.",
                lineno=node.lineno,
                col_offset=node.col_offset,
                severity="error",
            )
        )


def _check_mutable_default(node: ast.AST, report: ASTReport) -> None:
    """Flag mutable default arguments (list, dict, set literals)."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        for default in node.args.defaults + node.args.kw_defaults:
            if default is not None and isinstance(default, ast.List | ast.Dict | ast.Set):
                report.insights.append(
                    ASTInsight(
                        category="mutable_default",
                        message=f"Mutable default argument in '{node.name}' — use None and assign inside the body.",
                        lineno=node.lineno,
                        severity="warning",
                    )
                )


def _check_global_usage(node: ast.AST, report: ASTReport) -> None:
    """Flag usage of the ``global`` statement."""
    if isinstance(node, ast.Global):
        report.insights.append(
            ASTInsight(
                category="global_usage",
                message=f"'global' statement for {', '.join(node.names)} — prefer passing state explicitly.",
                lineno=node.lineno,
                severity="warning",
            )
        )


def _check_star_import(node: ast.AST, report: ASTReport) -> None:
    """Flag wildcard ``from X import *`` imports."""
    if isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                report.insights.append(
                    ASTInsight(
                        category="star_import",
                        message=f"Wildcard import 'from {node.module} import *' pollutes namespace.",
                        lineno=node.lineno,
                        severity="warning",
                    )
                )


def get_function_source(full_source: str, function_name: str) -> str | None:
    """Extract the source code of a specific function from a module.

    Args:
        full_source: The full module source.
        function_name: Name of the function to extract.

    Returns:
        The function source as a string, or ``None`` if not found.
    """
    try:
        tree = ast.parse(full_source)
    except SyntaxError:
        return None

    lines = full_source.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function_name:
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            return "".join(lines[start:end])
    return None
