# Dhill (ظل)

**Thermal and dust operating envelope intelligence for autonomous ground systems in hot arid environments.**

*Know when your robot should rest in the shade.*

> **Status: v0.5.0, working proof of concept (TRL 3).** The engine, API, dashboard, planner and calibration run and are tested. Bundled robot profiles are **illustrative (evidence level L0)**; nothing here has been validated against field data. See [Honest limits](#honest-limits).

---

## The problem

Autonomous ground systems in the Gulf work in air near 50 °C, in direct sun, and in some of the heaviest airborne dust measured anywhere. Operators decide when to run with blanket rules ("nothing at midday") or the air temperature rating on a datasheet. Neither accounts for solar heating of the chassis, the heat the robot makes during its own mission, dust on LiDAR windows, filters and heat sinks, or the robot's thermal history before it starts. Robots end up parked unnecessarily, or throttle, shut down and age their batteries early.

## What Dhill does

For a robot profile, a mission, a place and a time, Dhill returns a decision with reasons:

| Decision | Meaning |
|---|---|
| **GO** | Every component stays inside its limit less a margin, for the whole mission, at a 95% risk quantile |
| **DERATE** | Run at a reduced speed/power scale; Dhill finds the largest safe scale and names the binding constraint |
| **PARK** | Not safe even at the minimum scale; Dhill reports the shade fraction that would help and the next feasible window |

Non GO decisions also report the **probability of exceeding a hard limit** and the **time to limit** at full scale. Every decision carries the profile's **evidence level** (L0 uncalibrated, L1 datasheet parameterised, L2 field calibrated, L3 independently validated) and the share of parameters that are assumptions.

Also included: a multiday **timeline**, a **fleet scheduler** (mixed integer programme with rest gaps, concurrency limits and a battery ageing penalty), a **sensitivity analysis** that ranks which unknown parameter to measure first ([`docs/sensitivity.md`](docs/sensitivity.md)), a **policy comparison** against simple operator rules on a hidden robot ([`docs/policy-comparison.md`](docs/policy-comparison.md)), **calibration** from telemetry with confidence intervals and an identifiability flag, an offline **dashboard**, a **REST API**, and a **ROS 2 telemetry recorder**.

## Quick start

```bash
pip install -e ".[dev]"
dhill list sites
dhill decide  --site sweihan --scenario heatwave --at 2026-08-05T09:00
dhill timeline --site sweihan --scenario heatwave --step-min 120
dhill sensitivity --profile ugv_medium_inspection --site sweihan --scenario heatwave --at 2026-08-05T09:00
dhill plan --robots ugv_medium_inspection sidewalk_delivery_robot
dhill serve            # dashboard at http://127.0.0.1:8080
# live forecast and PM10 (Open-Meteo, falls back to synthetic with a warning)
dhill timeline --site abu_dhabi --source live
```
or `docker compose up`.

## What it produces (synthetic weather, illustrative robot)

```
ugv_medium_inspection @ sweihan  (synthetic, L0)  1 h missions
08-05T00:00  GO     1.00 ####################
08-05T04:00  DERATE 0.56 ###########
08-05T06:00  PARK   0.00
08-05T14:00  PARK   0.00
08-05T16:00  DERATE 0.91 ##################
08-05T18:00  GO     1.00 ####################
```

Versus a fixed 08:00 to 17:00 full speed shift, the scheduler completes the same 12 work hours with no predicted limit breach, while the fixed shift would breach a limit in 20 of 24 blocks (`dhill plan --robots ugv_medium_inspection sidewalk_delivery_robot`). That count is **relative to Dhill's own L0 model**: it shows what the method does, and is exactly what a field trial must test.

A second result is worth stating plainly (`examples/value_of_calibration.py`): a nominal model that ignores parameter uncertainty is unsafe in 8 slots against a hidden "true" robot that runs hotter than assumed, while the uncertainty aware envelope is not. Calibration cut hold out temperature error from 1.2 K to 0.4 K. Details and caveats in [`docs/results.md`](docs/results.md).

## Recorded weather, routes and a preregistered test (v0.6 work)

- **Operating calendar** ([`docs/operating-calendar.md`](docs/operating-calendar.md)): eleven years (2015 to 2025) of recorded Open-Meteo weather at six UAE sites, run hour by hour through the envelope for the datasheet anchored but L0 Clearpath Jackal profile. The air exceeds the Jackal's rated 45 degC in 0.8 % of recorded hours; the envelope returns GO in 63.9 %, DERATE in 16.5 % and PARK in 19.6 % of hours, with the battery binding. These figures follow the profile fix of branch `fix/jackal-rated-ambient` (GO was 6.0 % before it), which raised three unmeasured conductances so the profile matches its rated ambient in shade. That the answer moves this much with three assumptions is the main finding.
- **Route simulation** ([`docs/route-simulation.md`](docs/route-simulation.md)): a patrol graph with shaded segments, three planners, scored on SYNTHETIC hotter robots on recorded July 2024 days. The envelope changes the plan (reduced scale, shaded corridor, canopy wait, later start) and its accepted plans exceeded no hard limit, but it completes fewer Jackal requests than the shortest path and finishes later in heat. Python kinematic and thermal simulation, not Gazebo, not a physical test.
- **Preregistered evaluation** ([`docs/preregistration-v0.6.md`](docs/preregistration-v0.6.md), [`docs/prereg-results.md`](docs/prereg-results.md), [`docs/prereg-results-addendum-fixed-profile.md`](docs/prereg-results-addendum-fixed-profile.md)): predictions committed before the run; 2 of 6 hit, unchanged after the Jackal fix because the evaluation uses only the medium UGV. The envelope had no risky hour in any of 80 synthetic runs, but the 40 degC rule was slightly more productive and the 95 % risk quantile proved more conservative than its label.
- **Preregistered evaluation of the Jackal, v0.7** ([`docs/preregistration-v0.7.md`](docs/preregistration-v0.7.md), [`docs/prereg-results-v07.md`](docs/prereg-results-v07.md)): 6 of 7 predictions hit, including two that predicted the envelope would lose. It loses about 3.3 productive hours a day to a 40 degC air rule; its only risky runs in the planner's own prior come from one SYNTHETIC hidden robot with a low DC-DC efficiency; with the conductances as they were before the fix it was risky in 29 % of runs.
- **Evidence checks** ([`docs/evidence-checks.md`](docs/evidence-checks.md)): restricting the calendar to days with recorded CAMS PM10, and running every day of one year instead of five sampled days per month, each changes the headline by at most 0.3 points. A seed level bootstrap widens the coverage interval of the preregistered H5 ([`docs/prereg-coverage-bootstrap-addendum.md`](docs/prereg-coverage-bootstrap-addendum.md)).
- Open review findings and their status are listed in [`docs/known-issues.md`](docs/known-issues.md).

![Dhill dashboard: hour by hour GO / DERATE / PARK for the illustrative UGV at Sweihan in a synthetic heatwave](docs/img/dashboard.png)

*Dashboard, illustrative L0 robot, synthetic heatwave at Sweihan.* A real live forecast run is in [`examples/`](examples/) (Abu Dhabi, 10 October 2026: GO overnight, PARK 07:00 to 11:00 UTC, GO again from 14:00 UTC).

## How it works

```mermaid
flowchart LR
    W[Weather: Open-Meteo, CSV, synthetic] --> E
    P[Robot profile YAML, provenance per parameter] --> E
    E[Envelope engine: six-node thermal network, battery, dust, LiDAR range, Monte Carlo] --> D[GO / DERATE / PARK + reasons]
    D --> S[Fleet scheduler MILP]
    T[Telemetry CSV / ROS 2 recorder] --> C[Calibration] --> P
```

A batched backward Euler solver integrates every start time, scale, shade level and Monte Carlo sample at once; a 72 hour hourly timeline with 64 samples took 2.3 s on a Windows laptop on 2026-10-15 (requirement NFR-02: under 10 s; rerun with `python scripts/benchmark_timeline.py`). Parameter spreads follow their provenance (measured 2% to assumption 25%). See [`docs/architecture.md`](docs/architecture.md), [`docs/model-card.md`](docs/model-card.md) and [`docs/parameters.md`](docs/parameters.md).

## Why the UAE, why now

Abu Dhabi's Smart and Autonomous Systems Council has directed a move from pilots to practical deployment of autonomous systems; heat and dust are where pilots end and deployment begins. Mapping to UAE and Abu Dhabi strategies, with the items still to verify, is in [`docs/uae-alignment.md`](docs/uae-alignment.md). The path to industry adoption, without implying any endorsement, is in [`docs/edge-integration.md`](docs/edge-integration.md).

## Honest limits

- **L0 profiles.** At least 80% of bundled parameters are assumptions. Treat outputs as method demonstrations, not operating authorisations.
- **No field validation yet.** The validation protocol ([`docs/validation-protocol.md`](docs/validation-protocol.md)) defines the bench and field steps needed for L2 and L3.
- **Calibration tests are synthetic** and share a model with the data generator.
- **The policy comparison is synthetic**: the engine and the hidden robot share a model structure. A conservative rule (air ≤ 40 °C) was competitive in some cases. See [`docs/policy-comparison.md`](docs/policy-comparison.md) and [`docs/requirements-traceability.md`](docs/requirements-traceability.md).
- **ROS 2 node** has not been run on a live ROS graph (ROS package servers were unreachable from the build environment); its logic is unit tested.
- **No compliance claims** against MIL-STD-810H, IEC 60529, ISO 13482 or similar.
- **Not the EDGE ATP 2026 ChallengeOn track**, which concerns connectivity.
- **Novelty is only partly checked.** A shallow web pass (`docs/literature-log.md`) found no tool combining these elements, but the closest work (Moore et al. 2012 on temperature aware field robots; `desert-av-reliability`, a UAE sensor reliability model) overlaps in part. IEEE Xplore and Scopus have not been searched.
- **The Jackal profile rests on three unmeasured conductances.** They were raised to match the 45 degC rating and sit at the upper end of plausible (`docs/robot-sources.md`); the calendar's GO share moved from 6.0 % to 63.9 % with them (`docs/operating-calendar.md`).
- **Next real step:** one instrumented robot run, using [`docs/field-test-kit.md`](docs/field-test-kit.md) and a preregistered prediction.

## Repository map

`src/dhill/physics` models · `profiles` robot profiles · `weather` providers · `envelope.py` decisions · `planner.py` scheduling · `climatology.py` operating calendar · `route.py` route simulation · `calibrate.py` fitting · `api` + `web` service · `ros2` recorder · `docs` documentation · `examples` studies · `tests` 152 tests (`pytest`, 2026-10-18).

## Development

`make install test lint`. CI runs ruff, pytest on Python 3.11 to 3.13, pip-audit and a CycloneDX SBOM. Release history in [`CHANGELOG.md`](CHANGELOG.md); the plan is in [`plan.md`](plan.md).

## Licence

No licence selected yet (all rights reserved by default); see [`docs/adr/0002-licensing.md`](docs/adr/0002-licensing.md).
