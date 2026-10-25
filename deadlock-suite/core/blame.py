"""Shapley Blame Index for Fair Responsibility Assignment in Deadlocks.

Implements game-theoretic cooperative game formulation for deadlocks:
- Grand coalition: Deadlocked set D
- Characteristic function v(S):
    Processes in D \\ S are removed (their allocations released to Available,
    requests dropped). v(S) is the number of deadlocked processes in the
    reduced system, with v(empty) = 0.
- Shapley value phi_i:
    Average marginal contribution of process i across all coalitional orders.
    Exact memoized subset evaluation for |D| <= 10.
    Monte Carlo sampling (>= 2000 permutations) for |D| > 10.

Zero third-party dependencies outside the standard library.
"""

from __future__ import annotations

import itertools
import math
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.deadlock_core import DeadlockSystem


class ShapleyBlameEngine:
    """Calculates Shapley Blame values for deadlocked processes."""

    def __init__(self, system: DeadlockSystem, deadlocked_procs: list[int]) -> None:
        self.system = system
        self.deadlocked_procs = sorted(list(deadlocked_procs))
        self.d_size = len(self.deadlocked_procs)
        self._v_cache: dict[frozenset[int], int] = {}

    def characteristic_function(self, s: frozenset[int]) -> int:
        """Evaluate v(S) for subset S of deadlocked processes."""
        if not s:
            return 0
        if s in self._v_cache:
            return self._v_cache[s]

        # Processes in D \ S are removed
        s_set = set(s)
        removed_procs = [p for p in self.deadlocked_procs if p not in s_set]

        # Build reduced system
        avail = list(self.system.available)
        alloc = [list(row) for row in self.system.allocation]
        req = [list(row) for row in self.system.request]

        for p in removed_procs:
            for j in range(self.system.m):
                avail[j] += alloc[p][j]
                alloc[p][j] = 0
                req[p][j] = 0

        # Run detection directly
        work = list(avail)
        finish = [
            False if any(alloc[i][j] != 0 for j in range(self.system.m)) else True
            for i in range(self.system.n)
        ]

        while True:
            progress = False
            for i in range(self.system.n):
                if not finish[i]:
                    if all(req[i][j] <= work[j] for j in range(self.system.m)):
                        for j in range(self.system.m):
                            work[j] += alloc[i][j]
                        finish[i] = True
                        progress = True
                        break
            if not progress:
                break

        # Number of deadlocked processes in reduced system
        val = sum(1 for f in finish if not f)
        self._v_cache[s] = val
        return val

    def compute_exact(self) -> dict[int, float]:
        """Compute exact Shapley values using coalitional formula over all 2^|D| subsets."""
        d = self.deadlocked_procs
        n = self.d_size
        if n == 0:
            return {}
        if n == 1:
            val = self.characteristic_function(frozenset(d))
            return {d[0]: float(val)}

        # Precompute v(S) for all subsets of D
        all_subsets = []
        for r in range(n + 1):
            for subset in itertools.combinations(d, r):
                all_subsets.append(frozenset(subset))

        for s in all_subsets:
            self.characteristic_function(s)

        shapley_values: dict[int, float] = {p: 0.0 for p in d}
        factorial_table = [math.factorial(k) for k in range(n + 1)]
        denom = float(factorial_table[n])

        for p in d:
            remaining = [other for other in d if other != p]
            phi_p = 0.0
            for r in range(n):
                weight = (factorial_table[r] * factorial_table[n - r - 1]) / denom
                for subset in itertools.combinations(remaining, r):
                    s_without = frozenset(subset)
                    s_with = frozenset(subset + (p,))
                    v_without = self.characteristic_function(s_without)
                    v_with = self.characteristic_function(s_with)
                    marginal = v_with - v_without
                    phi_p += weight * marginal
            shapley_values[p] = phi_p

        return shapley_values

    def compute_monte_carlo(
        self, samples: int = 2000, seed: int = 42
    ) -> dict[int, float]:
        """Estimate Shapley values via Monte Carlo sampling over random permutations."""
        d = self.deadlocked_procs
        n = self.d_size
        if n == 0:
            return {}

        rng = random.Random(seed)
        marginals: dict[int, float] = {p: 0.0 for p in d}

        for _ in range(samples):
            perm = list(d)
            rng.shuffle(perm)
            current_s: list[int] = []
            v_curr = 0

            for p in perm:
                next_s = frozenset(current_s + [p])
                v_next = self.characteristic_function(next_s)
                marginals[p] += v_next - v_curr
                current_s.append(p)
                v_curr = v_next

        return {p: val / float(samples) for p, val in marginals.items()}

    def calculate(self, seed: int = 42) -> dict[str, Any]:
        """Calculate Shapley blame index (exact if |D| <= 10, otherwise Monte Carlo)."""
        if self.d_size == 0:
            return {
                "blame_scores": {},
                "normalized_blame": {},
                "grand_coalition_value": 0,
                "mode": "trivial",
            }

        if self.d_size <= 10:
            raw_scores = self.compute_exact()
            mode = "exact"
        else:
            raw_scores = self.compute_monte_carlo(samples=2000, seed=seed)
            mode = "monte_carlo"

        v_grand = self.characteristic_function(frozenset(self.deadlocked_procs))

        # Normalize to [0, 1] range for lending cost discount
        max_score = max(raw_scores.values()) if raw_scores else 0.0
        normalized: dict[int, float] = {}
        for p, score in raw_scores.items():
            if max_score > 1e-12:
                normalized[p] = max(0.0, min(1.0, score / max_score))
            else:
                normalized[p] = 0.0

        # Format with string process names for API/UI serialization
        formatted_raw: dict[str, float] = {
            self.system.process_names[p]: round(score, 6) for p, score in raw_scores.items()
        }
        formatted_norm: dict[str, float] = {
            self.system.process_names[p]: round(norm, 6) for p, norm in normalized.items()
        }

        return {
            "blame_scores": formatted_raw,
            "normalized_blame": formatted_norm,
            "raw_scores_by_idx": raw_scores,
            "normalized_by_idx": normalized,
            "grand_coalition_value": v_grand,
            "mode": mode,
        }


def compute_shapley_blame(
    system: DeadlockSystem, deadlocked_procs: list[int]
) -> dict[str, Any]:
    """Helper function to compute Shapley Blame for a given system and deadlocked set."""
    engine = ShapleyBlameEngine(system, deadlocked_procs)
    return engine.calculate()
