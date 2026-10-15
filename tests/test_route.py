"""Route simulation tests. Synthetic weather and an illustrative graph; no physical claims."""

from __future__ import annotations

import numpy as np
import pytest

from dhill import route as R
from dhill.envelope import EngineConfig, Envelope
from dhill.profiles.loader import load_builtin
from dhill.weather import synthetic_weather

CFG = EngineConfig(n_mc=24, dt_s=120.0, parked_shade=0.9)
BASE = load_builtin("clearpath_jackal")
TRUTH = BASE.with_overrides(
    {
        "surface.alpha_clean": 0.57,
        "coupling.ua_shell_interior_w_k": 9.0,
        "shell.heat_capacity_j_k": 6500.0,
    }
)
GRAPH = R.patrol_graph()
MISSION = R.Mission()


def _case(site, scenario, hour, worlds=40):
    w = synthetic_weather(site, scenario, start="2026-08-05T00:00", days=2)
    env = Envelope(BASE, w, CFG)
    idx = env._idx(f"2026-08-05T{hour:02d}:00")
    return w, idx


def test_sheltered_path_is_longer_but_less_exposed():
    g = GRAPH
    short = g.shortest("depot", "T1")
    shade = g.least_exposed("depot", "T1")
    assert short != shade
    assert g.path_length(shade) > g.path_length(short)

    def exposed(path):
        return sum(
            g.edge(u, v).length_m * (1 - g.edge(u, v).shade)
            for u, v in zip(path[:-1], path[1:], strict=True)
        )

    assert exposed(shade) < exposed(short)


def test_pieces_add_up_to_distance_over_speed_plus_wait():
    path = GRAPH.shortest("T3", "depot")
    pieces = R.leg_pieces(GRAPH, path, 10.0, "depot", 1.0)
    drive = sum(p.seconds for p in pieces if p.kind == "drive")
    wait = sum(p.seconds for p in pieces if p.kind == "wait")
    assert drive == pytest.approx(GRAPH.path_length(path) / 1.0)
    assert wait == pytest.approx(600.0)


def test_shortest_plan_visits_every_stop_in_order():
    plan = R.shortest_plan(GRAPH, MISSION)
    visited = [leg.path[0] for leg in plan.legs] + [plan.legs[-1].path[-1]]
    assert visited == list(MISSION.stops)
    assert R.nominal_minutes(GRAPH, plan, MISSION, 1.0) == pytest.approx(
        (2200 / 1.0 + 3 * 6 * 60) / 60.0
    )


def test_cool_day_everyone_runs_and_envelope_does_not_wait_needlessly():
    w, idx = _case("al_ain", "winter_mild", 12)
    scores = R.compare_case(BASE, TRUTH, w, idx, GRAPH, MISSION, CFG, worlds=40)
    by = {s.policy: s for s in scores}
    assert all(s.runs and s.completed > 0.99 for s in by.values())
    assert by["envelope_l0"].minutes <= by["shortest"].minutes + 5.0


def test_air_rule_declines_when_air_never_falls_below_threshold():
    w, idx = _case("sweihan", "heatwave", 8)
    env = Envelope(BASE, w, CFG)
    plan = R.air_rule_plan(env, GRAPH, MISSION, idx, 40.0)
    assert not plan.runs and "40" in plan.reason


def test_air_rule_leaves_at_once_when_air_is_always_below_threshold():
    w, idx = _case("al_ain", "winter_mild", 12)
    env = Envelope(BASE, w, CFG)
    plan = R.air_rule_plan(env, GRAPH, MISSION, idx, 40.0)
    assert plan.runs and plan.legs[0].wait_min == 0.0


def test_envelope_changes_the_plan_when_it_is_hot_but_not_hopeless():
    """Abu Dhabi summer evening: the shortest route is borderline, so the envelope takes shade
    or pauses, and the mission takes longer than the shortest route."""
    cfg = EngineConfig(n_mc=48, dt_s=120.0, parked_shade=0.9)
    w = synthetic_weather("abu_dhabi", "summer_clear", start="2026-08-05T00:00", days=2)
    env = Envelope(BASE, w, cfg)
    speed = R._speed(env, MISSION)
    base_min = R.nominal_minutes(GRAPH, R.shortest_plan(GRAPH, MISSION), MISSION, speed)
    changed_any = False
    for hour in (16, 18, 20):
        idx = env._idx(f"2026-08-05T{hour:02d}:00")
        plan = R.envelope_plan(env, GRAPH, MISSION, idx)
        if not plan.runs:
            continue
        changed = any(leg.wait_min > 0 for leg in plan.legs) or any(
            leg.path != GRAPH.shortest(leg.path[0], leg.path[-1]) for leg in plan.legs
        )
        if changed:
            changed_any = True
            assert R.nominal_minutes(GRAPH, plan, MISSION, speed) > base_min
    assert changed_any


def test_envelope_declines_in_extreme_heat_and_says_why():
    w, idx = _case("sweihan", "heatwave", 8)
    env = Envelope(BASE, w, CFG)
    plan = R.envelope_plan(env, GRAPH, MISSION, idx)
    assert not plan.runs and plan.reason


def test_planned_missions_are_feasible_on_the_planning_ensemble():
    w, idx = _case("abu_dhabi", "summer_clear", 20)
    env = Envelope(BASE, w, CFG)
    plan = R.envelope_plan(env, GRAPH, MISSION, idx)
    assert plan.runs
    pieces = R.plan_pieces(GRAPH, plan, MISSION, R._speed(env, MISSION))
    assert R.feasible(env, R.execute(env, pieces, idx))


def test_results_are_deterministic():
    w, idx = _case("abu_dhabi", "summer_clear", 18)
    a = R.compare_case(BASE, TRUTH, w, idx, GRAPH, MISSION, CFG, worlds=30)
    b = R.compare_case(BASE, TRUTH, w, idx, GRAPH, MISSION, CFG, worlds=30)
    assert [(s.policy, s.completed, s.minutes) for s in a] == [
        (s.policy, s.completed, s.minutes) for s in b
    ]


def test_scores_are_probabilities():
    w, idx = _case("abu_dhabi", "summer_clear", 14)
    for s in R.compare_case(BASE, TRUTH, w, idx, GRAPH, MISSION, CFG, worlds=30):
        assert 0.0 <= s.completed <= 1.0
        if s.runs:
            assert s.completed == pytest.approx(1.0 - s.violation_prob)
        else:
            assert s.completed == 0.0 and np.isnan(s.minutes)
