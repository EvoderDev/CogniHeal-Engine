"""Secure Python code execution sandbox.

Provides two backends:

1. **subprocess** — runs code in an isolated ``subprocess.Popen`` with
   resource limits (timeout, restricted environment variables).
2. **docker** — (optional) runs code inside a disposable Docker
   container for full filesystem / network isolation.

Both backends capture stdout and stderr, enforce a hard timeout,
and return a structured ``SandboxResult``.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from cogniheal.config import settings
from cogniheal.memory.models import SandboxResult

logger = logging.getLogger(__name__)


# ── Subprocess backend ─────────────────────────────────────────────────────

def _build_safe_env() -> dict[str, str]:
    """Build a minimal environment dict for the subprocess.

    Strips potentially dangerous variables while keeping PATH and
    locale settings so that Python can find its standard library.
    """
    keep_keys = {
        "PATH", "SYSTEMROOT", "TEMP", "TMP",
        "HOME", "LANG", "LC_ALL", "PYTHONIOENCODING",
        "VIRTUAL_ENV", "PYTHONPATH",
    }
    env: dict[str, str] = {k: v for k, v in os.environ.items() if k in keep_keys}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def execute_subprocess(
    code: str,
    timeout: int | None = None,
) -> SandboxResult:
    """Execute Python code in a subprocess sandbox.

    The code is written to a temporary file and executed with the
    current interpreter.  stdout and stderr are fully captured.

    Args:
        code: Python source code to execute.
        timeout: Hard timeout in seconds (defaults to config).

    Returns:
        A ``SandboxResult`` with captured output and timing.
    """
    timeout = timeout or settings.sandbox_timeout_seconds
    tmp_dir = tempfile.mkdtemp(prefix="cogniheal_sandbox_")
    script_path = Path(tmp_dir) / "__cogniheal_run.py"

    try:
        script_path.write_text(code, encoding="utf-8")
        start = time.perf_counter_ns()

        proc = subprocess.Popen(
            [sys.executable, "-u", str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_build_safe_env(),
            cwd=tmp_dir,
        )

        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate()
            timed_out = True

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        return SandboxResult(
            success=(proc.returncode == 0 and not timed_out),
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=elapsed_ms,
            timed_out=timed_out,
        )
    except Exception as exc:
        return SandboxResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Sandbox setup error: {exc}",
            duration_ms=0,
            timed_out=False,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Docker backend ─────────────────────────────────────────────────────────

def _docker_available() -> bool:
    """Check whether the Docker CLI is available on PATH."""
    return shutil.which("docker") is not None


def execute_docker(
    code: str,
    timeout: int | None = None,
    image: str | None = None,
) -> SandboxResult:
    """Execute Python code inside a disposable Docker container.

    The code is bind-mounted into the container and executed with
    ``python -u``.  The container is removed after execution.

    Args:
        code: Python source code to execute.
        timeout: Hard timeout in seconds.
        image: Docker image name (defaults to config).

    Returns:
        A ``SandboxResult`` with captured output and timing.
    """
    if not _docker_available():
        return SandboxResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr="Docker is not available on this system. Falling back to subprocess.",
            duration_ms=0,
            timed_out=False,
        )

    timeout = timeout or settings.sandbox_timeout_seconds
    image = image or settings.docker_image
    tmp_dir = tempfile.mkdtemp(prefix="cogniheal_docker_")
    script_path = Path(tmp_dir) / "run.py"

    try:
        script_path.write_text(code, encoding="utf-8")
        start = time.perf_counter_ns()

        cmd = [
            "docker", "run",
            "--rm",
            "--network=none",
            "--memory=256m",
            "--cpus=1",
            "--pids-limit=64",
            "-v", f"{tmp_dir}:/sandbox:ro",
            "-w", "/sandbox",
            image,
            "python", "-u", "run.py",
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate()
            timed_out = True
            # Also kill the container
            subprocess.run(
                ["docker", "kill", f"cogniheal_{os.getpid()}"],
                capture_output=True,
            )

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        return SandboxResult(
            success=(proc.returncode == 0 and not timed_out),
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=elapsed_ms,
            timed_out=timed_out,
        )
    except Exception as exc:
        return SandboxResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Docker sandbox error: {exc}",
            duration_ms=0,
            timed_out=False,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Unified entry point ───────────────────────────────────────────────────

def execute_code(
    code: str,
    timeout: int | None = None,
    mode: str | None = None,
) -> SandboxResult:
    """Execute Python code using the configured sandbox backend.

    Automatically selects the backend based on ``settings.sandbox_mode``
    or the explicit *mode* argument.  Falls back to subprocess if Docker
    is requested but unavailable.

    Args:
        code: Python source code to execute.
        timeout: Hard timeout in seconds.
        mode: Override sandbox mode ("subprocess" or "docker").

    Returns:
        A ``SandboxResult`` with captured output and timing.
    """
    mode = mode or settings.sandbox_mode
    logger.debug("Executing code in '%s' sandbox (timeout=%ss)", mode, timeout or settings.sandbox_timeout_seconds)

    if mode == "docker":
        result = execute_docker(code, timeout=timeout)
        if not result.success and "Docker is not available" in result.stderr:
            logger.warning("Docker unavailable, falling back to subprocess.")
            return execute_subprocess(code, timeout=timeout)
        return result

    return execute_subprocess(code, timeout=timeout)
