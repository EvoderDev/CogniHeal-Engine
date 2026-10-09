"""Unit tests for the sandbox execution subsystem."""

from __future__ import annotations

import unittest

from cogniheal.sandbox.executor import execute_code, execute_subprocess


class TestSandboxExecutor(unittest.TestCase):
    """Tests for sandbox execution."""

    def test_sandbox_successful_execution(self) -> None:
        code = """
import sys
print("CogniHeal Sandbox Online")
sys.exit(0)
"""
        result = execute_code(code, timeout=10, mode="subprocess")
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("CogniHeal Sandbox Online", result.stdout)
        self.assertFalse(result.timed_out)
        self.assertGreaterEqual(result.duration_ms, 0)

    def test_sandbox_failure_captures_stderr(self) -> None:
        code = """
def fail():
    raise ValueError("Deliberate failure inside sandbox")
fail()
"""
        result = execute_code(code, timeout=10, mode="subprocess")
        self.assertFalse(result.success)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("ValueError", result.stderr)
        self.assertIn("Deliberate failure inside sandbox", result.stderr)

    def test_sandbox_timeout_handling(self) -> None:
        code = """
import time
time.sleep(10)
"""
        result = execute_code(code, timeout=1, mode="subprocess")
        self.assertFalse(result.success)
        self.assertTrue(result.timed_out)


if __name__ == "__main__":
    unittest.main()
