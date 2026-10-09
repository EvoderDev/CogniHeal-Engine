"""Unit and integration tests for the self-healing orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from cogniheal.agent.orchestrator import HealingOrchestrator, HealCycleEvent
from cogniheal.memory.episodic_engine import EpisodicMemoryEngine


class TestOrchestrator(unittest.TestCase):
    """Tests for the autonomous self-healing orchestrator."""

    def test_orchestrator_successful_code(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            sqlite_path = data_dir / "orch_episodes.db"
            chroma_dir = data_dir / "chroma"

            events: list[HealCycleEvent] = []

            def on_event(ev: HealCycleEvent) -> None:
                events.append(ev)

            with EpisodicMemoryEngine(
                data_dir=data_dir,
                sqlite_path=sqlite_path,
                chroma_persist_dir=chroma_dir,
                collection_name="orch_test_collection",
            ) as memory:
                orchestrator = HealingOrchestrator(
                    memory_engine=memory,
                    max_iterations=3,
                    on_event=on_event,
                )

                code = """
def add(a: int, b: int) -> int:
    return a + b

print(f"Result: {add(10, 20)}")
"""
                result = orchestrator.run(
                    task_prompt="Add two integers",
                    initial_code=code,
                )

                self.assertTrue(result.success)
                self.assertEqual(result.total_iterations, 1)
                self.assertIsNotNone(result.final_result)
                assert result.final_result is not None
                self.assertIn("Result: 30", result.final_result.stdout)
                stages = [e.stage for e in events]
                self.assertIn("memory_scan", stages)
                self.assertIn("execute", stages)
                self.assertIn("success", stages)

    def test_orchestrator_healing_flow(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            sqlite_path = data_dir / "orch_heal_episodes.db"
            chroma_dir = data_dir / "chroma"

            events: list[HealCycleEvent] = []

            with EpisodicMemoryEngine(
                data_dir=data_dir,
                sqlite_path=sqlite_path,
                chroma_persist_dir=chroma_dir,
                collection_name="orch_heal_collection",
            ) as memory:
                orchestrator = HealingOrchestrator(
                    memory_engine=memory,
                    max_iterations=3,
                    on_event=events.append,
                )

                buggy_code = """
print(undefined_variable_123)
"""
                result = orchestrator.run(
                    task_prompt="Access undefined variable",
                    initial_code=buggy_code,
                )

                self.assertGreaterEqual(len(result.attempts), 1)
                self.assertTrue(any(e.stage == "reflect" for e in events))
                self.assertGreaterEqual(memory.count_episodes(), 1)


if __name__ == "__main__":
    unittest.main()
