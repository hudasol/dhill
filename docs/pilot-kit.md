# Pilot kit

This kit takes one robot from evidence level L0 to L2, and to L3 after an independent day. It collects the
steps scattered across the field test kit, the logging session quickstart and the validation protocol into
one sequence. Nothing in it has been run on a real robot. The real run is the one external dependency of
the project, and it is planned with Al Ain University.

## What the project needs from a host

* One robot of any type that Dhill can describe: a battery, a compute module, a sensor and motors.
* A person who can attach temperature sensors and read the battery and compute telemetry.
* Three days on site, one of them a hot day, with a small weather station or a nearby station record.
* An independent hardware thermal protection on the robot, which Dhill never replaces.

## Step by step

1. **Describe the robot.** Run `dhill profile new --out robot.yaml` and answer from the datasheet. Every
   answer records its source. The profile is L0 whatever is entered. Check it with `dhill profile check`.
2. **Predict before measuring.** Copy `docs/prediction-template.md`, fill in the peak temperatures Dhill
   expects on the calibration day and commit the file before the run.
3. **Log the calibration day.** Follow `docs/logging-session-quickstart.md`. Log shell, interior, battery
   and compute temperatures, battery power and the weather, on one time base.
4. **Calibrate.** Run `dhill calibrate --profile robot.yaml --telemetry day1.csv --out calibrated.json`.
   Read which parameters were identified. A parameter that was not identified keeps its prior.
5. **Log an independent day.** A different day and route. Do not use it to fit anything.
6. **Validate.** Run `dhill validate --profile calibrated.json --telemetry day2.csv --weather-csv station.csv
   --report report.md`. The V2 criteria are in `docs/validation-protocol.md`. A failure is a result and is
   reported with the prediction.
7. **Report both outcomes.** Misses are reported with hits. A profile moves to L3 only after an independent
   campaign passes. Fitting and testing on the same data stays L2.

## What the result can and cannot say

A pass says that Dhill matched this robot on that day under that weather. It does not say that Dhill is
accurate for other robots, other seasons or other dust conditions. A failure says which node the model did
not match, and the calibration report says which parameter could not be identified from the data.

## Files used

| File | Purpose |
|---|---|
| `docs/field-test-kit.md` | Sensors, ranked quantities to measure, safety |
| `docs/logging-session-quickstart.md` | The supervisor's one page and the exact commands |
| `docs/validation-protocol.md` | Pass criteria for the bench and the field |
| `docs/prediction-template.md` | Predictions committed before the run |
| `examples/telemetry_demo.csv` | The telemetry file format |
| `examples/fleet_example.yaml` | A fleet file for planning after the profile is calibrated |
