"""FastAPI Application Server for Deadlock Detection & Recovery Visualizer.

Serves the interactive D3.js web visualizer and provides REST endpoints for:
- GET /api/scenarios
- POST /api/detect
- POST /api/recover
- POST /api/compare
- POST /api/benchmark-random (runs 200 random deadlocked systems)
"""

from __future__ import annotations

import os
import random
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.blame import compute_shapley_blame
from core.costmodel import CostModel
from core.deadlock_core import DeadlockSystem
from core.recovery import (
    ProcessAttributes,
    default_process_attributes,
    recover_abort_all,
    recover_abort_one_by_one,
    recover_debt_ledger,
    recover_preemption_rollback,
    run_recovery_strategy,
)
from demo_scenarios import SCENARIOS, get_scenario, list_scenarios

app = FastAPI(
    title="Deadlock Detection & Recovery Visualizer API",
    description="OS BCSE303L Project - Multi-instance detection, D3 RAG, DLR novel recovery",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format validation errors into clear, readable error messages."""
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error: " + "; ".join(errors), "errors": exc.errors()},
    )


class MatrixPayload(BaseModel):
    """Payload representing multi-instance resource system matrices."""

    available: list[int] = Field(..., description="Available vector of length m")
    allocation: list[list[int]] = Field(..., description="Allocation matrix of shape n x m")
    request: list[list[int]] = Field(..., description="Request matrix of shape n x m")
    process_names: list[str] | None = Field(None, description="Optional process labels")
    resource_names: list[str] | None = Field(None, description="Optional resource labels")


class AttributeItem(BaseModel):
    """Per-process attribute payload."""

    priority: int = 5
    progress: float = 0.5
    work_units: int = 100
    rollback_fraction: float = 0.5
    restartable: bool = True
    times_victimized: int = 0


class RecoveryPayload(MatrixPayload):
    """Payload for executing a recovery strategy."""

    strategy: str = Field(
        ..., description="Recovery strategy name: abort_all, abort_one_by_one, preemption, dlr"
    )
    attributes: list[AttributeItem] | None = None
    cost_model: dict[str, Any] | None = None
    blame_lambda: float = 0.5


class ComparePayload(MatrixPayload):
    """Payload for comparing all recovery strategies."""

    attributes: list[AttributeItem] | None = None
    cost_model: dict[str, Any] | None = None
    blame_lambda: float = 0.5


def build_system_or_422(payload: MatrixPayload) -> DeadlockSystem:
    """Construct DeadlockSystem from payload, raising HTTP 422 on validation failure."""
    try:
        return DeadlockSystem(
            available=payload.available,
            allocation=payload.allocation,
            request=payload.request,
            process_names=payload.process_names,
            resource_names=payload.resource_names,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid matrix configuration: {err}",
        ) from err


@app.get("/api/scenarios")
def api_get_scenarios() -> dict[str, Any]:
    """Retrieve all curated benchmark scenarios."""
    summaries = list_scenarios()
    full_scenarios = {k: s.to_dict() for k, s in SCENARIOS.items()}
    return {"summaries": summaries, "scenarios": full_scenarios}


@app.get("/api/scenarios/{key}")
def api_get_scenario_by_key(key: str) -> dict[str, Any]:
    """Retrieve details for a specific benchmark scenario."""
    try:
        scenario = get_scenario(key)
        return scenario.to_dict()
    except KeyError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@app.post("/api/detect")
def api_detect(payload: MatrixPayload) -> dict[str, Any]:
    """Execute Silberschatz multi-instance deadlock detection algorithm."""
    system = build_system_or_422(payload)
    report = system.detect()
    return report.to_dict()


@app.post("/api/recover")
def api_recover(payload: RecoveryPayload) -> dict[str, Any]:
    """Execute selected recovery strategy (abort_all, abort_one_by_one, preemption, dlr)."""
    system = build_system_or_422(payload)

    # Convert attributes
    if payload.attributes:
        attrs = [ProcessAttributes(**item.model_dump()) for item in payload.attributes]
        if len(attrs) != system.n:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"attributes length ({len(attrs)}) != processes ({system.n})",
            )
    else:
        attrs = default_process_attributes(system.n)

    cm = CostModel.from_dict(payload.cost_model) if payload.cost_model else CostModel()

    try:
        report = run_recovery_strategy(
            system=system,
            strategy=payload.strategy,
            attributes=attrs,
            cost_model=cm,
        )
        return report.to_dict()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err


@app.post("/api/compare")
def api_compare(payload: ComparePayload) -> dict[str, Any]:
    """Run all 4 recovery strategies and return comparative cost metrics and rankings."""
    system = build_system_or_422(payload)

    if payload.attributes:
        attrs = [ProcessAttributes(**item.model_dump()) for item in payload.attributes]
        if len(attrs) != system.n:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"attributes length ({len(attrs)}) != processes ({system.n})",
            )
    else:
        attrs = default_process_attributes(system.n)

    cm = CostModel.from_dict(payload.cost_model) if payload.cost_model else CostModel()

    # Initial detection check
    init_report = system.detect()
    if not init_report.deadlocked:
        return {
            "deadlocked": False,
            "message": "System is safe; no recovery needed.",
            "strategies": {},
            "winners": {},
            "blame": {},
        }

    # Execute all 4 strategies
    rep_abort_all = recover_abort_all(system, attrs, cm)
    rep_abort_one = recover_abort_one_by_one(system, attrs, cm)
    rep_preempt = recover_preemption_rollback(system, attrs, cm)
    rep_dlr = recover_debt_ledger(system, attrs, cm, blame_lambda=payload.blame_lambda)

    strategies_data = {
        "abort_all": {
            "name": "Abort-All",
            "metrics": rep_abort_all.metrics,
            "actions_count": len(rep_abort_all.actions),
            "success": rep_abort_all.success,
        },
        "abort_one_by_one": {
            "name": "Abort-One-by-One",
            "metrics": rep_abort_one.metrics,
            "actions_count": len(rep_abort_one.actions),
            "success": rep_abort_one.success,
        },
        "preemption": {
            "name": "Preemption + Rollback",
            "metrics": rep_preempt.metrics,
            "actions_count": len(rep_preempt.actions),
            "success": rep_preempt.success,
        },
        "dlr": {
            "name": "Debt-Ledger Recovery (DLR)",
            "metrics": rep_dlr.metrics,
            "actions_count": len(rep_dlr.actions),
            "success": rep_dlr.success,
            "fallback_aborts": rep_dlr.fallback_aborts,
            "lend_plan": rep_dlr.lend_plan,
            "repayment_order": rep_dlr.repayment_order,
            "ious_count": len(rep_dlr.ledger_entries),
        },
    }

    # Compute winner per metric
    metric_keys = [
        "total_lost_work",
        "processes_aborted",
        "processes_rolled_back",
        "composite_cost",
        "fairness_score",
    ]
    winners: dict[str, str] = {}
    for mk in metric_keys:
        if mk == "fairness_score":
            # Higher is better
            best_strat = max(
                strategies_data.keys(), key=lambda k: strategies_data[k]["metrics"].get(mk, 0.0)
            )
        else:
            # Lower is better
            best_strat = min(
                strategies_data.keys(), key=lambda k: strategies_data[k]["metrics"].get(mk, 999999)
            )
        winners[mk] = best_strat

    # Compute Shapley Blame for deadlocked processes
    blame_info = compute_shapley_blame(system, init_report.deadlocked_processes)

    return {
        "deadlocked": True,
        "strategies": strategies_data,
        "winners": winners,
        "blame": blame_info,
    }


@app.post("/api/benchmark-random")
def api_benchmark_random(count: int = 200) -> dict[str, Any]:
    """Run aggregate benchmarks across random deadlocked systems."""
    rng = random.Random(42)
    sample_size = min(300, max(10, count))

    aggregates = {
        "abort_all": {"lost_work": 0.0, "aborted": 0, "cost": 0.0, "fairness": 0.0},
        "abort_one_by_one": {"lost_work": 0.0, "aborted": 0, "cost": 0.0, "fairness": 0.0},
        "preemption": {"lost_work": 0.0, "aborted": 0, "cost": 0.0, "fairness": 0.0},
        "dlr": {"lost_work": 0.0, "aborted": 0, "cost": 0.0, "fairness": 0.0},
    }

    tested = 0
    while tested < sample_size:
        n = rng.randint(2, 5)
        m = rng.randint(1, 3)
        avail = [rng.randint(0, 1) for _ in range(m)]
        alloc = [[rng.randint(1, 3) for _ in range(m)] for _ in range(n)]
        req = [[rng.randint(1, 4) for _ in range(m)] for _ in range(n)]
        sys = DeadlockSystem(avail, alloc, req)
        det = sys.detect()
        if not det.deadlocked:
            continue

        tested += 1
        attrs = default_process_attributes(n)
        cm = CostModel()

        r_all = recover_abort_all(sys, attrs, cm)
        r_one = recover_abort_one_by_one(sys, attrs, cm)
        r_pre = recover_preemption_rollback(sys, attrs, cm)
        r_dlr = recover_debt_ledger(sys, attrs, cm)

        for strat_key, rep in [
            ("abort_all", r_all),
            ("abort_one_by_one", r_one),
            ("preemption", r_pre),
            ("dlr", r_dlr),
        ]:
            aggregates[strat_key]["lost_work"] += rep.metrics["total_lost_work"]
            aggregates[strat_key]["aborted"] += rep.metrics["processes_aborted"]
            aggregates[strat_key]["cost"] += rep.metrics["composite_cost"]
            aggregates[strat_key]["fairness"] += rep.metrics["fairness_score"]

    # Compute averages
    averages = {}
    for k, v in aggregates.items():
        averages[k] = {
            "avg_lost_work": round(v["lost_work"] / sample_size, 2),
            "avg_aborted": round(v["aborted"] / sample_size, 2),
            "avg_composite_cost": round(v["cost"] / sample_size, 2),
            "avg_fairness_score": round(v["fairness"] / sample_size, 4),
        }

    return {"sample_size": sample_size, "averages": averages}


# Mount static files directory for web frontend
web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
