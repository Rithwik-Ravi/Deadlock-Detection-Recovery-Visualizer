"""
Deadlock Detection Core Engine (Phase 1)
========================================
Academic Operating Systems Project:
"Deadlock Detection & Recovery - Resource Allocation Graph Visualizer"

This module implements the classic multi-instance resource deadlock detection
algorithm (Silberschatz, Galvin, and Gagne - Operating System Concepts).
It encapsulates input validation, state representations, execution step-tracing,
and structured report generation ready for GUI visualization in Phase 2.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
import copy
import json
import sys

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


@dataclass
class AlgorithmStep:
    """
    Represents a single granular step taken by the deadlock detection algorithm.
    Used for step-by-step playback in the terminal and visual graph updates in Phase 2 GUI.
    """
    step_number: int
    process: str
    process_index: int
    request: List[int]
    work_before: List[int]
    can_satisfy: bool
    allocation_released: List[int]
    work_after: List[int]
    finish_snapshot: Dict[str, bool]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionReport:
    """
    Structured outcome of the deadlock detection algorithm.
    Contains complete execution telemetry, safe sequences, and deadlock identification.
    """
    is_deadlocked: bool
    safe_sequence: List[str]
    deadlocked_processes: List[str]
    initial_work: List[int]
    final_work: List[int]
    initial_finish: Dict[str, bool]
    final_finish: Dict[str, bool]
    steps: List[AlgorithmStep] = field(default_factory=list)
    total_processes: int = 0
    total_resources: int = 0
    process_names: List[str] = field(default_factory=list)
    resource_names: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the report to a JSON-serializable dictionary for Phase 2 GUI consumption."""
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        return data

    def to_json(self, indent: int = 2) -> str:
        """Export report as formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class DeadlockSystem:
    """
    Core engine for deadlock detection in systems with multiple instances of resources.

    Mathematical Representation:
      - n: number of processes (P_0, P_1, ..., P_{n-1})
      - m: number of resource types (R_0, R_1, ..., R_{m-1})
      - Available: 1D vector of length m
      - Allocation: 2D matrix of shape (n x m)
      - Request: 2D matrix of shape (n x m)
    """

    def __init__(
        self,
        allocation: Optional[List[List[int]]] = None,
        request: Optional[List[List[int]]] = None,
        available: Optional[List[int]] = None,
        process_names: Optional[List[str]] = None,
        resource_names: Optional[List[str]] = None,
    ):
        self.allocation: List[List[int]] = []
        self.request: List[List[int]] = []
        self.available: List[int] = []
        self.process_names: List[str] = []
        self.resource_names: List[str] = []
        self.last_report: Optional[DetectionReport] = None

        if allocation is not None and request is not None and available is not None:
            self.set_state(allocation, request, available, process_names, resource_names)

    def set_state(
        self,
        allocation: List[List[int]],
        request: List[List[int]],
        available: List[int],
        process_names: Optional[List[str]] = None,
        resource_names: Optional[List[str]] = None,
    ) -> None:
        """Set or update the system state matrices with deep copies and validate them."""
        self.allocation = copy.deepcopy(allocation)
        self.request = copy.deepcopy(request)
        self.available = copy.deepcopy(available)

        num_processes = len(self.allocation)
        num_resources = len(self.available) if self.available else 0

        # Auto-generate process and resource labels if not explicitly supplied
        if process_names is not None:
            self.process_names = list(process_names)
        else:
            self.process_names = [f"P{i}" for i in range(num_processes)]

        if resource_names is not None:
            self.resource_names = list(resource_names)
        else:
            self.resource_names = [f"R{j}" for j in range(num_resources)]

        self.last_report = None
        self.validate_inputs()

    def validate_inputs(self) -> None:
        """
        Validate all matrices and vectors for academic rigor and mathematical correctness.

        Enforces:
          1. Matrices and vectors are non-empty.
          2. Allocation and Request have matching row counts (processes).
          3. All rows in Allocation and Request have identical column counts (resources).
          4. Length of Available matches the column count of Allocation and Request.
          5. Process and Resource name lists match matrix dimensions.
          6. All matrix/vector entries are non-negative integers.
        """
        if not self.allocation or not self.request or self.available is None:
            raise ValueError("Allocation, Request, and Available vectors must not be empty.")

        n = len(self.allocation)
        if n == 0:
            raise ValueError("System must have at least one process (Allocation rows = 0).")

        if len(self.request) != n:
            raise ValueError(
                f"Row mismatch: Allocation has {n} processes, but Request has {len(self.request)}."
            )

        m = len(self.available)
        if m == 0:
            raise ValueError("System must have at least one resource type (Available length = 0).")

        # Validate resource dimension consistency across all rows
        for i in range(n):
            if len(self.allocation[i]) != m:
                raise ValueError(
                    f"Dimension mismatch in Allocation[{i}]: expected {m} resource types, "
                    f"got {len(self.allocation[i])}."
                )
            if len(self.request[i]) != m:
                raise ValueError(
                    f"Dimension mismatch in Request[{i}]: expected {m} resource types, "
                    f"got {len(self.request[i])}."
                )

        # Validate process and resource name lengths
        if len(self.process_names) != n:
            raise ValueError(
                f"Process names length ({len(self.process_names)}) does not match process count ({n})."
            )
        if len(self.resource_names) != m:
            raise ValueError(
                f"Resource names length ({len(self.resource_names)}) does not match resource count ({m})."
            )

        # Validate non-negative integers
        for j, val in enumerate(self.available):
            if not isinstance(val, int) or val < 0:
                raise ValueError(
                    f"Available[{j}] ('{self.resource_names[j]}') must be a non-negative integer. Got: {val}"
                )

        for i in range(n):
            for j in range(m):
                alloc_val = self.allocation[i][j]
                req_val = self.request[i][j]
                if not isinstance(alloc_val, int) or alloc_val < 0:
                    raise ValueError(
                        f"Allocation[{self.process_names[i]}][{self.resource_names[j]}] "
                        f"must be a non-negative integer. Got: {alloc_val}"
                    )
                if not isinstance(req_val, int) or req_val < 0:
                    raise ValueError(
                        f"Request[{self.process_names[i]}][{self.resource_names[j]}] "
                        f"must be a non-negative integer. Got: {req_val}"
                    )

    def load_demo_scenario(self, name: str) -> None:
        """
        Load a predefined scenario from demo_scenarios.py by scenario name or key.
        """
        from demo_scenarios import get_scenario
        scenario = get_scenario(name)
        self.set_state(
            allocation=scenario.allocation,
            request=scenario.request,
            available=scenario.available,
            process_names=scenario.process_names,
            resource_names=scenario.resource_names,
        )

    def detect_deadlock(self) -> DetectionReport:
        """
        Execute the standard Multi-Instance Resource Deadlock Detection Algorithm.

        Algorithm Mechanics:
          Step 1:
            Initialize Work vector = Available vector copy.
            Initialize Finish[i] boolean array for each process i:
              - Finish[i] = False if process i currently holds resources (Allocation[i] != 0).
              - Finish[i] = True  if process i holds 0 resources (it cannot block others).

          Step 2:
            Search for an index i such that:
              a) Finish[i] == False
              b) Request[i] <= Work (i.e. for all j, Request[i][j] <= Work[j])
            If no such i exists, jump to Step 4.

          Step 3:
            Process i can successfully acquire its needed resources, run to completion,
            and release its currently allocated resources back to the pool:
              Work = Work + Allocation[i]
              Finish[i] = True
            Record this step in the execution trace.
            Repeat from Step 2.

          Step 4:
            If Finish[i] == False for any i, the system is DEADLOCKED.
            Processes with Finish[i] == False are the deadlocked processes.
            If all Finish[i] == True, the system is DEADLOCK-FREE (SAFE).
        """
        self.validate_inputs()

        n = len(self.allocation)
        m = len(self.available)

        # 1. Initialize Work vector as a copy of Available
        work = copy.deepcopy(self.available)
        initial_work = copy.deepcopy(work)

        # 2. Initialize Finish:
        # If Allocation[i] != 0 -> Finish[i] = False; otherwise Finish[i] = True
        finish: List[bool] = []
        for i in range(n):
            holds_resources = any(self.allocation[i][j] > 0 for j in range(m))
            finish.append(not holds_resources)

        initial_finish_dict = {
            self.process_names[i]: finish[i] for i in range(n)
        }

        steps: List[AlgorithmStep] = []
        safe_sequence: List[str] = []
        step_counter = 1

        # 3. Iterative satisfaction loop
        while True:
            found_candidate = False

            # Deterministic scan: find first process that satisfies Request <= Work
            for i in range(n):
                if not finish[i]:
                    # Check vector inequality: Request[i][j] <= Work[j] for all resources j
                    can_satisfy = all(self.request[i][j] <= work[j] for j in range(m))

                    if can_satisfy:
                        p_name = self.process_names[i]
                        work_before = copy.deepcopy(work)
                        alloc_released = copy.deepcopy(self.allocation[i])

                        # Process executes and releases its allocated resources back to Work
                        for j in range(m):
                            work[j] += self.allocation[i][j]

                        finish[i] = True
                        work_after = copy.deepcopy(work)
                        safe_sequence.append(p_name)
                        found_candidate = True

                        explanation = (
                            f"Step {step_counter}: Process '{p_name}' has Request "
                            f"{self.request[i]} <= Work {work_before}. "
                            f"Satisfied! Runs to completion and releases Allocation {alloc_released}. "
                            f"New Work = {work_after}."
                        )

                        step_record = AlgorithmStep(
                            step_number=step_counter,
                            process=p_name,
                            process_index=i,
                            request=copy.deepcopy(self.request[i]),
                            work_before=work_before,
                            can_satisfy=True,
                            allocation_released=alloc_released,
                            work_after=work_after,
                            finish_snapshot={
                                self.process_names[k]: finish[k] for k in range(n)
                            },
                            explanation=explanation,
                        )
                        steps.append(step_record)
                        step_counter += 1
                        break  # Restart loop to check updated Work against all remaining processes

            if not found_candidate:
                # No remaining unfinished process can be satisfied with current Work
                break

        # 4. Deadlock evaluation
        deadlocked_processes = [
            self.process_names[i] for i in range(n) if not finish[i]
        ]
        is_deadlocked = len(deadlocked_processes) > 0

        final_finish_dict = {
            self.process_names[i]: finish[i] for i in range(n)
        }

        if is_deadlocked:
            summary = (
                f"DEADLOCK DETECTED! {len(deadlocked_processes)} process(es) are in a circular "
                f"wait state: {', '.join(deadlocked_processes)}. System cannot make progress."
            )
        else:
            summary = (
                f"SYSTEM IS DEADLOCK-FREE (SAFE). All processes can run to completion. "
                f"Execution Sequence: {' -> '.join(safe_sequence) if safe_sequence else 'None (all zero-allocation)'}."
            )

        report = DetectionReport(
            is_deadlocked=is_deadlocked,
            safe_sequence=safe_sequence,
            deadlocked_processes=deadlocked_processes,
            initial_work=initial_work,
            final_work=work,
            initial_finish=initial_finish_dict,
            final_finish=final_finish_dict,
            steps=steps,
            total_processes=n,
            total_resources=m,
            process_names=self.process_names,
            resource_names=self.resource_names,
            summary=summary,
        )

        self.last_report = report
        return report

    def get_detection_report(self) -> Optional[DetectionReport]:
        """Return the most recently generated detection report or None if not run yet."""
        return self.last_report

    def pretty_print_state(self) -> None:
        """
        Print a clean, aligned tabular view of the Allocation matrix, Request matrix,
        and Available vector for terminal display and academic viva defense.
        """
        n = len(self.allocation)
        m = len(self.available)

        res_header = " ".join(f"{r:>4}" for r in self.resource_names)

        print("\n" + "=" * 65)
        print("          CURRENT RESOURCE ALLOCATION SYSTEM STATE")
        print("=" * 65)

        # Print Available Vector
        avail_str = "  ".join(f"{r}: {val}" for r, val in zip(self.resource_names, self.available))
        print(f"Available Vector: [ {avail_str} ]")
        print("-" * 65)

        # Print Table Headers
        print(f"{'Process':<9} | {'Allocation':^{len(res_header)}} | {'Request':^{len(res_header)}}")
        print(f"{'':<9} | {res_header} | {res_header}")
        print("-" * 65)

        for i in range(n):
            p_name = self.process_names[i]
            alloc_str = " ".join(f"{self.allocation[i][j]:>4}" for j in range(m))
            req_str = " ".join(f"{self.request[i][j]:>4}" for j in range(m))
            print(f"{p_name:<9} | {alloc_str} | {req_str}")

        print("=" * 65 + "\n")

    def print_detection_trace(
        self,
        report: Optional[DetectionReport] = None,
        step_by_step: bool = False,
    ) -> None:
        """
        Print an explanatory, visual trace of the detection algorithm showing
        how resources are requested, compared, allocated, and freed step-by-step.
        """
        rep = report or self.last_report
        if rep is None:
            rep = self.detect_deadlock()

        # Unicode symbols with graceful fallback for legacy terminals
        try:
            CHECK = "✓"
            CROSS = "✗"
            HOURGLASS = "⏳"
            DOWN_ARROW = "↓"
            "✓ ✗ ⏳ ↓".encode(sys.stdout.encoding or "utf-8")
        except Exception:
            CHECK = "[OK]"
            CROSS = "[X]"
            HOURGLASS = "[WAIT]"
            DOWN_ARROW = "v"

        n = len(self.allocation)
        m = len(self.available)

        work = copy.deepcopy(self.available)
        finish = [
            False if any(self.allocation[i][j] > 0 for j in range(m)) else True
            for i in range(n)
        ]
        safe_sequence: List[str] = []

        DIVIDER = "----------------------------------------------------"

        # Note any zero-allocation processes initialized as finished per Step 1b
        zero_allocs = [self.process_names[i] for i in range(n) if finish[i]]
        if zero_allocs:
            print(f"Note: Process(es) {', '.join(zero_allocs)} hold 0 resources.")
            print(f"Initial Status: Marked as Finished (cannot cause circular wait).\n")

        while True:
            # 1. Before every iteration print the current Work vector
            print(DIVIDER)
            print("Current Available Resources (Work)")
            print(DIVIDER)
            print()
            for j in range(m):
                print(f"{self.resource_names[j]} : {work[j]}")
            print()
            print(DIVIDER)
            print()

            found_candidate = False

            # 2. Check unfinished processes
            for i in range(n):
                if not finish[i]:
                    p_name = self.process_names[i]
                    print(f"Checking Process {p_name}...\n")

                    print("Request:")
                    for j in range(m):
                        print(f"{self.resource_names[j]} : {self.request[i][j]}")
                    print()

                    print("Current Work:")
                    for j in range(m):
                        print(f"{self.resource_names[j]} : {work[j]}")
                    print()

                    print("Comparison:")
                    can_satisfy = True
                    insufficient_resources: List[str] = []
                    for j in range(m):
                        req_val = self.request[i][j]
                        work_val = work[j]
                        if req_val <= work_val:
                            print(f"{self.resource_names[j]} : {req_val} <= {work_val} {CHECK}")
                        else:
                            print(f"{self.resource_names[j]} : {req_val} <= {work_val} {CROSS}")
                            can_satisfy = False
                            insufficient_resources.append(self.resource_names[j])
                    print()

                    if can_satisfy:
                        print("Result:")
                        print(f"{CHECK} {p_name} CAN FINISH\n")

                        # Show resources being released
                        print(DIVIDER)
                        print(f"{p_name} HAS FINISHED\n")

                        print(f"Resources currently held by {p_name}:")
                        for j in range(m):
                            print(f"{self.resource_names[j]} : {self.allocation[i][j]}")
                        print()

                        print("Releasing resources...\n")

                        print("Old Work:")
                        for j in range(m):
                            print(f"{self.resource_names[j]} : {work[j]}")
                        print("\n+\n")

                        print("Released:")
                        for j in range(m):
                            print(f"{self.resource_names[j]} : {self.allocation[i][j]}")
                        print("\n=\n")

                        for j in range(m):
                            work[j] += self.allocation[i][j]

                        print("New Work:")
                        for j in range(m):
                            print(f"{self.resource_names[j]} : {work[j]}")
                        print()

                        print(f"{p_name} has released all of its resources back to the system.")
                        print(DIVIDER)
                        print()

                        finish[i] = True
                        safe_sequence.append(p_name)
                        found_candidate = True

                        # Print updated process status
                        print("Processes:")
                        for k in range(n):
                            p_k = self.process_names[k]
                            status_str = f"{CHECK} Finished" if finish[k] else f"{HOURGLASS} Waiting"
                            print(f"{p_k} {status_str}")
                        print()

                        # Print gradual safe sequence
                        print("Current Safe Sequence:")
                        if safe_sequence:
                            print(f"\n{DOWN_ARROW}\n".join(safe_sequence))
                        else:
                            print("(Empty)")
                        print()

                        if step_by_step:
                            try:
                                input("[Press Enter to proceed to next step...] ")
                                print()
                            except (EOFError, KeyboardInterrupt):
                                pass

                        # Restart scan with updated Work vector
                        break
                    else:
                        print("Result:")
                        print(f"{p_name} CANNOT EXECUTE\n")
                        print("Reason:")
                        if len(insufficient_resources) == 1:
                            print(f"Resource {insufficient_resources[0]} is insufficient.\n")
                        else:
                            print(f"Resources {', '.join(insufficient_resources)} are insufficient.\n")

                        if step_by_step:
                            try:
                                input("[Press Enter to check next process...] ")
                                print()
                            except (EOFError, KeyboardInterrupt):
                                pass

            if not found_candidate:
                # No remaining unfinished process can be satisfied
                break

        # 3. Final termination status
        deadlocked = [self.process_names[i] for i in range(n) if not finish[i]]

        if deadlocked:
            print(DIVIDER)
            print("No runnable process found.\n")
            print("Checking remaining processes...\n")

            for i in range(n):
                if not finish[i]:
                    p_name = self.process_names[i]
                    print(f"{p_name} waiting for:")
                    for j in range(m):
                        req_val = self.request[i][j]
                        work_val = work[j]
                        if req_val > work_val:
                            print(f"{self.resource_names[j]} = {req_val}")
                            print(f"Current {self.resource_names[j]} = {work_val}")
                    print()

            print("Since no remaining request can be satisfied, the algorithm terminates.\n")
            print("DEADLOCK DETECTED.\n")
            print("Deadlocked Processes:")
            for p in deadlocked:
                print(p)
            print(DIVIDER)
            print()
        else:
            print(DIVIDER)
            print("All processes have successfully finished!\n")
            print("SYSTEM IS DEADLOCK-FREE (SAFE).\n")
            print("Final Safe Sequence:")
            print(f"\n{DOWN_ARROW}\n".join(safe_sequence))
            print(f"\n(Sequence: {' -> '.join(safe_sequence)})")
            print(DIVIDER)
            print()
