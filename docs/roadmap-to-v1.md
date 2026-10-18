# Roadmap to v1.0

v0.6.0 is a tested proof of concept: every profile is L0 and every "true" robot so far is synthetic
(`docs/overnight-report-3.md`). v1.0.0 is reserved for the first release backed by field data from a real
robot. This page lists what that takes, who does it, and what is already prepared.

## Definition of v1.0.0

All of the following, on one real robot (Clearpath Jackal or similar) logged with the Al Ain University
robotics programme:

1. A calibration record (field days 1 and 2) and an independent validation record (day 3, other day and
   route), with an on site weather station, in the telemetry format of `docs/field-test-kit.md`.
2. A prediction for day 3 committed before the run (`docs/proposals/aau-session-preregistration.md`).
3. `dhill validate` run on day 3 against the calibrated profile, and the report published with every miss.
4. The profile updated from the calibration, at evidence level L2 if day 3 passes; if it fails, the failure is
   published and the profile stays L1 or L0 with the reasons.

A FAIL on day 3 still allows v1.0.0: the release is defined by real field data and an honest report, not by a
pass.

## Steps

| # | Step | Who | Status | Where |
|---|---|---|---|---|
| 1 | Send the proposal and agree a robot, a supervisor and dates | Owner | Ready to send | `docs/proposals/aau-robotics-proposal.md`, `docs/proposals/aau-email-draft.md` |
| 2 | Agree sensors, route, safety stops and pass criteria with the supervisor | Owner and supervisor | Protocol ready | `docs/field-test-kit.md`, `docs/validation-protocol.md` |
| 3 | Record measurable parameters (mass, pack and cell data, component limits) | Owner | Not started | `docs/robot-sources.md` |
| 4 | Days 1 and 2: calibration logging; `dhill calibrate` | Owner with supervisor | Tool ready | `src/dhill/calibrate.py` |
| 5 | Commit the day 3 prediction before the run, signed by the supervisor | Owner and supervisor | Draft ready | `docs/proposals/aau-session-preregistration.md` |
| 6 | Day 3: validation logging; `dhill validate --report` | Owner | Tool ready, dry run done | `src/dhill/validate.py`, `examples/field_day_demo_output.md` |
| 7 | Publish the report, update the profile and the known issues, tag v1.0.0 | Owner | Not started | `docs/release-checklist.md` |
| 8 | Run the literature searches with institutional access | Owner | Not started | `docs/literature-search-protocol.md` |

## Already prepared

- `dhill validate`: replays measured loads through the profile and applies the V2 criteria (RMSE under 2 K;
  not colder than measurement by more than 2 K at the peak) per instrumented node; exit code 3 on FAIL.
- A SYNTHETIC dry run of days 1 to 3 (`examples/field_day_demo.py`): the L0 profile fails on the held out day
  and the calibrated profile passes, as expected when data come from the model itself. It shows the pipeline
  works; it is not evidence.
- What to measure first for the Jackal: DC-DC efficiency, drive efficiency and ground heating
  (`docs/sensitivity.md`), then the three conductances raised to match the rating (`docs/robot-sources.md`).
  The v0.7 evaluation showed one low DC-DC efficiency draw was enough to make the envelope risky
  (`docs/prereg-results-v07.md`).

## Not required for v1.0.0

A summer session (the first session may fall in the cool season and test mid range temperatures only; say so),
a second robot, the ROS 2 recorder on a live graph (useful, not required: the robot's own logs and a separate
logger are acceptable), and L3 (needs an independent campaign over at least two seasons).
