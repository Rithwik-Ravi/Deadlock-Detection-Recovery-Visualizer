"""Configurable Cost Model and Fairness Evaluator for Deadlock Recovery.

Computes multi-dimensional recovery costs:
- Lost computational work (progress * work_units * loss_fraction)
- Suspension penalty (steps_suspended * priority * epsilon)
- Restart overhead per aborted or rolled-back process
- Total recovery steps and detection reruns
- Fairness score (1 - Gini coefficient of per-process cost)

Standard library only, zero external dependencies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CostModel:
    """Configurable weights and parameters for recovery cost evaluation."""

    weight_lost_work: float = 1.0
    weight_suspension: float = 0.5
    weight_restart: float = 10.0
    weight_reruns: float = 2.0
    epsilon_suspension: float = 0.1
    restart_overhead: float = 15.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize cost model parameters."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostModel:
        """Create CostModel from dictionary."""
        return cls(
            weight_lost_work=float(data.get("weight_lost_work", 1.0)),
            weight_suspension=float(data.get("weight_suspension", 0.5)),
            weight_restart=float(data.get("weight_restart", 10.0)),
            weight_reruns=float(data.get("weight_reruns", 2.0)),
            epsilon_suspension=float(data.get("epsilon_suspension", 0.1)),
            restart_overhead=float(data.get("restart_overhead", 15.0)),
        )

    def calculate_gini(self, costs: list[float]) -> float:
        """Calculate Gini coefficient of per-process costs.

        Returns 0.0 if all costs are equal (perfect equality),
        approaches 1.0 for extreme inequality.
        """
        n = len(costs)
        if n <= 1:
            return 0.0

        total_cost = sum(costs)
        if total_cost <= 1e-12:
            return 0.0  # Zero cost across all processes is perfectly fair

        sorted_costs = sorted(costs)
        # Standard Gini formula: G = (2 * sum(i * y_i) / (n * sum(y))) - (n + 1) / n
        numerator = sum((idx + 1) * val for idx, val in enumerate(sorted_costs))
        gini = (2.0 * numerator) / (n * total_cost) - (n + 1.0) / n
        return max(0.0, min(1.0, gini))

    def evaluate(
        self,
        per_process_lost_work: list[float],
        per_process_steps_suspended: list[int],
        priorities: list[int],
        aborted_flags: list[bool],
        rolled_back_flags: list[bool],
        detection_reruns: int,
        total_recovery_steps: int,
    ) -> dict[str, Any]:
        """Compute aggregate cost metrics and fairness."""
        n = len(per_process_lost_work)

        total_lost_work = sum(per_process_lost_work)
        total_aborted = sum(1 for f in aborted_flags if f)
        total_rolled_back = sum(1 for f in rolled_back_flags if f)

        # Per-process composite costs
        process_costs: list[float] = []
        for i in range(n):
            c_work = per_process_lost_work[i] * self.weight_lost_work
            c_susp = (
                per_process_steps_suspended[i]
                * priorities[i]
                * self.epsilon_suspension
                * self.weight_suspension
            )
            c_rst = (
                self.restart_overhead * self.weight_restart
                if (aborted_flags[i] or rolled_back_flags[i])
                else 0.0
            )
            process_costs.append(c_work + c_susp + c_rst)

        composite_cost = (
            sum(process_costs)
            + (detection_reruns * self.weight_reruns)
            + (total_recovery_steps * 0.5)
        )

        gini = self.calculate_gini(process_costs)
        fairness_score = 1.0 - gini

        return {
            "total_lost_work": round(total_lost_work, 4),
            "processes_aborted": total_aborted,
            "processes_rolled_back": total_rolled_back,
            "total_recovery_steps": total_recovery_steps,
            "detection_reruns": detection_reruns,
            "composite_cost": round(composite_cost, 4),
            "gini_coefficient": round(gini, 4),
            "fairness_score": round(fairness_score, 4),
            "per_process_costs": [round(c, 4) for c in process_costs],
        }
