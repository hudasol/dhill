# Proposal to the Al Ain University robotics programme: one supervised logging session

**From:** Huda Mueen. **Project:** Dhill, heat and dust operating envelope software for outdoor ground robots.
**Request:** one robot, one supervised logging session, one senior robotics supervisor. No purchase required.

## 1. What the evidence shows and does not show

**Shows.** The software runs end to end: on eleven years of recorded weather at six UAE sites it assigns
each hour GO, DERATE or PARK for a robot profile (`docs/operating-calendar.md`); in a synthetic world its plans had
no risky hour (violation probability above 5 %) in any of 80 preregistered runs (`docs/prereg-results.md`, H1); its decisions
name the component that binds.
**Does not show.** All robot profiles are at evidence level L0 (assumed parameters). Every "true" robot used
for scoring is synthetic and shares the model's structure. There is no field data. The envelope's advantage
is a reasoned per component guarantee, not productivity: a 40 degC air rule was slightly more productive in
the preregistered test (H4 missed), and only 2 of 6 predictions hit.

## 2. Problem

Outdoor ground robots in the Gulf are run by the air temperature on their datasheet or by blanket rules.
The Clearpath Jackal and Husky are rated at or below 45 degC ambient, and the Husky's datasheet and manual
disagree (`docs/robot-sources.md`). A rating in air says nothing about a robot in sun.

## 3. What exists

| Item | File | Status |
|---|---|---|
| Thermal, battery and dust model; GO / DERATE / PARK at a 95 % risk quantile | `src/dhill/envelope.py`, `docs/model-card.md` | Unit tested |
| Calibration from telemetry with hold-out error | `src/dhill/calibrate.py` | Synthetic data only |
| ROS 2 telemetry recorder | `src/dhill/ros2_bridge/recorder.py` | Never run on a live robot |
| Operating calendar, six sites, 2015 to 2025 | `docs/operating-calendar.md`, `docs/evidence-checks.md` | Recorded weather, L0 profile |
| Patrol route simulation | `docs/route-simulation.md` | Python simulation, synthetic true robots |
| Preregistered evaluation and addenda | `docs/prereg-results.md`, `docs/prereg-results-addendum-fixed-profile.md`, `docs/prereg-coverage-bootstrap-addendum.md` | Synthetic; 2 of 6 hits |
| Field test kit, protocol, prediction template | `docs/field-test-kit.md`, `docs/validation-protocol.md`, `docs/prediction-template.md` | Ready, unused |

## 4. Why a robot is needed

The datasheet anchored Jackal profile has 5 of 60 parameters from the datasheet (`docs/robot-sources.md`).
Three conductances were raised so the profile is consistent with its 45 degC rating; that change alone moved
the calendar's GO share from 6.0 % to 63.9 % of hours (`docs/operating-calendar.md`). The air exceeds 45 degC in
0.8 % of recorded hours, yet the envelope withholds GO in 36.1 % of hours; the document attributes the gap to
sun on the robot and the parked soak before each mission (same file). When three unmeasured numbers move the answer this much, only measurement can settle it.

**What a supervisor would check first.** For the Jackal on a hot morning the battery binds, and three
assumed parameters carry 82 % of the additive variance of its peak (`docs/sensitivity.md`, Jackal section):
the DC-DC converter efficiency (`power.dcdc_efficiency`, 65 %), the drive efficiency
(`motors.drive_efficiency`, 13 %) and the ground heating coefficient (`environment.ground_rise_k_per_kw_m2`,
5 %). The first two are measured by logging battery terminal and converter output power on a short route; the
third by a surface thermometer on the test ground. The raised conductances are the next check
(`docs/robot-sources.md`).

## 5. The request

1. **One robot** the programme already operates outdoors (Jackal, Husky or similar), about three working days
   within six weeks. Sensors attached externally or read from the robot's own logs; no modification.
2. **One supervised logging session** following `docs/field-test-kit.md`: temperatures on shell, interior,
   battery, motor housing, computer heat sink and sensor housing; pack voltage and current; a small weather
   station. Driven only inside the normal operating range.
3. **A senior robotics supervisor** to approve the protocol, own robot safety and sign the preregistered
   prediction before the validation day.

## 6. Timeline (weeks)

| Week | Work | Output |
|---|---|---|
| 1 | Agree platform, sensors, route and safety stops | Signed test plan |
| 2 | Record measurable parameters (mass, pack and cell data, component limits) | Profile at L1 |
| 3 | Days 1 and 2: calibration runs across a full day | Telemetry; `dhill calibrate` result |
| 4 | Commit `docs/prediction-template.md`, then Day 3: validation on another day and route | Prediction; validation data |
| 5 | Compare predicted and measured peaks; report hits and misses | Validation report |
| 6 | Joint write up; decide on a summer repeat | Report; profile at L2 if passed |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Session in the cool season tests mid range temperatures only | State it; plan a summer repeat |
| Robot hardware at risk | No run toward limits; the robot's own protection stays active; supervisor can stop at any time (`docs/validation-protocol.md`) |
| Model structurally wrong for this robot | A valid result; reported, not tuned away |
| ROS 2 recorder fails on the live graph | Fall back to the robot's logs and a separate logger |

## 8. Success and failure

**Success:** hold-out error under 2 K on every instrumented node and the model not colder than measurement
by more than 2 K at peak (`docs/validation-protocol.md`); the profile moves to L2. **Failure:** either
criterion missed on the preregistered day. A failure still shows which assumptions were wrong and by how much.

No compliance with any standard is claimed. The robot owner keeps all robot data.
