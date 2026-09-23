"""
Unit and Integration Test Suite for Deadlock Core Engine
========================================================
Academic Operating Systems Project:
"Deadlock Detection & Recovery - Resource Allocation Graph Visualizer"

Tests the mathematical integrity of the multi-instance deadlock detection algorithm,
input validation, edge conditions, and structured report serialization.
"""

import unittest
import json
from deadlock_core import DeadlockSystem, DetectionReport, AlgorithmStep
from demo_scenarios import (
    SCENARIO_SAFE,
    SCENARIO_DEADLOCKED,
    SCENARIO_BORDERLINE,
    SCENARIO_CIRCULAR_WAIT,
    SCENARIO_ZERO_ALLOCATION,
    get_scenario,
    get_all_scenarios,
)


class TestDeadlockDetectionEngine(unittest.TestCase):

    def test_safe_scenario(self):
        """Verify that the safe scenario detects no deadlock and generates correct sequence."""
        system = DeadlockSystem(
            allocation=SCENARIO_SAFE.allocation,
            request=SCENARIO_SAFE.request,
            available=SCENARIO_SAFE.available,
            process_names=SCENARIO_SAFE.process_names,
            resource_names=SCENARIO_SAFE.resource_names,
        )
        report = system.detect_deadlock()

        self.assertFalse(report.is_deadlocked)
        self.assertEqual(len(report.deadlocked_processes), 0)
        self.assertEqual(report.safe_sequence, ["P0", "P2", "P1", "P3", "P4"])
        self.assertEqual(len(report.steps), 5)
        # All finish statuses should be True
        for p, fin in report.final_finish.items():
            self.assertTrue(fin, f"Process {p} should be finished in safe scenario")

    def test_deadlocked_scenario(self):
        """Verify that the deadlocked scenario identifies the exact cycle."""
        system = DeadlockSystem(
            allocation=SCENARIO_DEADLOCKED.allocation,
            request=SCENARIO_DEADLOCKED.request,
            available=SCENARIO_DEADLOCKED.available,
            process_names=SCENARIO_DEADLOCKED.process_names,
            resource_names=SCENARIO_DEADLOCKED.resource_names,
        )
        report = system.detect_deadlock()

        self.assertTrue(report.is_deadlocked)
        self.assertEqual(report.safe_sequence, ["P0"])
        self.assertListEqual(
            sorted(report.deadlocked_processes),
            sorted(["P1", "P2", "P3", "P4"]),
        )
        self.assertEqual(len(report.steps), 1)

    def test_borderline_cascade_scenario(self):
        """Verify single process unlock cascade sequence."""
        system = DeadlockSystem(
            allocation=SCENARIO_BORDERLINE.allocation,
            request=SCENARIO_BORDERLINE.request,
            available=SCENARIO_BORDERLINE.available,
            process_names=SCENARIO_BORDERLINE.process_names,
            resource_names=SCENARIO_BORDERLINE.resource_names,
        )
        report = system.detect_deadlock()

        self.assertFalse(report.is_deadlocked)
        self.assertEqual(report.safe_sequence, ["P2", "P0", "P1"])
        self.assertEqual(len(report.deadlocked_processes), 0)

    def test_circular_wait_2_processes(self):
        """Verify classic 2-process circular wait."""
        system = DeadlockSystem(
            allocation=SCENARIO_CIRCULAR_WAIT.allocation,
            request=SCENARIO_CIRCULAR_WAIT.request,
            available=SCENARIO_CIRCULAR_WAIT.available,
            process_names=SCENARIO_CIRCULAR_WAIT.process_names,
            resource_names=SCENARIO_CIRCULAR_WAIT.resource_names,
        )
        report = system.detect_deadlock()

        self.assertTrue(report.is_deadlocked)
        self.assertEqual(len(report.safe_sequence), 0)
        self.assertEqual(sorted(report.deadlocked_processes), ["P0", "P1"])

    def test_zero_allocation_handling(self):
        """Verify that process with 0 allocation is handled per Step 1b of algorithm."""
        system = DeadlockSystem(
            allocation=SCENARIO_ZERO_ALLOCATION.allocation,
            request=SCENARIO_ZERO_ALLOCATION.request,
            available=SCENARIO_ZERO_ALLOCATION.available,
            process_names=SCENARIO_ZERO_ALLOCATION.process_names,
            resource_names=SCENARIO_ZERO_ALLOCATION.resource_names,
        )
        report = system.detect_deadlock()

        # P0 holds 0 resources -> marked True initially
        self.assertTrue(report.initial_finish["P0"])
        self.assertFalse(report.initial_finish["P1"])
        self.assertFalse(report.initial_finish["P2"])
        self.assertFalse(report.is_deadlocked)
        self.assertEqual(report.safe_sequence, ["P2", "P1"])

    def test_all_scenarios_registry(self):
        """Verify all scenarios in registry match their expected deadlock outcome."""
        for key, sc in get_all_scenarios().items():
            system = DeadlockSystem(
                allocation=sc.allocation,
                request=sc.request,
                available=sc.available,
                process_names=sc.process_names,
                resource_names=sc.resource_names,
            )
            rep = system.detect_deadlock()
            self.assertEqual(
                rep.is_deadlocked,
                sc.expected_deadlock,
                f"Scenario '{sc.name}' failed deadlock status expectation.",
            )

    def test_json_serialization(self):
        """Ensure report can be cleanly converted to dictionary and JSON string."""
        system = DeadlockSystem(
            allocation=SCENARIO_SAFE.allocation,
            request=SCENARIO_SAFE.request,
            available=SCENARIO_SAFE.available,
        )
        report = system.detect_deadlock()

        data_dict = report.to_dict()
        self.assertIsInstance(data_dict, dict)
        self.assertIn("steps", data_dict)
        self.assertIn("is_deadlocked", data_dict)
        self.assertIn("safe_sequence", data_dict)

        # Check JSON string roundtrip
        json_str = report.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["is_deadlocked"], False)
        self.assertEqual(len(parsed["steps"]), 5)

    def test_input_validation_dimension_mismatch(self):
        """Check that dimension mismatches raise descriptive ValueErrors."""
        # Row count mismatch
        with self.assertRaises(ValueError):
            DeadlockSystem(
                allocation=[[1, 0], [0, 1]],
                request=[[0, 1]],  # only 1 row
                available=[1, 1],
            )

        # Column count mismatch in Allocation
        with self.assertRaises(ValueError):
            DeadlockSystem(
                allocation=[[1, 0, 0], [0, 1]],  # row 0 has 3, row 1 has 2
                request=[[0, 1], [1, 0]],
                available=[1, 1],
            )

        # Available length mismatch
        with self.assertRaises(ValueError):
            DeadlockSystem(
                allocation=[[1, 0], [0, 1]],
                request=[[0, 1], [1, 0]],
                available=[1, 1, 1],  # 3 resources instead of 2
            )

    def test_input_validation_negative_numbers(self):
        """Check that negative values raise ValueError."""
        with self.assertRaises(ValueError):
            DeadlockSystem(
                allocation=[[-1, 0], [0, 1]],
                request=[[0, 1], [1, 0]],
                available=[1, 1],
            )

        with self.assertRaises(ValueError):
            DeadlockSystem(
                allocation=[[1, 0], [0, 1]],
                request=[[0, -2], [1, 0]],
                available=[1, 1],
            )

        with self.assertRaises(ValueError):
            DeadlockSystem(
                allocation=[[1, 0], [0, 1]],
                request=[[0, 1], [1, 0]],
                available=[1, -1],
            )

    def test_load_demo_scenario_by_name(self):
        """Check loading demo scenario via core method."""
        sys = DeadlockSystem()
        sys.load_demo_scenario("safe")
        report = sys.detect_deadlock()
        self.assertFalse(report.is_deadlocked)
        self.assertEqual(len(report.safe_sequence), 5)


if __name__ == "__main__":
    unittest.main()
