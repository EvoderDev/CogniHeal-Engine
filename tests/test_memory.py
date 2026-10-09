"""Unit tests for the episodic memory models and engine."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from cogniheal.memory.embeddings import cosine_similarity, generate_embedding
from cogniheal.memory.episodic_engine import EpisodicMemoryEngine
from cogniheal.memory.models import (
    EpisodicRecord,
    ErrorCategory,
    ErrorSeverity,
    FixRecord,
    HardConstraintRule,
    RootCauseAnalysis,
    StackFrame,
)


class TestMemorySubsystem(unittest.TestCase):
    """Tests for models, embeddings, and hybrid memory engine."""

    def test_models_to_semantic_text(self) -> None:
        rca = RootCauseAnalysis(
            summary="TypeError: str cannot be multiplied by str",
            category=ErrorCategory.TYPE,
            severity=ErrorSeverity.MEDIUM,
            root_cause_chain=["input validation failed", "attempted multiply"],
            affected_symbols=["calculate_area"],
        )
        fix = FixRecord(
            description="Cast string input to float before multiplication",
            diff="- return w * h\n+ return float(w) * float(h)",
            fixed_code="def calculate_area(w, h): return float(w) * float(h)",
            iteration=1,
        )
        rule = HardConstraintRule(
            description="Always coerce dimension arguments to numeric floats.",
            code_pattern=r"float\(",
        )
        record = EpisodicRecord(
            original_code="def calculate_area(w, h): return w * h",
            task_prompt="Compute rectangle area from user form input",
            raw_error="TypeError: can't multiply sequence by non-int of type 'str'",
            stack_frames=[
                StackFrame(
                    filename="calc.py",
                    lineno=2,
                    function_name="calculate_area",
                    code_context="return w * h",
                )
            ],
            rca=rca,
            fix=fix,
            hard_constraint=rule,
            tags=["type_error", "geometry"],
            success=True,
        )

        text = record.to_semantic_text()
        self.assertIn("TypeError", text)
        self.assertIn("type_error", text)
        self.assertIn("Always coerce", text)

        injection = record.to_prompt_injection()
        self.assertIn("PAST LESSON", injection)
        self.assertIn("🚫 RULE", injection)

    def test_embedding_fallback_deterministic(self) -> None:
        text_a = "TypeError: cannot add str to int"
        text_b = "TypeError: cannot add str to int"
        text_c = "SyntaxError: invalid syntax"

        vec_a = generate_embedding(text_a)
        vec_b = generate_embedding(text_b)
        vec_c = generate_embedding(text_c)

        self.assertGreater(len(vec_a), 0)
        self.assertEqual(vec_a, vec_b)

        sim_ab = cosine_similarity(vec_a, vec_b)
        self.assertLess(abs(sim_ab - 1.0), 1e-4)

        sim_ac = cosine_similarity(vec_a, vec_c)
        self.assertLess(sim_ac, 0.99)

    def test_memory_engine_crud(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            sqlite_path = data_dir / "test_episodes.db"
            chroma_dir = data_dir / "chroma"

            with EpisodicMemoryEngine(
                data_dir=data_dir,
                sqlite_path=sqlite_path,
                chroma_persist_dir=chroma_dir,
                collection_name="test_episodes_collection",
            ) as engine:
                self.assertEqual(engine.count_episodes(), 0)
                self.assertEqual(engine.count_constraints(), 0)

                rca = RootCauseAnalysis(
                    summary="ZeroDivisionError in calculate_ratio",
                    category=ErrorCategory.RUNTIME,
                    severity=ErrorSeverity.HIGH,
                    root_cause_chain=["denominator was zero"],
                    affected_symbols=["calculate_ratio"],
                )
                fix = FixRecord(
                    description="Add guard condition for denominator == 0",
                    diff="+ if b == 0: return 0.0",
                    fixed_code="def calculate_ratio(a, b): return a / b if b != 0 else 0.0",
                    iteration=1,
                )
                rule = HardConstraintRule(
                    description="Never divide without validating denominator is non-zero.",
                )
                record = EpisodicRecord(
                    original_code="def calculate_ratio(a, b): return a / b",
                    task_prompt="Compute ratio of two metrics",
                    raw_error="ZeroDivisionError: division by zero",
                    rca=rca,
                    fix=fix,
                    hard_constraint=rule,
                    tags=["zero_division"],
                    success=True,
                    total_iterations=1,
                )

                engine.upsert(record)
                self.assertEqual(engine.count_episodes(), 1)
                self.assertEqual(engine.count_constraints(), 1)

                recent = engine.recent_episodes(limit=5)
                self.assertEqual(len(recent), 1)
                self.assertEqual(recent[0].episode_id, record.episode_id)

                constraints = engine.get_all_constraints()
                self.assertEqual(len(constraints), 1)
                self.assertIn("Never divide without validating", constraints[0]["description"])

                results = engine.query("division by zero error", top_k=3, min_similarity=0.0)
                self.assertGreaterEqual(len(results), 1)
                self.assertEqual(results[0].episode_id, record.episode_id)


if __name__ == "__main__":
    unittest.main()
