"""
Command-Line Runner for Deadlock Detection Engine (Phase 1)
===========================================================
Academic Operating Systems Project:
"Deadlock Detection & Recovery - Resource Allocation Graph Visualizer"

Usage:
    python main.py                     # Interactive menu mode
    python main.py --all               # Run and trace all demo scenarios
    python main.py --scenario safe     # Run a specific scenario (safe/deadlocked/borderline/circular/zero_alloc)
    python main.py --step-by-step      # Interactive step-through mode for vivas
    python main.py --json              # Output machine-readable JSON for Phase 2 GUI
    python main.py --custom            # Enter custom matrices interactively
"""

import sys
import json
import argparse
from typing import List

# Configure UTF-8 encoding for standard output on Windows to support ✓, ✗, ⏳, ↓
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from deadlock_core import DeadlockSystem, DetectionReport
from demo_scenarios import get_scenario, get_all_scenarios, Scenario


# ANSI Terminal Colors for viva and demonstration clarity
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def colorize(text: str, color: str) -> str:
    """Colorize text if terminal supports ANSI, otherwise return clean text."""
    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


def print_banner() -> None:
    banner = f"""
{Colors.CYAN}{Colors.BOLD}======================================================================
     DEADLOCK DETECTION & RECOVERY - CORE ENGINE (PHASE 1)
           Operating Systems Project - Academic Milestone
======================================================================{Colors.RESET}
Multi-Instance Resource Allocation Graph & Matrix-Based Detection Engine
Ready for Phase 2 (GUI Visualizer) & Phase 3 (Automated Recovery).
"""
    print(banner)


def run_scenario(scenario: Scenario, step_by_step: bool = False, print_json: bool = False) -> DetectionReport:
    """Run a scenario, display its metadata, matrix state, trace, and final verdict."""
    print("\n" + "=" * 70)
    print(colorize(f"SCENARIO: {scenario.name}", Colors.BOLD + Colors.CYAN))
    print("=" * 70)
    print(f"{colorize('Description:', Colors.BOLD)} {scenario.description}")
    print(f"{colorize('Viva Notes: ', Colors.BOLD)} {scenario.viva_notes}")

    system = DeadlockSystem(
        allocation=scenario.allocation,
        request=scenario.request,
        available=scenario.available,
        process_names=scenario.process_names,
        resource_names=scenario.resource_names,
    )

    # 1. Print formatted matrix state
    system.pretty_print_state()

    # 2. Run detection and print detailed, step-by-step explanatory trace
    if step_by_step:
        print(colorize("\n[Step-by-Step Viva Mode Enabled - Press Enter to Advance Each Step]\n", Colors.YELLOW))

    rep = system.detect_deadlock()
    system.print_detection_trace(rep, step_by_step=step_by_step)

    # 3. Optional JSON payload dump (verifying GUI contract)
    if print_json:
        print(colorize("\n--- Phase 2 GUI JSON Payload Preview ---", Colors.YELLOW))
        print(rep.to_json(indent=2))

    return rep


def run_all_scenarios(step_by_step: bool = False, print_json: bool = False) -> None:
    """Run all predefined scenarios and print a high-level summary scorecard."""
    scenarios = get_all_scenarios()
    print(f"\nRunning all {len(scenarios)} demonstration scenarios...\n")

    results = []
    for key, sc in scenarios.items():
        rep = run_scenario(sc, step_by_step=step_by_step, print_json=print_json)
        results.append((sc.name, rep.is_deadlocked, sc.expected_deadlock))

    # Print summary table
    print("\n" + "=" * 70)
    print(colorize("                     PHASE 1 VALIDATION SUMMARY", Colors.BOLD + Colors.CYAN))
    print("=" * 70)
    print(f"{'Scenario Name':<45} | {'Detected':<10} | {'Expected':<10} | {'Status'}")
    print("-" * 70)
    all_matched = True
    for name, detected, expected in results:
        det_str = "Deadlock" if detected else "Safe"
        exp_str = "Deadlock" if expected else "Safe"
        matched = detected == expected
        status_str = colorize("MATCH [PASS]", Colors.GREEN) if matched else colorize("MISMATCH [FAIL]", Colors.RED)
        if not matched:
            all_matched = False
        print(f"{name:<45} | {det_str:<10} | {exp_str:<10} | {status_str}")
    print("=" * 70)
    if all_matched:
        print(colorize(">> ALL SCENARIOS MATCH EXPECTED ACADEMIC OUTCOMES PERFECTLY! <<", Colors.BOLD + Colors.GREEN))
    print("=" * 70 + "\n")


def custom_matrix_interactive() -> None:
    """Interactive CLI to input custom matrices from an examiner during project viva."""
    print(colorize("\n--- Custom Matrix Input Mode ---", Colors.BOLD + Colors.CYAN))
    try:
        n = int(input("Enter number of processes (e.g. 3): ").strip())
        m = int(input("Enter number of resource types (e.g. 2): ").strip())

        if n <= 0 or m <= 0:
            print(colorize("Error: Number of processes and resources must be positive integers.", Colors.RED))
            return

        p_names = [f"P{i}" for i in range(n)]
        r_names = [f"R{j}" for j in range(m)]

        print(f"\nEnter Available Vector (space-separated {m} non-negative integers):")
        avail_input = input(f"Available [{', '.join(r_names)}]: ").strip().split()
        available = [int(x) for x in avail_input]

        allocation: List[List[int]] = []
        print(f"\nEnter Allocation Matrix ({n} rows, {m} integers each):")
        for i in range(n):
            row = input(f"Allocation for {p_names[i]}: ").strip().split()
            allocation.append([int(x) for x in row])

        request: List[List[int]] = []
        print(f"\nEnter Request Matrix ({n} rows, {m} integers each):")
        for i in range(n):
            row = input(f"Request for {p_names[i]}: ").strip().split()
            request.append([int(x) for x in row])

        custom_scenario = Scenario(
            name="Custom User/Examiner Scenario",
            scenario_id="custom",
            description="Entered interactively during CLI execution.",
            viva_notes="Live custom matrix evaluation.",
            allocation=allocation,
            request=request,
            available=available,
            process_names=p_names,
            resource_names=r_names,
            expected_deadlock=False,
        )

        run_scenario(custom_scenario, step_by_step=True)

    except ValueError as ve:
        print(colorize(f"\n[Validation Error] {ve}", Colors.RED))
    except Exception as e:
        print(colorize(f"\n[Input Error] Failed to parse input: {e}", Colors.RED))


def interactive_menu() -> None:
    """Primary interactive CLI menu."""
    while True:
        print_banner()
        print("Select an option:")
        print("  1. Run All Demo Scenarios (Overview & Scorecard)")
        print("  2. Run Scenario 1: Safe Scenario (All processes complete)")
        print("  3. Run Scenario 2: Deadlocked Scenario (Circular wait)")
        print("  4. Run Scenario 3: Borderline Scenario (Domino cascade unlock)")
        print("  5. Run Scenario 4: Circular Wait (Classic 2-process cycle)")
        print("  6. Run Scenario 5: Zero-Allocation Process (Boundary edge case)")
        print("  7. Step-by-Step Mode (Interactive step-through for Viva)")
        print("  8. Custom Matrix Input Mode (Enter matrices live)")
        print("  9. GUI Integration Test (Export JSON report payload)")
        print("  0. Exit")

        choice = input("\nEnter choice (0-9): ").strip()

        if choice == "1":
            run_all_scenarios()
        elif choice == "2":
            run_scenario(get_scenario("safe"))
        elif choice == "3":
            run_scenario(get_scenario("deadlocked"))
        elif choice == "4":
            run_scenario(get_scenario("borderline"))
        elif choice == "5":
            run_scenario(get_scenario("circular"))
        elif choice == "6":
            run_scenario(get_scenario("zero_alloc"))
        elif choice == "7":
            print("\nSelect scenario to step through:")
            scenarios = get_all_scenarios()
            keys = list(scenarios.keys())
            for idx, k in enumerate(keys, 1):
                print(f"  {idx}. {scenarios[k].name}")
            sub_choice = input(f"Choose scenario (1-{len(keys)}): ").strip()
            try:
                selected_key = keys[int(sub_choice) - 1]
                run_scenario(scenarios[selected_key], step_by_step=True)
            except (ValueError, IndexError):
                print(colorize("Invalid selection.", Colors.RED))
        elif choice == "8":
            custom_matrix_interactive()
        elif choice == "9":
            print("\nGenerating sample JSON payload from Safe scenario...")
            rep = DeadlockSystem(
                allocation=get_scenario("safe").allocation,
                request=get_scenario("safe").request,
                available=get_scenario("safe").available,
                process_names=get_scenario("safe").process_names,
                resource_names=get_scenario("safe").resource_names,
            ).detect_deadlock()
            print(colorize(rep.to_json(indent=2), Colors.CYAN))
            print(colorize("\n[Success] JSON payload is valid and ready for Phase 2 GUI integration.", Colors.GREEN))
        elif choice == "0":
            print("Exiting Deadlock Detection Engine. Good luck with Project Review 1!")
            break
        else:
            print(colorize("Invalid option. Please choose between 0 and 9.", Colors.RED))

        input("\nPress Enter to return to main menu...")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deadlock Detection & Recovery - Phase 1 Core Engine"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all demo scenarios and print a summary scorecard.",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["safe", "deadlocked", "borderline", "circular", "zero_alloc"],
        help="Run a specific scenario by id.",
    )
    parser.add_argument(
        "--step-by-step",
        action="store_true",
        help="Step through algorithm iterations interactively.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the detection report as a JSON payload for GUI integration.",
    )
    parser.add_argument(
        "--custom",
        action="store_true",
        help="Enter custom allocation, request, and available matrices interactively.",
    )

    args = parser.parse_args()

    # Direct flag invocations
    if args.all:
        run_all_scenarios(step_by_step=args.step_by_step, print_json=args.json)
    elif args.scenario:
        sc = get_scenario(args.scenario)
        run_scenario(sc, step_by_step=args.step_by_step, print_json=args.json)
    elif args.custom:
        custom_matrix_interactive()
    else:
        # Default: open user-friendly interactive CLI menu
        interactive_menu()


if __name__ == "__main__":
    main()
