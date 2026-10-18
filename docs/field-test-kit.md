# Field test kit: one page for the robotics lead

Goal: move one robot from L0 (illustrative) to L2/L3 evidence so Dhill's decisions can be tested against reality.
Read `docs/validation-protocol.md` for the full design; this is the short version.

## What to measure first (ranked by what moves the answer)
`docs/sensitivity.md` shows which unknowns drive the uncertainty for the medium UGV profile. In order:

1. **Drive efficiency / battery terminal power while driving** (about 60 % of peak temperature variance). Log pack
   voltage and current at 1 Hz+ over a real route. Cheapest, biggest win.
2. **Battery heat capacity and pack thermal behaviour** (about 11 %): weigh the pack; log pack temperature through
   a heat up and a cool down.
3. **DC-DC / converter efficiency** (about 10 %): log input and output power.
4. Shell absorptance and shell to interior conductance: from the calibration run below.

## Minimum sensor list (indicative; confirm with suppliers)
| Item | Purpose | Notes |
|---|---|---|
| 4-6 thermocouples/NTCs (K-type or 10k NTC) | shell, interior air, battery, motor housing, compute heatsink, LiDAR housing | log at ≥ 0.1 Hz, same clock |
| Pack V/I logging (shunt or BMS CAN) | measured electrical power | clock sync with temperatures |
| Ambient T/RH + wind (small weather station) | on site forcing | place shaded; wind at robot height |
| Pyranometer or lux sensor + calibrated reference | irradiance | optional but strongly preferred |
| Dust: optical particle counter | PM10 | optional |
| Compute die temperature, SoC | from the OS / BMS | free, log them |
Costs are not quoted here on purpose; get supplier quotes.

## Protocol (one robot, ~3 days)
1. Day 0: instrument, record parameters you can measure (mass, dimensions, battery data sheet, cooling setpoint).
2. Day 1-2 (**calibration campaign**): run mixed drive/idle/park cycles across a full day including midday. Save as
   CSV (see `examples/telemetry_demo.csv`). Run `dhill calibrate`.
3. Day 3 (**independent validation campaign**): a different day, different route. Do not use it to fit anything.
   Check it with `dhill validate --profile <calibrated.json> --telemetry <day3.csv> --weather-csv <station.csv>
   --report <report.md>`; it applies the V2 criteria of `docs/validation-protocol.md` and exits 3 on FAIL. A
   SYNTHETIC dry run of days 1 to 3 is in `examples/field_day_demo_output.md`.
4. Before Day 3, fill in `docs/prediction-template.md` and commit it **before** the run. Compare predicted vs
   measured peaks afterwards and report misses, not just hits.
5. Only a Day-3-style independent campaign can move a profile to L3. Fitting and testing on the same data stays L2.

## Safety
Do not run a robot toward its limits to "find the edge". Use conservative stop thresholds; the goal is to
validate the model in the safe region and record near misses.
