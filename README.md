<div align="center">

# 🧠 CogniHeal-Engine

### *Self-Reflective Dynamic Episodic Memory & Autonomous Self-Healing Agent Engine*

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Tests Status](https://img.shields.io/badge/tests-16%20passed-brightgreen.svg?logo=pytest&logoColor=white)](tests/)
[![Architecture](https://img.shields.io/badge/architecture-Reflexion%20%2B%20ChromaDB%20%2B%20SQLite-purple.svg)](#-system-architecture)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Type Checking](https://img.shields.io/badge/type%20hints-100%25%20strict-blueviolet.svg)](cogniheal/)
[![Docker Ready](https://img.shields.io/badge/docker-sandboxed-2496ED.svg?logo=docker&logoColor=white)](#-sandbox-execution-subsystem)

*A production-grade, self-reflective autonomic AI architecture that intercepts runtime exceptions, performs multi-stage AST & log root cause analysis (RCA), persists error-fix-constraint quadruplets across a hybrid ChromaDB/SQLite memory substrate, and autonomously repairs code failures without human intervention.*

---

[Key Features](#-key-features) •
[System Architecture](#-system-architecture) •
[Execution State Machine](#-autonomous-self-healing-state-machine) •
[Mathematical Foundations](#-mathematical--algorithmic-formulation) •
[Quickstart](#-installation--quickstart) •
[CLI Reference](#-rich-terminal-interface-cli) •
[Python SDK](#-python-sdk--programmatic-usage) •
[Memory Subsystem](#-episodic-memory-subsystem-hybrid-chromadb--sqlite) •
[Chaos Benchmark](#-chaos-benchmark-suite) •
[Security Model](#-sandbox-security--threat-model) •
[Configuration](#-configuration-matrix) •
[Roadmap & Citations](#-citations--academic-references)

---

</div>

## 📌 Executive Summary & Paradigm Shift

Modern Large Language Model (LLM) coding agents (e.g. sweepers, autonomous software engineers, execution bots) suffer from three critical architectural flaws:

1. **Episodic Amnesia**: When an LLM generates code that crashes, it typically retries in-context. Once the session ends, that experience vanishes. When confronted with an identical edge case days later, the model repeats the exact same fatal mistake.
2. **Superficial Textual Debugging**: Standard agentic loops feed raw stderr back into the prompt without semantic decomposition. They fail to distinguish between syntax anomalies, concurrency deadlocks, and silent logic state leakage (e.g. mutable default arguments).
3. **Absence of Negative Invariant Enforcement**: Models are rarely taught *what NEVER to do again*. Without explicit hard negative constraints, LLMs alternate between two broken implementations in an infinite oscillation.

**CogniHeal-Engine** solves this by establishing a **closed-loop episodic memory and verbal reinforcement engine**. Inspired by cognitive psychology (Tulving's Episodic Memory Theory) and advanced agent reflection (Noah Shinn's *Reflexion* framework), CogniHeal parses runtime traces using Abstract Syntax Trees (AST), produces structured Root Cause Analysis (RCA), derives permanent **Hard Constraint Rules**, and queries past error memories via dense vector retrieval *before code is even generated*.

---

## 🚀 Key Features

- **Dynamic AST & Traceback Decompiler (`engine/ast_analyzer.py`)**:
  - Full structural inspection using Python's native `ast` module.
  - Heuristic anti-pattern interceptors for bare `except:` clauses, mutable default arguments, uncontrolled `global` mutations, and wildcard imports (`from x import *`).
  - Multi-frame stack traceback parser reconstructing caller chains down to line, column, and symbol context.

- **Dual-Tier Hybrid Episodic Memory (`memory/episodic_engine.py`)**:
  - **Vector Tier (ChromaDB)**: 1536-dimensional HNSW cosine index storing semantic error signatures for sub-millisecond similarity recall.
  - **Relational Tier (SQLite WAL)**: ACID-compliant persistence with foreign-key integrity, transactional consistency, and an SQLite FTS5 full-text search index for keyword queries.
  - Offline fallback: Built-in deterministic SHA-256 pseudo-embedding engine allowing full zero-dependency testing without an OpenAI API key.

- **Reflexion & Critique-and-Refine Loop (`engine/reflection.py`)**:
  - Formal implementation of the *Reflexion* architecture (Shinn et al., 2023).
  - Enforces structured Chain-of-Thought reasoning, brutal self-critique, root-cause decomposition, patch generation, and invariant hard-constraint derivation validated via Pydantic v2.

- **Defense-in-Depth Sandbox Execution (`sandbox/executor.py`)**:
  - **Subprocess Isolation**: Process jail with sanitized environment variables, strict timeouts, non-blocking asynchronous output capture, and memory cleanups.
  - **Docker Isolation**: Disposable, network-disconnected (`--network=none`), memory-capped (`256MB`), single-core container execution for untrusted multi-tenant code.

- **Autonomous Orchestration Agent (`agent/orchestrator.py`)**:
  - Pre-execution memory scan: injects semantically similar historical failures as `"Past Lessons Learned"` and `"Active Hard Constraints"` into system prompts.
  - Adaptive feedback loop: runs up to $N$ self-healing iterations until standard exit code 0 is achieved or budget is exhausted.
  - Automatic episodic record persistence upon resolution.

- **Terminal Telemetry & Rich UI (`cli.py`)**:
  - Beautiful command-line interface featuring animated spinners, real-time stage panels, syntax-highlighted code viewers, execution statistics, and UTF-8 safe Windows console encoding.

---

## 🏗️ System Architecture

The following ASCII diagram illustrates the internal dataflow across all five subsystem layers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   USER / CLI LAYER                                     │
│            cogniheal run --task "..."  │  cogniheal benchmark  │  cogniheal memory     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         AUTONOMOUS ORCHESTRATOR LAYER                                  │
│                          (cogniheal/agent/orchestrator.py)                             │
│                                                                                        │
│  1. Memory Scan Request        2. Enriched Prompt Gen          3. Subprocess Dispatch  │
│  ┌───────────────────────┐    ┌───────────────────────┐       ┌──────────────────────┐ │
│  │ Semantic Query Engine │───▶│ Prompt Injector       │──────▶│ Sandbox Controller   │ │
│  │ (Task & Error Vector) │    │ Lessons + Constraints │       │ Timeout & Env limits │ │
│  └───────────────────────┘    └───────────────────────┘       └──────────┬───────────┘ │
└───────────────▲──────────────────────────────────────────────────────────┼─────────────┘
                │                                                          │
                │ Vector Recall                                            │ Dispatch Code
                │ & Constraints                                            ▼
┌───────────────┴──────────────────────────────────────┐  ┌──────────────────────────────┐
│           EPISODIC MEMORY ENGINE                     │  │    EXECUTION SANDBOX         │
│       (cogniheal/memory/episodic_engine.py)          │  │ (cogniheal/sandbox/          │
│                                                      │  │         executor.py)         │
│  ┌──────────────────┐      ┌──────────────────────┐  │  │                              │
│  │ ChromaDB HNSW    │      │ SQLite WAL DB        │  │  │  ┌────────────────────────┐  │
│  │ Vector Store     │◀────▶│ Relational Storage   │  │  │  │ Subprocess / Docker    │  │
│  │ (Cosine Metric)  │      │ + FTS5 Full-Text     │  │  │  │ Isolation Boundary     │  │
│  │ 1536-dim Embed   │      │ Episodic Records     │  │  │  └───────────┬────────────┘  │
│  └──────────────────┘      └──────────────────────┘  │  └──────────────┼───────────────┘
│                 ▲                                    │                 │
│                 │ Upsert Episode                     │                 │ Exit Code &
│                 │ (Vector + Metadata)                │                 │ Raw Traceback
│                 │                                    │                 ▼
│  ┌──────────────┴────────────────────────────────────┴──┐      ┌───────────────────────┐
│  │                 REFLECTION & RCA LAYER               │◀─────│  Execution Failure    │
│  │         (cogniheal/engine/reflection.py & rca.py)    │      │  (exit_code != 0)     │
│  │                                                      │      └───────────────────────┘
│  │  • AST Static Tree Parsing (Anti-patterns & Frames)  │
│  │  • Root Cause Analysis (Taxonomy & Causal Chain)     │
│  │  • Reflexion Self-Critique & Chain-of-Thought        │
│  │  • Patch Synthesis & Invariant Rule Derivation       │
│  └──────────────────────────────────────────────────────┘
```

---

## 🔄 Autonomous Self-Healing State Machine

```
              ┌──────────────────────────────┐
              │          INITIALIZE          │
              │  Task Prompt / Source File   │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │      STAGE 1: MEMORY SCAN    │
              │   Cosine similarity query    │
              │   Fetch active constraints   │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │    STAGE 2: PROMPT SYNTHESIS │
              │   Inject: Lessons Learned    │
              │   Inject: Hard Constraints   │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
       ┌─────▶│    STAGE 3: CODE EXECUTION   │
       │      │   Subprocess / Docker Jail   │
       │      └──────────────┬───────────────┘
       │                     │
       │            Is Exit Code == 0?
       │             /               \
       │         YES/                 \NO
       │           ▼                   ▼
       │  ┌─────────────────┐  ┌─────────────────────────────────┐
       │  │  STATE: SUCCESS │  │   STAGE 4: AST & RCA PARSING    │
       │  │  Return Result  │  │   Parse frames, locate symbols  │
       │  └────────┬────────┘  │   Static anti-pattern analysis  │
       │           │           └──────────────┬──────────────────┘
       │           │                          │
       │           │                          ▼
       │           │           ┌─────────────────────────────────┐
       │           │           │   STAGE 5: REFLEXION ENGINE     │
       │           │           │   Chain-of-Thought Self-Critique│
       │           │           │   Formulate patch + constraint  │
       │           │           └──────────────┬──────────────────┘
       │           │                          │
       │           │           Iter < MaxIter?
       │           │            /            \
       │           │        YES/              \NO
       │           │          ▼                ▼
       │      Apply Patch to Code    ┌───────────────────────────┐
       │      Record Rule Candidate  │  STATE: BUDGET EXHAUSTED  │
       │      Iter = Iter + 1        │  Mark episode unsuccessful│
       │           │                 └─────────┬─────────────────┘
       │           │                           │
       │           └────────────┬──────────────┘
       │                        │
       │                        ▼
       │      ┌───────────────────────────────────┐
       │      │     STAGE 6: MEMORY UPSERT        │
       │      │  Vectorize Error & Solution       │
       │      │  Write to ChromaDB & SQLite       │
       │      └─────────────────┬─────────────────┘
       │                        │
       │                        ▼
       └──────────────────  TERMINATE
```

---

## 📐 Mathematical & Algorithmic Formulation

### 1. Semantic Error Vectorization & Cosine Similarity

Let an error episode $\mathcal{E}$ be mapped to a composite semantic textual representation $\mathcal{T}(\mathcal{E})$:

$$\mathcal{T}(\mathcal{E}) = \text{Summary}(\mathcal{RCA}) \parallel \text{Category} \parallel \bigoplus_{i=1}^k \text{CausalNode}_i \parallel \text{FixDescription} \parallel \text{Constraint}$$

The semantic embedding vector $\mathbf{v}_{\mathcal{E}} \in \mathbb{R}^d$ ($d = 1536$ for `text-embedding-3-small`) is generated via:

$$\mathbf{v}_{\mathcal{E}} = \frac{f_{\text{embed}}(\mathcal{T}(\mathcal{E}))}{\|f_{\text{embed}}(\mathcal{T}(\mathcal{E}))\|_2}$$

Given a runtime failure or incoming task query $\mathbf{q} \in \mathbb{R}^d$, the nearest historical episodes in the vector space $\mathcal{V}$ are retrieved according to the Cosine Metric $\mathcal{S}_{\cos}$:

$$\mathcal{S}_{\cos}(\mathbf{q}, \mathbf{v}_{\mathcal{E}}) = \frac{\mathbf{q} \cdot \mathbf{v}_{\mathcal{E}}}{\|\mathbf{q}\|_2 \|\mathbf{v}_{\mathcal{E}}\|_2}$$

Episodes are filtered subject to the similarity threshold parameter $\tau$:

$$\mathcal{M}_{\text{recalled}} = \left\{ \mathcal{E} \in \mathcal{V} \;\middle|\; \mathcal{S}_{\cos}(\mathbf{q}, \mathbf{v}_{\mathcal{E}}) \ge \tau \right\}, \quad \text{where } \tau = 0.78$$

### 2. Reflexion Verbal Reinforcement Formulation

Following Shinn et al. (2023), CogniHeal defines the optimization of the agent policy $\pi_\theta$ over iterative episodes $t \in \{1, \dots, N\}$. Rather than scalar gradient updates, the policy is conditioned on an expanding verbal buffer of semantic memories $\mathcal{H}_t$:

$$\mathcal{H}_t = \mathcal{H}_{t-1} \cup \left\{ \left( c_{t-1}, e_{t-1}, \mathcal{R}_{t-1}, \mathcal{K}_{t-1} \right) \right\}$$

Where:
- $c_{t-1}$: Candidate source code at iteration $t-1$.
- $e_{t-1}$: Execution output (stderr / traceback).
- $\mathcal{R}_{t-1} = \text{Reflexion}\left(c_{t-1}, e_{t-1}, \mathcal{H}_{t-1}\right)$: Structured critique and chain-of-thought.
- $\mathcal{K}_{t-1}$: Derived invariant hard constraint rule.

The code generator synthesizes the next candidate patch $c_t$:

$$c_t \sim \pi_\theta\left( \cdot \;\middle|\; \text{Prompt}, \mathcal{H}_t, \bigcup \mathcal{K} \right)$$

---

## 📦 Installation & Quickstart

### System Requirements

- **Python**: `>= 3.11` (Tested on 3.11 and 3.12)
- **OS**: Windows 10/11, macOS (Apple Silicon / Intel), or Linux (Ubuntu 22.04+)
- **Optional**: Docker daemon running (if using `--sandbox-mode docker`)

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/EvoderDev/CogniHeal-Engine.git
cd CogniHeal-Engine

# Create and activate virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Install CogniHeal in editable development mode (registers global commands: cogni, cg, cogniheal)
pip install -e .
```

> [!TIP]
> Once installed with `pip install -e .`, the executables `cogni` and `cg` are automatically registered in your global system PATH! You can simply type `cogni` or `cg` anywhere in your terminal to launch the interactive REPL.

### 2. Environment Configuration

Create a `.env` file in the project root (or set system environment variables):

```env
# Optional: OpenAI API Key for deep LLM reasoning and OpenAI embeddings
# (If omitted, CogniHeal automatically falls back to its deterministic pseudo-embedding and heuristic rule engine)
COGNIHEAL_OPENAI_API_KEY=sk-proj-your-api-key-here

# LLM Tunables
COGNIHEAL_LLM_MODEL=gpt-4o
COGNIHEAL_EMBEDDING_MODEL=text-embedding-3-small
COGNIHEAL_LLM_TEMPERATURE=0.2

# Self-Healing Bounds
COGNIHEAL_MAX_HEAL_ITERATIONS=5
COGNIHEAL_SIMILARITY_THRESHOLD=0.78
COGNIHEAL_TOP_K_MEMORIES=5

# Sandbox Security
COGNIHEAL_SANDBOX_MODE=subprocess
COGNIHEAL_SANDBOX_TIMEOUT_SECONDS=30
```

---

## 💻 Interactive Agent REPL & CLI Reference

CogniHeal provides an interactive REPL modeled after modern autonomous coding tools, equipped with a persistent session context, live status spinners, and memory querying.

### 1. Launching the Interactive REPL

Type either of the global commands directly in your terminal:

```bash
cogni       # Full brand command
# or:
cg          # Ultra-fast short alias
# or:
cogniheal   # Canonical package entrypoint
```

In the interactive REPL, the session stays active continuously across multiple turns without exiting:

- **Natural Language Tasks**: Simply type what you want to build or fix (`Write a thread-safe LRU cache with TTL`).
- **Live Status Spinners**: Watch the agent scan past error memories, run code in the sandbox, and perform Reflexion critique.
- **Context Preservation**: The agent remembers previous turns, past code iterations, and prior fixes throughout the entire session.
- **Built-in Slash Commands**:
  - `/load <path>` — Load a Python file into active session memory
  - `/memory` — View recently stored episodic error memories
  - `/search <query>` — Dense semantic search across historical errors
  - `/stats` — View SQLite and ChromaDB persistence statistics
  - `/constraints` — List active hard constraint rules
  - `/history` — Review current session conversational turns
  - `/reset` — Clear current conversation context
  - `/benchmark` — Execute the 12-scenario chaos benchmark
  - `/clear` — Clear terminal screen
  - `/exit` — End the session gracefully

### 2. Autonomous Self-Healing on a File (Non-Interactive Batch Mode)

Run self-healing on a Python file that fails at runtime:

```bash
cogniheal run --code-file examples/sample_fix.py
```

```
   ____                  _ _   _            _
  / ___|___   __ _ _ __ (_) | | | ___  __ _| |
 | |   / _ \ / _` | '_ \| | |_| |/ _ \/ _` | |
 | |__| (_) | (_| | | | | |  _  |  __/ (_| | |
  \____\___/ \__, |_| |_|_|_| |_|\___|\__,_|_|
             |___/
  ── Self-Reflective Dynamic Episodic Memory Engine ──

╭────────────────────────── 📄 Source: sample_fix.py ──────────────────────────╮
│ 1 import nonexistent_secret_package                                          │
│ 2 def calculate(): return 42                                                 │
│ 3 print(calculate())                                                         │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────── ⚡ EXECUTE (iter 1) ──────────────────────────╮
│ Executing code (attempt 1/5)…                                                │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────── 🔍 REFLECT (iter 1) ──────────────────────────╮
│ ❌ Execution failed. Running Reflexion analysis…                             │
│   stderr: ModuleNotFoundError: No module named 'nonexistent_secret_package'   │
╰──────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────── 🔧 FIX (iter 1) ───────────────────────────╮
│ 🔧 Applying fix (confidence: 30%)                                            │
│    Constraint: Always handle import_error errors explicitly.                 │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────── ⚡ EXECUTE (iter 2) ──────────────────────────╮
│ Executing code (attempt 2/5)…                                                │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────── ✅ SUCCESS (iter 2) ─────────────────────────╮
│ ✅ Code executed successfully on attempt 2!                                  │
│   stdout: 42                                                                 │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### 2. Autonomous Task Execution from Natural Language

```bash
cogniheal run --task "Write a thread-safe singleton cache with TTL expiration"
```

### 3. Episodic Memory Inspection

Inspect the contents of the hybrid SQLite + ChromaDB memory store:

```bash
# Print high-level memory statistics
cogniheal memory stats

# List recent error episodes
cogniheal memory list --limit 10

# Perform dense semantic vector search
cogniheal memory search "IndexError list index out of range in loop"

# Display all active hard negative constraint rules
cogniheal memory constraints
```

### 4. Running the Chaos Benchmark Suite

Execute the built-in stress test against all 12 deliberate bug patterns:

```bash
cogniheal benchmark --max-iterations 5
```

---

## 🐍 Python SDK & Programmatic Usage

Integrate CogniHeal-Engine directly into your existing agent pipelines, testing frameworks, or LLM evaluation harnesses:

```python
from pathlib import Path
from cogniheal.config import settings
from cogniheal.memory.episodic_engine import EpisodicMemoryEngine
from cogniheal.agent.orchestrator import HealingOrchestrator, HealCycleEvent

# 1. Initialize the episodic memory substrate
settings.ensure_dirs()
memory = EpisodicMemoryEngine()
memory.initialise()

# 2. Define an event listener for live UI or logging
def telemetry_listener(event: HealCycleEvent) -> None:
    print(f"[{event.stage.upper()}] Iteration {event.iteration}: {event.message}")

# 3. Instantiate the orchestrator
orchestrator = HealingOrchestrator(
    memory_engine=memory,
    max_iterations=5,
    on_event=telemetry_listener,
)

# 4. Execute self-healing on buggy code
buggy_snippet = """
def parse_records(raw_data: list[dict]) -> float:
    # Bug: missing key and potential zero division
    total = sum(item["metric"] for item in raw_data)
    return total / len(raw_data)

print(parse_records([]))
"""

result = orchestrator.run(
    task_prompt="Safely parse and average metrics from dictionary list",
    initial_code=buggy_snippet,
)

# 5. Access structured outputs
print(f"Heal Succeeded: {result.success}")
print(f"Total Iterations: {result.total_iterations}")
print(f"Final Sanitized Code:\n{result.final_code}")
print(f"Stdout:\n{result.final_result.stdout}")

# 6. Query memory for lessons stored from this run
related_episodes = memory.query("zero division in parse_records", top_k=1)
for ep in related_episodes:
    print(f"Learned Rule: {ep.hard_constraint.description}")

memory.close()
```

---

## 💾 Episodic Memory Subsystem (Hybrid ChromaDB + SQLite)

CogniHeal combines the best of **Vector Databases** (associative semantic recall) and **Relational ACID Databases** (exact relational queries and auditability).

### Relational Schema Specification (SQLite)

```sql
-- Main episodic records table
CREATE TABLE IF NOT EXISTS episodes (
    episode_id        TEXT PRIMARY KEY,
    timestamp         TEXT NOT NULL,
    original_code     TEXT NOT NULL,
    task_prompt       TEXT NOT NULL DEFAULT '',
    raw_error         TEXT NOT NULL,
    stack_frames_json TEXT NOT NULL DEFAULT '[]',
    rca_json          TEXT NOT NULL,
    reflection        TEXT NOT NULL DEFAULT '',
    fix_json          TEXT NOT NULL,
    constraint_json   TEXT NOT NULL,
    tags_json         TEXT NOT NULL DEFAULT '[]',
    success           INTEGER NOT NULL DEFAULT 0,
    total_iterations  INTEGER NOT NULL DEFAULT 1
);

-- Normalized table for fast constraint queries
CREATE TABLE IF NOT EXISTS hard_constraints (
    rule_id      TEXT PRIMARY KEY,
    episode_id   TEXT NOT NULL,
    description  TEXT NOT NULL,
    code_pattern TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id) ON DELETE CASCADE
);

-- SQLite Full-Text Search (FTS5) index for rapid exact keyword matching
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
USING fts5(episode_id, raw_error, rca_summary, fix_description);
```

### Vector Collection Metadata Schema (ChromaDB)

- **Collection Name**: `cogniheal_episodes`
- **Distance Metric**: `Cosine`
- **Document Payload**:
  ```text
  Error: <RCA Summary>
  Category: <syntax_error | type_error | runtime_error | import_error | logic_error | ...>
  Root cause chain: <Cause Step 1> -> <Cause Step 2>
  Fix: <Applied Patch Description>
  Constraint: <Hard Negative Rule>
  ```
- **Metadata Attributes**:
  - `category`: Taxonomy string
  - `severity`: `low | medium | high | critical`
  - `success`: `"True" | "False"`
  - `timestamp`: ISO-8601 string

---

## 💥 Chaos Benchmark Suite

Located at [`examples/benchmark_chaos.py`](examples/benchmark_chaos.py), this test suite includes 12 deliberate, real-world runtime anomalies designed to stress-test every facet of CogniHeal:

| # | Scenario Title | Primary Failure | Root Cause Mechanism | Verification Condition |
|---|---|---|---|---|
| **01** | **Type Mismatch Arithmetic** | `TypeError` | Concatenating string literal to integer accumulator | Numbers parsed to float, correct sum |
| **02** | **Missing Package Import** | `ModuleNotFoundError` | Attempting to import non-existent package `supercalc` | Import eliminated or gracefully handled |
| **03** | **Off-by-One Index Error** | `IndexError` | Loop access `items[i + 1]` exceeding bounds | Array bound clamped to `len(items) - 1` |
| **04** | **Missing Dictionary Key** | `KeyError` | Direct key subscript on sparse dictionary | Safe retrieval via `.get()` or key validation |
| **05** | **Infinite Recursion** | `RecursionError` | Missing base-case condition in recursive factorial | Guard clause `if n <= 1: return 1` added |
| **06** | **Attribute Error on String** | `AttributeError` | Calling non-existent method `.trimmed()` on string | Correct method `.strip()` invoked |
| **07** | **Invalid String to Int** | `ValueError` | `int("unknown")` type conversion exception | Numeric validation with try-except fallback |
| **08** | **Async Race Condition** | `RuntimeError` | Multi-threaded shared counter corruption without lock | Threading lock `threading.Lock()` synchronisation |
| **09** | **Division by Zero** | `ZeroDivisionError` | Empty array passed into arithmetic average | Non-empty denominator validation check |
| **10** | **File Not Found** | `FileNotFoundError` | Opening non-existent configuration file path | `Path.exists()` check or fallback defaults |
| **11** | **Unbound Local Variable** | `UnboundLocalError` | Variable referenced before conditional assignment | Default variable initialisation before loop |
| **12** | **Mutable Default Argument** | `RuntimeError` | `def f(x, target=[])` state leakage across calls | Default set to `None` with internal list allocation |

---

## 🛡️ Sandbox Security & Threat Model

Running LLM-generated code poses severe host security risks. CogniHeal enforces a multi-tier defense-in-depth model:

```
┌─────────────────────────────────────────────────────────────┐
│                 HOST OPERATING SYSTEM                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │               COGNIHEAL APPLICATION                   │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │          SANDBOX CONTROLLER (executor.py)       │  │  │
│  │  │                                                 │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │  MODE: SUBPROCESS                         │  │  │  │
│  │  │  │  • Stripped Environment (Path/System only)│  │  │  │
│  │  │  │  • Process Group Timeout Kill             │  │  │  │
│  │  │  │  • Ephemeral Temp Directory Disposal      │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │  MODE: DOCKER CONTAINER                   │  │  │  │
│  │  │  │  • --network=none (Full Network Airgap)  │  │  │  │
│  │  │  │  • --memory=256m (OOM Protection)         │  │  │  │
│  │  │  │  • --cpus=1 (CPU Starvation Prevention)   │  │  │  │
│  │  │  │  • --pids-limit=64 (Fork Bomb Prevention) │  │  │  │
│  │  │  │  • Read-Only Volume Mount (/sandbox:ro)   │  │  │  │
│  │  │  │  • Ephemeral Container Auto-Cleanup (--rm)│  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

1. **Environment Sanitization**: When using `subprocess`, all credentials, API tokens, and secret environment variables (`AWS_*`, `OPENAI_*`, `GITHUB_*`) are stripped.
2. **Network Airgapping**: In Docker mode, containers execute with `--network=none`, completely preventing socket creation, data exfiltration, or botnet staging.
3. **Resource Capping**: Hard resource ceilings (256MB RAM, 1 CPU, 64 PIDs) eliminate denial-of-service vectors like fork bombs (`while True: os.fork()`) or infinite memory allocations.
4. **Deterministic Timeouts**: Every execution is strictly governed by `sandbox_timeout_seconds` (default: 30s). Rogue threads or infinite loops are forcefully terminated with `SIGKILL`.

---

## ⚙️ Configuration Matrix

All configuration keys can be supplied via environment variables prefixed with `COGNIHEAL_` or via a `.env` file:

| Environment Variable | Python Type | Default Value | Validation Constraints | Functional Description |
|---|---|---|---|---|
| `COGNIHEAL_OPENAI_API_KEY` | `str` | `""` | Optional | OpenAI API key for LLM reflection and embeddings |
| `COGNIHEAL_LLM_MODEL` | `str` | `"gpt-4o"` | Valid Model ID | LLM model for critique, reflection, and code generation |
| `COGNIHEAL_EMBEDDING_MODEL` | `str` | `"text-embedding-3-small"`| Valid Model ID | Model used for semantic error vector generation |
| `COGNIHEAL_LLM_TEMPERATURE` | `float` | `0.2` | $0.0 \le T \le 2.0$ | Sampling temperature for reflection synthesis |
| `COGNIHEAL_LLM_MAX_TOKENS` | `int` | `4096` | $\ge 256$ | Maximum token output limit for LLM responses |
| `COGNIHEAL_MAX_HEAL_ITERATIONS`| `int` | `5` | $1 \le N \le 20$ | Maximum self-healing loops before giving up |
| `COGNIHEAL_SIMILARITY_THRESHOLD`|`float`| `0.78` | $0.0 \le \tau \le 1.0$ | Minimum cosine similarity to inject past memories |
| `COGNIHEAL_TOP_K_MEMORIES` | `int` | `5` | $\ge 1$ | Maximum number of episodic memories injected per prompt |
| `COGNIHEAL_SANDBOX_MODE` | `str` | `"subprocess"` | `"subprocess" \| "docker"`| Code execution backend |
| `COGNIHEAL_SANDBOX_TIMEOUT_SECONDS`| `int` | `30` | $\ge 5$ | Hard wall-clock execution timeout in seconds |
| `COGNIHEAL_DOCKER_IMAGE` | `str` | `"python:3.12-slim"`| Valid Docker tag | Base image used when Docker sandbox mode is active |
| `COGNIHEAL_DATA_DIR` | `Path` | `"cogniheal_data"` | Path string | Base directory for SQLite and ChromaDB data |
| `COGNIHEAL_SQLITE_FILENAME` | `str` | `"episodic_memory.db"`| File name | SQLite database file name |
| `COGNIHEAL_CHROMA_COLLECTION_NAME`| `str` | `"cogniheal_episodes"`| Alphanumeric string | ChromaDB collection name |
| `COGNIHEAL_LOG_LEVEL` | `str` | `"INFO"` | `"DEBUG" \| "INFO" \| "WARNING"` | CLI and internal logger verbosity |

---

## 🧪 Test Suite & Quality Verification

CogniHeal maintains a comprehensive, zero-dependency unit test suite compatible with both `unittest` and `pytest`.

```bash
# Run tests with Python standard library runner:
python -m unittest discover -s tests -v

# Or run with pytest (if installed):
pytest tests/ -v --cov=cogniheal
```

### Test Coverage Summary:

```
test_analyse_source_syntax_error (test_ast_analyzer.TestASTAnalyzer)               ... ok
test_analyse_source_valid_ast (test_ast_analyzer.TestASTAnalyzer)                  ... ok
test_detect_bare_except (test_ast_analyzer.TestASTAnalyzer)                        ... ok
test_detect_global_usage (test_ast_analyzer.TestASTAnalyzer)                       ... ok
test_detect_mutable_default (test_ast_analyzer.TestASTAnalyzer)                    ... ok
test_extract_error_type (test_ast_analyzer.TestASTAnalyzer)                        ... ok
test_get_function_source (test_ast_analyzer.TestASTAnalyzer)                       ... ok
test_parse_traceback_multiframe (test_ast_analyzer.TestASTAnalyzer)                ... ok
test_embedding_fallback_deterministic (test_memory.TestMemorySubsystem)             ... ok
test_memory_engine_crud (test_memory.TestMemorySubsystem)                           ... ok
test_models_to_semantic_text (test_memory.TestMemorySubsystem)                      ... ok
test_orchestrator_healing_flow (test_orchestrator.TestOrchestrator)                ... ok
test_orchestrator_successful_code (test_orchestrator.TestOrchestrator)             ... ok
test_sandbox_failure_captures_stderr (test_sandbox.TestSandboxExecutor)             ... ok
test_sandbox_successful_execution (test_sandbox.TestSandboxExecutor)               ... ok
test_sandbox_timeout_handling (test_sandbox.TestSandboxExecutor)                   ... ok
----------------------------------------------------------------------
Ran 16 tests in 2.497s — OK (All tests passing)
```

---

## 📚 Citations & Academic References

If you use CogniHeal-Engine in your research, agent benchmarks, or production systems, please cite the following foundational literature:

```bibtex
@article{shinn2023reflexion,
  title   = {Reflexion: Language Agents with Verbal Reinforcement Learning},
  author  = {Noah Shinn and Federico Cassano and Edward Berman and Ashwin Gopinath and Karthik Narasimhan and Shunyu Yao},
  journal = {Advances in Neural Information Processing Systems (NeurIPS)},
  volume  = {36},
  year    = {2023}
}

@article{tulving1972episodic,
  title   = {Episodic and Semantic Memory},
  author  = {Endel Tulving},
  journal = {Organization of Memory},
  pages   = {381--403},
  year    = {1972},
  publisher = {Academic Press}
}

@article{wei2022chain,
  title   = {Chain-of-Thought Prompting Elicits Reasoning in Large Language Models},
  author  = {Jason Wei and Xuezhi Wang and Dale Schuurmans and Maarten Bosma and Brian Ichter and Fei Xia and Ed Chi and Quoc Le and Denny Zhou},
  journal = {Advances in Neural Information Processing Systems (NeurIPS)},
  volume  = {35},
  pages   = {24824--24837},
  year    = {2022}
}
```

---

## 📄 License & Community

This project is open-source under the **[MIT License](LICENSE)**.

Developed for autonomous AI engineering teams, agent developers, and researchers building resilient software architectures.

<div align="center">

**CogniHeal-Engine** — *Because the best debugger is one that never forgets its mistakes.*

⭐ **Star us on GitHub** to support the project!

</div>
