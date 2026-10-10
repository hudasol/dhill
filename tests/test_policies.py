import numpy as np

from dhill.envelope import EngineConfig, Envelope
from dhill.policies import (
    ambient_threshold,
    envelope_policy,
    midday_ban,
    score_policies,
    slot_starts,
)
from dhill.profiles.loader import load_builtin
from dhill.weather import synthetic_weather

DAY = ("2026-08-06T00:00", "2026-08-06T23:00")


def _setup():
    base = load_builtin("ugv_medium_inspection")
    w = synthetic_weather("sweihan", "heatwave", days=3)
    env = Envelope(base, w, EngineConfig(n_mc=16))
    return base, w, env, slot_starts(env, *DAY)


def test_slot_starts_hourly_and_rules_are_binary():
    _, _, env, starts = _setup()
    assert len(starts) == 24
    for pol in (ambient_threshold(env, starts, 1.0, 40.0), midday_ban(env, starts)):
        assert set(np.unique(pol)) <= {0.0, 1.0}
        assert pol.shape == starts.shape


def test_stricter_air_rule_operates_no_more_than_looser_one():
    _, _, env, starts = _setup()
    assert (
        ambient_threshold(env, starts, 1.0, 40.0).sum()
        <= ambient_threshold(env, starts, 1.0, 45.0).sum()
    )


def test_midday_ban_blocks_only_midday():
    _, _, env, starts = _setup()
    pol = midday_ban(env, starts)
    hours = env.forcing.solar_hour[starts]
    assert np.all(pol[(hours >= 12.5) & (hours < 15.0)] == 0.0)
    assert np.all(pol[(hours < 12.0) | (hours >= 15.0)] == 1.0)


def test_scores_are_probabilities_and_envelope_is_not_riskier_than_nominal():
    base, w, env, starts = _setup()
    cfg = EngineConfig(n_mc=16)
    pols = {
        "nominal": envelope_policy(
            base, w, starts, 1.0, "drive", EngineConfig(n_mc=16, sigma_scale=0.0)
        ),
        "uncertain": envelope_policy(base, w, starts, 1.0, "drive", cfg),
        "always": np.ones(len(starts)),
    }
    s = {x.name: x for x in score_policies(base, w, starts, pols, 1.0, "drive", worlds=40)}
    for x in s.values():
        assert 0.0 <= x.violation_prob_mean <= 1.0
        assert x.risky_hours <= x.operated_slots <= 24
    # Operating around the clock in a heatwave must be worse than any envelope policy.
    assert s["always"].expected_violation_h >= s["uncertain"].expected_violation_h
    # Accounting for uncertainty must not buy more productive hours than ignoring it.
    assert s["uncertain"].productive_h <= s["nominal"].productive_h + 1e-9


def test_never_operating_scores_zero():
    base, w, _, starts = _setup()
    s = score_policies(base, w, starts, {"idle": np.zeros(len(starts))}, 1.0, "drive", worlds=10)[0]
    assert s.productive_h == 0.0 and s.operated_slots == 0 and s.expected_violation_h == 0.0
