# Preregistered evaluation v0.7 (Jackal): results

Rendered by `examples/prereg_eval_jackal.py` from `examples/prereg_results_v07.json`; do not edit by hand.
`tests/test_prereg_v07.py` fails if a number here differs from the JSON. Design, predictions and failure
criteria were fixed in `docs/preregistration-v0.7.md` and committed before the script existed.

**SYNTHETIC world.** Hidden robots and forecast error draws are synthetic, built by the same author as
the method, with the same model structure. Weather is synthetic in C1 to C3 and recorded (Open-Meteo
archive and CAMS PM10, July 2024) in C4 (Abu Dhabi) and C5 (Al Ain). The profile is L0.

Runs: 100 in W1 (planner's prior) and 100 in W2 (three conductances at their
values before the fix). Intervals: 95 % percentile bootstrap over seeds.

## Predictions against results

| ID | Prediction | Result | 95 % interval | Verdict |
|---|---|---|---|---|
| H1 | W1: P5 zero risky hours in at least 90 % of runs | 95.0 % | 85.0 % to 100.0 % | HIT |
| H2 | W1: P1 (45 degC rule) at least one risky hour in at least 50 % of runs | 100.0 % | 100.0 % to 100.0 % | HIT |
| H3 | W1: P4 (no uncertainty) at least one risky hour in at least 30 % of runs | 71.0 % | 52.0 % to 89.0 % | HIT |
| H4 | W1: mean (P5 minus P2) productive hours below 0, interval below 0 (envelope loses) | -3.34 h | -3.55 h to -3.13 h | HIT |
| H5 | W1: coverage of the 95 % risk quantile between 0.90 and 0.995 | 0.9334 | 0.8326 to 0.9958 | HIT |
| H6 | W2: P5 at least one risky hour in at least 50 % of runs (envelope loses) | 29.0 % | 10.0 % to 49.0 % | MISS |
| H7 | W2: mean (P1 minus P5) violation probability above 0, interval above 0 | +28.8 points | +23.0 points to +35.2 points | HIT |

6 of 7 predictions hit.

## Policy summary, W1

| Policy | Mean productive h | Runs with a risky hour | Mean P(violation), operated slots |
|---|---:|---:|---:|
| P1 Air at or below 45 degC | 20.20 | 100 | 20.8 % |
| P2 Air at or below 40 degC | 15.40 | 64 | 9.4 % |
| P3 Midday ban 12:30 to 15:00 | 21.00 | 100 | 25.1 % |
| P4 Envelope, no uncertainty | 16.20 | 71 | 7.0 % |
| P5 Envelope L0 | 12.06 | 5 | 0.4 % |

## Policy summary, W2

| Policy | Mean productive h | Runs with a risky hour | Mean P(violation), operated slots |
|---|---:|---:|---:|
| P1 Air at or below 45 degC | 20.20 | 100 | 39.1 % |
| P2 Air at or below 40 degC | 15.40 | 76 | 25.8 % |
| P3 Midday ban 12:30 to 15:00 | 21.00 | 100 | 43.5 % |
| P4 Envelope, no uncertainty | 16.20 | 100 | 25.0 % |
| P5 Envelope L0 | 12.06 | 29 | 10.3 % |

## Per world and case (20 seeds each): mean productive hours / runs with a risky hour

| World and case | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| W1 C1 abu_dhabi summer_clear | 24.0 / 20 | 14.0 / 19 | 21.0 / 20 | 16.1 / 14 | 12.3 / 1 |
| W1 C2 sweihan heatwave | 14.0 / 20 | 10.0 / 4 | 21.0 / 20 | 13.7 / 13 | 10.2 / 1 |
| W1 C3 dubai humid_coastal | 24.0 / 20 | 18.0 / 20 | 21.0 / 20 | 16.1 / 15 | 12.0 / 1 |
| W1 C4 abu_dhabi recorded | 24.0 / 20 | 24.0 / 20 | 21.0 / 20 | 20.0 / 15 | 13.8 / 1 |
| W1 C5 al_ain recorded | 15.0 / 20 | 11.0 / 1 | 21.0 / 20 | 15.2 / 14 | 12.0 / 1 |
| W2 C1 abu_dhabi summer_clear | 24.0 / 20 | 14.0 / 20 | 21.0 / 20 | 16.1 / 20 | 12.3 / 6 |
| W2 C2 sweihan heatwave | 14.0 / 20 | 10.0 / 9 | 21.0 / 20 | 13.7 / 20 | 10.2 / 6 |
| W2 C3 dubai humid_coastal | 24.0 / 20 | 18.0 / 20 | 21.0 / 20 | 16.1 / 20 | 12.0 / 5 |
| W2 C4 abu_dhabi recorded | 24.0 / 20 | 24.0 / 20 | 21.0 / 20 | 20.0 / 20 | 13.8 / 6 |
| W2 C5 al_ain recorded | 15.0 / 20 | 11.0 / 7 | 21.0 / 20 | 15.2 / 20 | 12.0 / 6 |

## Reading

Written after the run. It interprets the tables above and changes none of them.

- **H1 hit, with one exception that matters.** All five W1 runs with a risky hour for the envelope come from
  one hidden robot (seed 18), across all five cases. Its DC-DC converter efficiency was drawn at about 0.58
  against the profile's assumed 0.90 (computed by `hidden_robot(18, "W1")` in the script). That is the
  parameter `docs/sensitivity.md` ranks first for the Jackal. The envelope's prior spread on it was not wide
  enough for that draw.
- **H4 hit: the envelope loses on productivity, as predicted.** The 40 degC air rule delivered about three
  more productive hours a day than the envelope. The rule paid for them with risky hours in most W1 runs.
  The envelope's value for the Jackal is safety with stated reasons, not throughput.
- **H6 missed: the envelope held up better than predicted under the old conductances.** With shell,
  battery and compute conductances at their values before the fix, the envelope had a risky hour in 29 % of
  W2 runs, not the predicted 50 % or more. Its safety does depend on those conductances (risky runs rose
  from 5 % in W1), but less sharply than expected. The interval reaches 49 %, so the miss is not decisive.
- **H5 hit, with a wide interval.** Coverage is closer to the stated 95 % than for the medium UGV in v0.6,
  and the seed level interval spans from overconfident to overcautious.
- **H2, H3 and H7 hit.** The datasheet rating rule (45 degC air) was risky in every W1 run; ignoring
  parameter uncertainty was risky in most; and the envelope stayed safer than the rating rule even in W2.

## Limitations

- The world is synthetic and shares the engine's structure and author; structural model error is absent.
- W1 is the planner's own prior, which favours the planner. W2 changes three parameters only.
- The scale of the H4 loss depends on the 1.5 h parked soak in sun before each mission, a choice of this
  method, and on the battery limit, an assumption in the profile.
- One check run on seed 999 (not an evaluation seed) preceded the full run. Nothing was changed after it.
