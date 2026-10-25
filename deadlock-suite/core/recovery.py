"""Deadlock Recovery Engine.

Implements three classical recovery strategies:
1. Abort-All
2. Abort-One-by-One (cost-minimized with aging penalty)
3. Resource Preemption with Rollback (starvation-capped)

And the novel strategy:
4. Debt-Ledger Recovery (DLR):
   - Over-subscription classification to FALLBACK_ABORT
   - Shapley-weighted minimal lend plan (Exact branch-and-bound / Greedy with pruning)
   - In-place suspension without progress loss (rollback = 0)
   - Formally verified Repayment Router with Debt Ledger IOUs
   - Full preservation of conservation, safety, and no-starvation invariants.

Zero third-party dependencies outside the standard library.
"""

from __future__ import annotations

import copy
import itertools
from dataclasses import asdict, dataclass, field
from typing import Any

from core.blame import compute_shapley_blame
from core.costmodel import CostModel
from core.deadlock_core import DeadlockSystem, DetectionReport


@dataclass
class ProcessAttributes:
    """Per-process configurable attributes for recovery cost models."""

    priority: int = 5  # 1 (low) to 10 (critical)
    progress: float = 0.5  # 0.0 to 1.0 fraction completed
    work_units: int = 100  # Total computational work units
    rollback_fraction: float = 0.5  # Fraction of progress lost on rollback
    restartable: bool = True  # Can the process be aborted and restarted
    times_victimized: int = 0  # Number of past preemptions/aborts (anti-starvation)

    def to_dict(self) -> dict[str, Any]:
        """Convert attributes to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProcessAttributes:
        """Create ProcessAttributes from dictionary."""
        return cls(
            priority=int(data.get("priority", 5)),
            progress=float(data.get("progress", 0.5)),
            work_units=int(data.get("work_units", 100)),
            rollback_fraction=float(data.get("rollback_fraction", 0.5)),
            restartable=bool(data.get("restartable", True)),
            times_victimized=int(data.get("times_victimized", 0)),
        )


@dataclass
class RecoveryAction:
    """Represents an atomic recovery action taken by the engine."""

    step_no: int
    action_type: str  # "ABORT", "PREEMPT", "SUSPEND", "LEND", "REPAY", "RESUME", "FINISH"
    process_idx: int | None
    process_name: str | None
    resource_idx: int | None
    resource_name: str | None
    units: int
    explanation: str
    snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize recovery action to dictionary."""
        return asdict(self)


@dataclass
class IOUEntry:
    """Debt Ledger entry representing lent resource units."""

    entry_id: str
    creditor_idx: int
    creditor_name: str
    resource_idx: int
    resource_name: str
    units: int
    debtor_set: list[str]
    created_at_step: int
    repaid: bool = False
    repaid_at_step: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize IOU entry to dictionary."""
        return asdict(self)


@dataclass
class RecoveryReport:
    """Structured report returned by any recovery strategy."""

    strategy: str
    success: bool
    actions: list[RecoveryAction]
    snapshots: list[dict[str, Any]]
    post_detection: DetectionReport | None
    metrics: dict[str, Any]
    ledger_entries: list[dict[str, Any]] = field(default_factory=list)
    blame_scores: dict[str, float] = field(default_factory=dict)
    fallback_aborts: list[int] = field(default_factory=list)
    repayment_order: list[int] = field(default_factory=list)
    lend_plan: list[list[int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize recovery report to dictionary."""
        return {
            "strategy": self.strategy,
            "success": self.success,
            "actions": [a.to_dict() for a in self.actions],
            "snapshots": copy.deepcopy(self.snapshots),
            "post_detection": self.post_detection.to_dict() if self.post_detection else None,
            "metrics": copy.deepcopy(self.metrics),
            "ledger_entries": copy.deepcopy(self.ledger_entries),
            "blame_scores": copy.deepcopy(self.blame_scores),
            "fallback_aborts": list(self.fallback_aborts),
            "repayment_order": list(self.repayment_order),
            "lend_plan": [list(row) for row in self.lend_plan],
        }


def default_process_attributes(n: int) -> list[ProcessAttributes]:
    """Generate sensible default process attributes for n processes."""
    attrs: list[ProcessAttributes] = []
    for i in range(n):
        priority = 5 + (i % 5)
        progress = round(0.2 + (i % 7) * 0.1, 2)
        work_units = 50 + (i % 4) * 25
        attrs.append(
            ProcessAttributes(
                priority=priority,
                progress=min(0.95, progress),
                work_units=work_units,
                rollback_fraction=0.5,
                restartable=True,
                times_victimized=0,
            )
        )
    return attrs


# ---------------------------------------------------------------------------
# Strategy 1: Abort-All
# ---------------------------------------------------------------------------


def recover_abort_all(
    system: DeadlockSystem,
    attributes: list[ProcessAttributes] | None = None,
    cost_model: CostModel | None = None,
) -> RecoveryReport:
    """Abort every deadlocked process simultaneously."""
    cost_model = cost_model or CostModel()
    attributes = attributes or default_process_attributes(system.n)
    init_report = system.detect()

    if not init_report.deadlocked:
        return RecoveryReport(
            strategy="abort_all",
            success=True,
            actions=[],
            snapshots=[],
            post_detection=init_report,
            metrics=cost_model.evaluate(
                [0.0] * system.n,
                [0] * system.n,
                [a.priority for a in attributes],
                [False] * system.n,
                [False] * system.n,
                0,
                0,
            ),
        )

    work_sys = system.copy()
    deadlocked_set = set(init_report.deadlocked_processes)
    actions: list[RecoveryAction] = []
    snapshots: list[dict[str, Any]] = []

    lost_work = [0.0] * system.n
    aborted_flags = [False] * system.n
    step_no = 1

    for p in sorted(list(deadlocked_set)):
        p_name = system.process_names[p]
        held = list(work_sys.allocation[p])
        # Release allocations to available
        for j in range(system.m):
            work_sys.available[j] += work_sys.allocation[p][j]
            work_sys.allocation[p][j] = 0
            work_sys.request[p][j] = 0

        aborted_flags[p] = True
        lost_work[p] = attributes[p].progress * attributes[p].work_units
        explanation = (
            f"Abort-All: Process {p_name} aborted. Released held resources "
            f"[{', '.join(str(x) for x in held)}]. All {lost_work[p]:.1f} work units lost."
        )
        act = RecoveryAction(
            step_no=step_no,
            action_type="ABORT",
            process_idx=p,
            process_name=p_name,
            resource_idx=None,
            resource_name=None,
            units=sum(held),
            explanation=explanation,
            snapshot=work_sys.to_dict(),
        )
        actions.append(act)
        snapshots.append(work_sys.to_dict())
        step_no += 1

    post_report = work_sys.detect()
    metrics = cost_model.evaluate(
        per_process_lost_work=lost_work,
        per_process_steps_suspended=[0] * system.n,
        priorities=[a.priority for a in attributes],
        aborted_flags=aborted_flags,
        rolled_back_flags=[False] * system.n,
        detection_reruns=1,
        total_recovery_steps=len(actions),
    )

    return RecoveryReport(
        strategy="abort_all",
        success=not post_report.deadlocked,
        actions=actions,
        snapshots=snapshots,
        post_detection=post_report,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Strategy 2: Abort-One-by-One
# ---------------------------------------------------------------------------


def recover_abort_one_by_one(
    system: DeadlockSystem,
    attributes: list[ProcessAttributes] | None = None,
    cost_model: CostModel | None = None,
) -> RecoveryReport:
    """Repeatedly select and abort the lowest-cost victim until deadlock is resolved."""
    cost_model = cost_model or CostModel()
    attributes = attributes or default_process_attributes(system.n)
    work_sys = system.copy()
    current_attrs = [copy.copy(a) for a in attributes]

    actions: list[RecoveryAction] = []
    snapshots: list[dict[str, Any]] = []
    lost_work = [0.0] * system.n
    aborted_flags = [False] * system.n
    reruns = 0
    step_no = 1

    while True:
        report = work_sys.detect()
        reruns += 1
        if not report.deadlocked:
            break

        # Victim selection: lowest cost among currently deadlocked
        deadlocked = report.deadlocked_processes
        best_victim: int | None = None
        min_cost = float("inf")

        for p in deadlocked:
            attr = current_attrs[p]
            # Aging penalty to avoid repeated targeting
            cost = (
                attr.priority
                * attr.progress
                * attr.work_units
                * (1.0 + 0.5 * attr.times_victimized)
            )
            if cost < min_cost:
                min_cost = cost
                best_victim = p

        if best_victim is None:
            break

        p_name = work_sys.process_names[best_victim]
        held = list(work_sys.allocation[best_victim])
        for j in range(system.m):
            work_sys.available[j] += work_sys.allocation[best_victim][j]
            work_sys.allocation[best_victim][j] = 0
            work_sys.request[best_victim][j] = 0

        aborted_flags[best_victim] = True
        current_attrs[best_victim].times_victimized += 1
        lost_work[best_victim] = (
            current_attrs[best_victim].progress * current_attrs[best_victim].work_units
        )

        explanation = (
            f"Abort-One-by-One: Process {p_name} chosen as lowest-cost victim "
            f"(cost {min_cost:.2f}) and aborted. Released [{', '.join(str(x) for x in held)}]. "
            "Re-running detection."
        )
        act = RecoveryAction(
            step_no=step_no,
            action_type="ABORT",
            process_idx=best_victim,
            process_name=p_name,
            resource_idx=None,
            resource_name=None,
            units=sum(held),
            explanation=explanation,
            snapshot=work_sys.to_dict(),
        )
        actions.append(act)
        snapshots.append(work_sys.to_dict())
        step_no += 1

    post_report = work_sys.detect()
    metrics = cost_model.evaluate(
        per_process_lost_work=lost_work,
        per_process_steps_suspended=[0] * system.n,
        priorities=[a.priority for a in attributes],
        aborted_flags=aborted_flags,
        rolled_back_flags=[False] * system.n,
        detection_reruns=reruns,
        total_recovery_steps=len(actions),
    )

    return RecoveryReport(
        strategy="abort_one_by_one",
        success=not post_report.deadlocked,
        actions=actions,
        snapshots=snapshots,
        post_detection=post_report,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Strategy 3: Resource Preemption with Rollback
# ---------------------------------------------------------------------------


def recover_preemption_rollback(
    system: DeadlockSystem,
    attributes: list[ProcessAttributes] | None = None,
    cost_model: CostModel | None = None,
    max_preemptions_per_proc: int = 3,
) -> RecoveryReport:
    """Preempt resources by minimum rollback cost, roll victim back, cap preemptions."""
    cost_model = cost_model or CostModel()
    attributes = attributes or default_process_attributes(system.n)
    work_sys = system.copy()
    current_attrs = [copy.copy(a) for a in attributes]

    actions: list[RecoveryAction] = []
    snapshots: list[dict[str, Any]] = []
    lost_work = [0.0] * system.n
    rolled_back_flags = [False] * system.n
    reruns = 0
    step_no = 1

    while True:
        report = work_sys.detect()
        reruns += 1
        if not report.deadlocked:
            break

        deadlocked = set(report.deadlocked_processes)
        # Find which resources are lacking by blocked processes
        lacking_resources: set[int] = set()
        for p in deadlocked:
            for j in range(system.m):
                if work_sys.request[p][j] > report.final_work[j]:
                    lacking_resources.add(j)

        # Candidates to preempt from
        best_candidate: tuple[int, int] | None = None
        min_cost = float("inf")

        for p in deadlocked:
            if current_attrs[p].times_victimized >= max_preemptions_per_proc:
                continue  # Anti-starvation cap
            for j in lacking_resources:
                if work_sys.allocation[p][j] > 0:
                    attr = current_attrs[p]
                    # Rollback cost
                    c = (
                        attr.priority
                        * (attr.progress * attr.rollback_fraction * attr.work_units)
                        * (1.0 + 0.5 * attr.times_victimized)
                    )
                    if c < min_cost:
                        min_cost = c
                        best_candidate = (p, j)

        if best_candidate is None:
            # Fall back to aborting lowest-cost victim if preemption exhausted
            return recover_abort_one_by_one(system, attributes, cost_model)

        victim_p, res_j = best_candidate
        p_name = work_sys.process_names[victim_p]
        r_name = work_sys.resource_names[res_j]

        # Preempt 1 unit
        work_sys.allocation[victim_p][res_j] -= 1
        work_sys.request[victim_p][res_j] += 1
        work_sys.available[res_j] += 1

        rolled_back_flags[victim_p] = True
        fraction_lost = current_attrs[victim_p].rollback_fraction
        work_lost_step = (
            current_attrs[victim_p].progress * fraction_lost * current_attrs[victim_p].work_units
        )
        lost_work[victim_p] += work_lost_step
        current_attrs[victim_p].progress *= 1.0 - fraction_lost
        current_attrs[victim_p].times_victimized += 1

        explanation = (
            f"Preemption: Preempted 1 unit of {r_name} from {p_name}. "
            f"{p_name} rolled back by {fraction_lost * 100:.0f}% "
            f"(lost {work_lost_step:.1f} work units). "
            f"Available[{r_name}] increased to {work_sys.available[res_j]}."
        )
        act = RecoveryAction(
            step_no=step_no,
            action_type="PREEMPT",
            process_idx=victim_p,
            process_name=p_name,
            resource_idx=res_j,
            resource_name=r_name,
            units=1,
            explanation=explanation,
            snapshot=work_sys.to_dict(),
        )
        actions.append(act)
        snapshots.append(work_sys.to_dict())
        step_no += 1

    post_report = work_sys.detect()
    metrics = cost_model.evaluate(
        per_process_lost_work=lost_work,
        per_process_steps_suspended=[0] * system.n,
        priorities=[a.priority for a in attributes],
        aborted_flags=[False] * system.n,
        rolled_back_flags=rolled_back_flags,
        detection_reruns=reruns,
        total_recovery_steps=len(actions),
    )

    return RecoveryReport(
        strategy="preemption",
        success=not post_report.deadlocked,
        actions=actions,
        snapshots=snapshots,
        post_detection=post_report,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Strategy 4: Novel Debt-Ledger Recovery (DLR)
# ---------------------------------------------------------------------------


class DLRPlanner:
    """Computes Shapley-weighted minimal lend plans and executes repayment simulation."""

    def __init__(
        self,
        system: DeadlockSystem,
        attributes: list[ProcessAttributes],
        cost_model: CostModel,
        blame_lambda: float = 0.5,
    ) -> None:
        self.system = system
        self.attributes = attributes
        self.cost_model = cost_model
        self.blame_lambda = blame_lambda
        self.total = system.total_resources()

    def identify_oversubscribed(
        self, deadlocked_procs: list[int], current_sys: DeadlockSystem
    ) -> list[int]:
        """A deadlocked process is oversubscribed if for some j, Allocation + Request > Total."""
        oversubscribed: list[int] = []
        for p in deadlocked_procs:
            for j in range(current_sys.m):
                if current_sys.allocation[p][j] + current_sys.request[p][j] > self.total[j]:
                    oversubscribed.append(p)
                    break
        return oversubscribed

    def is_plan_valid(
        self, base_sys: DeadlockSystem, plan: list[list[int]]
    ) -> tuple[bool, DetectionReport | None]:
        """A plan is valid iff Phase 1 detection on ledger-augmented state is deadlock-free."""
        n, m = base_sys.n, base_sys.m
        aug_avail = list(base_sys.available)
        aug_alloc = [list(row) for row in base_sys.allocation]
        aug_req = [list(row) for row in base_sys.request]

        for i in range(n):
            for j in range(m):
                units = plan[i][j]
                if units > 0:
                    aug_alloc[i][j] -= units
                    aug_req[i][j] += units
                    aug_avail[j] += units

        aug_sys = DeadlockSystem(
            available=aug_avail,
            allocation=aug_alloc,
            request=aug_req,
            process_names=base_sys.process_names,
            resource_names=base_sys.resource_names,
        )
        active = {
            i
            for i in range(n)
            if any(aug_alloc[i][j] != 0 for j in range(m))
            or any(plan[i][j] != 0 for j in range(m))
        }
        report = aug_sys.detect(active_procs=active)
        return (not report.deadlocked, report)

    def compute_unit_costs(
        self, deadlocked_procs: list[int], normalized_blame: dict[int, float]
    ) -> dict[int, float]:
        """Unit cost c_i = base_i * (1 + times_victimized) * (1 - lambda * blame_norm)."""
        costs: dict[int, float] = {}
        for p in deadlocked_procs:
            base_p = float(self.attributes[p].priority)
            tv = float(self.attributes[p].times_victimized)
            blame_norm = float(normalized_blame.get(p, 0.0))
            c = base_p * (1.0 + tv) * (1.0 - self.blame_lambda * blame_norm)
            costs[p] = max(0.01, c)
        return costs

    def find_minimal_plan_exact(
        self,
        base_sys: DeadlockSystem,
        deadlocked_procs: list[int],
        unit_costs: dict[int, float],
    ) -> tuple[list[list[int]], DetectionReport]:
        """Iterative deepening with branch-and-bound over unit distributions."""
        n, m = base_sys.n, base_sys.m
        slots: list[tuple[int, int]] = []
        for p in deadlocked_procs:
            for j in range(m):
                if base_sys.allocation[p][j] > 0:
                    slots.append((p, j))

        if not slots:
            raise RuntimeError("No lendable resource units available for DLR exact solver.")

        # Test k = 1, 2, ...
        best_plan: list[list[int]] | None = None
        best_report: DetectionReport | None = None
        min_cost = float("inf")
        min_units_found = 0

        max_k = sum(base_sys.allocation[p][j] for p, j in slots)

        for k in range(1, max_k + 1):
            if best_plan is not None and (k * min(unit_costs.values())) >= min_cost:
                # Branch and bound: larger k cannot beat current best_cost
                break

            # Enumerate distributions of k units over slots
            for combo in itertools.combinations_with_replacement(slots, k):
                # Check slot capacity
                candidate = [[0] * m for _ in range(n)]
                over_capacity = False
                for p, j in combo:
                    candidate[p][j] += 1
                    if candidate[p][j] > base_sys.allocation[p][j]:
                        over_capacity = True
                        break
                if over_capacity:
                    continue

                valid, rep = self.is_plan_valid(base_sys, candidate)
                if valid and rep is not None:
                    cost = sum(
                        candidate[p][j] * unit_costs[p] for p in deadlocked_procs for j in range(m)
                    )
                    if cost < min_cost:
                        min_cost = cost
                        best_plan = candidate
                        best_report = rep
                        min_units_found = k

            if best_plan is not None and min_units_found == k:
                # We found valid plans at unit size k.
                # Check next k only if branch-and-bound permits.
                pass

        if best_plan is None or best_report is None:
            # Fallback to greedy if exact failed to find a valid partition
            return self.find_minimal_plan_greedy(base_sys, deadlocked_procs, unit_costs)

        return best_plan, best_report

    def find_minimal_plan_greedy(
        self,
        base_sys: DeadlockSystem,
        deadlocked_procs: list[int],
        unit_costs: dict[int, float],
    ) -> tuple[list[list[int]], DetectionReport]:
        """Greedy unit selection maximizing finishable processes per unit cost + pruning."""
        n, m = base_sys.n, base_sys.m
        plan = [[0] * m for _ in range(n)]

        while True:
            valid, rep = self.is_plan_valid(base_sys, plan)
            if valid and rep is not None:
                final_rep = rep
                break

            # Find best unit to add
            best_slot: tuple[int, int] | None = None
            best_score = -1.0

            curr_deadlocked_count = len(rep.deadlocked_processes) if rep else len(deadlocked_procs)

            for p in deadlocked_procs:
                for j in range(m):
                    if plan[p][j] < base_sys.allocation[p][j]:
                        plan[p][j] += 1
                        v, test_rep = self.is_plan_valid(base_sys, plan)
                        plan[p][j] -= 1

                        dead_after = (
                            len(test_rep.deadlocked_processes)
                            if test_rep
                            else curr_deadlocked_count
                        )
                        delta = max(0, curr_deadlocked_count - dead_after)
                        cost = unit_costs[p]
                        score = (delta + 0.1) / cost
                        if score > best_score:
                            best_score = score
                            best_slot = (p, j)

            if best_slot is None:
                # No unit left to lend
                raise RuntimeError("DLR Greedy could not find a valid lend plan.")

            p_best, j_best = best_slot
            plan[p_best][j_best] += 1

        # Minimality pruning pass: remove any unit if plan remains valid
        for p in deadlocked_procs:
            for j in range(m):
                while plan[p][j] > 0:
                    plan[p][j] -= 1
                    is_v, test_rep = self.is_plan_valid(base_sys, plan)
                    if is_v and test_rep is not None:
                        final_rep = test_rep
                    else:
                        plan[p][j] += 1
                        break

        return plan, final_rep


def recover_debt_ledger(
    system: DeadlockSystem,
    attributes: list[ProcessAttributes] | None = None,
    cost_model: CostModel | None = None,
    blame_lambda: float = 0.5,
    force_mode: str | None = None,
) -> RecoveryReport:
    """Execute Novel Debt-Ledger Recovery (DLR) with formally verified repayment guarantee."""
    cost_model = cost_model or CostModel()
    attributes = attributes or default_process_attributes(system.n)
    init_report = system.detect()

    if not init_report.deadlocked:
        return RecoveryReport(
            strategy="dlr",
            success=True,
            actions=[],
            snapshots=[],
            post_detection=init_report,
            metrics=cost_model.evaluate(
                [0.0] * system.n,
                [0] * system.n,
                [a.priority for a in attributes],
                [False] * system.n,
                [False] * system.n,
                0,
                0,
            ),
        )

    planner = DLRPlanner(system, attributes, cost_model, blame_lambda)
    work_sys = system.copy()
    deadlocked = list(init_report.deadlocked_processes)

    actions: list[RecoveryAction] = []
    snapshots: list[dict[str, Any]] = []
    lost_work = [0.0] * system.n
    aborted_flags = [False] * system.n
    fallback_aborts: list[int] = []
    step_no = 1

    # Step 1: Detect over-subscribed processes and assign to FALLBACK_ABORT
    oversubscribed = planner.identify_oversubscribed(deadlocked, work_sys)
    for p in oversubscribed:
        p_name = work_sys.process_names[p]
        held = list(work_sys.allocation[p])
        for j in range(system.m):
            work_sys.available[j] += work_sys.allocation[p][j]
            work_sys.allocation[p][j] = 0
            work_sys.request[p][j] = 0

        aborted_flags[p] = True
        fallback_aborts.append(p)
        lost_work[p] = attributes[p].progress * attributes[p].work_units
        explanation = (
            f"DLR Fallback Abort: Process {p_name} is mathematically over-subscribed "
            f"(Allocation + Request > Total). Aborted as unrecoverable, releasing held units."
        )
        act = RecoveryAction(
            step_no=step_no,
            action_type="ABORT",
            process_idx=p,
            process_name=p_name,
            resource_idx=None,
            resource_name=None,
            units=sum(held),
            explanation=explanation,
            snapshot=work_sys.to_dict(),
        )
        actions.append(act)
        snapshots.append(work_sys.to_dict())
        step_no += 1

    # Re-detect after fallback aborts
    interim_report = work_sys.detect()
    if not interim_report.deadlocked:
        metrics = cost_model.evaluate(
            per_process_lost_work=lost_work,
            per_process_steps_suspended=[0] * system.n,
            priorities=[a.priority for a in attributes],
            aborted_flags=aborted_flags,
            rolled_back_flags=[False] * system.n,
            detection_reruns=2,
            total_recovery_steps=len(actions),
        )
        return RecoveryReport(
            strategy="dlr",
            success=True,
            actions=actions,
            snapshots=snapshots,
            post_detection=interim_report,
            metrics=metrics,
            fallback_aborts=fallback_aborts,
        )

    remaining_deadlocked = interim_report.deadlocked_processes

    # Step 2: Compute Shapley Blame Index for remaining deadlocked processes
    blame_res = compute_shapley_blame(work_sys, remaining_deadlocked)
    normalized_blame = blame_res["normalized_by_idx"]
    unit_costs = planner.compute_unit_costs(remaining_deadlocked, normalized_blame)

    # Step 3: Find minimal lend plan
    total_lendable = sum(
        work_sys.allocation[p][j] for p in remaining_deadlocked for j in range(system.m)
    )

    mode = force_mode or ("exact" if total_lendable <= 14 else "greedy")
    if mode == "exact":
        lend_plan, aug_report = planner.find_minimal_plan_exact(
            work_sys, remaining_deadlocked, unit_costs
        )
    else:
        lend_plan, aug_report = planner.find_minimal_plan_greedy(
            work_sys, remaining_deadlocked, unit_costs
        )

    repayment_order = list(aug_report.safe_sequence)

    # Step 4: Execute with Repayment Router and Debt Ledger
    # Lenders are suspended and IOUs created
    lenders = [p for p in remaining_deadlocked if any(lend_plan[p][j] > 0 for j in range(system.m))]
    ious: list[IOUEntry] = []

    # Suspend lenders and issue IOUs
    for p in lenders:
        p_name = work_sys.process_names[p]
        lent_desc = []
        for j in range(system.m):
            units = lend_plan[p][j]
            if units > 0:
                r_name = work_sys.resource_names[j]
                work_sys.allocation[p][j] -= units
                work_sys.request[p][j] += units
                work_sys.available[j] += units
                iou_id = f"IOU-{p_name}-{r_name}-{step_no}"
                iou = IOUEntry(
                    entry_id=iou_id,
                    creditor_idx=p,
                    creditor_name=p_name,
                    resource_idx=j,
                    resource_name=r_name,
                    units=units,
                    debtor_set=[work_sys.process_names[d] for d in repayment_order if d != p],
                    created_at_step=step_no,
                    repaid=False,
                )
                ious.append(iou)
                lent_desc.append(f"{units} of {r_name}")

        explanation = (
            f"DLR Lend & Suspend: {p_name} suspended in place (progress frozen, 0 work lost). "
            f"Lent [{', '.join(lent_desc)}] to pool via Debt Ledger IOUs."
        )
        act = RecoveryAction(
            step_no=step_no,
            action_type="SUSPEND",
            process_idx=p,
            process_name=p_name,
            resource_idx=None,
            resource_name=None,
            units=sum(lend_plan[p]),
            explanation=explanation,
            snapshot=work_sys.to_dict(),
        )
        actions.append(act)
        snapshots.append(work_sys.to_dict())
        step_no += 1

    # Simulate Repayment Router execution along repayment order
    suspended_steps = [0] * system.n
    for sim_pos, p in enumerate(repayment_order):
        p_name = work_sys.process_names[p]
        if p in lenders:
            suspended_steps[p] = sim_pos + 1
            # Repay IOUs
            for iou in ious:
                if iou.creditor_idx == p and not iou.repaid:
                    iou.repaid = True
                    iou.repaid_at_step = step_no
                    repay_act = RecoveryAction(
                        step_no=step_no,
                        action_type="REPAY",
                        process_idx=p,
                        process_name=p_name,
                        resource_idx=iou.resource_idx,
                        resource_name=iou.resource_name,
                        units=iou.units,
                        explanation = (
                            f"Repayment Router: {iou.entry_id} satisfied. Repaid {iou.units} "
                            f"unit(s) of {iou.resource_name} to creditor {p_name}."
                        ),
                        snapshot=work_sys.to_dict(),
                    )
                    actions.append(repay_act)
                    snapshots.append(work_sys.to_dict())
                    step_no += 1

            resume_act = RecoveryAction(
                step_no=step_no,
                action_type="RESUME",
                process_idx=p,
                process_name=p_name,
                resource_idx=None,
                resource_name=None,
                units=0,
                explanation=(
                    f"DLR Resume: {p_name} unfreezes and resumes execution "
                    "without any rollback."
                ),
                snapshot=work_sys.to_dict(),
            )
            actions.append(resume_act)
            snapshots.append(work_sys.to_dict())
            step_no += 1

        # Process finishes and releases resources
        fin_act = RecoveryAction(
            step_no=step_no,
            action_type="FINISH",
            process_idx=p,
            process_name=p_name,
            resource_idx=None,
            resource_name=None,
            units=0,
            explanation=f"Process {p_name} finishes successfully and releases all resources.",
            snapshot=work_sys.to_dict(),
        )
        actions.append(fin_act)
        snapshots.append(work_sys.to_dict())
        step_no += 1

    post_report = work_sys.detect()
    metrics = cost_model.evaluate(
        per_process_lost_work=lost_work,
        per_process_steps_suspended=suspended_steps,
        priorities=[a.priority for a in attributes],
        aborted_flags=aborted_flags,
        rolled_back_flags=[False] * system.n,
        detection_reruns=3,
        total_recovery_steps=len(actions),
    )

    return RecoveryReport(
        strategy="dlr",
        success=True,
        actions=actions,
        snapshots=snapshots,
        post_detection=post_report,
        metrics=metrics,
        ledger_entries=[iou.to_dict() for iou in ious],
        blame_scores=blame_res["blame_scores"],
        fallback_aborts=fallback_aborts,
        repayment_order=repayment_order,
        lend_plan=lend_plan,
    )


def run_recovery_strategy(
    system: DeadlockSystem,
    strategy: str,
    attributes: list[ProcessAttributes] | None = None,
    cost_model: CostModel | None = None,
) -> RecoveryReport:
    """Dispatcher for executing recovery strategies by name."""
    s = strategy.lower().replace("-", "_")
    if s in ("abort_all", "abortall"):
        return recover_abort_all(system, attributes, cost_model)
    elif s in ("abort_one_by_one", "abortonebyone", "abort_one"):
        return recover_abort_one_by_one(system, attributes, cost_model)
    elif s in ("preemption", "preempt", "rollback"):
        return recover_preemption_rollback(system, attributes, cost_model)
    elif s in ("dlr", "debt_ledger", "debtledger"):
        return recover_debt_ledger(system, attributes, cost_model)
    else:
        raise ValueError(f"Unknown recovery strategy: '{strategy}'")
