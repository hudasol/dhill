from __future__ import annotations

import json

import numpy as np
import pytest

from dhill import cli
from dhill.calibrate import calibrate, load_telemetry_csv, save_telemetry_csv, synthetic_telemetry
from dhill.envelope import EngineConfig, Envelope
from dhill.planner import PlannerSpec, compare, plan_fleet
from dhill.profiles.loader import load_builtin
from dhill.weather import synthetic_weather


@pytest.fixture(scope="module")
def timelines():
    w = synthetic_weather("abu_dhabi", "summer_clear", days=2)
    out = {}
    for rid in ("ugv_medium_inspection", "sidewalk_delivery_robot"):
        e = Envelope(load_builtin(rid), w, EngineConfig(n_mc=16))
        out[rid] = e.timeline(
            1.0, "drive", 30.0, first_utc="2026-08-05T00:00", last_utc="2026-08-05T20:00"
        )
    return out


def test_plan_respects_rest_and_concurrency(timelines):
    spec = PlannerSpec(block_h=1.0, rest_h=0.5, max_concurrent=1, demand_work_h=100.0)
    plan = plan_fleet(timelines, spec)
    assert plan.blocks
    starts = sorted((np.datetime64(b.start_utc[:-1]), b.robot) for b in plan.blocks)
    # one robot at a time: consecutive starts at least one block apart
    for (a, _), (b, _) in zip(starts, starts[1:], strict=False):
        assert (b - a) >= np.timedelta64(3600, "s")
    for rid in timelines:
        mine = [t for t, r in starts if r == rid]
        for a, b in zip(mine, mine[1:], strict=False):
            assert (b - a) >= np.timedelta64(5400, "s")


def test_plan_never_uses_parked_slots(timelines):
    plan = plan_fleet(timelines, PlannerSpec(block_h=1.0, demand_work_h=100.0))
    scale = {(r, s.start_utc): s.scale for r, tl in timelines.items() for s in tl.slots}
    assert all(scale[(b.robot, b.start_utc)] > 0 for b in plan.blocks)


def test_dhill_plan_beats_naive_and_has_no_risk(timelines):
    c = compare(timelines, PlannerSpec(block_h=1.0, rest_h=0.5, demand_work_h=10.0))
    assert c.dhill.completed_work_h >= c.naive.completed_work_h
    assert c.naive_at_risk_blocks > 0 and c.dhill_at_risk_blocks == 0


def test_demand_is_a_cap(timelines):
    plan = plan_fleet(timelines, PlannerSpec(block_h=1.0, demand_work_h=3.0))
    assert plan.completed_work_h <= 3.0 + 1e-9


def test_calibration_recovers_hidden_parameters(tmp_path):
    w = synthetic_weather("abu_dhabi", "summer_clear", days=2)
    base = load_builtin("ugv_medium_inspection")
    true = base.with_overrides(
        {
            "surface.alpha_clean": 0.52,
            "coupling.ua_shell_interior_w_k": 14.0,
            "shell.heat_capacity_j_k": 24000.0,
        }
    )
    tel = synthetic_telemetry(true, w, "2026-08-05T01:00", hours=18, seed=3)
    path = tmp_path / "t.csv"
    save_telemetry_csv(tel, path)
    tel2 = load_telemetry_csv(path)
    cal, res = calibrate(base, w, tel2)
    got = {f.key: f for f in res.params}
    assert got["surface.alpha_clean"].fitted == pytest.approx(0.52, rel=0.05)
    assert got["coupling.ua_shell_interior_w_k"].fitted == pytest.approx(14.0, rel=0.10)
    assert got["shell.heat_capacity_j_k"].fitted == pytest.approx(24000.0, rel=0.20)
    assert res.rmse_holdout_k < 0.6 * res.rmse_prior_holdout_k
    assert cal.evidence_level == "L2" and cal.calibrated_from
    assert cal.sigma("surface.alpha_clean") <= 0.05


def test_telemetry_validation(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("time_utc,t_shell_c\n" + "\n".join(f"2026-08-05T00:0{i}:00,30" for i in range(5)))
    with pytest.raises(ValueError):
        cli_load = __import__("dhill.calibrate", fromlist=["x"]).load_telemetry_csv
        cli_load(p)


def test_cli_decide_json(capsys):
    rc = cli.main(["decide", "--at", "2026-08-05T00:00", "--samples", "16", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["action"] == "GO" and data["evidence_level"] == "L0"


def test_cli_lists_and_errors(capsys):
    assert cli.main(["list", "profiles"]) == 0
    assert "ugv_medium_inspection" in capsys.readouterr().out
    assert cli.main(["decide", "--profile", "nope"]) == 2


def test_ageing_penalty_reduces_ageing_without_losing_work(timelines):
    spec = PlannerSpec(block_h=1.0, rest_h=0.5, demand_work_h=6.0, age_penalty=0.05)
    aware = plan_fleet(timelines, spec)
    from dataclasses import replace

    blind = plan_fleet(timelines, replace(spec, age_penalty=0.0))
    assert aware.completed_work_h == pytest.approx(blind.completed_work_h)
    assert aware.age_equiv_h <= blind.age_equiv_h + 1e-9
    assert aware.age_equiv_h > 0


def test_slots_carry_ageing(timelines):
    slots = timelines["ugv_medium_inspection"].slots
    assert all(s.age_equiv_h >= 0 for s in slots)
    assert any(s.age_equiv_h > 0 for s in slots if s.scale > 0)
    assert all(s.age_equiv_h == 0 for s in slots if s.scale == 0)
