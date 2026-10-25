"""Unit tests for Game-Theoretic Shapley Blame Index.

Verifies axiomatic properties:
1. Efficiency: sum(phi_i) == v(D) exactly in exact mode.
2. Symmetry: Two processes with identical allocation and requests get equal blame.
3. Null player: A process that contributes nothing to deadlock gets zero blame.
4. Monte Carlo convergence: Monte Carlo approximation is consistent with exact values.
"""

from __future__ import annotations

import pytest

from core.blame import ShapleyBlameEngine, compute_shapley_blame
from core.deadlock_core import DeadlockSystem
from demo_scenarios import get_scenario


class TestShapleyBlameAxioms:
    """Validate game-theoretic Shapley properties."""

    def test_efficiency_axiom_circular_scenario(self) -> None:
        """In circular scenario, v(D) = 2, so phi_0 + phi_1 == 2.0 exactly."""
        scenario = get_scenario("circular")
        system = scenario.to_system()
        report = system.detect()
        assert report.deadlocked

        engine = ShapleyBlameEngine(system, report.deadlocked_processes)
        scores = engine.compute_exact()
        v_d = engine.characteristic_function(frozenset(report.deadlocked_processes))

        assert v_d == 2
        sum_phi = sum(scores.values())
        assert pytest.approx(v_d, abs=1e-9) == sum_phi

    def test_efficiency_axiom_deadlocked_scenario(self) -> None:
        """In classic deadlocked scenario with 4 deadlocked processes, sum(phi_i) == v(D)."""
        scenario = get_scenario("deadlocked")
        system = scenario.to_system()
        report = system.detect()
        assert report.deadlocked

        engine = ShapleyBlameEngine(system, report.deadlocked_processes)
        scores = engine.compute_exact()
        v_d = engine.characteristic_function(frozenset(report.deadlocked_processes))

        sum_phi = sum(scores.values())
        assert pytest.approx(v_d, abs=1e-9) == sum_phi

    def test_symmetry_axiom(self) -> None:
        """Two identical deadlocked processes must receive identical blame scores."""
        # System where P1 and P2 have identical holdings and requests in a circular wait
        system = DeadlockSystem(
            available=[0, 0],
            allocation=[
                [1, 0],  # P0
                [0, 1],  # P1
                [0, 1],  # P2 (identical to P1)
            ],
            request=[
                [0, 1],  # P0
                [1, 0],  # P1
                [1, 0],  # P2 (identical to P1)
            ],
            process_names=["P0", "P1", "P2"],
        )
        report = system.detect()
        assert report.deadlocked

        engine = ShapleyBlameEngine(system, report.deadlocked_processes)
        scores = engine.compute_exact()

        # P1 and P2 are symmetric
        assert pytest.approx(scores[1], abs=1e-9) == scores[2]

    def test_null_player_axiom(self) -> None:
        """A process that does not participate in or cause deadlock gets 0 blame."""
        # P0 holds nothing, requests [0, 0]
        # P1 and P2 are circularly deadlocked
        system = DeadlockSystem(
            available=[0, 0],
            allocation=[
                [0, 0],  # P0 holds nothing
                [1, 0],  # P1
                [0, 1],  # P2
            ],
            request=[
                [0, 0],  # P0 requests nothing
                [0, 1],  # P1
                [1, 0],  # P2
            ],
            process_names=["P0", "P1", "P2"],
        )
        report = system.detect()
        # Initial finish for P0 is True, so only P1 and P2 are deadlocked
        assert set(report.deadlocked_processes) == {1, 2}

        # If we artificially evaluate a coalition including P0
        engine = ShapleyBlameEngine(system, [0, 1, 2])
        scores = engine.compute_exact()
        assert pytest.approx(scores[0], abs=1e-9) == 0.0

    def test_monte_carlo_convergence(self) -> None:
        """Monte Carlo values should approximate exact values within a reasonable bound."""
        scenario = get_scenario("deadlocked")
        system = scenario.to_system()
        report = system.detect()

        engine = ShapleyBlameEngine(system, report.deadlocked_processes)
        exact = engine.compute_exact()
        mc = engine.compute_monte_carlo(samples=3000, seed=123)

        for p in report.deadlocked_processes:
            assert abs(exact[p] - mc[p]) < 0.15

    def test_convenience_function(self) -> None:
        scenario = get_scenario("circular")
        system = scenario.to_system()
        report = system.detect()

        res = compute_shapley_blame(system, report.deadlocked_processes)
        assert res["mode"] == "exact"
        assert "P0" in res["blame_scores"]
        assert "P1" in res["blame_scores"]
