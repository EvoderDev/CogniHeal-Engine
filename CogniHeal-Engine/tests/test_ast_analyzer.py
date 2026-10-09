"""Unit tests for AST static analysis and traceback parsing."""

from __future__ import annotations

import unittest

from cogniheal.engine.ast_analyzer import (
    analyse_source,
    extract_error_type,
    get_function_source,
    parse_traceback,
)


class TestASTAnalyzer(unittest.TestCase):
    """Tests for the AST analyzer and traceback parser."""

    def test_analyse_source_valid_ast(self) -> None:
        code = """
def hello(name: str) -> str:
    return f"Hello, {name}!"

class Greeter:
    def greet(self):
        return hello("world")
"""
        report = analyse_source(code)
        self.assertIsNone(report.parse_error)
        self.assertIn("hello", report.defined_functions)
        self.assertIn("Greeter", report.defined_classes)
        self.assertEqual(len(report.insights), 0)

    def test_analyse_source_syntax_error(self) -> None:
        broken_code = "def broken(:\n    pass"
        report = analyse_source(broken_code)
        self.assertIsNotNone(report.parse_error)
        self.assertIsNone(report.tree)

    def test_detect_bare_except(self) -> None:
        code = """
try:
    x = 1 / 0
except:
    pass
"""
        report = analyse_source(code)
        bare_excepts = [i for i in report.insights if i.category == "bare_except"]
        self.assertEqual(len(bare_excepts), 1)
        self.assertIn("swallows all exceptions", bare_excepts[0].message)

    def test_detect_mutable_default(self) -> None:
        code = """
def append_item(item, items=[]):
    items.append(item)
    return items
"""
        report = analyse_source(code)
        mutables = [i for i in report.insights if i.category == "mutable_default"]
        self.assertEqual(len(mutables), 1)
        self.assertIn("Mutable default argument", mutables[0].message)

    def test_detect_global_usage(self) -> None:
        code = """
count = 0
def increment():
    global count
    count += 1
"""
        report = analyse_source(code)
        globals_found = [i for i in report.insights if i.category == "global_usage"]
        self.assertEqual(len(globals_found), 1)

    def test_parse_traceback_multiframe(self) -> None:
        sample_traceback = """Traceback (most recent call last):
  File "main.py", line 12, in <module>
    run_service()
  File "service.py", line 45, in run_service
    process_data(data)
  File "processor.py", line 88, in process_data
    raise TypeError("unsupported operand type(s) for +: 'int' and 'str'")
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""
        frames = parse_traceback(sample_traceback)
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0].filename, "main.py")
        self.assertEqual(frames[0].lineno, 12)
        self.assertEqual(frames[0].function_name, "<module>")
        self.assertEqual(frames[2].filename, "processor.py")
        self.assertEqual(frames[2].lineno, 88)
        self.assertEqual(frames[2].function_name, "process_data")

    def test_extract_error_type(self) -> None:
        tb = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
ZeroDivisionError: division by zero
"""
        err_type, msg = extract_error_type(tb)
        self.assertEqual(err_type, "ZeroDivisionError")
        self.assertEqual(msg, "division by zero")

    def test_get_function_source(self) -> None:
        module_code = '''
def alpha():
    return 1

def beta(x: int):
    """Docstring."""
    return x * 2

def gamma():
    return 3
'''
        source = get_function_source(module_code, "beta")
        self.assertIsNotNone(source)
        assert source is not None
        self.assertIn("def beta(x: int):", source)
        self.assertIn("return x * 2", source)
        self.assertNotIn("def gamma", source)


if __name__ == "__main__":
    unittest.main()
