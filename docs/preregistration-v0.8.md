# Preregistration for version 0.8

Author: Huda Mueen. Written on 3 November 2026, before any experiment of section 5 was run.

Everything in this document is synthetic and at evidence level L0. The reference robots are
simulated by an independent model (`src/dhill/plant`) and are not hardware. No result here is a
measurement of a real robot. The one external dependency for any claim about hardware is an
instrumented robot run, planned with Al Ain University.

This file is not edited after the first experiment is run. Corrections and new information are
added only as dated addenda at the end.

## 1. Disclosure of what was already done

1. The independent reference model was developed and unit tested before this document was written.
   During development its rating filter (datasheet style acceptance at 45 degC in shade for two
   hours with no hard limit exceeded) was run for a few seeds. The acceptance rates observed were
   0.91 for `small_ugv`, 1.0 for `delivery` and 1.0 for `pv_cleaner`. The delivery and PV classes are
   therefore thermally benign under the rating, and the engine may rarely bind for them. This is
   reported as found and is not tuned.
2. Pilot runs for debugging and for cost estimates use seeds 900 to 999 only. No pilot seed appears
   in any reported result. Pilots may change code and run sizes only through a dated addendum made
   before the final run.
3. Weather records available offline are three six day July windows from reanalysis: Abu Dhabi 1 to 6
   July 2021, Abu Dhabi 1 to 6 July 2024 and Al Ain 6 to 11 July 2024 (`tests/data/climatology`). A
   full eleven year calendar could not be rebuilt here because the download service rate limited
   the request. Section 5.3 therefore uses a reduced July calendar and says so wherever it is quoted.
4. Evaluation seeds were not examined before this document was committed.

## 2. Common design

Robots. A hidden robot is a draw from `draw_rated_plants(n, seed, cls=...)`. The classes are
`small_ugv`, `delivery` and `pv_cleaner`. The engine never sees the hidden parameters: for each class
it uses the class profile (`ugv_medium_inspection`, `sidewalk_delivery_robot`, `pv_cleaning_robot`)
at its stated evidence level L0.

Independence. `tests/test_structural.py` fails if the simulator package imports any engine physics
module (`dhill.physics`, `dhill.envelope`, `dhill.profiles`).

Cases. A case is one robot, one day of the three weather records, and one local start hour from 06 to
18 inclusive, with a one hour drive mission. Local time is UTC plus 4 hours. Scenario S1 (structure
only) is the headline. S2 (moving shade), S3 (soiled robot), S4 (forecast bias of 2 K and 10 percent
brightness) and S5 (dust front after fifteen minutes) are reported separately and never pooled with
S1.

Engine configuration. `EngineConfig(n_mc=64, dt_s=600, precondition_h=1.5, seed=7)`, risk quantile
0.95 from the profile.

Breach. A breach is a case in which the plant peak temperature of any component exceeds the allowed
value used by the engine (`limit_c` minus `margin_k`), or the plant minimum state of charge falls below
the profile reserve. Exceedance of the hard limit itself is reported separately.

Oracle. For each robot and case, the largest scale on the grid 0, 0.1, ..., 1.0 whose plant run does
not breach. The perception cap is a common constraint applied to every policy and to the oracle.

Productive hours. Executed scale multiplied by one hour, summed over cases. Missed productive hours
are oracle productive hours minus policy productive hours.

Policies.

| Id | Policy |
|---|---|
| P1 | Always scale 1.0, no envelope. |
| P2 | Scale 1.0 if air temperature is below 35 degC, otherwise 0. |
| P3 | Engine with parameter uncertainty and weather error switched off (nominal run, no risk margin). |
| P4 | Engine at the 0.95 quantile, uncalibrated class profile. |
| P5 | As P4 with the split conformal offsets of experiment E2. |
| P6 | Oracle. |

Robots per class: 68 (204 in total). Seeds: evaluation robots use seed 1000 plus the class index,
conformal calibration robots use seed 2000 plus the class index, experiment E3 uses 3000 plus the class
index. Parameter and weather draws inside the engine use seed 7.

## 3. Experiments

### E1. Closed loop with hidden robots

Question. Does the envelope keep hidden robots inside their limits, and what does it cost in
productive hours?

Hypotheses and numerical predictions (S1, all classes pooled, then per class):

| Quantity | Prediction | Range |
|---|---|---|
| P1 breach rate | 0.30 | 0.15 to 0.55 |
| P2 breach rate | 0.12 | 0.03 to 0.30 |
| P3 breach rate | 0.14 | 0.05 to 0.30 |
| P4 breach rate | 0.06 | 0.02 to 0.15 |
| P5 breach rate | 0.04 | 0.01 to 0.08 |
| P4 productive hours as a fraction of the oracle | 0.75 | 0.55 to 0.90 |
| P5 productive hours as a fraction of the oracle | 0.70 | 0.50 to 0.88 |
| Median of (plant peak minus engine risk peak), battery | 0 K | minus 3 to 3 K |
| Interquartile width of (plant peak minus engine risk peak), compute die | 5 K | 2 to 8 K |

Success. P4 breach rate is below P1, P2 and P3 breach rates, and P4 breach rate is at most 0.10.
Failure. P4 breach rate above 0.15, or P4 not below P3. If the delivery or PV class shows fewer than
10 breaching cases for P1, the class is reported as non binding and is excluded from breach
comparisons but kept in the productive hours comparison.

Seeds. Evaluation robots 1000 to 1002 (class index added). Runs: 204 robots by 18 days by 13 hours
by 5 scenarios, each with the six policies.

### E2. Split conformal recalibration of the 95 percent quantile

Question. Does a Mondrian split conformal offset restore the nominal coverage on robots not used to
fit it?

Method. For each class and component, on the calibration robots (seed 2000 plus class index), the
score of a case with positive P4 scale is the plant peak minus the engine risk peak at that scale. The
offset is the empirical quantile of the scores at level ceil((n + 1) times 0.95) divided by n, not
floored at zero. Coverage is the fraction of cases with score at or below zero. Because cases of one
robot are dependent, intervals are bootstrap intervals over robots.

Predictions.

| Quantity | Prediction | Range |
|---|---|---|
| Coverage before, compute die, `small_ugv` | 0.85 | 0.60 to 0.98 |
| Coverage before, battery, `small_ugv` | 0.90 | 0.60 to 0.99 |
| Coverage after, every cell with at least 200 cases, on the evaluation robots | 0.95 | 0.92 to 0.98 |
| Median absolute offset | 1.5 K | 0 to 5 K |

Success. Coverage after lies in 0.93 to 0.97 in every cell with at least 200 cases. Failure. Any such
cell outside 0.90 to 0.99, which is reported with the cell, its offset and its sample size.

Caveat stated in advance. Scores are computed at the scales chosen by P4, while P5 chooses new
scales after the offset is applied, so the score distribution shifts slightly. Coverage is therefore
also reported as the P5 breach rate on the disjoint evaluation robots, and both are shown.

Seeds. Fit on robots 2000 to 2002 (class index added); evaluate on robots 1000 to 1002.

### E3. Calibration under structural mismatch

Question. Does calibrating the class profile on a robot's own telemetry reduce breaches on other
days, when the engine's six node structure differs from the sixteen node robot?

Method. For each of 20 robots per class (seed 3000 plus class index), generate noisy telemetry
(0.3 K noise, 300 s, sensors on shell, interior, battery and compute) from one day of the first
record, calibrate with `dhill.calibrate.calibrate` using its default free parameters, then run P4 once
with the class profile (uncalibrated) and once with the calibrated profile, on days not used for
calibration.

Predictions.

| Quantity | Prediction | Range |
|---|---|---|
| Held out RMSE reduction on measured nodes | 40 percent | 15 to 70 percent |
| Breach rate, uncalibrated | 0.07 | 0.02 to 0.15 |
| Breach rate, calibrated | 0.05 | 0.01 to 0.12 |
| Productive hours, calibrated minus uncalibrated, fraction of oracle | plus 0.05 | minus 0.05 to plus 0.15 |

Success. Calibrated breach rate is no higher than uncalibrated, and the held out RMSE is reduced.
Failure. Calibrated breach rate exceeds uncalibrated by more than 0.02.

This is the prediction most likely to fail. Calibration fits a six node model to a sixteen node
robot, so the fitted conductances can absorb structural error on the training day and still produce a
colder or hotter peak on other days, and a profile that also becomes tighter in its stated
uncertainty (calibrated sources carry a smaller spread) can raise the breach rate even as the RMSE
falls. If this happens it is reported as the finding.

### E4. Calendar sensitivity with Morris screening and Sobol indices

Question. How wide is the GO share of the calendar when the unmeasured parameters of the Jackal
profile are varied jointly, and which parameters drive it?

Method. Profile `clearpath_jackal` (L0). Reduced calendar: the three July records, every local hour,
a one hour drive mission at full scale, engine run nominal (parameter and weather uncertainty off), so
the output is a deterministic function of the parameter vector. Every parameter whose source is
`assumption` or `textbook` is varied as `value times exp(sigma times z)`, with z standard normal
truncated to plus or minus 2 and the result clipped to the registry bounds. Morris screening with
SALib uses 16 trajectories and four levels. The eight parameters with the largest Morris mu star are
taken to Sobol analysis (Saltelli sampling, base size 512, first and total order indices, 95 percent
bootstrap intervals, seed 4000). The headline becomes the 5th to 95th percentile interval of the GO
share and the ranking, with the old point value (nominal parameters on the same reduced calendar)
shown beside it. The earlier headline figures of 6.0 to 63.9 percent come from the full eleven year
calendar and are not directly comparable with the reduced calendar.

Predictions.

| Quantity | Prediction | Range |
|---|---|---|
| Width of the 5th to 95th percentile interval of the GO share | 25 points | 10 to 50 points |
| Old point value relative to the interval | inside the interval | inside or within 5 points |
| Sum of first order Sobol indices | 0.75 | 0.50 to 0.95 |
| Top three parameters by total order index include at least two of `power.dcdc_efficiency`, `motors.drive_efficiency`, `environment.ground_rise_k_per_kw_m2` | yes | not applicable |

Success. All four predictions hold. Failure. The interval is narrower than 5 points or wider than 70
points, or fewer than two of the three named parameters appear in the top three.

Cost control. If the evaluation count (about 5,000) is too slow, the Sobol base size is lowered to 256
by a dated addendum written before the final run.

### E5. Obstacle shade from solar position in the route study

Question. Does shade from synthetic street canyons, computed from solar position and obstacle
geometry, change when and where a robot may drive?

Method. Solar position from `pvlib` at the Al Ain and Abu Dhabi coordinates for the 18 days. An
infinite street canyon with obstacle height to street width ratio 0.2, 0.5, 1.0 and 2.0, with the
street oriented north to south and east to west, labelled synthetic. Beam shade fraction at the robot is
the fraction of the beam path blocked. The route study is rerun with this shade against the existing
fixed shade assumption.

Prediction. Midday is when parking occurs and the sun is within about 10 degrees of the zenith at
these latitudes in July, so canyon shade adds little at the binding hours. Predicted gain in GO hours
per day between 10:00 and 15:00 local: at most 0.5 hour for every ratio up to 2.0 and both
orientations. Larger gains, up to 2 hours, are predicted in the early morning and late afternoon.

Success. Midday gain at most 0.5 hour and monotone non decreasing in the ratio. Failure. Any midday
gain above 1.0 hour, or a decrease with the ratio.

## 4. Reporting

`docs/prereg-results-v08.md` lists every prediction above beside the observed value, marks each as
hit or miss, and discusses misses. Raw outputs are committed as JSON next to the scripts. A published
number that changes is entered in `CHANGELOG.md` and `docs/known-issues.md` with the old and new
value, and the dependent documents are regenerated from code.

## 5. Exact commands

```
python examples/structural_eval.py fit-conformal --robots-per-class 68 --seed 2000 --out examples/conformal_offsets_v08.json
python examples/structural_eval.py evaluate --robots-per-class 68 --seed 1000 --offsets examples/conformal_offsets_v08.json --out examples/structural_results_v08.json
python examples/calibration_mismatch.py --robots-per-class 20 --seed 3000 --out examples/calibration_mismatch_v08.json
python examples/calendar_sobol.py --morris-r 16 --sobol-n 512 --seed 4000 --out examples/calendar_sobol_v08.json
python examples/route_solar_shade.py --out examples/route_solar_shade_v08.json
```

## 6. Prediction most likely to fail

E3: that the calibrated breach rate is no higher than the uncalibrated one. The reasoning is given in
the E3 section above.

## Addenda

None yet.
