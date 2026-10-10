"""Do simple operator rules beat the envelope? Scored on a hidden true robot.

The 'true' robot is hotter than the L0 profile assumes (higher absorptance, lower shell
conductance, larger shell heat capacity). Policies see only the forecast; reality adds
forecast error (heavier than the engine assumes). Violation = any component exceeding its
hard limit during the mission. Synthetic weather and illustrative robots: a method test,
not field evidence.
"""

import sys

from dhill.calibrate import calibrate, synthetic_telemetry
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

CASES = [("abu_dhabi", "summer_clear"), ("sweihan", "heatwave"), ("dubai", "humid_coastal")]
base = load_builtin("ugv_medium_inspection")
true = base.with_overrides(
    {
        "surface.alpha_clean": 0.52,
        "coupling.ua_shell_interior_w_k": 14.0,
        "shell.heat_capacity_j_k": 24000.0,
    }
)
lines = []
for site, scen in CASES:
    w = synthetic_weather(site, scen, days=3)
    tel = synthetic_telemetry(true, w, "2026-08-05T01:00", hours=18, seed=3)
    cal, _ = calibrate(base, w, tel)
    env = Envelope(base, w, EngineConfig(n_mc=64))
    starts = slot_starts(env, "2026-08-06T00:00", "2026-08-06T23:00")
    cfg = EngineConfig(n_mc=64)
    policies = {
        "Air <= 45 C rule": ambient_threshold(env, starts, 1.0, 45.0),
        "Air <= 40 C rule": ambient_threshold(env, starts, 1.0, 40.0),
        "Midday ban 12:30-15:00": midday_ban(env, starts),
        "Envelope, no uncertainty": envelope_policy(
            base, w, starts, 1.0, "drive", EngineConfig(n_mc=64, sigma_scale=0.0)
        ),
        "Envelope L0 (uncertainty)": envelope_policy(base, w, starts, 1.0, "drive", cfg),
        "Envelope L2 (calibrated)": envelope_policy(cal, w, starts, 1.0, "drive", cfg),
    }
    scores = score_policies(true, w, starts, policies, 1.0, "drive")
    lines.append(f"\n{site} / {scen}  (24 hourly missions, 200 weather realisations)")
    lines.append(
        f"{'policy':<28}{'productive h':>13}{'mean P(violate)':>17}{'risky hours':>13}{'expected viol. h':>18}"
    )
    for s in scores:
        lines.append(
            f"{s.name:<28}{s.productive_h:>13.1f}{s.violation_prob_mean:>17.1%}{s.risky_hours:>13d}{s.expected_violation_h:>18.2f}"
        )
print("\n".join(lines))
sys.stdout.flush()
