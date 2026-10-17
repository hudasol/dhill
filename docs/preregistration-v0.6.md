# Preregistration v0.6

Written and committed on 15 October 2026 before `examples/prereg_eval.py` existed or was run.
The commit that adds this file precedes the commit that adds the evaluation script; `git log` is the
record. This file is not edited after the run. Any change of design is recorded as a dated amendment
at the end, keeping the original text.

## What is being tested

Whether the uncertainty aware envelope (Dhill v0.5 engine, unchanged) keeps an illustrative robot inside
its hard limits more reliably than simple operator rules, what that costs in productive hours, whether its
95 % risk quantile is honest, and whether envelope aware route planning lowers violations on a patrol.

## Who built the world

Everything below is synthetic or recorded weather driving a synthetic robot. The hidden "true" robots,
the forecast error model and the scoring were written by the same author as the method, and the hidden
robots share the engine's model structure. A pass here shows internal consistency of the method under
stated perturbations. It is not evidence about any real robot.

## What was known before writing this

- `docs/policy-comparison.md` (v0.5): one hotter hidden robot, three synthetic cases. The envelope had zero
  risky hours in all three; the no uncertainty envelope and the 45 degC rule had risky hours; the 40 degC rule
  beat the envelope on productive hours in one of three cases. Predictions H1 to H4 are informed by it.
- `docs/route-simulation.md` (this session): one hotter hidden robot, seed 123. For the medium UGV the
  envelope planner avoided all violations and finished later than the shortest path; the shortest path was
  nearly always safe as well. H6 is informed by it. The evaluation below uses different hidden robots.
- `docs/operating-calendar.md` (this session): the L0 Jackal profile parks or derates almost always in
  summer. The Jackal is therefore not used for H1 to H5, where it would make H1 trivially true.

## Fixed design

| Item | Value |
|---|---|
| Planner profile | `ugv_medium_inspection`, evidence level L0, unchanged |
| Hidden robot per seed | Nine parameters drawn from the planner's own prior, value x exp(sigma z), sigma from the profile's provenance: `surface.alpha_clean` (capped at 0.95), `coupling.ua_shell_interior_w_k`, `shell.heat_capacity_j_k`, `interior.heat_capacity_j_k`, `battery.cell_resistance_25c_ohm`, `compute.die_rise_k_per_w`, `coupling.ua_compute_interior_w_k`, `coupling.ua_battery_interior_w_k`, `environment.ground_rise_k_per_kw_m2`. All other parameters nominal. Generator `numpy.random.default_rng(1000 + seed)`. |
| Seeds | 0 to 19 (20 seeds). No other seeds are run for evaluation. Nothing is tuned. |
| Cases | C1 `abu_dhabi` synthetic `summer_clear`; C2 `sweihan` synthetic `heatwave`; C3 `dubai` synthetic `humid_coastal`; C4 `abu_dhabi` recorded Open-Meteo archive and CAMS PM10, 1 to 6 July 2024 (`tests/data/climatology`). |
| Evaluated slots | 24 hourly 1 h drive missions. Synthetic cases: starts 2026-08-06T00:00 to 23:00 UTC (weather generated for 3 days from 2026-08-05). C4: starts 2024-07-03T00:00 to 23:00 UTC. |
| Engine | `EngineConfig` defaults (64 Monte Carlo samples, 95 % risk quantile, 600 s step, 1.5 h parked soak in sun), engine seed = seed. |
| Scoring weather | 200 draws per run; forecast error heavier than the engine assumes: air temperature sigma 2 K, irradiance 15 %, wind 30 % (engine: 1.5 K, 10 %, 25 %); generator seed 2000 + seed. Same scorer as `src/dhill/policies.py`. |
| Violation | Any component above its hard limit during a mission, on the hidden robot. |

Policies: P1 air at or below 45 degC; P2 air at or below 40 degC; P3 midday ban 12:30 to 15:00 local
solar time; P4 envelope without uncertainty (sigma scale 0); P5 envelope L0 with uncertainty.

Runs: 20 seeds x 4 cases = 80 runs for H1 to H5.

## Metrics

- Productive hours: sum of operating scale x 1 h over the 24 slots.
- Risky hours: operated slots whose violation probability across the 200 draws exceeds 5 %.
- Mean violation probability over operated slots.
- Coverage (H5): for every slot P5 operates, the engine's 95 % risk quantile peak of the binding component
  (smallest headroom at the chosen scale) is compared with that component's true peak in each of the 200
  draws. Coverage is the share of (slot, draw) pairs where the true peak is at or below the prediction.

Intervals: proportions over runs use the Wilson 95 % interval. Means use a percentile bootstrap over seeds
(resampling whole seeds with all their cases), 2000 resamples, generator seed 99.

## Hypotheses and predictions

| ID | Hypothesis | Prediction (HIT if) |
|---|---|---|
| H1 | The envelope keeps the hidden robot inside its limits | P5 has zero risky hours in at least 90 % of the 80 runs |
| H2 | Ignoring uncertainty is unsafe | P4 has at least one risky hour in at least 50 % of runs |
| H3 | An ambient rule at the datasheet rating is unsafe | P1 has at least one risky hour in at least 50 % of runs |
| H4 | The envelope is more productive than the conservative ambient rule | Mean over runs of (P5 minus P2 productive hours) is above 0 and its 95 % bootstrap interval excludes 0 |
| H5 | The 95 % risk quantile is honest under heavier forecast error | Pooled coverage between 0.90 and 0.995 |
| H6 | Envelope aware routing lowers violations at a cost in time | With the route, recorded days and request hours of `examples/route_demo.py` (Abu Dhabi 2 and 4 July, Al Ain 8 and 9 July 2024; 06, 09, 12, 15 and 18 local; 20 requests per seed), 20 seeds, 100 draws per request: the envelope planner's mean violation probability over planned requests is at or below the shortest path's, its mean completion rate is at or above the shortest path's, and its mean finish time over planned requests is longer |

For H6 the hidden robot uses the same seeded draw as above; the route planner uses 48 Monte Carlo
samples and a 120 s step, as in `src/dhill/route.py`.

## What counts as failure

- A MISS on H1 is the most serious outcome: the envelope would not deliver what it claims, even in a world
  built to match its own model structure.
- A MISS on H5 below 0.90 means the risk quantile is overconfident; above 0.995 means it is so conservative
  that the 95 % label is misleading. Both are reported as MISS.
- A MISS on H4 means the conservative rule is at least as productive; the envelope's value would then rest
  on per component reasons alone.
- Every MISS is reported next to its prediction. No seed, case or metric is dropped after the run.

## Reproduce

`python examples/prereg_eval.py` writes `examples/prereg_results.json` and renders
`docs/prereg-results.md` from it. A test checks that every number in the document equals the JSON.
