"""Core Deadlock Detection Engine.

Implements the multi-instance deadlock detection algorithm by Silberschatz,
Galvin, and Gagne (Operating System Concepts).
Includes Tarjan's Strongly Connected Components algorithm for identifying
concrete deadlock cycles in the wait-for graph.

Zero external dependencies outside the Python standard library.

"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AlgorithmStep:
    """Represents a single step in the deadlock detection algorithm."""

    step_no: int
    candidate: int
    candidate_name: str
    request: list[int]
    work_before: list[int]
    work_after: list[int]
    finish_snapshot: list[bool]
    explanation: str
    allocated: list[int]

    def to_dict(self) -> dict[str, Any]:
        """Convert step to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlgorithmStep:
        """Create an AlgorithmStep instance from a dictionary."""
        return cls(
            step_no=int(data["step_no"]),
            candidate=int(data["candidate"]),
            candidate_name=str(data["candidate_name"]),
            request=[int(x) for x in data["request"]],
            work_before=[int(x) for x in data["work_before"]],
            work_after=[int(x) for x in data["work_after"]],
            finish_snapshot=[bool(x) for x in data["finish_snapshot"]],
            explanation=str(data["explanation"]),
            allocated=[int(x) for x in data.get("allocated", [])],
        )


@dataclass
class DetectionReport:
    """Structured result of running the deadlock detection algorithm."""

    deadlocked: bool
    safe_sequence: list[int]
    deadlocked_processes: list[int]
    finished_processes: list[int]
    final_work: list[int]
    initial_finish: list[bool]
    steps: list[AlgorithmStep]
    matrices: dict[str, Any]
    resource_names: list[str]
    process_names: list[str]
    wait_for_edges: list[dict[str, Any]] = field(default_factory=list)
    deadlock_cycles: list[list[int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert detection report to a JSON-serializable dictionary."""
        return {
            "deadlocked": self.deadlocked,
            "safe_sequence": list(self.safe_sequence),
            "deadlocked_processes": list(self.deadlocked_processes),
            "finished_processes": list(self.finished_processes),
            "final_work": list(self.final_work),
            "initial_finish": list(self.initial_finish),
            "steps": [s.to_dict() for s in self.steps],
            "matrices": copy.deepcopy(self.matrices),
            "resource_names": list(self.resource_names),
            "process_names": list(self.process_names),
            "wait_for_edges": copy.deepcopy(self.wait_for_edges),
            "deadlock_cycles": copy.deepcopy(self.deadlock_cycles),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DetectionReport:
        """Create a DetectionReport instance from a dictionary."""
        steps = [AlgorithmStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            deadlocked=bool(data["deadlocked"]),
            safe_sequence=[int(x) for x in data.get("safe_sequence", [])],
            deadlocked_processes=[int(x) for x in data.get("deadlocked_processes", [])],
            finished_processes=[int(x) for x in data.get("finished_processes", [])],
            final_work=[int(x) for x in data.get("final_work", [])],
            initial_finish=[bool(x) for x in data.get("initial_finish", [])],
            steps=steps,
            matrices=copy.deepcopy(data.get("matrices", {})),
            resource_names=[str(x) for x in data.get("resource_names", [])],
            process_names=[str(x) for x in data.get("process_names", [])],
            wait_for_edges=copy.deepcopy(data.get("wait_for_edges", [])),
            deadlock_cycles=[[int(i) for i in c] for c in data.get("deadlock_cycles", [])],
        )


class DeadlockSystem:
    """Multi-instance resource deadlock system.

    Parameters
    ----------
    available : List[int]
        Number of available instances of each resource type (length m).
    allocation : List[List[int]]
        Current allocation matrix (n x m), where allocation[i][j] is instances of Rj held by Pi.
    request : List[List[int]]
        Current request matrix (n x m), where request[i][j] is instances of Rj needed by Pi.
    process_names : Optional[List[str]]
        Human-readable names for processes (defaults to P0..Pn-1).
    resource_names : Optional[List[str]]
        Human-readable names for resources (defaults to R0..Rm-1 or A, B, C...).
    """

    def __init__(
        self,
        available: list[int],
        allocation: list[list[int]],
        request: list[list[int]],
        process_names: list[str] | None = None,
        resource_names: list[str] | None = None,
    ) -> None:
        self._validate(available, allocation, request, process_names, resource_names)

        self.n: int = len(allocation)
        self.m: int = len(available)

        self.available: list[int] = [int(x) for x in available]
        self.allocation: list[list[int]] = [[int(x) for x in row] for row in allocation]
        self.request: list[list[int]] = [[int(x) for x in row] for row in request]

        if process_names is not None:
            self.process_names: list[str] = [str(p) for p in process_names]
        else:
            self.process_names = [f"P{i}" for i in range(self.n)]

        if resource_names is not None:
            self.resource_names: list[str] = [str(r) for r in resource_names]
        else:
            if self.m <= 26:
                self.resource_names = [chr(65 + j) for j in range(self.m)]
            else:
                self.resource_names = [f"R{j}" for j in range(self.m)]

    @staticmethod
    def _validate(
        available: Any,
        allocation: Any,
        request: Any,
        process_names: Any | None,
        resource_names: Any | None,
    ) -> None:
        """Validate shapes, non-negativity, types, and dimension constraints."""
        if (
            not isinstance(available, list)
            or not isinstance(allocation, list)
            or not isinstance(request, list)
        ):
            raise ValueError("Available, Allocation, and Request must be lists.")

        n = len(allocation)
        if n < 1:
            raise ValueError("Number of processes (n) must be at least 1.")

        m = len(available)
        if m < 1:
            raise ValueError("Number of resource types (m) must be at least 1.")

        if len(request) != n:
            raise ValueError(f"Allocation has {n} rows but Request has {len(request)} rows.")

        for j, val in enumerate(available):
            if isinstance(val, bool) or not isinstance(val, int):
                raise ValueError(
                    f"Available[{j}] is '{val}' (type {type(val).__name__}), expected integer."
                )
            if val < 0:
                raise ValueError(f"Available[{j}] cannot be negative ({val}).")

        for i in range(n):
            alloc_row = allocation[i]
            req_row = request[i]

            if not isinstance(alloc_row, list):
                raise ValueError(f"Allocation row {i} must be a list.")
            if len(alloc_row) != m:
                raise ValueError(f"Allocation row {i} has length {len(alloc_row)}, expected {m}.")

            if not isinstance(req_row, list):
                raise ValueError(f"Request row {i} must be a list.")
            if len(req_row) != m:
                raise ValueError(f"Request row {i} has length {len(req_row)}, expected {m}.")

            for j in range(m):
                a_val = alloc_row[j]
                if isinstance(a_val, bool) or not isinstance(a_val, int):
                    raise ValueError(f"Allocation[{i}][{j}] is not an integer.")
                if a_val < 0:
                    raise ValueError(f"Allocation[{i}][{j}] cannot be negative ({a_val}).")

                r_val = req_row[j]
                if isinstance(r_val, bool) or not isinstance(r_val, int):
                    raise ValueError(f"Request[{i}][{j}] is not an integer.")
                if r_val < 0:
                    raise ValueError(f"Request[{i}][{j}] cannot be negative ({r_val}).")

        if process_names is not None:
            if not isinstance(process_names, list) or len(process_names) != n:
                raise ValueError(f"process_names must be a list of length {n}.")

        if resource_names is not None:
            if not isinstance(resource_names, list) or len(resource_names) != m:
                raise ValueError(f"resource_names must be a list of length {m}.")

    def total_resources(self) -> list[int]:
        """Compute Total = Available + column sums of Allocation."""
        total = list(self.available)
        for j in range(self.m):
            total[j] += sum(self.allocation[i][j] for i in range(self.n))
        return total

    def copy(self) -> DeadlockSystem:
        """Return a deep copy of this system."""
        return DeadlockSystem(
            available=list(self.available),
            allocation=[list(row) for row in self.allocation],
            request=[list(row) for row in self.request],
            process_names=list(self.process_names),
            resource_names=list(self.resource_names),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize system state to dictionary."""
        return {
            "n": self.n,
            "m": self.m,
            "available": list(self.available),
            "allocation": [list(row) for row in self.allocation],
            "request": [list(row) for row in self.request],
            "process_names": list(self.process_names),
            "resource_names": list(self.resource_names),
            "total_resources": self.total_resources(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeadlockSystem:
        """Construct system from dictionary."""
        return cls(
            available=data["available"],
            allocation=data["allocation"],
            request=data["request"],
            process_names=data.get("process_names"),
            resource_names=data.get("resource_names"),
        )

    def detect(self, active_procs: set[int] | None = None) -> DetectionReport:
        """Run the Silberschatz multi-instance deadlock detection algorithm.

        Algorithm:
        1. Work = Available (copy).
           Finish[i] = False if Allocation[i] != 0 or i in active_procs, else True.
        2. Find lowest index i such that Finish[i] == False and Request[i] <= Work.
           If none found, go to step 4.
        3. Work += Allocation[i], Finish[i] = True, record step, rescan from index 0.
        4. If any Finish[i] == False, system is deadlocked; otherwise safe.
        """
        work = list(self.available)
        # Finish[i] = False if Allocation[i] has any non-zero element or in active_procs, else True
        finish: list[bool] = [
            False
            if (
                any(self.allocation[i][j] != 0 for j in range(self.m))
                or (active_procs is not None and i in active_procs)
            )
            else True
            for i in range(self.n)
        ]
        initial_finish = list(finish)
        safe_sequence: list[int] = []
        steps: list[AlgorithmStep] = []
        step_no = 1

        while True:
            candidate_found = False
            for i in range(self.n):
                if not finish[i]:
                    # Componentwise check: Request[i][j] <= work[j] for all j
                    if all(self.request[i][j] <= work[j] for j in range(self.m)):
                        work_before = list(work)
                        for j in range(self.m):
                            work[j] += self.allocation[i][j]
                        finish[i] = True
                        candidate_found = True
                        safe_sequence.append(i)

                        p_name = self.process_names[i]
                        req_str = f"[{','.join(str(x) for x in self.request[i])}]"
                        wb_str = f"[{','.join(str(x) for x in work_before)}]"
                        rel_str = f"[{','.join(str(x) for x in self.allocation[i])}]"
                        wa_str = f"[{','.join(str(x) for x in work)}]"
                        explanation = (
                            f"{p_name} requests {req_str} <= Work {wb_str}, so {p_name} "
                            f"can finish and releases {rel_str} (Work becomes {wa_str})."
                        )

                        steps.append(
                            AlgorithmStep(
                                step_no=step_no,
                                candidate=i,
                                candidate_name=p_name,
                                request=list(self.request[i]),
                                work_before=work_before,
                                work_after=list(work),
                                finish_snapshot=list(finish),
                                explanation=explanation,
                                allocated=list(self.allocation[i]),
                            )
                        )
                        step_no += 1
                        # Rescan strictly from index 0
                        break

            if not candidate_found:
                break

        deadlocked = any(not f for f in finish)
        deadlocked_processes = [i for i in range(self.n) if not finish[i]]
        finished_processes = [i for i in range(self.n) if finish[i]]

        if deadlocked:
            safe_sequence = []

        # Compute wait-for edges and cycles among deadlocked processes
        wait_for_edges = self._compute_wait_for_edges(deadlocked_processes, work)
        deadlock_cycles = self._find_deadlock_cycles(deadlocked_processes, wait_for_edges)

        matrices = {
            "Available": list(self.available),
            "Allocation": [list(row) for row in self.allocation],
            "Request": [list(row) for row in self.request],
            "Total": self.total_resources(),
        }

        return DetectionReport(
            deadlocked=deadlocked,
            safe_sequence=safe_sequence,
            deadlocked_processes=deadlocked_processes,
            finished_processes=finished_processes,
            final_work=list(work),
            initial_finish=initial_finish,
            steps=steps,
            matrices=matrices,
            resource_names=list(self.resource_names),
            process_names=list(self.process_names),
            wait_for_edges=wait_for_edges,
            deadlock_cycles=deadlock_cycles,
        )

    def _compute_wait_for_edges(
        self, deadlocked_procs: list[int], final_work: list[int]
    ) -> list[dict[str, Any]]:
        """Compute wait-for edges for blocked deadlocked processes.

        For each blocked process Pi in deadlocked_procs, for every resource Rj where
        Request[i][j] > final_work[j], Pi waits on every process Pk that holds units of Rj.
        """
        edges: list[dict[str, Any]] = []

        for i in deadlocked_procs:
            for j in range(self.m):
                needed = self.request[i][j]
                # If unsatisfied with respect to final available work
                if needed > final_work[j]:
                    for k in deadlocked_procs:
                        if k != i and self.allocation[k][j] > 0:
                            edges.append(
                                {
                                    "from_p": i,
                                    "from_name": self.process_names[i],
                                    "to_p": k,
                                    "to_name": self.process_names[k],
                                    "resource_idx": j,
                                    "resource_name": self.resource_names[j],
                                    "units_requested": needed,
                                    "units_held": self.allocation[k][j],
                                }
                            )
        return edges

    def _find_deadlock_cycles(
        self, deadlocked_procs: list[int], wait_for_edges: list[dict[str, Any]]
    ) -> list[list[int]]:
        """Identify concrete cycles among deadlocked processes using Tarjan's SCC algorithm.

        Returns one concrete cycle per non-trivial strongly connected component.
        """
        if not deadlocked_procs or not wait_for_edges:
            return []

        # Build adjacency graph
        adj: dict[int, list[int]] = {p: [] for p in deadlocked_procs}
        for e in wait_for_edges:
            u, v = e["from_p"], e["to_p"]
            if u in adj and v in adj:
                if v not in adj[u]:
                    adj[u].append(v)

        # Tarjan's SCC algorithm
        index = 0
        indices: dict[int, int] = {}
        lowlinks: dict[int, int] = {}
        on_stack: dict[int, bool] = {p: False for p in deadlocked_procs}
        stack: list[int] = []
        sccs: list[list[int]] = []

        def strongconnect(v: int) -> None:
            nonlocal index
            indices[v] = index
            lowlinks[v] = index
            index += 1
            stack.append(v)
            on_stack[v] = True

            for w in adj[v]:
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif on_stack[w]:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc: list[int] = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == v:
                        break
                sccs.append(scc)

        for p in deadlocked_procs:
            if p not in indices:
                strongconnect(p)

        # For each non-trivial SCC, extract one concrete cycle
        cycles: list[list[int]] = []
        for scc in sccs:
            scc_set = set(scc)
            if len(scc) == 1:
                u = scc[0]
                if u in adj[u]:
                    cycles.append([u])
            elif len(scc) > 1:
                # Find cycle using DFS within this SCC
                cycle = self._extract_cycle_dfs(scc[0], scc_set, adj)
                if cycle:
                    cycles.append(cycle)

        return cycles

    @staticmethod
    def _extract_cycle_dfs(start: int, scc_set: set[int], adj: dict[int, list[int]]) -> list[int]:
        """Extract a simple directed cycle within an SCC starting from start."""
        visited: dict[int, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        parent: dict[int, int] = {}
        cycle_found: list[int] = []

        def dfs(u: int) -> bool:
            visited[u] = 1
            for v in adj.get(u, []):
                if v not in scc_set:
                    continue
                if visited.get(v, 0) == 1:
                    # Back edge detected: extract cycle
                    curr = u
                    c = [curr]
                    while curr != v:
                        curr = parent.get(curr, v)
                        c.append(curr)
                    c.reverse()
                    cycle_found.extend(c)
                    return True
                elif visited.get(v, 0) == 0:
                    parent[v] = u
                    if dfs(v):
                        return True
            visited[u] = 2
            return False

        dfs(start)
        return cycle_found
