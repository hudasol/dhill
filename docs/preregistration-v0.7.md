# Preregistration v0.7: the Jackal profile

Written and committed on 18 October 2026 before `examples/prereg_eval_jackal.py` existed or was run. The commit
that adds this file precedes the commit that adds the script; `git log` is the record. This file is not edited
after the run. Any change of design goes in a dated amendment file, keeping this text.

## Why

The v0.6 evaluation (`docs/preregistration-v0.6.md`) used only `ugv_medium_inspection`; the Jackal profile, which
the operating calendar, route simulation and proposals rely on, has never been tested this way
(`docs/prereg-results-addendum-fixed-profile.md`).

## What was known before writing this

- v0.6 results for the medium UGV: 2 of 6 predictions hit; the envelope had no risky hour in 80 runs; a 40 degC
  air rule was slightly more productive; the 95 % risk quantile covered the truth 99.6 % of the time
  (`docs/prereg-results.md`, `docs/prereg-coverage-bootstrap-addendum.md`).
- Route simulation with one hotter hidden Jackal: the envelope exceeded no hard limit but completed fewer
  requests than the shortest path (`docs/route-simulation.md`).
- Operating calendar: with the fixed profile GO is the majority decision only up to about 35 degC mission air,
  and the battery binds (`docs/operating-calendar.md`). The Jackal sensitivity ranks DC-DC efficiency and drive
  efficiency first (`docs/sensitivity.md`).
- The three conductances were raised by commit 6f38479 to match the rated ambient; their earlier values were
  4.4, 1.2 and 2.0 W/K (`docs/robot-sources.md`).

## Who built the world

The hidden "true" robots, the forecast error model and the scorer were written by the same author as the method
and share its six node model structure. World W1 draws the hidden robot from the planner's own prior, so the
planner's uncertainty model is correct by construction there. World W2 is deliberately outside that prior for
three parameters. Neither world is evidence about a real Jackal.

## Fixed design

| Item | Value |
|---|---|
| Planner profile | `clearpath_jackal` as on main after commit 6f38479, evidence level L0, unchanged |
| Parameters varied in the hidden robot | `surface.alpha_clean` (cap 0.95), `coupling.ua_shell_interior_w_k`, `shell.heat_capacity_j_k`, `interior.heat_capacity_j_k`, `battery.cell_resistance_25c_ohm`, `compute.die_rise_k_per_w`, `coupling.ua_compute_interior_w_k`, `coupling.ua_battery_interior_w_k`, `environment.ground_rise_k_per_kw_m2`, `power.dcdc_efficiency` (cap 0.98), `motors.drive_efficiency` (cap 0.95). Each is value x exp(sigma z) with sigma from the profile's provenance; generator `numpy.random.default_rng(3000 + seed)`. All other parameters nominal. |
| World W1 | The draw above. |
| World W2 | The same draw, then the three conductances replaced by their values before the fix: shell to interior 4.4, battery to interior 1.2, compute to interior 2.0 W/K. |
| Seeds | 0 to 19 (20 seeds). Evaluation seeds are not used for any trial run; a single check that the script runs uses seed 999 only. Nothing is tuned. |
| Cases | C1 `abu_dhabi` synthetic `summer_clear`; C2 `sweihan` synthetic `heatwave`; C3 `dubai` synthetic `humid_coastal`; C4 `abu_dhabi` recorded Open-Meteo archive and CAMS PM10, July 2024; C5 `al_ain` recorded, July 2024 (both from `tests/data/climatology`). |
| Evaluated slots | 24 hourly 1 h drive missions. C1 to C3: 2026-08-06T00:00 to 23:00 UTC (weather generated for 3 days from 2026-08-05). C4: 2024-07-03T00:00 to 23:00 UTC. C5: 2024-07-08T00:00 to 23:00 UTC. |
| Engine | `EngineConfig` defaults (64 Monte Carlo samples, 95 % risk quantile, 600 s step, 1.5 h parked soak in sun), engine seed = seed. |
| Scoring | 200 weather draws per run, forecast error heavier than the engine assumes (air temperature sigma 2 K, irradiance 15 %, wind 30 %), generator seed 4000 + seed, scorer `src/dhill/policies.py`, as in v0.6. |
| Violation | Any component above its hard limit during a mission, on the hidden robot. |
| Policies | P1 air at or below 45 degC (the datasheet rating); P2 air at or below 40 degC; P3 midday ban 12:30 to 15:00 local solar time; P4 envelope without uncertainty; P5 envelope L0. |

Runs: 20 seeds x 5 cases x 2 worlds = 200 runs.

## Metrics

- Productive hours: sum of operating scale x 1 h over the 24 slots.
- Risky hour: an operated slot whose violation probability across the 200 draws exceeds 5 %.
- Mean violation probability over operated slots (0 when nothing is operated).
- Coverage (W1, P5): for each operated slot, whether the true peak of the binding component (smallest headroom
  at the chosen scale) is at or below the engine's 95 % risk quantile peak, over all draws; pooled over runs.

Intervals: every interval is a percentile bootstrap over seeds (2000 resamples, generator seed 99), resampling
whole seeds with all their cases. Shares and coverage are recomputed as ratios of pooled counts in each resample.

## Hypotheses and predictions

| ID | World | Hypothesis | Prediction (HIT if) |
|---|---|---|---|
| H1 | W1 | The envelope keeps the hidden Jackal inside its limits | P5 has zero risky hours in at least 90 % of the 100 W1 runs |
| H2 | W1 | The datasheet ambient rating is not a safe operating rule for a robot in sun | P1 has at least one risky hour in at least 50 % of W1 runs |
| H3 | W1 | Ignoring parameter uncertainty is unsafe | P4 has at least one risky hour in at least 30 % of W1 runs |
| H4 | W1 | The envelope loses on productivity to the conservative air rule | Mean over W1 runs of (P5 minus P2) productive hours is below 0 and the upper end of its interval is below 0 |
| H5 | W1 | The 95 % risk quantile is honest | Pooled coverage between 0.90 and 0.995 |
| H6 | W2 | The envelope is not safe when three conductances are as wrong as they were before the fix | P5 has at least one risky hour in at least 50 % of W2 runs |
| H7 | W2 | Even then the envelope is safer than the datasheet rule | Mean over W2 runs of (P1 minus P5) mean violation probability is above 0 and the lower end of its interval is above 0 |

H4 and H6 predict that the envelope loses. A HIT on them is a result against the method, and is reported as such.

## What counts as failure

- A MISS on H1 is the most serious outcome: the envelope would not deliver its claim even in a world matching its
  own prior.
- A HIT on H6 means the envelope's safety for the Jackal depends on the unmeasured conductances being right; this
  is the expected outcome and must be stated next to any Jackal result.
- A MISS on H5 below 0.90 means the quantile is overconfident; above 0.995 means it is overcautious.
- Every MISS is reported next to its prediction. No seed, case, world or metric is dropped after the run.

## Reproduce

`python examples/prereg_eval_jackal.py` writes `examples/prereg_results_v07.json` and renders
`docs/prereg-results-v07.md` from it; a test checks that the document equals the rendering.
