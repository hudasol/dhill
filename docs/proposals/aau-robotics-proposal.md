# Proposal to the Al Ain University robotics programme: one supervised logging session

**From:** Huda Mueen. **Project:** Dhill, heat and dust operating envelope software for outdoor ground robots.
**Request:** one robot, one supervised logging session, one senior robotics supervisor. No purchase required.

## 1. Problem

Outdoor ground robots in the Gulf are run by the air temperature on their datasheet or by blanket rules
such as no midday work. Neither accounts for solar heating, the robot's own heat or its recent history. The
Clearpath Jackal and Husky datasheets rate ambient operation at or below 45 degC; the Husky's datasheet and
manual disagree on its limit (`docs/robot-sources.md`). Nobody can yet say, from measurement, how many hours
a given robot can work at full speed at a given UAE site.

## 2. What exists (all in the repository)

| Item | File | Status |
|---|---|---|
| Thermal, battery and dust model, GO / DERATE / PARK decisions at a 95 % risk quantile | `src/dhill/envelope.py`, `docs/model-card.md` | Working, unit tested |
| Calibration from telemetry with hold-out error | `src/dhill/calibrate.py` | Tested on synthetic data only |
| ROS 2 telemetry recorder | `src/dhill/ros2_bridge/recorder.py` | Logic tested; never run on a live robot |
| Operating calendar, six UAE sites, recorded weather 2015 to 2025 | `docs/operating-calendar.md` | Runs; result limited by the profile (below) |
| Patrol route simulation | `docs/route-simulation.md` | Python simulation, not a physical test |
| Preregistered evaluation, 80 synthetic runs | `docs/prereg-results.md` | 2 of 6 predictions hit |
| Field test kit, validation protocol, prediction template | `docs/field-test-kit.md`, `docs/validation-protocol.md`, `docs/prediction-template.md` | Ready, unused |
| 134 automated tests | `tests/` (`README.md`) | Passing |

## 3. What is missing, and why a robot is needed

Every robot profile is at evidence level L0. The datasheet anchored Jackal profile has 5 of 60 parameters
from the datasheet and 83 % assumptions (`docs/robot-sources.md`). Run on eleven years of recorded weather,
it returns GO in only 6.0 % of hours, although the air exceeds the 45 degC rating in only 0.8 % of hours
(`docs/operating-calendar.md`). The profile forbids full speed above about 20 degC air, which contradicts the
datasheet; the assumed computer heat path is the likely cause. All comparisons so far use a "true" robot
built by the same author with the same model (`docs/known-issues.md`, items 1 and 2). Only measurement on a
real robot can settle which assumptions are wrong.

## 4. The request

1. **One robot** that the programme already owns and operates outdoors (a Jackal, a Husky or similar), for
   about three working days within six weeks. The robot is not modified; sensors are attached externally or
   read from its own logs.
2. **One supervised logging session** following `docs/field-test-kit.md`: temperature sensors on shell,
   interior, battery, motor housing, computer heat sink and sensor housing; pack voltage and current; a small
   on site weather station. The robot is driven only inside its normal operating range.
3. **A senior robotics supervisor** to approve the protocol, own robot safety, and sign the
   preregistered prediction before the validation day.

## 5. Timeline (weeks)

| Week | Work | Output |
|---|---|---|
| 1 | Agree platform, sensors, route and safety stops with the supervisor | Signed test plan |
| 2 | Record measurable parameters (mass, pack and cell data, component limits from datasheets) | Profile at L1 |
| 3 | Day 1 and 2: calibration runs (drive, idle, park, across a full day) | Telemetry CSV; `dhill calibrate` result |
| 4 | Commit `docs/prediction-template.md`, then Day 3: independent validation run on another day and route | Preregistered prediction; validation data |
| 5 | Compare predicted and measured peaks; report hits and misses | Validation report |
| 6 | Joint write up; decide on a summer repeat | Report, profile at L2 if passed |

## 6. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Session falls in the cool season | Tests mid range temperatures only, not 45 degC conditions | State this in the report; plan a summer repeat |
| Robot hardware at risk | Damage, safety | No run toward limits; the robot's own thermal protection stays active; supervisor can stop at any time (`docs/validation-protocol.md`) |
| Model structurally wrong for this robot | Large hold-out error | That is a valid result; it is reported, not tuned away |
| ROS 2 recorder fails on the live graph | Lost data | Fall back to the robot's own logs and a separate data logger |
| Robot or supervisor unavailable | Delay | The software work continues; the request stands |

## 7. What success and failure look like

**Success:** hold-out error under 2 K on every instrumented node, and the model not colder than measurement by
more than 2 K at peak (pass criterion in `docs/validation-protocol.md`); the profile moves to L2.
**Failure:** either criterion is missed on the preregistered validation day. A failure is still a useful
result, because it shows which assumptions in the profile were wrong and by how much.

No compliance with any standard is claimed. The robot owner keeps ownership of all robot data; the analysis
code is in this repository.
