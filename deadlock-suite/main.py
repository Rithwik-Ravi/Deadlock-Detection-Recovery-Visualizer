"""Interactive CLI for Deadlock Detection and Recovery Visualizer.

Course: Operating Systems (BCSE303L)
Authors:
- Sri Krishna (24BCE2630)
- Rithvik Ravi (24BCE2254)
- Aditya (24BCE2242)

Usage:
  python main.py --scenario safe
  python main.py --scenario deadlocked --viva
  python main.py --list
  python main.py --custom
  python main.py --scenario deadlocked --export report.json
  python main.py --scenario deadlocked --recover dlr
"""

from __future__ import annotations

import argparse
import json
import sys

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from core.deadlock_core import DeadlockSystem, DetectionReport
from demo_scenarios import get_scenario, list_scenarios


def make_console(no_color: bool = False) -> Console:
    """Instantiate a Rich console honoring no_color flag."""
    import contextlib

    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")
    return Console(no_color=no_color, highlight=False)


def print_banner(console: Console) -> None:
    """Print project header banner."""
    header = (
        "[bold cyan]Deadlock Detection & Recovery: "
        "Resource Allocation Graph Visualizer[/bold cyan]\n"
        "[yellow]Course:[/yellow] Operating Systems (BCSE303L) | "
        "[dim]Silberschatz Multi-Instance Model[/dim]\n"
        "[green]Team:[/green] Sri Krishna (24BCE2630) | "
        "Rithvik Ravi (24BCE2254) | Aditya (24BCE2242)"
    )
    console.print(Panel.fit(header, border_style="cyan", box=box.ROUNDED))


def print_matrices_tables(system: DeadlockSystem, console: Console) -> None:
    """Display Available vector, Allocation matrix, and Request matrix in rich tables."""
    # Available Table
    avail_table = Table(title="[bold green]Available Resources[/bold green]", box=box.ROUNDED)
    for r_name in system.resource_names:
        avail_table.add_column(r_name, justify="center", style="bold cyan")
    avail_table.add_row(*[str(x) for x in system.available])

    # Allocation & Request Combined or Side-by-Side
    matrix_table = Table(
        title="[bold blue]Allocation & Request Matrices[/bold blue]", box=box.ROUNDED
    )
    matrix_table.add_column("Process", justify="center", style="bold yellow")
    for r_name in system.resource_names:
        matrix_table.add_column(f"Alloc({r_name})", justify="center", style="green")
    for r_name in system.resource_names:
        matrix_table.add_column(f"Req({r_name})", justify="center", style="magenta")

    for i in range(system.n):
        p_name = system.process_names[i]
        alloc_vals = [str(x) for x in system.allocation[i]]
        req_vals = [str(x) for x in system.request[i]]
        matrix_table.add_row(p_name, *alloc_vals, *req_vals)

    console.print(avail_table)
    console.print(matrix_table)


def print_step_trace(report: DetectionReport, console: Console, viva: bool = False) -> None:
    """Print the step-by-step trace of the detection algorithm."""
    console.print("\n[bold cyan]--- Step-by-Step Algorithm Execution ---[/bold cyan]")

    trace_table = Table(box=box.ROUNDED)
    trace_table.add_column("Step", justify="center", style="cyan", width=6)
    trace_table.add_column("Candidate", justify="center", style="yellow", width=10)
    trace_table.add_column("Request", justify="center", style="magenta")
    trace_table.add_column("Work Before", justify="center", style="blue")
    trace_table.add_column("Released (Alloc)", justify="center", style="green")
    trace_table.add_column("Work After", justify="center", style="bold green")

    if not report.steps:
        console.print(
            "[yellow]No processes could satisfy Request <= Work from initial state.[/yellow]"
        )
        return

    for step in report.steps:
        req_str = f"[{', '.join(str(x) for x in step.request)}]"
        wb_str = f"[{', '.join(str(x) for x in step.work_before)}]"
        rel_str = f"[{', '.join(str(x) for x in step.allocated)}]"
        wa_str = f"[{', '.join(str(x) for x in step.work_after)}]"

        trace_table.add_row(
            str(step.step_no),
            step.candidate_name,
            req_str,
            wb_str,
            rel_str,
            wa_str,
        )

        if viva:
            console.print(trace_table)
            console.print(
                Panel(
                    f"[bold white]{step.explanation}[/bold white]\n"
                    f"[dim]Finish snapshot: {step.finish_snapshot}[/dim]",
                    title=f"[cyan]Step {step.step_no} Viva Explanation[/cyan]",
                    border_style="yellow",
                )
            )
            # Recreate empty table for single-step display in viva mode
            trace_table = Table(box=box.ROUNDED)
            trace_table.add_column("Step", justify="center", style="cyan", width=6)
            trace_table.add_column("Candidate", justify="center", style="yellow", width=10)
            trace_table.add_column("Request", justify="center", style="magenta")
            trace_table.add_column("Work Before", justify="center", style="blue")
            trace_table.add_column("Released (Alloc)", justify="center", style="green")
            trace_table.add_column("Work After", justify="center", style="bold green")

            Prompt.ask("[bold reverse] Press Enter to continue to next step [/bold reverse]")

    if not viva:
        console.print(trace_table)


def print_final_outcome(report: DetectionReport, console: Console) -> None:
    """Print the final outcome banner (Safe vs Deadlocked)."""
    if not report.deadlocked:
        seq_names = [report.process_names[i] for i in report.safe_sequence]
        seq_str = " -> ".join(seq_names)
        console.print(
            Panel.fit(
                f"[bold green][OK] SYSTEM SAFE[/bold green]\n\n"
                f"Deadlock-free execution sequence: [bold cyan]{seq_str}[/bold cyan]\n"
                f"All {len(report.finished_processes)} processes can finish without deadlock.\n"
                f"Final Available Work: [bold]{report.final_work}[/bold]",
                border_style="green",
                box=box.DOUBLE,
            )
        )
    else:
        dead_names = [report.process_names[i] for i in report.deadlocked_processes]
        dead_str = ", ".join(dead_names)
        fin_names = [report.process_names[i] for i in report.finished_processes]
        fin_str = ", ".join(fin_names) if fin_names else "None"

        cycles_str = ""
        if report.deadlock_cycles:
            cycle_desc = []
            for c in report.deadlock_cycles:
                c_names = [report.process_names[i] for i in c]
                cycle_desc.append(" -> ".join(c_names + [c_names[0]]))
            cycles_str = (
                "\nConcrete Cycle(s): [bold yellow]" + " | ".join(cycle_desc) + "[/bold yellow]"
            )

        console.print(
            Panel.fit(
                f"[bold red][X] DEADLOCK DETECTED[/bold red]\n\n"
                f"Deadlocked Processes: [bold red]{dead_str}[/bold red]\n"
                f"Processes that finished safely: [green]{fin_str}[/green]\n"
                f"Final Work vector: [bold]{report.final_work}[/bold]"
                f"{cycles_str}",
                border_style="red",
                box=box.DOUBLE,
            )
        )


def prompt_custom_matrix(console: Console) -> DeadlockSystem:
    """Interactively collect and validate matrix entries from the user."""
    console.print(Panel("[bold yellow]Interactive Custom Matrix Entry[/bold yellow]"))

    while True:
        try:
            n_str = Prompt.ask("Enter number of processes (n >= 1)").strip()
            n = int(n_str)
            if n < 1:
                raise ValueError("n must be at least 1")
            break
        except ValueError as err:
            console.print(f"[red]Invalid input: {err}. Please try again.[/red]")

    while True:
        try:
            m_str = Prompt.ask("Enter number of resource types (m >= 1)").strip()
            m = int(m_str)
            if m < 1:
                raise ValueError("m must be at least 1")
            break
        except ValueError as err:
            console.print(f"[red]Invalid input: {err}. Please try again.[/red]")

    res_names = [chr(65 + j) if m <= 26 else f"R{j}" for j in range(m)]
    proc_names = [f"P{i}" for i in range(n)]

    console.print(f"[cyan]Resources defined:[/cyan] {', '.join(res_names)}")
    console.print(f"[cyan]Processes defined:[/cyan] {', '.join(proc_names)}")

    while True:
        try:
            avail_str = Prompt.ask(
                f"Enter Available vector of {m} integers (space or comma separated)"
            ).strip()
            parts = [int(x.strip()) for x in avail_str.replace(",", " ").split() if x.strip()]
            if len(parts) != m:
                raise ValueError(f"Expected {m} values for Available, got {len(parts)}.")
            if any(x < 0 for x in parts):
                raise ValueError("Available values must be non-negative.")
            available = parts
            break
        except ValueError as err:
            console.print(f"[red]Invalid Available vector: {err}. Try again.[/red]")

    allocation: list[list[int]] = []
    console.print("[dim]Enter Allocation matrix rows (held resource units):[/dim]")
    for i in range(n):
        while True:
            try:
                row_str = Prompt.ask(f"Allocation row for {proc_names[i]} ({m} ints)").strip()
                parts = [int(x.strip()) for x in row_str.replace(",", " ").split() if x.strip()]
                if len(parts) != m:
                    raise ValueError(f"Expected {m} values, got {len(parts)}.")
                if any(x < 0 for x in parts):
                    raise ValueError("Values must be non-negative.")
                allocation.append(parts)
                break
            except ValueError as err:
                console.print(f"[red]Error: {err}. Try again.[/red]")

    request: list[list[int]] = []
    console.print("[dim]Enter Request matrix rows (needed resource units):[/dim]")
    for i in range(n):
        while True:
            try:
                row_str = Prompt.ask(f"Request row for {proc_names[i]} ({m} ints)").strip()
                parts = [int(x.strip()) for x in row_str.replace(",", " ").split() if x.strip()]
                if len(parts) != m:
                    raise ValueError(f"Expected {m} values, got {len(parts)}.")
                if any(x < 0 for x in parts):
                    raise ValueError("Values must be non-negative.")
                request.append(parts)
                break
            except ValueError as err:
                console.print(f"[red]Error: {err}. Try again.[/red]")

    return DeadlockSystem(
        available=available,
        allocation=allocation,
        request=request,
        process_names=proc_names,
        resource_names=res_names,
    )


def handle_recovery_cli(
    system: DeadlockSystem, strategy: str, console: Console, export_path: str | None
) -> None:
    """Execute recovery strategy (Phase 3) if requested."""
    try:
        from core.recovery import run_recovery_strategy
    except ImportError:
        console.print(
            f"[bold red]Recovery engine module not loaded or in progress. "
            f"Strategy '{strategy}' will be enabled in Phase 3.[/bold red]"
        )
        return

    rec_banner = (
        f"\n[bold magenta]─── Executing Recovery Strategy: {strategy.upper()} ───[/bold magenta]"
    )
    console.print(rec_banner)
    rec_report = run_recovery_strategy(system, strategy)

    table = Table(title="[bold yellow]Recovery Action Plan[/bold yellow]", box=box.ROUNDED)
    table.add_column("Step", justify="center")
    table.add_column("Action", style="cyan")
    table.add_column("Target Process", style="yellow")
    table.add_column("Explanation", style="white")

    for idx, act in enumerate(rec_report.actions, 1):
        table.add_row(str(idx), act.action_type, act.process_name or "-", act.explanation)
    console.print(table)

    metrics_table = Table(title="[bold green]Post-Recovery Metrics[/bold green]", box=box.ROUNDED)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="bold green")
    for k, v in rec_report.metrics.items():
        metrics_table.add_row(str(k), f"{v:.4f}" if isinstance(v, float) else str(v))
    console.print(metrics_table)

    if rec_report.post_detection:
        print_final_outcome(rec_report.post_detection, console)

    if export_path:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(rec_report.to_dict(), f, indent=2)
        console.print(f"[green]Recovery report exported to {export_path}[/green]")


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Deadlock Detection & Recovery: Resource Allocation Graph Visualizer"
    )
    parser.add_argument(
        "--scenario",
        choices=["safe", "deadlocked", "borderline", "circular", "zero_alloc"],
        help="Run detection on one of the curated benchmark scenarios",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all benchmark scenarios with viva notes and configurations",
    )
    parser.add_argument(
        "--custom",
        action="store_true",
        help="Interactively input a custom Available vector and Allocation/Request matrices",
    )
    parser.add_argument(
        "--viva",
        action="store_true",
        help="Interactive viva mode: pause after every algorithm step and explain state evolution",
    )
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="Export detection or recovery report to a JSON file",
    )
    parser.add_argument(
        "--recover",
        choices=["abort_all", "abort_one_by_one", "preemption", "dlr"],
        help="Run Phase 3 recovery strategy on deadlocked system",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in console output",
    )

    args = parser.parse_args()
    console = make_console(no_color=args.no_color)
    print_banner(console)

    if args.list:
        table = Table(title="[bold cyan]Benchmark Scenarios[/bold cyan]", box=box.ROUNDED)
        table.add_column("Key", style="bold yellow")
        table.add_column("Title", style="bold white")
        table.add_column("Expected", style="magenta")
        table.add_column("Viva Note", style="dim")
        for sc in list_scenarios():
            is_dl = sc["expected_deadlocked"]
            exp_str = "[red]Deadlocked[/red]" if is_dl else "[green]Safe[/green]"
            table.add_row(sc["key"], sc["title"], exp_str, sc["viva_note"])
        console.print(table)
        return

    system: DeadlockSystem | None = None
    viva_note: str | None = None

    if args.custom:
        system = prompt_custom_matrix(console)
    elif args.scenario:
        sc = get_scenario(args.scenario)
        system = sc.to_system()
        viva_note = sc.viva_note
        console.print(f"\n[bold yellow]Scenario:[/bold yellow] [bold white]{sc.title}[/bold white]")
    else:
        # Default to safe scenario if no flags provided
        sc = get_scenario("safe")
        system = sc.to_system()
        viva_note = sc.viva_note
        console.print(
            "\n[dim]No scenario specified. Defaulting to classic [bold cyan]safe[/bold cyan] "
            "benchmark. Use --help or --list for options.[/dim]"
        )

    print_matrices_tables(system, console)
    report = system.detect()
    print_step_trace(report, console, viva=args.viva)
    print_final_outcome(report, console)

    if viva_note:
        console.print(
            Panel(
                f"[bold yellow]Viva Exam Note:[/bold yellow] {viva_note}",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

    if args.recover and report.deadlocked:
        handle_recovery_cli(system, args.recover, console, args.export)
    elif args.export:
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        console.print(f"[green]Detection report exported to {args.export}[/green]")


if __name__ == "__main__":
    main()
