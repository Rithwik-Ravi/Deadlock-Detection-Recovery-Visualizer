"""Unit and property tests for Phase 1: Core Deadlock Detection Engine.

Covers:
- All 5 benchmark scenarios (safe, deadlocked, borderline, circular, zero_alloc)
- Scan-order determinism and rescan behavior
- Input validation (negatives, ragged shapes, invalid types, zero dimensions)
- Edge cases (n=1, zero requests, huge available, 3-process circular chain)
- Tarjan SCC cycle detection
- JSON serialization round-trip
- Property-based test with 500 seeded random systems vs independent BFS oracle
"""

from __future__ import annotations

import collections
import random

import pytest

from core.deadlock_core import DeadlockSystem, DetectionReport
from demo_scenarios import SCENARIOS, get_scenario


class TestBenchmarkScenarios:
    """Validate all 5 benchmark scenarios against exact expected values."""

    def test_scenario_safe(self) -> None:
        scenario = get_scenario("safe")
        system = scenario.to_system()
        report = system.detect()

        assert not report.deadlocked
        assert report.safe_sequence == scenario.expected_sequence
        assert report.deadlocked_processes == []
        assert report.finished_processes == [0, 1, 2, 3, 4]
        assert report.final_work == scenario.expected_final_work
        assert len(report.steps) == 5
        assert report.deadlock_cycles == []

    def test_scenario_deadlocked(self) -> None:
        scenario = get_scenario("deadlocked")
        system = scenario.to_system()
        report = system.detect()

        assert report.deadlocked
        assert report.safe_sequence == []
        assert set(report.deadlocked_processes) == {1, 2, 3, 4}
        assert report.finished_processes == [0]
        assert report.final_work == scenario.expected_final_work
        assert len(report.steps) == 1
        assert len(report.deadlocked_processes) == 4

    def test_scenario_borderline(self) -> None:
        scenario = get_scenario("borderline")
        system = scenario.to_system()
        report = system.detect()

        assert not report.deadlocked
        assert report.safe_sequence == scenario.expected_sequence  # [2, 0, 1]
        assert report.deadlocked_processes == []
        assert report.finished_processes == [0, 1, 2]
        assert report.final_work == scenario.expected_final_work  # [2, 3]

    def test_scenario_circular(self) -> None:
        scenario = get_scenario("circular")
        system = scenario.to_system()
        report = system.detect()

        assert report.deadlocked
        assert report.safe_sequence == []
        assert set(report.deadlocked_processes) == {0, 1}
        assert report.finished_processes == []
        assert len(report.deadlock_cycles) >= 1
        cycle = report.deadlock_cycles[0]
        assert set(cycle) == {0, 1}

    def test_scenario_zero_alloc(self) -> None:
        scenario = get_scenario("zero_alloc")
        system = scenario.to_system()
        report = system.detect()

        # P0 holds nothing at start, so initial Finish[0] MUST be True
        assert report.initial_finish[0] is True
        assert report.deadlocked is True
        assert set(report.deadlocked_processes) == {1, 2}
        assert 0 in report.finished_processes
        assert 0 not in report.deadlocked_processes


class TestAlgorithmDeterminismAndEdgeCases:
    """Validate scan-order determinism, rescan behavior, and edge cases."""

    def test_scan_order_determinism(self) -> None:
        # P0 and P1 are both immediately satisfiable with Available [1]
        # P0 should be picked first because index 0 < index 1
        system = DeadlockSystem(
            available=[1],
            allocation=[[1], [1], [1]],
            request=[[1], [1], [2]],
        )
        report = system.detect()
        assert not report.deadlocked
        assert report.safe_sequence[0] == 0
        assert report.safe_sequence[1] == 1
        assert report.safe_sequence[2] == 2

    def test_single_process_safe(self) -> None:
        system = DeadlockSystem(
            available=[2, 2],
            allocation=[[1, 1]],
            request=[[2, 1]],
        )
        report = system.detect()
        assert not report.deadlocked
        assert report.safe_sequence == [0]
        assert report.final_work == [3, 3]

    def test_single_process_deadlocked(self) -> None:
        system = DeadlockSystem(
            available=[1, 0],
            allocation=[[2, 1]],
            request=[[1, 1]],
        )
        report = system.detect()
        assert report.deadlocked
        assert report.deadlocked_processes == [0]
        assert report.safe_sequence == []

    def test_all_zero_request(self) -> None:
        # When all requests are 0, every process can finish in index order
        system = DeadlockSystem(
            available=[0, 0],
            allocation=[[1, 2], [3, 4], [0, 1]],
            request=[[0, 0], [0, 0], [0, 0]],
        )
        report = system.detect()
        assert not report.deadlocked
        assert report.safe_sequence == [0, 1, 2]
        assert report.final_work == [4, 7]

    def test_huge_available_immediate_finish(self) -> None:
        system = DeadlockSystem(
            available=[100, 100],
            allocation=[[1, 0], [0, 2]],
            request=[[5, 5], [10, 10]],
        )
        report = system.detect()
        assert not report.deadlocked
        assert report.safe_sequence == [0, 1]

    def test_three_process_circular_chain_tarjan(self) -> None:
        # P0 holds R0, needs R1
        # P1 holds R1, needs R2
        # P2 holds R2, needs R0
        system = DeadlockSystem(
            available=[0, 0, 0],
            allocation=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            request=[[0, 1, 0], [0, 0, 1], [1, 0, 0]],
            process_names=["P0", "P1", "P2"],
            resource_names=["R0", "R1", "R2"],
        )
        report = system.detect()
        assert report.deadlocked
        assert set(report.deadlocked_processes) == {0, 1, 2}
        assert len(report.deadlock_cycles) >= 1
        cycle = report.deadlock_cycles[0]
        assert set(cycle) == {0, 1, 2}


class TestInputValidation:
    """Ensure strict validation raises descriptive ValueError for invalid inputs."""

    def test_validation_negative_available(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            DeadlockSystem(
                available=[-1, 0],
                allocation=[[0, 0]],
                request=[[0, 0]],
            )

    def test_validation_negative_allocation(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            DeadlockSystem(
                available=[1, 1],
                allocation=[[-1, 0]],
                request=[[0, 0]],
            )

    def test_validation_negative_request(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            DeadlockSystem(
                available=[1, 1],
                allocation=[[0, 0]],
                request=[[0, -2]],
            )

    def test_validation_ragged_allocation_row(self) -> None:
        with pytest.raises(ValueError, match="expected 2"):
            DeadlockSystem(
                available=[1, 1],
                allocation=[[0, 0, 1]],  # length 3 != 2
                request=[[0, 0]],
            )

    def test_validation_mismatched_request_rows(self) -> None:
        with pytest.raises(ValueError, match="rows"):
            DeadlockSystem(
                available=[1],
                allocation=[[0], [1]],
                request=[[0]],  # 1 row != 2
            )

    def test_validation_boolean_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="not an integer|expected integer"):
            DeadlockSystem(
                available=[True],  # bool is subclass of int in Python, must be rejected
                allocation=[[0]],
                request=[[0]],
            )

    def test_validation_float_rejected(self) -> None:
        with pytest.raises(ValueError, match="not an integer|expected integer"):
            DeadlockSystem(
                available=[1],
                allocation=[[1.5]],
                request=[[0]],
            )

    def test_validation_empty_n_or_m(self) -> None:
        with pytest.raises(ValueError, match="must be at least 1"):
            DeadlockSystem(
                available=[],
                allocation=[],
                request=[],
            )

    def test_validation_custom_names_length(self) -> None:
        with pytest.raises(ValueError, match="process_names"):
            DeadlockSystem(
                available=[1],
                allocation=[[0]],
                request=[[0]],
                process_names=["P0", "P1"],  # length 2 != 1
            )


class TestSerialization:
    """Test JSON serialization and deserialization round-trip."""

    def test_json_round_trip(self) -> None:
        scenario = SCENARIOS["safe"]
        system = scenario.to_system()
        report = system.detect()

        data = report.to_dict()
        reconstructed = DetectionReport.from_dict(data)

        assert reconstructed.deadlocked == report.deadlocked
        assert reconstructed.safe_sequence == report.safe_sequence
        assert reconstructed.deadlocked_processes == report.deadlocked_processes
        assert reconstructed.finished_processes == report.finished_processes
        assert reconstructed.final_work == report.final_work
        assert len(reconstructed.steps) == len(report.steps)
        for s1, s2 in zip(reconstructed.steps, report.steps, strict=True):
            assert s1.candidate == s2.candidate
            assert s1.work_before == s2.work_before
            assert s1.work_after == s2.work_after
            assert s1.explanation == s2.explanation


class TestPropertyRandomOracle:
    """Property-based verification with 500 seeded random systems vs BFS oracle."""

    @staticmethod
    def _bfs_oracle(system: DeadlockSystem) -> set[int]:
        """Independent BFS oracle finding the maximum reachable set of finished processes."""
        n, m = system.n, system.m
        initial_finished = frozenset(
            i for i in range(n) if all(system.allocation[i][j] == 0 for j in range(m))
        )

        visited: set[frozenset[int]] = set()
        queue = collections.deque([initial_finished])
        visited.add(initial_finished)
        max_finished = set(initial_finished)

        while queue:
            curr = queue.popleft()
            if len(curr) > len(max_finished):
                max_finished = set(curr)
            if len(curr) == n:
                return set(range(n))

            # Calculate current available work
            curr_work = list(system.available)
            for i in curr:
                for j in range(m):
                    curr_work[j] += system.allocation[i][j]

            # Find all candidates that can finish next
            for cand in range(n):
                if cand not in curr:
                    if all(system.request[cand][j] <= curr_work[j] for j in range(m)):
                        nxt = curr | {cand}
                        if nxt not in visited:
                            visited.add(nxt)
                            queue.append(nxt)

        return max_finished

    def test_property_500_random_systems(self) -> None:
        rng = random.Random(42)  # Seeded for strict reproducibility

        for trial in range(500):
            n = rng.randint(1, 5)
            m = rng.randint(1, 4)

            available = [rng.randint(0, 3) for _ in range(m)]
            allocation = [[rng.randint(0, 3) for _ in range(m)] for _ in range(n)]
            request = [[rng.randint(0, 4) for _ in range(m)] for _ in range(n)]

            sys = DeadlockSystem(available, allocation, request)
            report = sys.detect()
            oracle_finished = self._bfs_oracle(sys)

            # Assert exact match between greedy detection engine and independent BFS oracle
            assert set(report.finished_processes) == oracle_finished, (
                f"Trial {trial} failed! Engine finished {report.finished_processes}, "
                f"Oracle finished {oracle_finished}."
            )
            assert set(report.deadlocked_processes) == set(range(n)) - oracle_finished
            assert report.deadlocked == (len(report.deadlocked_processes) > 0)
