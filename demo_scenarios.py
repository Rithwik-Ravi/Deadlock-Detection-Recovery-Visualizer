"""
Predefined Demonstration Scenarios (Phase 1)
============================================
Academic Operating Systems Project:
"Deadlock Detection & Recovery - Resource Allocation Graph Visualizer"

This module contains curated scenarios for verifying the deadlock detection engine
and presenting in project reviews and academic vivas.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Scenario:
    """
    Encapsulates a complete OS resource allocation scenario with descriptive metadata.
    """
    name: str
    scenario_id: str
    description: str
    viva_notes: str
    allocation: List[List[int]]
    request: List[List[int]]
    available: List[int]
    process_names: List[str]
    resource_names: List[str]
    expected_deadlock: bool
    expected_deadlocked_processes: List[str] = field(default_factory=list)
    expected_safe_sequence: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenario 1: Safe Scenario (Classic Silberschatz Multi-Instance Benchmark)
# ---------------------------------------------------------------------------
SCENARIO_SAFE = Scenario(
    name="Safe Scenario - Complete Execution Sequence",
    scenario_id="safe",
    description=(
        "Standard multi-instance resource system with 5 processes (P0-P4) and "
        "3 resource types (A, B, C). All processes can obtain their requested "
        "resources and complete successfully without deadlock."
    ),
    viva_notes=(
        "Examiner explanation: Initial Work is [0, 0, 0]. Both P0 and P2 have zero "
        "outstanding requests. P0 runs first, releasing resource B. Then P2 runs, "
        "releasing A and C instances. At this point Work is [3, 1, 3], which satisfies "
        "both P1 and P3. Under deterministic lowest-index selection, P1 runs next, followed "
        "by P3 and P4: P0 -> P2 -> P1 -> P3 -> P4 (or P0 -> P2 -> P3 -> P1 -> P4)."
    ),
    allocation=[
        [0, 1, 0],  # P0
        [2, 0, 0],  # P1
        [3, 0, 3],  # P2
        [2, 1, 1],  # P3
        [0, 0, 2],  # P4
    ],
    request=[
        [0, 0, 0],  # P0: needs nothing
        [2, 0, 2],  # P1: needs 2A, 2C
        [0, 0, 0],  # P2: needs nothing
        [1, 0, 0],  # P3: needs 1A
        [0, 0, 2],  # P4: needs 2C
    ],
    available=[0, 0, 0],
    process_names=["P0", "P1", "P2", "P3", "P4"],
    resource_names=["A", "B", "C"],
    expected_deadlock=False,
    expected_deadlocked_processes=[],
    expected_safe_sequence=["P0", "P2", "P1", "P3", "P4"],
)


# ---------------------------------------------------------------------------
# Scenario 2: Deadlocked Scenario (Silberschatz Circular Wait Variation)
# ---------------------------------------------------------------------------
SCENARIO_DEADLOCKED = Scenario(
    name="Deadlocked Scenario - Multi-Process Circular Wait",
    scenario_id="deadlocked",
    description=(
        "Same 5 processes and 3 resources as Scenario 1, except Process P2 now makes "
        "an additional request for 1 instance of resource C (Request: [0, 0, 1]). "
        "Although P0 can finish, no other process can be satisfied, leaving P1, P2, "
        "P3, and P4 deadlocked."
    ),
    viva_notes=(
        "Examiner explanation: P0 runs initially because its request is [0, 0, 0]. "
        "P0 releases [0, 1, 0], bringing Work to [0, 1, 0]. At this point, P1 needs "
        "A and C, P2 needs C, P3 needs A, and P4 needs C. Since Work only has B available, "
        "no further requests can be satisfied. Hence, P1, P2, P3, and P4 form a deadlock."
    ),
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
        [0, 0, 1],  # P2: now requests 1 instance of C!
        [1, 0, 0],  # P3
        [0, 0, 2],  # P4
    ],
    available=[0, 0, 0],
    process_names=["P0", "P1", "P2", "P3", "P4"],
    resource_names=["A", "B", "C"],
    expected_deadlock=True,
    expected_deadlocked_processes=["P1", "P2", "P3", "P4"],
    expected_safe_sequence=["P0"],
)


# ---------------------------------------------------------------------------
# Scenario 3: Borderline / Cascade Scenario (Domino Effect Unlock)
# ---------------------------------------------------------------------------
SCENARIO_BORDERLINE = Scenario(
    name="Borderline Scenario - Single Process Cascade Unlock",
    scenario_id="borderline",
    description=(
        "A 3-process (P0, P1, P2) and 2-resource (R1, R2) system where Available is minimal [0, 1]. "
        "Initially, neither P0 nor P1 can execute. Exactly ONE process (P2) has its request met. "
        "Its completion releases resources that unlock P0, which in turn unlocks P1 in a chain reaction."
    ),
    viva_notes=(
        "Examiner explanation: This illustrates a borderline condition where the system is on the "
        "verge of deadlock. With Work=[0, 1], P0 needs [1, 0] (blocked) and P1 needs [2, 1] (blocked). "
        "Only P2 (needing [0, 1]) can execute. P2's release gives Work=[1, 1], which frees P0. "
        "P0's release gives Work=[2, 2], which finally frees P1. The order P2 -> P0 -> P1 avoids deadlock."
    ),
    allocation=[
        [1, 1],  # P0 holds 1 R1, 1 R2
        [0, 1],  # P1 holds 0 R1, 1 R2
        [1, 0],  # P2 holds 1 R1, 0 R2
    ],
    request=[
        [1, 0],  # P0 needs 1 R1 (blocked initially)
        [2, 1],  # P1 needs 2 R1, 1 R2 (blocked initially)
        [0, 1],  # P2 needs 0 R1, 1 R2 (satisfied by Available [0, 1])
    ],
    available=[0, 1],
    process_names=["P0", "P1", "P2"],
    resource_names=["R1", "R2"],
    expected_deadlock=False,
    expected_deadlocked_processes=[],
    expected_safe_sequence=["P2", "P0", "P1"],
)


# ---------------------------------------------------------------------------
# Scenario 4: Circular Wait (Classic 2-Process Textbook Deadlock)
# ---------------------------------------------------------------------------
SCENARIO_CIRCULAR_WAIT = Scenario(
    name="Circular Wait - Direct 2-Process Deadlock Cycle",
    scenario_id="circular",
    description=(
        "Classic 2-process, 2-resource deadlock. P0 holds R0 and requests R1. "
        "P1 holds R1 and requests R0. Available is [0, 0]. Complete stalemate."
    ),
    viva_notes=(
        "Examiner explanation: This is the fundamental definition of Coffman's circular wait condition. "
        "P0 holds resource R0 and waits for R1 held by P1. P1 holds R1 and waits for R0 held by P0. "
        "Available is [0, 0]. Neither process can make progress; both P0 and P1 are deadlocked."
    ),
    allocation=[
        [1, 0],  # P0 holds R0
        [0, 1],  # P1 holds R1
    ],
    request=[
        [0, 1],  # P0 requests R1
        [1, 0],  # P1 requests R0
    ],
    available=[0, 0],
    process_names=["P0", "P1"],
    resource_names=["R0", "R1"],
    expected_deadlock=True,
    expected_deadlocked_processes=["P0", "P1"],
    expected_safe_sequence=[],
)


# ---------------------------------------------------------------------------
# Scenario 5: Zero-Allocation Process Edge Case
# ---------------------------------------------------------------------------
SCENARIO_ZERO_ALLOCATION = Scenario(
    name="Zero Allocation - Boundary Condition Handling",
    scenario_id="zero_alloc",
    description=(
        "Process P0 holds 0 resources of all types (Allocation = [0, 0]). "
        "According to Step 1b of the detection algorithm, P0 is marked Finish[0] = True "
        "from the start because it holds no resources and cannot contribute to a circular wait."
    ),
    viva_notes=(
        "Examiner explanation: Demonstrates algorithmic accuracy regarding boundary conditions. "
        "A process with 0 allocation does not hold any resources that another process might wait for. "
        "Hence, Step 1b initializes Finish[i]=True for such processes, preventing false deadlock reporting."
    ),
    allocation=[
        [0, 0],  # P0 holds nothing
        [1, 0],  # P1 holds R0
        [0, 1],  # P2 holds R1
    ],
    request=[
        [1, 1],  # P0 requests R0, R1
        [0, 1],  # P1 requests R1
        [0, 0],  # P2 requests nothing
    ],
    available=[0, 0],
    process_names=["P0", "P1", "P2"],
    resource_names=["R0", "R1"],
    expected_deadlock=False,
    expected_deadlocked_processes=[],
    expected_safe_sequence=["P2", "P1"],
)


# Registry of all demo scenarios
ALL_SCENARIOS: Dict[str, Scenario] = {
    "safe": SCENARIO_SAFE,
    "deadlocked": SCENARIO_DEADLOCKED,
    "borderline": SCENARIO_BORDERLINE,
    "circular": SCENARIO_CIRCULAR_WAIT,
    "zero_alloc": SCENARIO_ZERO_ALLOCATION,
}


def get_scenario(key: str) -> Scenario:
    """Retrieve a scenario by key or raise KeyError with available options."""
    normalized_key = key.strip().lower()
    if normalized_key in ALL_SCENARIOS:
        return ALL_SCENARIOS[normalized_key]

    # Also search by partial name match
    for k, sc in ALL_SCENARIOS.items():
        if normalized_key in sc.name.lower():
            return sc

    valid = ", ".join(ALL_SCENARIOS.keys())
    raise KeyError(f"Unknown scenario '{key}'. Valid options are: {valid}")


def get_all_scenarios() -> Dict[str, Scenario]:
    """Return all demo scenarios."""
    return ALL_SCENARIOS


def list_scenario_names() -> List[str]:
    """Return list of available scenario keys."""
    return list(ALL_SCENARIOS.keys())
