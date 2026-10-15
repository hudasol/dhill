# Preregistered evaluation v0.6: results

Rendered by `examples/prereg_eval.py` from `examples/prereg_results.json`. Do not edit by hand;
`tests/test_prereg.py` fails if a number here differs from the JSON. The design, predictions and
failure criteria were fixed in `docs/preregistration-v0.6.md` and committed before the first run.

**SYNTHETIC world.** Hidden robots and forecast error draws are synthetic and were built by the
same author as the method, with the same model structure. Weather is synthetic in C1 to C3 and
recorded (Open-Meteo archive and CAMS PM10, Abu Dhabi, July 2024) in C4; H6 uses the recorded
Abu Dhabi and Al Ain July 2024 days of `examples/route_demo.py`. The profile is L0.

Runs: 80 (20 seeds x 4 cases) for H1 to H5; 400 route requests for H6.

## Predictions against results

| ID | Prediction | Result | 95 % interval | Verdict |
|---|---|---|---|---|
| H1 | P5 zero risky hours in at least 90 % of runs | 80 of 80 runs (100.0 %) | 95.4 % to 100.0 % | HIT |
| H2 | P4 at least one risky hour in at least 50 % of runs | 19 of 80 (23.8 %) | 15.8 % to 34.1 % | MISS |
| H3 | P1 at least one risky hour in at least 50 % of runs | 39 of 80 (48.8 %) | 38.1 % to 59.5 % | MISS |
| H4 | Mean (P5 minus P2) productive hours above 0, interval excludes 0 | -0.41 h | -0.71 to -0.18 h | MISS |
| H5 | Coverage of the 95 % risk quantile between 0.90 and 0.995 | 0.9963 (291902 of 293000 pairs) | 0.9960 to 0.9965 | MISS |
| H6 | Envelope routing: P(violation) at or below shortest, completion at or above, finish later | P(viol) 0.0 % vs 0.1 %; completion 100.0 % vs 99.9 %; finish 71.1 vs 34.0 min | not computed | HIT |

2 of 6 predictions hit.

## Policy summary over all 80 runs

| Policy | Mean productive h | Runs with a risky hour | Mean risky hours | Mean P(violation), operated slots |
|---|---:|---:|---:|---:|
| P1 Air at or below 45 degC | 21.50 | 39 | 1.94 | 2.0 % |
| P2 Air at or below 40 degC | 16.50 | 12 | 0.31 | 0.3 % |
| P3 Midday ban 12:30 to 15:00 | 21.00 | 42 | 1.90 | 3.7 % |
| P4 Envelope, no uncertainty | 21.46 | 19 | 1.06 | 1.0 % |
| P5 Envelope L0 | 16.09 | 0 | 0.00 | 0.0 % |

## Per case (20 seeds each): mean productive hours / runs with a risky hour

| Case | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| C1 abu_dhabi summer_clear | 24.0 / 16 | 14.0 / 0 | 21.0 / 10 | 22.2 / 5 | 15.8 / 0 |
| C2 sweihan heatwave | 14.0 / 4 | 10.0 / 0 | 21.0 / 20 | 17.0 / 5 | 13.7 / 0 |
| C3 dubai humid_coastal | 24.0 / 15 | 18.0 / 8 | 21.0 / 10 | 22.6 / 5 | 15.9 / 0 |
| C4 abu_dhabi recorded | 24.0 / 4 | 24.0 / 4 | 21.0 / 2 | 24.0 / 4 | 18.9 / 0 |

## Route requests (H6), all seeds

| Policy | Requests | Planned | Mean P(violation), planned | Mean completion | Mean finish, planned (min) |
|---|---:|---:|---:|---:|---:|
| shortest | 400 | 400 | 0.1 % | 99.9 % | 34.0 |
| air_rule_40C | 400 | 300 | 0.0 % | 75.0 % | 82.0 |
| envelope | 400 | 400 | 0.0 % | 100.0 % | 71.1 |

## Reading

Written after the run. It interprets the tables above and changes none of them.

- **H1 hit.** The uncertainty aware envelope had no risky hour in any run, including runs where the
  hidden robot was hotter than the profile and the forecast error was heavier than the engine assumes.
  This is the central claim of the method and it held in this synthetic world.
- **H2 and H3 missed.** The predictions that the no uncertainty envelope and the 45 degC rule would
  be unsafe in at least half of the runs were too pessimistic. Hidden robots drawn from the profile's
  own prior are on average not hotter than the profile, unlike the single hotter robot in
  `docs/policy-comparison.md` that informed these predictions. Simple rules and the nominal model were
  unsafe in a minority of runs, not a majority. The midday ban (P3) was the policy with the most runs
  containing a risky hour.
- **H4 missed, and in the wrong direction.** The conservative 40 degC rule delivered slightly more
  productive hours on average than the envelope, with an interval that excludes zero. The 40 degC rule
  did have risky hours in some runs (mainly the humid coastal and recorded cases), while the envelope had
  none. The envelope's value in this evaluation is safety with stated reasons, not productivity.
- **H5 missed on the high side.** The engine's 95 % risk quantile covered the true peak more often than
  the preregistered upper bound of 0.995. The envelope is more conservative than its label says, which
  is consistent with H4. The interval shown treats (slot, draw) pairs as independent, which they are not;
  it understates the real uncertainty of the coverage estimate.
- **H6 hit, narrowly.** The envelope planner's routes had no violations and the shortest path had very
  few. The hit rests on a very small difference in violation probability bought with roughly double the
  finish time. It confirms the cost of caution more than a safety gain.

## Limitations

- The world is synthetic and shares the engine's model structure and author. Structural model error,
  which real robots will have, is absent; a real test is the instrumented run in `docs/field-test-kit.md`.
- Hidden robots vary nine thermal parameters only; drive efficiency and converter efficiency, which
  `docs/sensitivity.md` ranks highly, were held at nominal.
- One profile (the medium UGV). The Jackal profile was excluded for the reason given in the
  preregistration; its behaviour is reported in `docs/operating-calendar.md` and `docs/route-simulation.md`.
- Before the full run, seed 0 of cases C1 and C4 was executed once to check that the script ran. Nothing
  in the design or code was changed after that check.
