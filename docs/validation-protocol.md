# Validation protocol

| Level | Claim | Evidence required | Status |
|---|---|---|---|
| V0 | Code does what the equations say | Unit tests, energy closure, invariants | Done in CI |
| V1 | Method recovers parameters when the model is right | Synthetic telemetry recovery with hold out | Done (`tests/test_planner_calibrate_cli.py`) |
| V2 | Model matches a real robot on a bench | Climatic chamber or sun lamp runs: step power, record node temperatures; fit; hold out runs | Not started |
| V3 | Decisions are right in the field | Instrumented field campaign over at least two seasons or a heatwave week, sensors on shell, interior, battery, compute, LiDAR; held out days | Not started |

## V2 bench protocol (minimum)
1. Instrument shell, interior air, battery cells, compute heat sink and LiDAR housing (class 1/2 thermocouples or calibrated NTCs); log power at the battery terminals.
2. Run three power steps (idle, half, full) in each of two ambient set points (30 and 45 degC) with and without a radiant source of known flux.
3. Fit with `dhill calibrate`; hold out one run per condition.
4. Pass criterion proposed: hold out RMSE under 2 K on every instrumented node and conservative bias (model not colder than measurement by more than 2 K at peak).

## V3 field protocol (minimum)
1. Two robots of the same type, one run by the Dhill schedule and one by the site's normal schedule, same routes.
2. Record telemetry at 1 to 5 minute intervals plus a weather station on site (temperature, humidity, wind, global irradiance, PM10 optical counter).
3. Track: thermal throttling events, shutdowns, battery temperature maxima, productive hours, intervention count.
4. Pass criteria to be agreed with the host: zero limit exceedances in Dhill scheduled runs; productive hours not lower than baseline minus an agreed tolerance; forecast versus measured temperature error reported separately from model error.
5. Promote the profile to L3 only after a held out period passes.

Safety: all trials need a hardware thermal protection independent of Dhill. Dhill never replaces it.
