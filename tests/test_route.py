"""Route simulation: graph, plan timing, shade effect, policies and determinism.

Weather here is the deterministic SYNTHETIC generator (summer_clear at Al Ain), used only
to exercise the code.
"""

from __future__ import annotations

import numpy as np
import pytest

from dhill.envelope import EngineConfig
from dhill.profiles.loader import load_profile
from dhill.route import (
    Plan,
    PlanningProblem,
    RouteGraph,
    Segment,
    Waypoint,
    compare,
    envelope_ok,
    execute,
    plan_air_rule,
    plan_envelope,
    plan_shortest,
    plan_steps,
)
from dhill.weather import synthetic_weather

W = synthetic_weather("al_ain", "summer_clear", days=2)
PROF = load_profile("ugv_medium_inspection")
TRUTH = PROF.with_overrides(
    {
        "surface.alpha_clean": 0.52,
        "coupling.ua_shell_interior_w_k": 14.0,
        "shell.heat_capacity_j_k": 24000.0,
    }
)


def graph(shade_route: float = 0.6) -> RouteGraph:
    return RouteGraph(
        {
            "D": Waypoint("D", 0.9),
            "A": Waypoint("A"),
            "S": Waypoint("S", 0.85),
            "P": Waypoint("P"),
        },
        [
            Segment("D", "A", 600, 0.0),
            Segment("A", "P", 600, 0.0),
            Segment("D", "S", 700, shade_route),
            Segment("S", "P", 700, shade_route),
        ],
    )


def problem(t="2026-08-05T05:00", **kw) -> PlanningProblem:
    cfg = EngineConfig(n_mc=16, dt_s=120.0)
    return PlanningProblem(PROF, W, graph(), "D", ("P",), t, cfg=cfg, **kw)


def test_shortest_and_simple_paths():
    g = graph()
    sp = g.shortest_path("D", "P")
    assert [s.b for s in sp] == ["A", "P"]
    paths = g.simple_paths("D", "P")
    assert len(paths) == 2
    assert sum(s.length_m for s in paths[0]) <= sum(s.length_m for s in paths[1])
    with pytest.raises(ValueError):
        g.shortest_path("D", "nowhere")


def test_graph_validation():
    with pytest.raises(ValueError):
        RouteGraph({"A": Waypoint("A")}, [Segment("A", "B", 10.0)])
    with pytest.raises(ValueError):
        RouteGraph({"A": Waypoint("A"), "B": Waypoint("B")}, [Segment("A", "B", 10.0, 1.5)])


def test_plan_steps_timing():
    g = graph()
    legs = (tuple(g.shortest_path("D", "P")), tuple(g.shortest_path("P", "D")))
    v = PROF.value("perception.nominal_speed_ms")
    steps = plan_steps(Plan("x", 30.0, legs, 0.5, "A", 15.0), g, v)
    assert steps[0].kind == "wait" and steps[0].minutes == 30.0 and steps[0].shade == 0.9
    moves = [s for s in steps if s.kind == "move"]
    assert sum(s.minutes for s in moves) == pytest.approx(2400.0 / (v * 0.5) / 60.0)
    waits = [s for s in steps[1:] if s.kind == "wait"]
    assert len(waits) == 1 and waits[0].minutes == 15.0  # waits once although A is visited twice


def test_shade_lowers_peak_temperature():
    pp = problem("2026-08-05T08:00")
    st = pp.soak()
    peaks = []
    for shade in (0.0, 0.9):
        g = graph(shade)
        legs = (tuple(g.simple_paths("D", "P")[1]), tuple(g.simple_paths("P", "D")[1]))
        ex = execute(PROF, pp.env, pp.env.params, Plan("x", 0, legs, 1.0), g, pp.request_idx, st)
        peaks.append(ex.peaks_c)
    assert np.all(peaks[1] <= peaks[0] + 1e-9)
    assert np.max(peaks[0] - peaks[1]) > 0.5


def test_envelope_plan_is_feasible_on_its_own_model():
    pp = problem("2026-08-05T06:00")
    plan = plan_envelope(pp)
    assert plan is not None
    ok, finish = envelope_ok(pp, plan, pp.soak())
    assert ok and finish <= pp.deadline_min


def test_air_rule_waits_or_declines_when_hot():
    pp = problem("2026-08-05T08:00")  # local noon, summer
    assert float(pp.air_c()[pp.request_idx]) > 40.0
    plan = plan_air_rule(pp, 40.0)
    assert plan is None or plan.delay_min > 0
    assert plan_shortest(pp).delay_min == 0.0


def test_compare_is_deterministic_and_bounded():
    pp = problem("2026-08-05T06:00")
    a = compare(pp, TRUTH, worlds=24, seed=5)
    b = compare(problem("2026-08-05T06:00"), TRUTH, worlds=24, seed=5)
    assert [s.__dict__ for s in a] == [s.__dict__ for s in b]
    for s in a:
        assert 0.0 <= s.p_violation <= 1.0 and 0.0 <= s.completion_rate <= 1.0
        if not s.planned:
            assert s.completion_rate == 0.0


def test_no_plan_scores_zero_completion():
    pp = problem("2026-08-05T08:00", deadline_min=10.0)  # too short for any plan
    scores = {s.policy: s for s in compare(pp, TRUTH, worlds=8, seed=1)}
    assert not scores["envelope"].planned
    assert scores["envelope"].completion_rate == 0.0
    # shortest always plans, even when it cannot meet the deadline
    assert scores["shortest"].planned and scores["shortest"].completion_rate == 0.0
