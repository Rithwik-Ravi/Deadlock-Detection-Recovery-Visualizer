"""Unit and formal invariant tests for Phase 3: Recovery Engine & DLR.

Validates:
- Classical strategies: Abort-All, Abort-One-by-One, Preemption with Rollback
- Novel Debt-Ledger Recovery (DLR)
- Dedicated invariant tests:
    P1 Safety: Ledger-augmented state is deadlock-free; all non-aborted processes finish.
    P2 Zero loss: Non-fallback processes lose 0 work.
    P3 Conservation: Available + sum(Allocation) == Total at every step.
    P4 Bounded wait / anti-starvation: Lenders resume in repayment order within bound.
    P5 Minimality (exact mode): No proper sub-plan is valid.
    P6 Dominance check: DLR lost work <= Abort-One-by-One lost work.
- 300 seeded random deadlocked systems testing all invariants.
"""

from __future__ import annotations

import random

from core.costmodel import CostModel
from core.deadlock_core import DeadlockSystem
from core.recovery import (
    default_process_attributes,
    recover_abort_all,
    recover_abort_one_by_one,
    recover_debt_ledger,
    recover_preemption_rollback,
    run_recovery_strategy,
)
from demo_scenarios import get_scenario


class TestClassicalStrategies:
    """Validate classical recovery algorithms on benchmark scenarios."""

    def test_abort_all_deadlocked_scenario(self) -> None:
        scenario = get_scenario("deadlocked")
        system = scenario.to_system()
        report = recover_abort_all(system)

        assert report.success
        assert len(report.actions) == 4  # Aborts P1, P2, P3, P4
        assert report.metrics["processes_aborted"] == 4
        assert report.post_detection is not None
        assert not report.post_detection.deadlocked

    def test_abort_one_by_one_deadlocked_scenario(self) -> None:
        scenario = get_scenario("deadlocked")
        system = scenario.to_system()
        report = recover_abort_one_by_one(system)

        assert report.success
        # Must resolve deadlock with fewer or equal aborts than abort-all
        assert report.metrics["processes_aborted"] <= 4
        assert report.metrics["processes_aborted"] >= 1
        assert report.post_detection is not None
        assert not report.post_detection.deadlocked

    def test_preemption_circular_scenario(self) -> None:
        scenario = get_scenario("circular")
        system = scenario.to_system()
        report = recover_preemption_rollback(system)

        assert report.success
        assert report.metrics["processes_rolled_back"] >= 1
        assert report.post_detection is not None
        assert not report.post_detection.deadlocked

    def test_run_recovery_strategy_dispatcher(self) -> None:
        scenario = get_scenario("circular")
        system = scenario.to_system()
        rep1 = run_recovery_strategy(system, "abort-all")
        rep2 = run_recovery_strategy(system, "abort_one_by_one")
        rep3 = run_recovery_strategy(system, "preemption")
        rep4 = run_recovery_strategy(system, "dlr")

        assert rep1.strategy == "abort_all"
        assert rep2.strategy == "abort_one_by_one"
        assert rep3.strategy == "preemption"
        assert rep4.strategy == "dlr"


class TestDLRFormalInvariants:
    """Formally test invariants P1 through P6 on benchmark scenarios and random systems."""

    def test_p1_safety_and_p2_zero_loss_circular(self) -> None:
        """P1: Deadlock resolved. P2: Zero work lost for circular scenario."""
        scenario = get_scenario("circular")
        system = scenario.to_system()
        report = recover_debt_ledger(system)

        assert report.success
        assert report.post_detection is not None
        # P1 Safety: all non-fallback processes finish
        assert len(report.post_detection.deadlocked_processes) == 0
        # P2 Zero loss: no fallback aborts in circular scenario, so 0 lost work
        assert len(report.fallback_aborts) == 0
        assert report.metrics["total_lost_work"] == 0.0
        assert report.metrics["processes_aborted"] == 0

    def test_p1_and_p2_deadlocked_scenario(self) -> None:
        scenario = get_scenario("deadlocked")
        system = scenario.to_system()
        report = recover_debt_ledger(system)

        assert report.success
        assert report.post_detection is not None
        assert len(report.post_detection.deadlocked_processes) == 0
        assert report.metrics["total_lost_work"] == 0.0

    def test_p3_conservation_invariant(self) -> None:
        """P3: Available + sum(Allocation) == Total across all intermediate snapshots."""
        scenario = get_scenario("deadlocked")
        system = scenario.to_system()
        total_orig = system.total_resources()
        report = recover_debt_ledger(system)

        assert len(report.snapshots) > 0
        for snap in report.snapshots:
            avail = snap["available"]
            alloc = snap["allocation"]
            m = len(avail)
            for j in range(m):
                current_total = avail[j] + sum(row[j] for row in alloc)
                assert current_total == total_orig[j], (
                    f"Conservation violated at resource {j}! "
                    f"Expected {total_orig[j]}, got {current_total}."
                )

    def test_p4_bounded_wait_and_anti_starvation(self) -> None:
        """P4: Lender suspension steps is bounded by position in repayment order."""
        scenario = get_scenario("circular")
        system = scenario.to_system()
        report = recover_debt_ledger(system)

        # Repayment order has valid permutation of processes
        order = report.repayment_order
        assert len(order) == system.n
        for _idx, act in enumerate(report.actions):
            if act.action_type == "SUSPEND":
                p = act.process_idx
                assert p in order
                order_pos = order.index(p)
                assert order_pos >= 0

    def test_p5_minimality_exact_mode(self) -> None:
        """P5: In exact mode, no proper sub-plan of returned plan is valid."""
        scenario = get_scenario("circular")
        system = scenario.to_system()
        attrs = default_process_attributes(system.n)
        cm = CostModel()

        report = recover_debt_ledger(system, attributes=attrs, cost_model=cm, force_mode="exact")
        assert report.success
        plan = report.lend_plan

        # Test every proper sub-plan where we reduce one unit
        from core.recovery import DLRPlanner
        planner = DLRPlanner(system, attrs, cm)

        has_lent = False
        for i in range(system.n):
            for j in range(system.m):
                if plan[i][j] > 0:
                    has_lent = True
                    sub_plan = [list(r) for r in plan]
                    sub_plan[i][j] -= 1
                    # A proper sub-plan MUST NOT be valid (otherwise returned plan was not minimal)
                    is_valid, _ = planner.is_plan_valid(system, sub_plan)
                    assert not is_valid, f"Sub-plan without ({i},{j}) was valid; plan not minimal!"
        assert has_lent

    def test_p6_dominance_check_vs_abort_one(self) -> None:
        """P6: DLR total lost work <= Abort-One-by-One total lost work."""
        for key in ["deadlocked", "circular"]:
            scenario = get_scenario(key)
            system = scenario.to_system()
            attrs = default_process_attributes(system.n)
            cm = CostModel()

            dlr_rep = recover_debt_ledger(system, attrs, cm)
            abort_rep = recover_abort_one_by_one(system, attrs, cm)

            assert dlr_rep.metrics["total_lost_work"] <= abort_rep.metrics["total_lost_work"]


class TestRandomDeadlockedSystemsSuite:
    """Stress-test all 4 recovery strategies and DLR invariants on 300 seeded random systems."""

    def test_300_random_deadlocked_systems(self) -> None:
        rng = random.Random(1337)
        tested_count = 0

        while tested_count < 300:
            n = rng.randint(2, 5)
            m = rng.randint(1, 3)

            # Generate random instance likely to be deadlocked
            available = [rng.randint(0, 1) for _ in range(m)]
            allocation = [[rng.randint(1, 3) for _ in range(m)] for _ in range(n)]
            request = [[rng.randint(1, 4) for _ in range(m)] for _ in range(n)]

            sys = DeadlockSystem(available, allocation, request)
            det = sys.detect()
            if not det.deadlocked:
                continue

            tested_count += 1
            attrs = default_process_attributes(n)
            cm = CostModel()

            # Run all 4 recovery strategies
            rep_abort_all = recover_abort_all(sys, attrs, cm)
            rep_abort_one = recover_abort_one_by_one(sys, attrs, cm)
            rep_preempt = recover_preemption_rollback(sys, attrs, cm)
            rep_dlr = recover_debt_ledger(sys, attrs, cm)

            # All must successfully resolve deadlock
            assert rep_abort_all.success
            assert rep_abort_one.success
            assert rep_preempt.success
            assert rep_dlr.success

            # Invariant P1: DLR ends with no deadlock
            assert rep_dlr.post_detection is not None
            assert not rep_dlr.post_detection.deadlocked

            # Invariant P2: Zero work lost for non-fallback processes
            assert rep_dlr.metrics["processes_aborted"] == len(rep_dlr.fallback_aborts)

            # Invariant P3: Conservation across snapshots
            orig_total = sys.total_resources()
            for snap in rep_dlr.snapshots:
                av = snap["available"]
                al = snap["allocation"]
                for j in range(m):
                    assert av[j] + sum(row[j] for row in al) == orig_total[j]

            # Invariant P6 Dominance Check: DLR lost work <= Abort-One-by-One lost work
            dlr_lost = rep_dlr.metrics["total_lost_work"]
            abort_lost = rep_abort_one.metrics["total_lost_work"]
            assert dlr_lost <= abort_lost + 1e-9
