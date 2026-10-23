# Logging session quickstart (one page for the supervisor)

A summary of `docs/field-test-kit.md`, `docs/validation-protocol.md` and
`docs/proposals/aau-session-preregistration.md`. Where this page and those documents differ, those documents
apply. The robot is not modified; sensors are attached externally or read from its own logs.

## What to bring

- The robot (Clearpath Jackal or similar), charged, with its own thermal protection enabled.
- 4 to 6 thermocouples or 10k NTC sensors and a logger: shell, interior air, battery, compute heatsink, LiDAR
  housing, motor housing.
- Pack voltage and current logging (shunt or the BMS over CAN), on the same clock as the temperatures.
- A small weather station placed in shade: air temperature, dew point or humidity, wind (record the height),
  and a pyranometer if available.
- A laptop with Dhill installed (`pip install -e .`), a surface thermometer for the test ground, and a
  stopwatch or log sheet for mission start and stop times.

## What to log

Robot file, one row per sample, UTC times on a uniform grid (format of `examples/telemetry_demo.csv`):

`time_utc, p_compute_w, p_lidar_w, p_comms_w, p_drive_mech_w, p_payload_w, t_shell_c, t_interior_c,
t_battery_c, t_compute_c, t_lidar_c, t_motor_c`

The five power columns are required; temperature columns may be left out if a node is not instrumented.

Weather station file, hourly or finer:

`time_utc, t_air_c, dew_c, wind10_ms, pm10_ugm3, precip_mm_h, ghi_wm2`

## Sampling rate

Temperatures at 0.1 Hz or faster; pack voltage and current at 1 Hz or faster. Resample both to one uniform
grid (for example 60 s) before running the commands. All clocks in UTC and synchronised at the start of each
day.

## Safety stop

The supervisor may stop the run at any time. The run stops in any case when a measured component temperature
comes within 5 K of its hard limit. Do not drive the robot towards its limits to find the edge. A stop is
recorded as a result, not discarded.

## The three commands

Days 1 and 2 (calibration):

```bash
dhill calibrate --profile clearpath_jackal --telemetry day1_day2.csv --weather-csv station.csv --site al_ain --out calibrated.json
```

The day before day 3 (prediction; paste the output into the preregistration and commit it before the run):

```bash
dhill timeline --profile calibrated.json --site al_ain --source live --days 2 --step-min 60 --samples 64
```

Day 3 (validation, other day and route, not used for fitting):

```bash
dhill validate --profile calibrated.json --telemetry day3.csv --weather-csv station.csv --site al_ain --report docs/aau-validation-report.md
```

## What a failed result means

`dhill validate` reports FAIL (exit code 3) when any instrumented node has an error of 2 K or more, or the
model is colder than the measurement by more than 2 K at the peak. A FAIL means the calibrated profile does not
reproduce this robot on that day within the agreed limits; it does not mean the session was wasted. The report
is published with every miss, the profile does not move to L2, and the per node errors show which assumptions
to revisit. A PASS on one day moves the profile to L2 for that robot only; it is not evidence for other
robots, sites or seasons.
