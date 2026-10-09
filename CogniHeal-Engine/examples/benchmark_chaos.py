"""Chaos Benchmark — Deliberately broken code scenarios.

This module defines a collection of intentionally buggy Python code
snippets that stress-test CogniHeal's self-healing pipeline.  Each
scenario targets a specific class of runtime error:

- Type mismatches and attribute errors
- Missing / broken imports
- Async race conditions and concurrency bugs
- Circular dependency simulations
- Index and key errors
- Infinite recursion and stack overflows
- Resource handling failures

The scenarios are consumed by ``cogniheal benchmark`` and by the
``HealingOrchestrator`` to demonstrate autonomous error recovery.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ChaosScenario(TypedDict):
    """Schema for a single chaos benchmark scenario."""

    name: str
    description: str
    code: str


# ──────────────────────────────────────────────────────────────────
# Scenario definitions
# ──────────────────────────────────────────────────────────────────

CHAOS_SCENARIOS: list[ChaosScenario] = [
    # 1 ── TypeError: wrong argument types
    {
        "name": "Type Mismatch Arithmetic",
        "description": (
            "Perform arithmetic between incompatible types (str + int). "
            "The agent must detect the TypeError and cast correctly."
        ),
        "code": '''\ndef calculate_total(prices: list) -> float:
    """Sum a list of prices that may contain strings."""\n    total = 0
    for p in prices:
        total = total + p  # bug: some items are strings
    return total

result = calculate_total([10, "20", 30, "40.5", 50])
print(f"Total: {result}")
''',
    },
    # 2 ── ModuleNotFoundError: missing package
    {
        "name": "Missing Package Import",
        "description": (
            "Import a non-existent package 'supercalc'. "
            "The agent must remove or replace the broken import."
        ),
        "code": '''\nimport supercalc  # This package does not exist

def compute(a: int, b: int) -> int:
    """Use supercalc to add two numbers."""\n    return supercalc.add(a, b)

print(compute(3, 7))
''',
    },
    # 3 ── IndexError: list index out of range
    {
        "name": "Off-by-One Index Error",
        "description": (
            "Access a list element beyond its bounds. "
            "The agent must fix the loop boundary."
        ),
        "code": '''\ndef get_pairs(items: list) -> list:
    """Return consecutive pairs from the list."""\n    pairs = []
    for i in range(len(items)):
        pairs.append((items[i], items[i + 1]))  # bug: off by one
    return pairs

data = [1, 2, 3, 4, 5]
print(get_pairs(data))
''',
    },
    # 4 ── KeyError: missing dictionary key
    {
        "name": "Missing Dictionary Key",
        "description": (
            "Access a non-existent key in a dictionary without a default. "
            "The agent must use .get() or add the key."
        ),
        "code": '''\ndef extract_email(user: dict) -> str:
    """Extract email from a user profile dict."""\n    return user["email"]  # bug: key might not exist

profile = {"name": "Alice", "age": 30}
print(extract_email(profile))
''',
    },
    # 5 ── RecursionError: infinite recursion
    {
        "name": "Infinite Recursion",
        "description": (
            "Recursive function without a proper base case. "
            "The agent must add a termination condition."
        ),
        "code": '''\ndef factorial(n: int) -> int:
    """Calculate factorial recursively."""\n    return n * factorial(n - 1)  # bug: no base case

print(factorial(5))
''',
    },
    # 6 ── AttributeError: wrong method name
    {
        "name": "Attribute Error on String",
        "description": (
            "Call a non-existent method on a string object. "
            "The agent must use the correct method name."
        ),
        "code": '''\ndef clean_text(text: str) -> str:
    """Remove leading/trailing whitespace and convert to lowercase."""\n    cleaned = text.trimmed()  # bug: should be strip()
    return cleaned.lower()

result = clean_text("  Hello World  ")
print(result)
''',
    },
    # 7 ── ValueError: invalid literal for int()
    {
        "name": "Invalid String to Int Conversion",
        "description": (
            "Convert a non-numeric string to int without validation. "
            "The agent must add error handling or validation."
        ),
        "code": '''\ndef parse_ages(raw_ages: list) -> list:
    """Parse a list of string ages into integers."""\n    return [int(age) for age in raw_ages]  # bug: 'unknown' is not a number

ages = ["25", "30", "unknown", "45", "N/A"]
print(parse_ages(ages))
''',
    },
    # 8 ── Async race condition (simulated)
    {
        "name": "Async Race Condition",
        "description": (
            "Simulate a race condition with shared mutable state in "
            "concurrent threads. The agent must add proper synchronisation."
        ),
        "code": '''\nimport threading
import time

counter = 0

def increment():
    global counter
    for _ in range(100000):
        temp = counter
        time.sleep(0)  # force context switch
        counter = temp + 1

threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

expected = 400000
if counter != expected:
    raise RuntimeError(
        f"Race condition detected! Expected {expected}, got {counter}"
    )
print(f"Counter: {counter}")
''',
    },
    # 9 ── ZeroDivisionError
    {
        "name": "Division by Zero",
        "description": (
            "Divide by zero in a statistics calculation. "
            "The agent must add a guard clause."
        ),
        "code": '''\ndef average(numbers: list) -> float:
    """Calculate the arithmetic mean of a list."""\n    return sum(numbers) / len(numbers)  # bug: empty list

print(average([]))
''',
    },
    # 10 ── FileNotFoundError
    {
        "name": "File Not Found",
        "description": (
            "Read from a non-existent file without checking existence. "
            "The agent must handle the missing file gracefully."
        ),
        "code": '''\ndef read_config() -> dict:
    """Read configuration from a JSON file."""\n    import json
    with open("nonexistent_config_42.json", "r") as f:
        return json.load(f)

config = read_config()
print(config)
''',
    },
    # 11 ── UnboundLocalError
    {
        "name": "Unbound Local Variable",
        "description": (
            "Reference a variable before assignment inside a function. "
            "The agent must fix the variable scoping."
        ),
        "code": '''\ndef process_data(items: list) -> str:
    """Process items and return a status message."""\n    for item in items:
        if item > 10:
            result = "found large item"
    return result  # bug: result may never be assigned

print(process_data([1, 2, 3]))
''',
    },
    # 12 ── Mutable default argument
    {
        "name": "Mutable Default Argument",
        "description": (
            "Use a mutable list as a default argument, causing state "
            "leakage across calls. The agent must use None + guard."
        ),
        "code": '''\ndef append_to(element, target=[]):  # bug: mutable default
    """Append element to target list and return it."""\n    target.append(element)
    return target

print(append_to(1))
print(append_to(2))
print(append_to(3))
# Expected: [1], [2], [3]
# Actual:   [1], [1,2], [1,2,3]

a = append_to(1)
b = append_to(2)
if a == b:
    raise RuntimeError(
        f"Mutable default bug! a={a}, b={b} — they should be independent"
    )
print(f"a={a}, b={b}")
''',
    },
]


def get_scenario_by_name(name: str) -> ChaosScenario | None:
    """Look up a scenario by its name (case-insensitive).

    Args:
        name: The scenario name to search for.

    Returns:
        The matching ``ChaosScenario`` or ``None``.
    """
    lower = name.lower()
    for s in CHAOS_SCENARIOS:
        if s["name"].lower() == lower:
            return s
    return None


def list_scenario_names() -> list[str]:
    """Return the names of all available scenarios.

    Returns:
        A list of scenario name strings.
    """
    return [s["name"] for s in CHAOS_SCENARIOS]


if __name__ == "__main__":
    print(f"Available chaos scenarios ({len(CHAOS_SCENARIOS)}):")
    for i, s in enumerate(CHAOS_SCENARIOS, 1):
        print(f"  {i:2d}. {s['name']}")
