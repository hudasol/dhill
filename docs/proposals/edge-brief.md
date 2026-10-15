# Technical brief: heat and dust operating limits for autonomous ground robots in the Gulf

Huda Mueen, Dhill project. This brief describes where the software could fit. It does not imply any existing
relationship with EDGE or its entities, and claims no result on any EDGE platform.

## Operational problem

Unmanned ground vehicles in the Gulf meet air near 50 degC, direct sun and heavy dust. Platform ratings are
ambient air limits: the Clearpath Jackal and Husky are rated at or below 45 degC, and the Husky's datasheet and
manual disagree (`docs/robot-sources.md`). A robot in sun runs hotter than the air, and its battery, computer
and sensors each have their own limit. Operators therefore plan with blanket rules, which park robots
unnecessarily on some hours and expose them on others.

## Approach

For a platform profile, a weather forecast or record, and a mission, Dhill integrates a six node thermal
network with battery and dust models under Monte Carlo uncertainty and returns GO, DERATE (largest safe
speed and power scale) or PARK, naming the binding component and the probability of exceeding a hard limit
(`docs/model-card.md`). Every output carries an evidence level from L0 (assumed) to L3 (independently
validated).

## Evidence so far, with honest labels

| Result | Label | Source |
|---|---|---|
| Recorded weather 2015 to 2025, six UAE sites: air above 45 degC in 0.8 % of hours, yet the L0 Jackal profile is GO in 6.0 % of hours | Real weather, L0 profile; the profile contradicts its datasheet and is the likely cause | `docs/operating-calendar.md` |
| 80 synthetic runs: the uncertainty aware envelope had no risky hour in any run; a 40 degC air rule was slightly more productive (0.41 h per day on average) | Synthetic, preregistered, 2 of 6 predictions hit | `docs/prereg-results.md` |
| Patrol routing: envelope plans use shade and timing, but add delay (108 against 34 min mean finish in Al Ain heat) for a small safety gain, and refuse all missions for the L0 Jackal | Recorded weather, synthetic robots, Python simulation, not Gazebo | `docs/route-simulation.md` |
| Field validation | None yet | `docs/validation-protocol.md` |

The method behaves as designed in a synthetic world built by the same author; it has not been tested on a
real robot. Open issues are listed in `docs/known-issues.md`.

## Integration surface

From `docs/edge-integration.md`: self hosted container with no outbound calls required; REST and JSON API
and a Python library; CSV telemetry and a ROS 2 recorder (logic tested, not yet run on a live graph);
weather from the operator's own station, a CSV feed or Open-Meteo; optional API key and audit log; SBOM and
dependency audit configured in CI. No compliance with MIL-STD-810H, IEC 60529 or similar is claimed.

## What a pilot would need

1. One platform with a thermal design description, or permission to instrument it externally.
2. Telemetry at 1 to 5 minute intervals: shell, interior, battery, computer and sensor temperatures, and
   electrical power (`docs/field-test-kit.md`).
3. A site weather source and a host engineer to agree the bench and field protocols
   (`docs/validation-protocol.md`), including a prediction committed before the validation run.
4. Duration: about three days of logging and two weeks of analysis for a first L2 profile.
