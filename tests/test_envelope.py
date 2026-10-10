from __future__ import annotations

import numpy as np
import pytest

from dhill.envelope import EngineConfig, Envelope
from dhill.profiles.loader import load_builtin
from dhill.weather import synthetic_weather


@pytest.fixture(scope="module")
def env():
    return Envelope(
        load_builtin("ugv_medium_inspection"),
        synthetic_weather("abu_dhabi", "summer_clear", days=2),
        EngineConfig(n_mc=48),
    )


def test_night_go_midday_park_and_shoulder_derate(env):
    night = env.decide("2026-08-05T00:00", 1.0)
    noon = env.decide("2026-08-05T09:00", 1.0)
    assert night.action == "GO" and night.scale == 1.0
    assert noon.action == "PARK" and noon.scale == 0.0
    tl = env.timeline(1.0, "drive", 60.0, last_utc="2026-08-05T22:00")
    actions = [s.action for s in tl.slots]
    assert "DERATE" in actions and "GO" in actions and "PARK" in actions


def test_go_decision_has_nonnegative_headroom_and_park_has_negative(env):
    go = env.decide("2026-08-05T00:00", 1.0)
    assert min(c.headroom_k for c in go.components) >= 0
    park = env.decide("2026-08-05T09:00", 1.0)
    assert min(c.headroom_k for c in park.components) < 0


def test_derate_scale_is_actually_feasible_and_larger_is_not(env):
    d = env.decide("2026-08-05T04:00", 1.0)
    if d.action != "DERATE":
        pytest.skip("scenario produced no derate at this hour")
    idx = env._idx("2026-08-05T04:00")
    ok = env.scan(np.array([idx]), np.array([[d.scale]]), 1.0, "drive")
    assert env._feasible(ok, np.array([[d.scale]]), np.array([1.0]))[0, 0]
    over = env.scan(np.array([idx]), np.array([[min(1.0, d.scale + 0.1)]]), 1.0, "drive")
    assert not env._feasible(over, np.array([[min(1.0, d.scale + 0.1)]]), np.array([1.0]))[0, 0]


def test_headroom_monotone_in_scale(env):
    idx = env._idx("2026-08-05T04:00")
    sc = np.linspace(0.3, 1.0, 8)
    r = env.scan(np.array([idx]), sc, 1.0, "drive")
    worst = r["headroom"][0].min(axis=1)
    assert np.all(np.diff(worst) <= 1e-9)


def test_shade_helps(env):
    idx = env._idx("2026-08-05T08:00")
    a = env.scan(np.array([idx]), np.array([[1.0]]), 1.0, "drive", shade=0.0)["headroom"].min()
    b = env.scan(np.array([idx]), np.array([[1.0]]), 1.0, "drive", shade=1.0)["headroom"].min()
    assert b > a


def test_shade_requirement_reported_and_sufficient():
    e = Envelope(
        load_builtin("ugv_medium_inspection"),
        synthetic_weather("abu_dhabi", "summer_clear", days=2),
        EngineConfig(n_mc=48),
    )
    for hour in ("2026-08-05T05:00", "2026-08-05T06:00", "2026-08-05T07:00"):
        d = e.decide(hour, 1.0)
        if d.action != "GO" and d.shade_required_fraction is not None:
            idx = e._idx(hour)
            r = e.scan(
                np.array([idx]), np.array([[1.0]]), 1.0, "drive", shade=d.shade_required_fraction
            )
            assert e._feasible(r, np.array([[1.0]]), np.array([1.0]))[0, 0]
            return
    pytest.skip("no shade-fixable window in scenario")


def test_more_samples_do_not_flip_clear_decisions():
    w = synthetic_weather("abu_dhabi", "summer_clear", days=2)
    p = load_builtin("ugv_medium_inspection")
    a = Envelope(p, w, EngineConfig(n_mc=48, seed=1)).decide("2026-08-05T00:00", 1.0)
    b = Envelope(p, w, EngineConfig(n_mc=96, seed=2)).decide("2026-08-05T00:00", 1.0)
    assert a.action == b.action == "GO"


def test_calibrated_uncertainty_unlocks_more_work():
    """Tighter parameter uncertainty (same nominal values) must not reduce, and here increases, safe scale."""
    w = synthetic_weather("abu_dhabi", "summer_clear", days=2)
    p = load_builtin("ugv_medium_inspection")
    wide = Envelope(p, w, EngineConfig(n_mc=48, sigma_scale=1.0)).timeline(
        1.0, "drive", 60.0, last_utc="2026-08-05T22:00"
    )
    tight = Envelope(p, w, EngineConfig(n_mc=48, sigma_scale=0.25)).timeline(
        1.0, "drive", 60.0, last_utc="2026-08-05T22:00"
    )
    assert tight.productive_hours >= wide.productive_hours


def test_dust_event_caps_speed_or_reports_range():
    w = synthetic_weather("madinat_zayed", "dust_event", days=2)
    e = Envelope(load_builtin("ugv_medium_inspection"), w, EngineConfig(n_mc=48))
    clear = e.decide("2026-08-05T02:00", 1.0)
    dusty = e.decide("2026-08-05T13:00", 1.0)
    assert dusty.perception.lidar_range_m < clear.perception.lidar_range_m
    assert dusty.perception.pm10_window_max_ugm3 > clear.perception.pm10_window_max_ugm3


def test_extreme_dust_forces_perception_limit():
    w = synthetic_weather("abu_dhabi", "winter_mild", days=2)
    w.pm10_ugm3[:] = 150000.0  # artificial, far beyond any recorded concentration
    fast = load_builtin("ugv_medium_inspection").with_overrides(
        {"perception.nominal_speed_ms": 4.0}, source="assumption"
    )
    e = Envelope(fast, w, EngineConfig(n_mc=48))
    d = e.decide("2026-08-05T02:00", 1.0)
    assert d.perception.speed_fraction_cap < 1.0
    assert d.action != "GO" and d.perception_limited


def test_decision_carries_evidence_and_caveat(env):
    d = env.decide("2026-08-05T00:00", 1.0)
    assert d.evidence_level == "L0" and "not an authorisation" in d.caveat
    assert 0.5 < d.assumption_fraction < 1.0
    assert d.model_dump_json()


def test_unknown_mode_rejected(env):
    with pytest.raises(KeyError):
        env.decide("2026-08-05T00:00", 1.0, mode="fly")


def test_exceedance_probability_ordering(env):
    go = env.decide("2026-08-05T00:00", 1.0)
    park = env.decide("2026-08-05T09:00", 1.0)
    assert 0.0 <= go.max_p_exceed_limit <= 0.1  # GO keeps the risk quantile below limit less margin
    assert park.max_p_exceed_limit > go.max_p_exceed_limit
    assert all(0.0 <= c.p_exceed_limit <= 1.0 for c in park.components)


def test_time_to_limit_reported_only_when_not_go(env):
    go = env.decide("2026-08-05T00:00", 1.0)
    assert go.time_to_limit_min is None
    d = env.decide("2026-08-05T04:00", 1.0)
    if d.action != "GO":
        assert d.time_to_limit_min is not None and 0 <= d.time_to_limit_min <= 60
        assert d.time_to_limit_component in {c.component for c in d.components}


def test_time_to_limit_shrinks_when_hotter():
    p = load_builtin("ugv_medium_inspection")
    cool = Envelope(
        p, synthetic_weather("abu_dhabi", "summer_clear", days=2), EngineConfig(n_mc=32)
    )
    hot = Envelope(p, synthetic_weather("sweihan", "heatwave", days=2), EngineConfig(n_mc=32))
    t_cool, _ = cool.time_to_limit(cool._idx("2026-08-05T05:00"), 2.0, "drive")
    t_hot, _ = hot.time_to_limit(hot._idx("2026-08-05T05:00"), 2.0, "drive")
    assert t_hot is not None
    assert t_cool is None or t_hot <= t_cool
