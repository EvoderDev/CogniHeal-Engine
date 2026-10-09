"""CogniHeal-Engine — Interactive REPL & Rich Terminal Interface.

Provides a persistent, interactive autonomous agent environment modeled
after modern AI developer tools (such as Claude Code).  Includes an
interactive REPL loop, multi-turn session context preservation, real-time
telemetry panels, status spinners, and a full suite of built-in commands.

Usage::

    # Launch interactive agent REPL:
    cogni
    cg
    cogniheal

    # Or run one-shot subcommands:
    cogniheal run --task "Sort a list of dicts by 'age'"
    cogniheal run --code-file buggy.py
    cogniheal memory stats
    cogniheal memory search "TypeError async"
    cogniheal benchmark
"""

from __future__ import annotations

import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# ── Cross-platform UTF-8 terminal encoding safety ──────────────────────────
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(legacy_windows=False)

_BANNER = r"""
   ____                  _ _   _            _
  / ___|___   __ _ _ __ (_) | | | ___  __ _| |
 | |   / _ \ / _` | '_ \| | |_| |/ _ \/ _` | |
 | |__| (_) | (_| | | | | |  _  |  __/ (_| | |
  \____\___/ \__, |_| |_|_|_| |_|\___|\__,_|_|
             |___/
  ── Self-Reflective Dynamic Episodic Memory Engine ──
"""

_STAGE_STYLES: dict[str, tuple[str, str]] = {
    "memory_scan": ("🧠", "bold cyan"),
    "execute": ("⚡", "bold yellow"),
    "reflect": ("🔍", "bold magenta"),
    "fix": ("🔧", "bold blue"),
    "success": ("✅", "bold green"),
    "exhausted": ("💀", "bold red"),
}


# ── Session Context ────────────────────────────────────────────────────────

@dataclass
class SessionTurn:
    """A single conversational turn in the interactive REPL session."""

    turn_id: int
    prompt: str
    code: str
    stdout: str
    stderr: str
    success: bool
    iterations: int
    duration_s: float
    timestamp: str


class SessionContext:
    """Preserves conversational context and evolving code across REPL turns."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id: str = session_id or uuid.uuid4().hex[:8]
        self.turns: list[SessionTurn] = []
        self.active_code: str | None = None
        self.started_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_turn(
        self,
        prompt: str,
        code: str,
        stdout: str,
        stderr: str,
        success: bool,
        iterations: int,
        duration_s: float,
    ) -> None:
        """Record an executed turn and update the active code state."""
        turn = SessionTurn(
            turn_id=len(self.turns) + 1,
            prompt=prompt,
            code=code,
            stdout=stdout,
            stderr=stderr,
            success=success,
            iterations=iterations,
            duration_s=duration_s,
            timestamp=datetime.now().strftime("%H:%M:%S"),
        )
        self.turns.append(turn)
        if success or code:
            self.active_code = code

    def get_summary_context(self) -> str:
        """Format the recent conversation history for prompt injection."""
        if not self.turns:
            return ""
        parts: list[str] = []
        for t in self.turns[-3:]:  # Keep up to 3 recent turns
            parts.append(
                f"[Turn #{t.turn_id} at {t.timestamp}]\n"
                f"User Goal: {t.prompt}\n"
                f"Outcome: {'SUCCESS' if t.success else 'FAILED'} (Iterations: {t.iterations})\n"
                f"Stdout Preview: {t.stdout[:150] if t.stdout else '(none)'}"
            )
        if self.active_code:
            parts.append(f"\n[Latest Active Code State]:\n{self.active_code}")
        return "\n\n".join(parts)


def _render_event(event: Any) -> None:
    """Render a HealCycleEvent as a Rich panel with live styling."""
    icon, style = _STAGE_STYLES.get(event.stage, ("ℹ️", "white"))
    title = f"{icon}  [{style}]{event.stage.upper()}[/{style}] (iter {event.iteration})"

    content_parts: list[str] = [event.message]
    if event.data:
        for key, value in event.data.items():
            if isinstance(value, str) and len(value) > 200:
                value = value[:200] + "…"
            content_parts.append(f"  {key}: {value}")

    panel = Panel(
        "\n".join(content_parts),
        title=title,
        border_style=style.replace("bold ", ""),
        padding=(0, 1),
    )
    console.print(panel)


def _get_memory_engine() -> Any:
    """Initialise and return the episodic memory engine."""
    from cogniheal.config import settings
    from cogniheal.memory.episodic_engine import EpisodicMemoryEngine

    settings.ensure_dirs()
    engine = EpisodicMemoryEngine()
    engine.initialise()
    return engine


def _print_welcome_banner(memory_engine: Any, session: SessionContext) -> None:
    """Print the launch banner and system telemetry grid."""
    from cogniheal.config import settings

    console.print(Text(_BANNER, style="bold cyan"))

    telemetry = Table(show_header=False, box=None, padding=(0, 2))
    telemetry.add_column("Key", style="dim cyan")
    telemetry.add_column("Value", style="bold white")
    telemetry.add_column("Key2", style="dim cyan")
    telemetry.add_column("Value2", style="bold white")

    telemetry.add_row(
        "Session ID:", session.session_id,
        "LLM Model:", settings.llm_model,
    )
    telemetry.add_row(
        "Sandbox:", f"{settings.sandbox_mode} ({settings.sandbox_timeout_seconds}s limit)",
        "Embedding:", settings.embedding_model,
    )
    telemetry.add_row(
        "Episodic Memories:", f"{memory_engine.count_episodes()} episodes",
        "Constraints:", f"{memory_engine.count_constraints()} rules active",
    )
    telemetry.add_row(
        "Database:", str(settings.sqlite_path),
        "Vector DB:", str(settings.chroma_persist_dir),
    )

    console.print(
        Panel(
            telemetry,
            title="⚡ [bold green]CogniHeal Autonomous Agent Online[/bold green]",
            subtitle="Type your task or [bold cyan]/help[/bold cyan] for commands • [bold red]/exit[/bold red] to quit",
            border_style="cyan",
        )
    )


# ──────────────────────────────────────────────────────────────────
# Interactive REPL Mode (Claude Code style)
# ──────────────────────────────────────────────────────────────────


def interactive_mode() -> None:
    """Run the persistent interactive REPL session."""
    memory = _get_memory_engine()
    session = SessionContext()
    _print_welcome_banner(memory, session)

    from cogniheal.agent.orchestrator import HealingOrchestrator

    orchestrator = HealingOrchestrator(
        memory_engine=memory,
        on_event=_render_event,
    )

    while True:
        try:
            prompt_label = f"\n[bold cyan]cogni[/bold cyan] [dim]({session.session_id})[/dim] [bold green]>[/bold green] "
            user_input = Prompt.ask(prompt_label).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Received exit interrupt.[/yellow]")
            break

        if not user_input:
            continue

        cmd_lower = user_input.lower()

        # ── Built-in Commands ─────────────────────────────────────────
        if cmd_lower in ("exit", "quit", "/exit", "/quit", ":q"):
            break

        elif cmd_lower in ("clear", "cls", "/clear"):
            console.clear()
            _print_welcome_banner(memory, session)
            continue

        elif cmd_lower in ("help", "/help", "?"):
            _print_help_table()
            continue

        elif cmd_lower in ("stats", "/stats", "memory stats"):
            _print_stats(memory)
            continue

        elif cmd_lower in ("memory", "/memory", "memory list"):
            _print_episodes(memory, limit=10)
            continue

        elif cmd_lower in ("constraints", "/constraints", "rules", "/rules"):
            _print_constraints(memory)
            continue

        elif cmd_lower.startswith("/search ") or cmd_lower.startswith("search ") or cmd_lower.startswith("memory search "):
            query = user_input.split(" ", 1)[-1].strip()
            _search_memory(memory, query)
            continue

        elif cmd_lower in ("history", "/history"):
            _print_session_history(session)
            continue

        elif cmd_lower in ("reset", "/reset"):
            session = SessionContext()
            console.print("[green]✔ Active session context reset to fresh state.[/green]")
            continue

        elif cmd_lower in ("benchmark", "/benchmark"):
            _run_chaos_benchmark(memory, orchestrator)
            continue

        elif cmd_lower.startswith("/load ") or cmd_lower.startswith("load ") or cmd_lower.startswith("/code "):
            file_path_str = user_input.split(" ", 1)[-1].strip().strip('"').strip("'")
            file_path = Path(file_path_str)
            if not file_path.exists():
                console.print(f"[red]Error:[/red] File not found: {file_path}")
                continue
            code_content = file_path.read_text(encoding="utf-8")
            session.active_code = code_content
            console.print(
                Panel(
                    Syntax(code_content, "python", theme="monokai", line_numbers=True),
                    title=f"📄 Loaded Code: {file_path.name}",
                    border_style="yellow",
                )
            )
            continue

        # ── Autonomous Task Execution ─────────────────────────────────
        task = user_input
        initial_code: str | None = None

        # Check if the user wants to execute the loaded/active code
        if session.active_code and any(kw in cmd_lower for kw in ("run this", "execute this", "fix this", "heal this", "test this")):
            initial_code = session.active_code

        console.print(
            Panel(task, title="🎯 Active Task", border_style="cyan")
        )

        # Execute with live status spinner
        with console.status("[bold cyan]Agent scanning memory & analyzing task…[/bold cyan]", spinner="dots"):
            start_t = time.perf_counter()
            result = orchestrator.run(
                task_prompt=task,
                initial_code=initial_code,
                context=session.get_summary_context(),
            )
            elapsed = time.perf_counter() - start_t

        # ── Execution Results ─────────────────────────────────────────
        summary_table = Table(title="📊 Task Summary", show_header=True)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="white")
        summary_table.add_row("Status", "✅ SUCCESS" if result.success else "❌ FAILED")
        summary_table.add_row("Total Iterations", str(result.total_iterations))
        summary_table.add_row("Elapsed Time", f"{result.elapsed_seconds:.2f}s")
        if result.final_result:
            summary_table.add_row("Exit Code", str(result.final_result.exit_code))
        console.print(summary_table)

        if result.success and result.final_result and result.final_result.stdout:
            console.print(
                Panel(
                    result.final_result.stdout[:2000],
                    title="💬 Captured stdout",
                    border_style="green",
                )
            )

        if result.final_code:
            console.print(
                Panel(
                    Syntax(result.final_code, "python", theme="monokai", line_numbers=True),
                    title="📝 Final Code State",
                    border_style="green" if result.success else "red",
                )
            )

        # Update persistent session context
        stdout_text = result.final_result.stdout if result.final_result else ""
        stderr_text = result.final_result.stderr if result.final_result else ""
        session.add_turn(
            prompt=task,
            code=result.final_code,
            stdout=stdout_text,
            stderr=stderr_text,
            success=result.success,
            iterations=result.total_iterations,
            duration_s=elapsed,
        )

    # ── Farewell Summary ──────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold green]Session {session.session_id} ended gracefully.[/bold green]\n"
            f"Total turns executed: {len(session.turns)}\n"
            f"All episodic error memories and hard constraints are persisted in SQLite & ChromaDB.",
            title="👋 Goodbye",
            border_style="cyan",
        )
    )
    memory.close()


def _print_help_table() -> None:
    """Display the interactive commands reference table."""
    table = Table(title="📖 CogniHeal Interactive REPL Commands", show_header=True)
    table.add_column("Command", style="bold cyan")
    table.add_column("Aliases", style="dim")
    table.add_column("Description", style="white")

    table.add_row("<any text>", "-", "Execute coding task with memory recall & self-healing")
    table.add_row("/load <path>", "load, /code", "Load a Python file into active session memory")
    table.add_row("/memory", "memory", "List recently saved episodic error memories")
    table.add_row("/search <query>", "search", "Semantic vector search across historical episodes")
    table.add_row("/stats", "stats", "View SQLite and ChromaDB memory statistics")
    table.add_row("/constraints", "rules", "Display active hard constraint rules")
    table.add_row("/history", "history", "Show session conversational turns and code state")
    table.add_row("/reset", "reset", "Clear active session conversation context")
    table.add_row("/benchmark", "benchmark", "Run the 12-scenario chaos benchmark stress test")
    table.add_row("/clear", "cls, clear", "Clear terminal screen")
    table.add_row("/exit", "quit, :q", "Exit the interactive REPL session")

    console.print(table)


def _print_stats(memory: Any) -> None:
    """Print memory statistics table."""
    n_episodes = memory.count_episodes()
    n_constraints = memory.count_constraints()
    table = Table(title="🧠 Episodic Memory Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="bold white")
    table.add_row("Total Error Episodes", str(n_episodes))
    table.add_row("Active Hard Constraints", str(n_constraints))
    table.add_row("SQLite Relational DB", str(memory._sqlite_path))
    table.add_row("ChromaDB Vector Store", str(memory._chroma_dir))
    console.print(table)


def _print_episodes(memory: Any, limit: int = 10) -> None:
    """Print recently saved memory episodes."""
    episodes = memory.recent_episodes(limit=limit)
    if not episodes:
        console.print("[yellow]No episodes stored in memory yet.[/yellow]")
        return

    table = Table(title=f"📚 Recent Memory Episodes (last {limit})")
    table.add_column("#", style="dim")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Severity", style="red")
    table.add_column("Success", style="green")
    table.add_column("Iterations", justify="right")
    table.add_column("Summary", max_width=45)

    for i, ep in enumerate(episodes, 1):
        table.add_row(
            str(i),
            ep.timestamp.strftime("%Y-%m-%d %H:%M"),
            ep.rca.category.value,
            ep.rca.severity.value,
            "✅" if ep.success else "❌",
            str(ep.total_iterations),
            ep.rca.summary[:45],
        )
    console.print(table)


def _search_memory(memory: Any, query: str) -> None:
    """Perform and print semantic vector search."""
    with console.status(f"[cyan]Searching memory for: '{query}'…[/cyan]"):
        results = memory.query(query, top_k=5, min_similarity=0.0)

    if not results:
        console.print("[yellow]No matching episodes found.[/yellow]")
        return

    for i, ep in enumerate(results, 1):
        tree = Tree(f"[bold]{i}. {ep.rca.summary}[/bold]")
        tree.add(f"[cyan]Category:[/cyan] {ep.rca.category.value}")
        tree.add(f"[red]Severity:[/red] {ep.rca.severity.value}")
        tree.add(f"[green]Fix:[/green] {ep.fix.description[:100]}")
        tree.add(f"[yellow]Constraint:[/yellow] {ep.hard_constraint.description}")
        console.print(tree)
        console.print()


def _print_constraints(memory: Any) -> None:
    """Print all active hard constraint rules."""
    constraints = memory.get_all_constraints()
    if not constraints:
        console.print("[yellow]No hard constraints stored yet.[/yellow]")
        return

    table = Table(title="🚫 Active Hard Constraint Rules")
    table.add_column("Rule ID", style="dim")
    table.add_column("Constraint Description", style="bold")
    table.add_column("Created", style="cyan")

    for c in constraints:
        table.add_row(
            c["rule_id"],
            c["description"],
            c["created_at"][:19],
        )
    console.print(table)


def _print_session_history(session: SessionContext) -> None:
    """Print current session conversational history."""
    if not session.turns:
        console.print("[yellow]No turns executed in this session yet.[/yellow]")
        return

    table = Table(title=f"📜 Session History ({session.session_id})")
    table.add_column("Turn", style="dim")
    table.add_column("Time", style="cyan")
    table.add_column("Prompt", max_width=40)
    table.add_column("Status")
    table.add_column("Iterations", justify="right")
    table.add_column("Duration", justify="right")

    for t in session.turns:
        status = "✅ SUCCESS" if t.success else "❌ FAILED"
        table.add_row(
            str(t.turn_id),
            t.timestamp,
            t.prompt[:40],
            status,
            str(t.iterations),
            f"{t.duration_s:.2f}s",
        )
    console.print(table)

    if session.active_code:
        console.print(
            Panel(
                Syntax(session.active_code, "python", theme="monokai", line_numbers=True),
                title="📝 Current Active Code Snippet",
                border_style="yellow",
            )
        )


def _run_chaos_benchmark(memory: Any, orchestrator: Any) -> None:
    """Run the chaos benchmark within the REPL session."""
    from examples.benchmark_chaos import CHAOS_SCENARIOS

    console.print(
        Panel(
            "[bold red]CHAOS BENCHMARK[/bold red]\n"
            "Testing autonomous self-healing on 12 challenging runtime failure scenarios.",
            title="💥 Stress Test Mode",
            border_style="red",
        )
    )

    results_table = Table(title="🏆 Benchmark Results")
    results_table.add_column("#", style="dim")
    results_table.add_column("Scenario", style="cyan")
    results_table.add_column("Status")
    results_table.add_column("Iterations", justify="right")
    results_table.add_column("Time", justify="right")

    total = len(CHAOS_SCENARIOS)
    passed = 0

    for i, scenario in enumerate(CHAOS_SCENARIOS, 1):
        console.rule(f"[bold] Scenario {i}/{total}: {scenario['name']} [/bold]")
        result = orchestrator.run(
            task_prompt=scenario["description"],
            initial_code=scenario["code"],
        )
        status = "✅ HEALED" if result.success else "❌ FAILED"
        if result.success:
            passed += 1

        results_table.add_row(
            str(i),
            scenario["name"],
            status,
            str(result.total_iterations),
            f"{result.elapsed_seconds:.1f}s",
        )

    console.print()
    console.print(results_table)
    score = (passed / total * 100) if total else 0
    color = "green" if score >= 70 else "yellow" if score >= 40 else "red"
    console.print(
        Panel(
            f"[bold {color}]Score: {passed}/{total} ({score:.0f}%)[/bold {color}]",
            title="🎯 Final Benchmark Score",
            border_style=color,
        )
    )


# ──────────────────────────────────────────────────────────────────
# Standard Click Commands (For Non-Interactive Scripting)
# ──────────────────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """CogniHeal-Engine — Autonomous Self-Healing Agent & Episodic Memory REPL."""
    if ctx.invoked_subcommand is None:
        interactive_mode()


@main.command()
@click.option(
    "--task", "-t",
    type=str,
    default=None,
    help="Natural-language task description.",
)
@click.option(
    "--code-file", "-f",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to a Python file to execute and self-heal.",
)
@click.option(
    "--max-iterations", "-n",
    type=int,
    default=None,
    help="Maximum self-heal iterations.",
)
def run(
    task: str | None,
    code_file: Path | None,
    max_iterations: int | None,
) -> None:
    """Execute a task with autonomous self-healing (non-interactive)."""
    if not task and not code_file:
        console.print("[red]Error:[/red] Provide --task or --code-file.")
        raise SystemExit(1)

    initial_code: str | None = None
    if code_file:
        initial_code = code_file.read_text(encoding="utf-8")
        task = task or f"Execute and fix: {code_file.name}"

    memory = _get_memory_engine()
    from cogniheal.agent.orchestrator import HealingOrchestrator

    orchestrator = HealingOrchestrator(
        memory_engine=memory,
        max_iterations=max_iterations,
        on_event=_render_event,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Self-healing pipeline running…[/bold blue]"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("heal", total=None)
        result = orchestrator.run(task, initial_code=initial_code)

    summary_table = Table(title="📊 Execution Summary", show_header=True)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    summary_table.add_row("Status", "✅ SUCCESS" if result.success else "❌ FAILED")
    summary_table.add_row("Total Iterations", str(result.total_iterations))
    summary_table.add_row("Elapsed Time", f"{result.elapsed_seconds:.2f}s")
    console.print(summary_table)

    if result.success and result.final_result and result.final_result.stdout:
        console.print(Panel(result.final_result.stdout[:2000], title="💬 stdout", border_style="green"))

    console.print(
        Panel(
            Syntax(result.final_code, "python", theme="monokai", line_numbers=True),
            title="📝 Final Code",
            border_style="green" if result.success else "red",
        )
    )
    memory.close()


@main.group()
def memory() -> None:
    """Inspect and manage the episodic memory store."""
    pass


@memory.command(name="stats")
def memory_stats() -> None:
    """Show memory store statistics."""
    engine = _get_memory_engine()
    _print_stats(engine)
    engine.close()


@memory.command(name="list")
@click.option("--limit", "-n", type=int, default=10, help="Number of recent episodes.")
def memory_list(limit: int) -> None:
    """List recent episodic memories."""
    engine = _get_memory_engine()
    _print_episodes(engine, limit=limit)
    engine.close()


@memory.command(name="search")
@click.argument("query")
@click.option("--top-k", "-k", type=int, default=5, help="Number of results.")
def memory_search(query: str, top_k: int) -> None:
    """Semantic search across episodic memories."""
    engine = _get_memory_engine()
    _search_memory(engine, query)
    engine.close()


@memory.command(name="constraints")
def memory_constraints() -> None:
    """List all active hard-constraint rules."""
    engine = _get_memory_engine()
    _print_constraints(engine)
    engine.close()


@main.command()
@click.option("--max-iterations", "-n", type=int, default=5)
def benchmark(max_iterations: int) -> None:
    """Run the chaos benchmark stress test."""
    memory = _get_memory_engine()
    from cogniheal.agent.orchestrator import HealingOrchestrator

    orchestrator = HealingOrchestrator(
        memory_engine=memory,
        max_iterations=max_iterations,
        on_event=_render_event,
    )
    _run_chaos_benchmark(memory, orchestrator)
    memory.close()


if __name__ == "__main__":
    main()
