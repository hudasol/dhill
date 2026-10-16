# Technical brief: heat and dust operating limits for autonomous ground robots in the Gulf

Huda Mueen, Dhill project. This brief describes where the software could fit. It implies no existing
relationship with EDGE or its entities and claims no result on any EDGE platform.

## What the evidence shows and does not show

The method runs end to end on recorded Gulf weather and names the component that limits each mission. All
robot profiles are at evidence level L0 (assumed parameters), every "true" robot used for scoring is
synthetic and shares the model's structure, and there is no field data. The envelope's advantage is a
reasoned per component guarantee, not productivity (`docs/prereg-results.md`, H4).

## Operational problem

Ground robots in the Gulf meet air near 50 degC, direct sun and heavy dust, while platform ratings are ambient
air limits: the Clearpath Jackal and Husky are rated at or below 45 degC (`docs/robot-sources.md`). A robot in
sun runs hotter than the air, and battery, computer and sensors each have their own limit.

## Approach

For a platform profile, a weather forecast or record, and a mission, Dhill integrates a six node thermal
network with battery and dust models under Monte Carlo uncertainty and returns GO, DERATE (largest safe scale)
or PARK, with the binding component and the probability of exceeding a hard limit (`docs/model-card.md`).

## Evidence so far, with labels

| Result | Label | Source |
|---|---|---|
| Six UAE sites, 2015 to 2025: air above 45 degC in 0.8 % of hours; Jackal profile GO 63.9 %, DERATE 16.5 %, PARK 19.6 % of hours | Recorded weather, L0 profile | `docs/operating-calendar.md` |
| Raising three unmeasured conductances to match the rating moved GO from 6.0 % to 63.9 % | Sensitivity of the answer to assumptions | `docs/operating-calendar.md` |
| PM10 fill and day sampling change the headline by at most 0.3 points | Method checks | `docs/evidence-checks.md` |
| 80 runs: no risky hour for the envelope; a 40 degC air rule slightly more productive; 2 of 6 predictions hit | Synthetic, preregistered | `docs/prereg-results.md` |
| Patrol routes: envelope plans (reduced speed, shade, timing) exceeded no hard limit but completed fewer Jackal requests than the shortest path | Recorded weather, synthetic robots, Python simulation | `docs/route-simulation.md` |
| Field validation | None | `docs/validation-protocol.md` |

Open issues and their status: `docs/known-issues.md`.

## Integration surface

From `docs/edge-integration.md`: self hosted container with no outbound calls required; REST and JSON API and a
Python library; CSV telemetry and a ROS 2 recorder (not yet run on a live graph); weather from the operator's
own station, a CSV feed or Open-Meteo; optional API key and audit log; SBOM and dependency audit configured
in CI. No compliance with MIL-STD-810H, IEC 60529 or similar is claimed.

## What a pilot would need

1. One platform with a thermal design description, or permission to instrument it externally.
2. Telemetry at 1 to 5 minute intervals: shell, interior, battery, computer and sensor temperatures and
   electrical power (`docs/field-test-kit.md`).
3. A site weather source and a host engineer to agree the bench and field protocols, including a prediction
   committed before the validation run (`docs/validation-protocol.md`).
4. About three days of logging and two weeks of analysis for a first L2 profile.
