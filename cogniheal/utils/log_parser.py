"""Advanced log and stderr parsing utilities.

Provides structured extraction of:
- Python tracebacks (standard and chained exceptions).
- Deprecation / runtime warnings.
- Segmentation faults and core dump signals.
- Package installation failure messages.

All parsers return typed dataclass results that can be consumed by the
RCA and Reflection engines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class ParsedTraceback:
    """A single parsed Python traceback block."""

    exception_type: str
    exception_message: str
    frames: list[dict[str, Any]] = field(default_factory=list)
    is_chained: bool = False
    chain_type: str = ""  # "cause" (__cause__) or "context" (__context__)


@dataclass
class ParsedWarning:
    """A parsed Python warning."""

    category: str  # e.g. "DeprecationWarning"
    message: str
    filename: str = ""
    lineno: int = 0


@dataclass
class LogParseResult:
    """Aggregated result of parsing a full stderr / log stream."""

    raw: str
    tracebacks: list[ParsedTraceback] = field(default_factory=list)
    warnings: list[ParsedWarning] = field(default_factory=list)
    has_segfault: bool = False
    has_oom: bool = False
    has_install_error: bool = False
    install_error_packages: list[str] = field(default_factory=list)
    unrecognised_lines: list[str] = field(default_factory=list)


# ── Regex patterns ─────────────────────────────────────────────────────────

_TB_HEADER = re.compile(r"^Traceback \(most recent call last\):")
_TB_FILE = re.compile(
    r'^\s+File "(?P<file>.+?)",\s+line\s+(?P<line>\d+)'
    r'(?:,\s+in\s+(?P<func>.+))?'
)
_TB_ERROR = re.compile(
    r"^(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Fault))"
    r"(?::\s*(?P<msg>.*))?"
)
_CHAIN_CAUSE = re.compile(
    r"^The above exception was the direct cause of the following exception:"
)
_CHAIN_CONTEXT = re.compile(
    r"^During handling of the above exception, another exception occurred:"
)
_WARNING_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):\s+(?P<cat>\w+Warning):\s+(?P<msg>.+)"
)
_SEGFAULT_RE = re.compile(r"Segmentation fault|SIGSEGV|core dumped", re.IGNORECASE)
_OOM_RE = re.compile(r"MemoryError|Out of memory|Cannot allocate memory", re.IGNORECASE)
_PIP_FAIL_RE = re.compile(
    r"(?:ERROR|error).*(?:No matching distribution|Could not find).*?(?P<pkg>[a-zA-Z0-9_-]+)"
)
_MODULE_NOT_FOUND = re.compile(r"ModuleNotFoundError: No module named '(?P<pkg>[^']+)'")


# ── Parser ─────────────────────────────────────────────────────────────────

def parse_log_output(raw: str) -> LogParseResult:
    """Parse raw stderr / log output into structured components.

    This function performs a single pass over the text, extracting:
    - One or more traceback blocks (including chained exceptions).
    - Python warnings.
    - Segfault / OOM indicators.
    - Package installation failures.

    Args:
        raw: The raw stderr or log text.

    Returns:
        A ``LogParseResult`` with all extracted information.
    """
    result = LogParseResult(raw=raw)
    lines = raw.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── Traceback block ──────────────────────────────────────────
        if _TB_HEADER.match(line):
            tb, i = _parse_one_traceback(lines, i)
            result.tracebacks.append(tb)
            continue

        # ── Chained exception markers ────────────────────────────────
        if _CHAIN_CAUSE.match(line):
            if result.tracebacks:
                result.tracebacks[-1].is_chained = True
                result.tracebacks[-1].chain_type = "cause"
            i += 1
            continue

        if _CHAIN_CONTEXT.match(line):
            if result.tracebacks:
                result.tracebacks[-1].is_chained = True
                result.tracebacks[-1].chain_type = "context"
            i += 1
            continue

        # ── Warnings ─────────────────────────────────────────────────
        wm = _WARNING_RE.match(line)
        if wm:
            result.warnings.append(
                ParsedWarning(
                    category=wm.group("cat"),
                    message=wm.group("msg"),
                    filename=wm.group("file"),
                    lineno=int(wm.group("line")),
                )
            )
            i += 1
            continue

        # ── Segfault ─────────────────────────────────────────────────
        if _SEGFAULT_RE.search(line):
            result.has_segfault = True
            i += 1
            continue

        # ── OOM ──────────────────────────────────────────────────────
        if _OOM_RE.search(line):
            result.has_oom = True
            i += 1
            continue

        # ── Install errors ───────────────────────────────────────────
        pip_m = _PIP_FAIL_RE.search(line)
        if pip_m:
            result.has_install_error = True
            result.install_error_packages.append(pip_m.group("pkg"))
            i += 1
            continue

        mod_m = _MODULE_NOT_FOUND.search(line)
        if mod_m:
            result.has_install_error = True
            pkg = mod_m.group("pkg").split(".")[0]
            if pkg not in result.install_error_packages:
                result.install_error_packages.append(pkg)
            i += 1
            continue

        # ── Unrecognised ─────────────────────────────────────────────
        stripped = line.strip()
        if stripped:
            result.unrecognised_lines.append(stripped)
        i += 1

    return result


def _parse_one_traceback(
    lines: list[str], start: int
) -> tuple[ParsedTraceback, int]:
    """Parse a single Traceback block starting at *start*.

    Returns the ``ParsedTraceback`` and the index of the next line to
    process.
    """
    frames: list[dict[str, Any]] = []
    i = start + 1  # skip the "Traceback (most recent call last):" line

    while i < len(lines):
        fm = _TB_FILE.match(lines[i])
        if fm:
            frame: dict[str, Any] = {
                "filename": fm.group("file"),
                "lineno": int(fm.group("line")),
                "function": fm.group("func") or "<module>",
                "code": "",
            }
            # Next line is usually the code context
            if i + 1 < len(lines) and not _TB_FILE.match(lines[i + 1]):
                code_line = lines[i + 1].strip()
                if not _TB_ERROR.match(code_line):
                    frame["code"] = code_line
                    i += 1
            frames.append(frame)
            i += 1
            continue

        # Error line
        em = _TB_ERROR.match(lines[i].strip())
        if em:
            tb = ParsedTraceback(
                exception_type=em.group("type"),
                exception_message=em.group("msg") or "",
                frames=frames,
            )
            return tb, i + 1

        # Unknown line inside traceback — might be multi-line error msg
        i += 1

    # Reached end without finding error line
    return ParsedTraceback(
        exception_type="UnknownError",
        exception_message="Traceback ended unexpectedly.",
        frames=frames,
    ), i


def extract_error_signature(result: LogParseResult) -> str:
    """Build a concise error signature string for embedding.

    Combines the exception type, message, and innermost frame into a
    single line suitable for semantic similarity search.

    Args:
        result: A parsed log result.

    Returns:
        A compact error signature string.
    """
    if not result.tracebacks:
        if result.has_segfault:
            return "SIGSEGV: Segmentation fault"
        if result.has_oom:
            return "MemoryError: Out of memory"
        return "UnknownError: " + (result.unrecognised_lines[0] if result.unrecognised_lines else "no output")

    tb = result.tracebacks[-1]  # innermost exception
    parts = [f"{tb.exception_type}: {tb.exception_message}"]
    if tb.frames:
        inner = tb.frames[-1]
        parts.append(f" in {inner['function']} at {inner['filename']}:{inner['lineno']}")
    return "".join(parts)
