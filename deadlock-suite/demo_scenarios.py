"""Curated benchmark scenarios for deadlock detection and recovery.

Includes exact configurations, expected outcomes, and viva notes for:
- safe: Classic Silberschatz et al. benchmark
- deadlocked: Classic benchmark variant with unmet request
- borderline: 3-process cascade requiring exact rescan behavior
- circular: 2-process circular wait (RAG cycle)
- zero_alloc: Process holding 0 units initialized Finish=True
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from core.deadlock_core import DeadlockSystem


@dataclass
class Scenario:
    """Represents a benchmark deadlock scenario."""

    key: str
    title: str
    available: list[int]
    allocation: list[list[int]]
    request: list[list[int]]
    process_names: list[str]
    resource_names: list[str]
    expected_deadlocked: bool
    expected_sequence: list[int]
    expected_deadlocked_processes: list[int]
    expected_finished_processes: list[int]
    expected_final_work: list[int]
    viva_note: str

    def to_system(self) -> DeadlockSystem:
        """Create an executable DeadlockSystem from this scenario."""
        return DeadlockSystem(
            available=list(self.available),
            allocation=[list(row) for row in self.allocation],
            request=[list(row) for row in self.request],
            process_names=list(self.process_names),
            resource_names=list(self.resource_names),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert scenario to dictionary format for API and serialization."""
        return asdict(self)


SCENARIOS: dict[str, Scenario] = {
    "safe": Scenario(
        key="safe",
        title="Classic Silberschatz Benchmark (Safe Cascade)",
        available=[0, 0, 0],
        allocation=[
            [0, 1, 0],  # P0
            [2, 0, 0],  # P1
            [3, 0, 3],  # P2
            [2, 1, 1],  # P3
            [0, 0, 2],  # P4
        ],
        request=[
            [0, 0, 0],  # P0
            [2, 0, 2],  # P1
            [0, 0, 0],  # P2
            [1, 0, 0],  # P3
            [0, 0, 2],  # P4
        ],
        process_names=["P0", "P1", "P2", "P3", "P4"],
        resource_names=["A", "B", "C"],
        expected_deadlocked=False,
        expected_sequence=[0, 2, 1, 3, 4],
        expected_deadlocked_processes=[],
        expected_finished_processes=[0, 1, 2, 3, 4],
        expected_final_work=[7, 2, 6],
        viva_note=(
            "Classic benchmark from Silberschatz, Galvin & Gagne (Section 8.6.2). "
            "Although Available is initially [0,0,0], P0 has request [0,0,0] so it can finish "
            "first, releasing [0,1,0]. Then P2 can finish and releases [3,0,3], enabling P1, "
            "P3, and P4 in cascade. Illustrates why deadlock detection is optimistic: it assumes "
            "processes will finish and release all held resources."
        ),
    ),
    "deadlocked": Scenario(
        key="deadlocked",
        title="Deadlocked Variant (P2 Request Augmented)",
        available=[0, 0, 0],
        allocation=[
            [0, 1, 0],  # P0
            [2, 0, 0],  # P1
            [3, 0, 3],  # P2
            [2, 1, 1],  # P3
            [0, 0, 2],  # P4
        ],
        request=[
            [0, 0, 0],  # P0
            [2, 0, 2],  # P1
            [0, 0, 1],  # P2 (requests 1 of C)
            [1, 0, 0],  # P3
            [0, 0, 2],  # P4
        ],
        process_names=["P0", "P1", "P2", "P3", "P4"],
        resource_names=["A", "B", "C"],
        expected_deadlocked=True,
        expected_sequence=[],
        expected_deadlocked_processes=[1, 2, 3, 4],
        expected_finished_processes=[0],
        expected_final_work=[0, 1, 0],
        viva_note=(
            "Modified benchmark from Silberschatz. P0 completes and releases [0,1,0]. "
            "However, every remaining process (P1, P2, P3, P4) requires resources not currently "
            "available in Work [0,1,0]. Hence, P1..P4 form a deadlocked set. Demonstrates that "
            "a single ungranted unit request can transition an entire system into deadlock."
        ),
    ),
    "borderline": Scenario(
        key="borderline",
        title="Borderline Cascade (Scan-Order Rescan Requirement)",
        available=[0, 1],
        allocation=[
            [0, 1],  # P0
            [1, 1],  # P1
            [1, 0],  # P2
        ],
        request=[
            [1, 1],  # P0
            [1, 2],  # P1
            [0, 1],  # P2
        ],
        process_names=["P0", "P1", "P2"],
        resource_names=["R0", "R1"],
        expected_deadlocked=False,
        expected_sequence=[2, 0, 1],
        expected_deadlocked_processes=[],
        expected_finished_processes=[0, 1, 2],
        expected_final_work=[2, 3],
        viva_note=(
            "3 processes and 2 resources. Initial Work [0,1] only satisfies P2 (Request [0,1]). "
            "When P2 finishes, it releases [1,0], making Work [1,1]. Now P0 (Request [1,1]) can "
            "finish, but only because the algorithm strictly rescans from index 0! P0 releases "
            "[0,1], yielding Work [1,2], allowing P1 to finish. Tests scan-order determinism."
        ),
    ),
    "circular": Scenario(
        key="circular",
        title="Circular Wait (Direct RAG Cycle)",
        available=[0, 0],
        allocation=[
            [1, 0],  # P0 holds R0
            [0, 1],  # P1 holds R1
        ],
        request=[
            [0, 1],  # P0 needs R1
            [1, 0],  # P1 needs R0
        ],
        process_names=["P0", "P1"],
        resource_names=["R0", "R1"],
        expected_deadlocked=True,
        expected_sequence=[],
        expected_deadlocked_processes=[0, 1],
        expected_finished_processes=[],
        expected_final_work=[0, 0],
        viva_note=(
            "Minimal 2-process, 2-resource circular wait: P0 holds R0 and requests R1; "
            "P1 holds R1 and requests R0. Available is [0,0]. Immediate deadlock where zero "
            "processes can finish. Wait-for graph has a direct directed cycle: P0 -> P1 -> P0."
        ),
    ),
    "zero_alloc": Scenario(
        key="zero_alloc",
        title="Zero Allocation Process (Initial Finish=True)",
        available=[0, 0],
        allocation=[
            [0, 0],  # P0 holds nothing
            [1, 0],  # P1 holds R0
            [0, 1],  # P2 holds R1
        ],
        request=[
            [5, 5],  # P0 requests 5 of each (huge unsatisfied request)
            [0, 1],  # P1 requests R1
            [1, 0],  # P2 requests R0
        ],
        process_names=["P0", "P1", "P2"],
        resource_names=["R0", "R1"],
        expected_deadlocked=True,
        expected_sequence=[],
        expected_deadlocked_processes=[1, 2],
        expected_finished_processes=[0],
        expected_final_work=[0, 0],
        viva_note=(
            "Crucial viva question: Why does the detection algorithm initialize Finish[i] = True "
            "if Allocation[i] == 0? Because a process holding no resources cannot cause deadlock "
            "by blocking others! Even though P0 has Request [5,5] exceeding available resources, "
            "P0 is not holding anything, so it is never part of the deadlocked set {P1, P2}."
        ),
    ),
}


def get_scenario(key: str) -> Scenario:
    """Retrieve scenario by key. Raises KeyError if not found."""
    if key not in SCENARIOS:
        valid_keys = ", ".join(SCENARIOS.keys())
        raise KeyError(f"Unknown scenario '{key}'. Valid scenarios are: {valid_keys}")
    return SCENARIOS[key]


def list_scenarios() -> list[dict[str, Any]]:
    """Return summary list of all available scenarios."""
    return [
        {
            "key": s.key,
            "title": s.title,
            "viva_note": s.viva_note,
            "processes": s.process_names,
            "resources": s.resource_names,
            "expected_deadlocked": s.expected_deadlocked,
        }
        for s in SCENARIOS.values()
    ]
