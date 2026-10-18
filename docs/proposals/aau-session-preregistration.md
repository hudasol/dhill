# Preregistered prediction: AAU logging session, validation day (DRAFT)

Draft prepared on 18 October 2026 from `docs/prediction-template.md`. Complete the blanks marked ___, run the
commands below the day before the validation run, paste their output, have the supervisor sign, and commit
this file **before** day 3 starts. After the commit, do not edit the sections above "After the run".

- Date and time of registration (UTC): ___
- Git commit of Dhill used: ___ (v0.6.0 or later; record `git rev-parse --short HEAD`)
- Profile id and file hash: `clearpath_jackal`, sha256 prefix `3e340ea2fa70` at v0.6.0 (line endings
  normalised). After calibration on days 1 and 2 the calibrated profile file and its hash: ___
- Robot: model ___, serial ___, computer ___, battery pack ___ (from step 3 of `docs/roadmap-to-v1.md`)
- Calibration data used: day 1 file ___, day 2 file ___ (`dhill calibrate` hold out error ___ K)
- Weather source: on site station logged to CSV with the columns `time_utc, t_air_c, dew_c, wind10_ms,
  pm10_ugm3, precip_mm_h, ghi_wm2` (`src/dhill/weather/csvio.py`); the model expects wind at 10 m, so record the
  anemometer height: ___ m. Forecast used for the prediction: Open-Meteo, issue time ___ UTC
- Site: Al Ain University campus, Al Ain (site preset `al_ain`, 24.21 N, 55.76 E; measure the actual
  coordinates on the day: ___); route ___, different from days 1 and 2
- Mission mode and duration: drive, 1 h missions, start times ___ UTC

## Predictions

Run the day before, with the calibrated profile, and paste the output below:

```bash
dhill timeline --profile <calibrated_profile.json> --site al_ain --source live --days 2 --step-min 60 --samples 64
dhill decide --profile <calibrated_profile.json> --site al_ain --source live --at <start UTC> --samples 64 --json
```

| Slot (UTC) | Decision | Predicted peak (95 % quantile) per component | Binding constraint | P(exceed hard limit) |
|---|---|---|---|---|
| ___ | ___ | ___ | ___ | ___ |

## What counts as a failure (fixed now)

From `docs/validation-protocol.md` (V2), evaluated by `dhill validate` on the day 3 record with the on site
weather:

- RMSE of 2 K or more on any instrumented node; or
- the model colder than the measurement by more than 2 K at the peak on any instrumented node; or
- a GO slot in which any component reaches its hard limit.

Also reported, not a pass criterion: whether each measured peak lies at or below the predicted 95 % quantile
peak, and the forecast versus measured air temperature error, kept separate from model error.

## Safety (fixed now)

The robot's own thermal protection stays enabled. The run is stopped by the supervisor at any time, and in any
case if a measured component temperature comes within 5 K of its hard limit. Stopping is recorded as a result.

## Signatures

- Owner: Huda Mueen, date ___
- Supervisor (Al Ain University robotics programme): name ___, signature ___, date ___

## After the run (fill in, do not edit the above)

`dhill validate --profile <calibrated_profile.json> --telemetry <day3.csv> --weather-csv <station.csv> --site al_ain --report docs/aau-validation-report.md`

| Slot | Measured peak per component | Within prediction? | Notes |
|---|---|---|---|

Summary of misses, and what changes in the model because of them:
