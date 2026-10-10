"""Does calibrating on telemetry unlock safe operating hours?

A hidden 'true' robot (different paint absorptance, shell conductance and heat capacity
from the L0 profile) generates synthetic telemetry. We calibrate the L0 profile on it and
compare scale-weighted productive hours per day, and decision safety against the truth,
with and without calibration. Synthetic data: this demonstrates the pipeline, it is not
field evidence.
"""

import numpy as np

from dhill.calibrate import calibrate, synthetic_telemetry
from dhill.envelope import EngineConfig, Envelope
from dhill.profiles.loader import load_builtin
from dhill.weather import synthetic_weather

SITE, SCEN = "sweihan", "summer_clear"
base = load_builtin("ugv_medium_inspection")
true = base.with_overrides(
    {
        "surface.alpha_clean": 0.52,
        "coupling.ua_shell_interior_w_k": 14.0,
        "shell.heat_capacity_j_k": 24000.0,
    }
)
w = synthetic_weather(SITE, SCEN, days=3)
tel = synthetic_telemetry(true, w, "2026-08-05T01:00", hours=18, seed=3)
cal, res = calibrate(base, w, tel)

window = dict(first_utc="2026-08-06T00:00", last_utc="2026-08-06T22:00")
rows = {}
rows["L0 nominal (ignores uncertainty)"] = Envelope(
    base, w, EngineConfig(n_mc=96, sigma_scale=0.0), site=SITE
).timeline(1.0, "drive", 60.0, **window)
for name, prof in (("L0 prior + uncertainty", base), ("L2 calibrated + uncertainty", cal)):
    e = Envelope(prof, w, EngineConfig(n_mc=96), site=SITE)
    rows[name] = e.timeline(1.0, "drive", 60.0, **window)
# ground truth: the hidden robot's nominal (no-uncertainty) envelope
truth = Envelope(true, w, EngineConfig(n_mc=96, sigma_scale=0.0), site=SITE).timeline(
    1.0, "drive", 60.0, **window
)
rows["hidden truth (zero uncertainty)"] = truth
t_scale = np.array([s.scale for s in truth.slots])

print(f"{'profile':<34}{'productive h':>13}{'unsafe slots':>14}{'lost vs truth h':>17}")
for name, tl in rows.items():
    sc = np.array([s.scale for s in tl.slots])
    unsafe = int(np.sum(sc > t_scale + 0.05))
    lost = float(np.sum(np.maximum(t_scale - sc, 0)))
    print(f"{name:<34}{tl.productive_hours:>13.1f}{unsafe:>14d}{lost:>17.1f}")
print(
    f"\ncalibration RMSE hold-out {res.rmse_holdout_k:.2f} K (prior {res.rmse_prior_holdout_k:.2f} K)"
)
