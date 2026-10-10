"""Fleet scheduler: choose when each robot works, using the envelope timeline.

Given each robot's feasible scale per candidate start (from ``Envelope.timeline``),
a mixed-integer program picks non-overlapping work blocks that maximise completed
work, subject to a rest gap after each block and a limit on concurrent robots.
A naive fixed-shift schedule is evaluated against the same envelope so the benefit
(and the number of at-risk blocks the naive plan contains) is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from pydantic import BaseModel
from scipy.optimize import Bounds, LinearConstraint, milp

from .models import Timeline


class Block(BaseModel):
    robot: str
    start_utc: str
    scale: float
    work_hours: float
    age_equiv_h: float = 0.0


class Plan(BaseModel):
    blocks: list[Block]
    completed_work_h: float
    demand_work_h: float
    status: str
    age_equiv_h: float = 0.0


class Comparison(BaseModel):
    dhill: Plan
    naive: Plan
    naive_at_risk_blocks: int
    naive_total_blocks: int
    dhill_at_risk_blocks: int = 0
    ageing_blind: Plan | None = None


@dataclass
class PlannerSpec:
    block_h: float
    rest_h: float = 0.5
    max_concurrent: int | None = None
    demand_work_h: float = 1e9
    time_penalty: float = 1e-4
    age_penalty: float = 0.02  # work-hours given up per battery-ageing hour (25 degC equivalent)


def _slots_per(hours: float, step_min: float) -> int:
    return max(1, int(round(hours * 60.0 / step_min)))


def plan_fleet(timelines: dict[str, Timeline], spec: PlannerSpec) -> Plan:
    """Solve the block-scheduling MILP. ``timelines`` maps robot id to its timeline."""
    robots = list(timelines)
    n_t = len(next(iter(timelines.values())).slots)
    step = next(iter(timelines.values())).step_min
    bl = _slots_per(spec.block_h, step)
    gap = _slots_per(spec.rest_h, step) if spec.rest_h > 0 else 0
    nr = len(robots)
    n_x = nr * n_t
    # variables: x[r,t] binary, then z (completed work)
    w = np.array([[s.scale * spec.block_h for s in timelines[r].slots] for r in robots])
    c = np.zeros(n_x + 1)
    age = np.array([[s.age_equiv_h for s in timelines[r].slots] for r in robots])
    c[:n_x] = (
        spec.time_penalty * np.arange(n_t)[None, :].repeat(nr, 0) + spec.age_penalty * age
    ).ravel() * (w > 0).ravel()
    c[n_x] = -1.0
    rows, lo, hi = [], [], []
    for r in range(nr):
        for t in range(n_t):
            row = np.zeros(n_x + 1)
            for u in range(t, min(n_t, t + bl + gap)):
                row[r * n_t + u] = 1.0
            rows.append(row)
            lo.append(0)
            hi.append(1)
    if spec.max_concurrent is not None:
        for t in range(n_t):
            row = np.zeros(n_x + 1)
            for r in range(nr):
                for u in range(max(0, t - bl + 1), t + 1):
                    row[r * n_t + u] = 1.0
            rows.append(row)
            lo.append(0)
            hi.append(spec.max_concurrent)
    row = np.zeros(n_x + 1)
    row[:n_x] = -w.ravel()
    row[n_x] = 1.0
    rows.append(row)  # z - sum(w x) <= 0
    lo.append(-np.inf)
    hi.append(0)
    ub = np.ones(n_x + 1)
    ub[:n_x] = (w.ravel() > 0).astype(float)
    ub[n_x] = spec.demand_work_h
    integrality = np.ones(n_x + 1)
    integrality[n_x] = 0
    res = milp(
        c,
        constraints=LinearConstraint(np.array(rows), lo, hi),
        integrality=integrality,
        bounds=Bounds(np.zeros(n_x + 1), ub),
    )
    if res.x is None:
        return Plan(
            blocks=[], completed_work_h=0.0, demand_work_h=spec.demand_work_h, status=res.message
        )
    x = np.round(res.x[:n_x]).reshape(nr, n_t)
    blocks = [
        Block(
            robot=robots[r],
            start_utc=timelines[robots[r]].slots[t].start_utc,
            scale=timelines[robots[r]].slots[t].scale,
            work_hours=float(w[r, t]),
            age_equiv_h=float(age[r, t]),
        )
        for r in range(nr)
        for t in range(n_t)
        if x[r, t] > 0.5
    ]
    blocks.sort(key=lambda b: (b.start_utc, b.robot))
    done = float(sum(b.work_hours for b in blocks))
    return Plan(
        blocks=blocks,
        completed_work_h=round(min(done, spec.demand_work_h), 3),
        demand_work_h=spec.demand_work_h,
        status="optimal" if res.success else str(res.message),
        age_equiv_h=round(float(sum(b.age_equiv_h for b in blocks)), 3),
    )


def naive_shift(
    timelines: dict[str, Timeline],
    spec: PlannerSpec,
    shift_start_hour: float,
    shift_end_hour: float,
    local_offset_h: float,
) -> tuple[Plan, int]:
    """Back-to-back full-speed blocks during a fixed local shift, ignoring the envelope.

    A block whose envelope scale is below 1.0 is *at risk*: it would breach a limit
    at the risk quantile. Its work is counted as lost in the naive tally.
    """
    blocks: list[Block] = []
    at_risk = 0
    for rid, tl in timelines.items():
        step = tl.step_min
        bl = _slots_per(spec.block_h, step)
        gap = _slots_per(spec.rest_h, step) if spec.rest_h > 0 else 0
        t = 0
        while t < len(tl.slots):
            s = tl.slots[t]
            hour = (
                int(s.start_utc[11:13]) + int(s.start_utc[14:16]) / 60.0 + local_offset_h
            ) % 24.0
            if shift_start_hour <= hour < shift_end_hour:
                ok = s.scale >= 0.999
                if not ok:
                    at_risk += 1
                blocks.append(
                    Block(
                        robot=rid,
                        start_utc=s.start_utc,
                        scale=1.0 if ok else 0.0,
                        work_hours=spec.block_h if ok else 0.0,
                    )
                )
                t += bl + gap
            else:
                t += 1
    done = float(sum(b.work_hours for b in blocks))
    return Plan(
        blocks=blocks,
        completed_work_h=round(min(done, spec.demand_work_h), 3),
        demand_work_h=spec.demand_work_h,
        status="naive",
    ), at_risk


def compare(
    timelines: dict[str, Timeline],
    spec: PlannerSpec,
    shift=(8.0, 17.0),
    local_offset_h: float = 4.0,
) -> Comparison:
    d = plan_fleet(timelines, spec)
    n, risk = naive_shift(timelines, spec, shift[0], shift[1], local_offset_h)
    blind = plan_fleet(timelines, replace(spec, age_penalty=0.0))
    return Comparison(
        dhill=d,
        naive=n,
        naive_at_risk_blocks=risk,
        naive_total_blocks=len(n.blocks),
        ageing_blind=blind,
    )
