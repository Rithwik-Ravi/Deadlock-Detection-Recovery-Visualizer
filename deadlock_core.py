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

    def print_detection_trace(self, report: Optional[DetectionReport] = None) -> None:
        """
        Print an annotated, human-readable trace of the detection algorithm's execution.
        """
        rep = report or self.last_report
        if rep is None:
            rep = self.detect_deadlock()

        print("\n" + "#" * 65)
        print("       DEADLOCK DETECTION ALGORITHM EXECUTION TRACE")
        print("#" * 65)

        # Initial conditions
        init_work_str = ", ".join(f"{r}={v}" for r, v in zip(rep.resource_names, rep.initial_work))
        print(f"1. Initial Work Vector: [ {init_work_str} ]")

        # Initial Finish status
        finish_statuses = [
            f"{p}: {'T' if rep.initial_finish[p] else 'F'}" for p in rep.process_names
        ]
        print(f"2. Initial Finish Array: [ {', '.join(finish_statuses)} ]")
        zero_allocs = [p for p in rep.process_names if rep.initial_finish[p]]
        if zero_allocs:
            print(f"   (Note: {', '.join(zero_allocs)} hold 0 resources -> marked Finish=True initially)")

        print("\n3. Iteration Steps:")
        if not rep.steps:
            print("   -> No process could be scheduled! Work is insufficient for any request.")
        else:
            for s in rep.steps:
                print(f"   [{s.step_number}] Selected Candidate: {s.process}")
                print(f"       * Outstanding Request : {s.request}")
                print(f"       * Work Available       : {s.work_before}")
                print(f"       * Condition Met        : Request <= Work (Satisfied)")
                print(f"       * Released Allocation  : {s.allocation_released}")
                print(f"       * Updated Work Vector  : {s.work_after}")
                finish_str = ", ".join(f"{p}: {'T' if s.finish_snapshot[p] else 'F'}" for p in rep.process_names)
                print(f"       * Finish Vector State  : [ {finish_str} ]")
                print()

        # Final Outcome
        print("4. Final Analysis:")
        final_work_str = ", ".join(f"{r}={v}" for r, v in zip(rep.resource_names, rep.final_work))
        print(f"   * Final Work Vector : [ {final_work_str} ]")
        final_fin_str = ", ".join(f"{p}: {'T' if rep.final_finish[p] else 'F'}" for p in rep.process_names)
        print(f"   * Final Finish State: [ {final_fin_str} ]")

        print("\n" + "-" * 65)
        if rep.is_deadlocked:
            print("   >>> RESULT: SYSTEM IS IN DEADLOCK <<<")
            print(f"   Deadlocked Processes : {rep.deadlocked_processes}")
            if rep.safe_sequence:
                print(f"   Processes that freed : {rep.safe_sequence}")
            else:
                print("   Processes that freed : None")
        else:
            print("   >>> RESULT: SYSTEM IS DEADLOCK-FREE (SAFE) <<<")
            print(f"   Safe Process Sequence: {' -> '.join(rep.safe_sequence)}")
            print("   Deadlocked Processes : None")
        print("-" * 65)
        print(f"Summary: {rep.summary}\n")
