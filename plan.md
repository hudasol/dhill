# Dhill (ظل): project plan

| | |
|---|---|
| **Product** | Dhill: thermal and dust operating-envelope intelligence for autonomous ground systems in hot-arid environments |
| **Owner / author** | Huda Mueen |
| **Plan version** | 1.0 (release tag `v0.0.1`) |
| **Date** | 10 October 2026 |
| **Maturity target** | TRL 3 → 4 on public/synthetic evidence; TRL 5 requires a field campaign (Section 9) |

*Dhill* is Arabic for **shade**. The product answers one question for every robot, place and hour: **should this robot work now, work slower, or rest in the shade?**

---

## 1. Summary

The UAE is moving autonomous systems from pilots into daily operation. Those systems must work in air temperatures above 50 °C, direct solar load, and airborne dust that is among the heaviest recorded anywhere. Fleet operators currently manage this with blanket rules ("no midday operations") or with the air-temperature rating printed on a component datasheet. Neither accounts for solar heating of the chassis, the heat the robot makes itself, the mission it is about to run, or the dust on its sensors and heat-sinks.

Dhill is a mission-level decision engine that closes that gap. It couples a lumped thermal model of the robot (shell, interior, battery, compute, LiDAR, motors) with hourly weather and particulate data, quantifies uncertainty, and returns an explicit operating decision with reasons: **GO**, **DERATE** (with the speed/power scale that keeps every component inside limits) or **PARK** (with the shade needed to recover). A fleet scheduler turns those windows into a work plan. A calibration toolkit and a ROS 2 telemetry recorder close the loop with measured data, so every decision carries an **evidence level** that says how much it can be trusted.

Dhill starts as software and research so it can be built, tested and published now, and extends into robotics when a robot is available for field data.

## 2. Problem statement

> **Autonomous ground systems operating in the Gulf have no mission-level, location- and time-aware way to decide when heat and dust make operation unsafe or wasteful, so they either park by guesswork or fail mid-mission.**

Evidence for the problem (all sources listed in Section 16):

- **Heat is extreme and local.** The UAE recorded 51.2 °C on 5 August 2026 and 50.2 °C at Sweihan (Al Ain region) on 15 August 2026. Peak summer interior highs routinely exceed 45–46 °C.
- **Component limits sit close to ambient.** A Livox Mid-360 LiDAR is rated to 55 °C. Typical Li-ion cells can be charged only up to about 45 °C and discharged up to 60 °C (Samsung INR21700-50E datasheet). Jetson Orin modules begin software throttling at 99 °C on-die. A sealed, dark chassis in direct sun runs well above ambient, so an ambient rating alone is not a safe operating test.
- **Dust is severe.** Western-UAE desert studies report hourly PM10 between 4 and 3,474 µg/m³, with 27% of daily means above the 150 µg/m³ national limit. Dust degrades LiDAR returns, clogs filters and raises shell absorptance.
- **Scale is arriving.** Abu Dhabi's Smart and Autonomous Systems Council directed a move from pilots to practical deployment (9 Feb 2026). An official stated at AI Everything Abu Dhabi (6 Oct 2026) that thousands of autonomous taxis, vans and robots will operate in the UAE in 2027. Dubai's own strategy targets 25% autonomous trips by 2030.
- **Existing practice is coarse.** Public deployments cite generic mitigations such as temperature-controlled storage. PV-cleaning research in the UAE shows that *when* a robot runs is an economic decision (performance-based cleaning beat fixed daily cleaning by roughly 10–34% in one UAE study), but those studies optimise cleaning cost, not robot thermal survivability.
- **Research gap.** Temperature-aware operation of field robots has been demonstrated for small platforms using on-robot thermal models; dust-filtering for LiDAR is studied separately. We have not found a public tool that combines ambient heat, solar load, particulates, mission power and fleet scheduling for the Gulf with field-calibrated parameters. This claim is based on web searches and must be checked against IEEE Xplore/Scopus before external use (task R-1 in Section 10).

## 3. Why now: UAE and Abu Dhabi alignment

Full mapping with sources: `docs/uae-alignment.md`. Summary:

| Strategy | Relevant goal | How Dhill maps |
|---|---|---|
| Abu Dhabi SASC (Feb 2026) | Move from pilots to practical deployment of autonomous systems | Deployments hit real heat and dust; Dhill provides the operating decision layer |
| Abu Dhabi SAVI cluster | Global hub for smart and autonomous vehicles across land, air, sea | Serves land (UGV) and air (UAV) environmental robustness, which road-focused programmes do not cover |
| UAE Strategy for AI 2031 | Leading AI nation; AI in energy, logistics and transport; AI test bed | Applied AI decision layer for energy-site and logistics robots; open evidence for the test-bed objective |
| UAE Net Zero 2050 | Decarbonise power, industry, transport | Schedules PV-cleaning and inspection robots around soiling and heat; logs energy per mission |
| Operation 300bn | Raise industrial GDP to AED 300bn by 2031; advanced-technology adoption | Uptime and safety planning for autonomous machines in outdoor industrial sites |
| UAE midday-break policy | Outdoor work in direct sun banned 12:30–15:00, 15 Jun–15 Sep | Same heat limits that stop people define robot windows; position as safety complement, not labour replacement |
| Data and hosting | PDPL (Federal Decree-Law 45/2021), data localisation expectations | Weather and telemetry are non-personal; product runs fully self-hosted and offline |

Gaps in verification are listed in `docs/uae-alignment.md` and must be closed before citing figures externally.

## 4. Product definition

### 4.1 What Dhill decides

1. **Operating decision** for a robot profile, mission, place and time: GO, DERATE or PARK, with the limiting component, margin, time-to-limit and probability of exceeding limits.
2. **Derate scale**: the largest power/speed fraction that keeps all components within limits, found by bisection.
3. **Shade requirement**: the shading fraction needed to turn PARK into GO, and the parked-in-sun heat-soak peak per component.
4. **Perception-limited speed**: maximum speed given dust-reduced LiDAR range and stopping distance.
5. **Ageing cost**: battery ageing acceleration relative to 25 °C for each candidate start time.
6. **Fleet schedule**: assignment of missions to robots and start times that maximises work delivered and respects windows, cooldown and ageing.
7. **Calibration**: parameters fitted from telemetry, with uncertainty and identifiability warnings.

### 4.2 Non-goals

- Not a certification tool. Dhill is **aligned to** and **informed by** standards such as MIL-STD-810H and IEC 60529; it does not claim compliance or replace accredited testing.
- Not a weapons or targeting system. Dhill is an environmental-risk and logistics tool for autonomous platforms.
- Not a robot controller. It advises mission planning and supervisory logic; it does not command actuators.
- Not a weather forecaster. It consumes forecasts and observations; forecast error is propagated as uncertainty.

### 4.3 Users

| Persona | Need |
|---|---|
| Fleet operations engineer | "Can fleet X run the 11:00 sortie at site Y?" with a defensible reason |
| Safety / test engineer | Evidence trail: parameters, provenance, evidence level, V&V artefacts |
| Platform integrator (e.g. a UGV or inspection-robot maker) | API and library to embed envelope logic; calibration workflow |
| Researcher / student | Reproducible model, synthetic benchmark and field-data protocol |

## 5. Requirements

IDs are traced to tests and docs in `docs/requirements-traceability.md`.

**Functional**

| ID | Requirement |
|---|---|
| FR-01 | Compute a GO/DERATE/PARK decision for a profile, mission, location and start time |
| FR-02 | Report limiting component, margin to limit, time-to-limit and exceedance probability |
| FR-03 | Compute derate scale by bisection and shade requirement |
| FR-04 | Model dust deposition, absorptance drift, filter/heat-sink fouling and LiDAR range loss |
| FR-05 | Produce a multi-day window timeline for a mission |
| FR-06 | Schedule missions across a fleet (MILP) with cooldown and ageing penalty |
| FR-07 | Fit thermal parameters from telemetry and report uncertainty and identifiability |
| FR-08 | Ingest weather from Open-Meteo, CSV, or a deterministic synthetic generator (offline) |
| FR-09 | Expose all functions through CLI, Python API and REST API |
| FR-10 | Record telemetry from ROS 2 in the Dhill schema |
| FR-11 | Tag every parameter with provenance and every decision with an evidence level |

**Non-functional**

| ID | Requirement |
|---|---|
| NFR-01 | Run fully offline and self-hosted; no external calls unless a provider is configured |
| NFR-02 | 72-hour forecast for one robot with uncertainty in under 10 s on a laptop CPU |
| NFR-03 | Deterministic results for a fixed seed; reproducible tests |
| NFR-04 | Typed, linted, tested; CI on every push |
| NFR-05 | Machine-readable API schema (OpenAPI) and versioned data schemas |
| NFR-06 | SBOM generation and dependency vulnerability scan in CI |
| NFR-07 | No personal data collected; optional API-key auth and structured audit log |
| NFR-08 | Dashboard works without internet (no CDN assets) and meets basic accessibility (not colour-only status) |

## 6. Architecture

```
            +--------------------------------------------------------+
            |                    Interfaces                          |
            |   CLI    Python API    REST (FastAPI)    Ops console   |
            +------------------------+-------------------------------+
                                     |
        +----------------------------+-----------------------------+
        |   planner (MILP fleet scheduler)   calibration (fit)     |
        +----------------------------+-----------------------------+
                                     |
        +----------------------------+-----------------------------+
        |   envelope: simulate -> decide -> derate -> shade -> MC  |
        +-------+---------------+---------------+------------------+
                |               |               |
        +-------+------+ +------+-------+ +-----+--------------+
        |  physics     | |  weather     | |  profiles          |
        |  thermal RC  | |  Open-Meteo  | |  YAML robot specs  |
        |  battery     | |  CSV         | |  provenance tags   |
        |  dust, lidar | |  synthetic   | |  limits, loads     |
        +--------------+ +--------------+ +--------------------+
                                     ^
                         telemetry CSV | (ROS 2 recorder)
```

Technology: Python 3.11+, NumPy/SciPy (vectorised batch simulation, `scipy.optimize.milp` for scheduling), Pydantic, FastAPI. The dashboard is plain HTML/CSS/JS served by the API, so it works air-gapped.

Repository layout is described in `README.md`; design decisions are recorded as ADRs in `docs/adr/`.

## 7. Modelling approach

**Thermal network.** Six lumped nodes: shell, interior air/chassis, battery, compute module, LiDAR, motors. Backward-Euler time stepping with temperature-dependent coefficients, batched over uncertainty samples and start times.

- *Solar:* DNI/DHI/GHI with solar position (NOAA algorithm). Top face sees DNI·sin(elevation); vertical faces use the heading-averaged projected area (2/π)·H·(L+W)·cos(elevation); diffuse and ground-reflected components use view factors.
- *Outer convection:* combined forced (flat-plate laminar/mixed) and natural (Churchill–Chu) convection, wind scaled from 10 m to robot height by a power law.
- *Radiation:* sky temperature (Berdahl–Martin) and ground temperature; ground heating above air temperature is an explicit parameter.
- *Heat sources:* battery I²R from pack resistance (Arrhenius in temperature), compute power with throttling feedback, LiDAR self-heating, motor and drive losses.

**Battery.** Equivalent-circuit current from power demand, temperature-dependent resistance, coulomb-counted state of charge, charge/discharge temperature limits, and Arrhenius ageing acceleration relative to 25 °C.

**Dust.** Deposition flux = v_d · PM10, cleared by rain; absorptance drifts toward a dust value with loading; heat-sink conductance falls with fouling; airborne extinction from mass-extinction efficiency, then LiDAR range from a two-way Beer–Lambert link budget; maximum safe speed from stopping distance.

**Decision logic.** Run the mission at full power; if all components stay below derate thresholds with exceedance probability below the profile limit, GO. Otherwise find the largest power scale that does; if it exceeds the profile's minimum useful scale, DERATE. Otherwise PARK, and compute the shade fraction that restores feasibility.

**Uncertainty.** Parameters carry relative uncertainty by provenance (textbook, datasheet, assumption, calibrated). Monte-Carlo samples run as a batch dimension; decisions use quantiles, not means.

**Evidence ladder.** L0 uncalibrated defaults; L1 datasheet-parameterised for a specific robot; L2 calibrated on field telemetry; L3 validated on a held-out campaign. Every decision states its level. Dhill never presents an L0 decision as validated.

## 8. Data sources and provenance rules

- **Weather:** Open-Meteo forecast API (temperature, humidity, wind, shortwave/direct/diffuse radiation, precipitation) and air-quality API (PM10, dust; CAMS-based, coarse grid). Historical: Open-Meteo archive (ERA5). Names and units are confirmed by a live call in the integration test, not assumed.
- **Local observations:** National Center of Meteorology and Environment Agency Abu Dhabi data where access is granted; to be confirmed.
- **Robot parameters:** datasheets, textbook values and explicit assumptions. Each parameter in a profile carries `source: textbook | datasheet | assumption | calibrated` and a citation or note. The API reports the assumption fraction.
- **Synthetic data** is always labelled as synthetic in file headers and outputs, and is never used as evidence of real-world accuracy.

## 9. Verification and validation plan

| Phase | Evidence | Pass criterion | Status |
|---|---|---|---|
| V0 Unit | Physics functions against textbook values and invariants (energy balance, monotonicity, limits) | All tests pass in CI | Planned for v0.1.0 |
| V1 Synthetic | Calibration recovers known parameters from noisy synthetic telemetry; scheduler optimality vs brute force on small cases | Parameter error < 10% on identifiable parameters; MILP equals brute force | Planned for v0.2.0 |
| V2 Public data | Compare forecast shell/interior temperature behaviour with published desert vehicle/enclosure measurements | Qualitative agreement, documented error | Planned |
| V3 Field | Instrumented robot logs on the Al Ain campus across morning/noon/evening; fit on one day, test on another | Held-out RMSE ≤ 3 K on battery and compute temperatures; decision agreement with an engineer's labels ≥ 90% | Needs robot access |

Field protocol: `docs/validation-protocol.md`. TRL statement: **TRL 3** (analytical proof of concept) until V3 data exist; TRL 4 after V2; TRL 5 only after a relevant-environment demonstration.

## 10. Roadmap and release tags

| Tag | Content |
|---|---|
| `v0.0.1` | This plan and README; repository scaffold |
| `v0.1.0` | Physics core: psychrometrics, solar, convection, thermal network, battery, dust and perception models, profiles, unit tests |
| `v0.2.0` | Envelope engine, Monte Carlo, shade and derate search, weather providers, MILP scheduler, calibration, CLI |
| `v0.3.0` | REST API, offline ops console, ROS 2 telemetry recorder, Docker, CI, SBOM |
| `v0.4.0` | Documentation set: UAE alignment, EDGE integration, model card, validation protocol, threat model, traceability; hardening |
| `v0.5.0` | Field-data release: calibrated profile from the first campaign (needs robot) |
| `v1.0.0` | Independent validation (L3), stable API, pilot with an operator |

Research tasks: **R-1** literature check (IEEE Xplore, Scopus) of the novelty claim; **R-2** obtain NCM/EAD station data; **R-3** identify the senior's robot platform and its datasheets; **R-4** agree an instrumented test plan with Al Ain University faculty.

## 11. Standards posture

Dhill is aligned to and informed by, never compliant with, the following. Standard numbers come from secondary sources and must be verified against the published text before external use.

- **MIL-STD-810H** methods 501.7 (high temperature), 505.7 (solar radiation), 510.7 (sand and dust): used to define test-style scenarios in the validation protocol.
- **IEC 60529** (IP ratings) and **IEC 60068-2-x** environmental tests: referenced for dust and heat scenarios.
- **IEC 62133-2** (Li-ion safety): reference for battery limits; cell datasheets take precedence.
- **ISO 13482, ISO 3691-4, ANSI/UL 3300**: service and driverless-vehicle robot safety context. None covers heat-and-dust envelope planning for military platforms.
- **ISO/IEC 25010** (software quality), **NIST SP 800-218** (secure development), **SPDX/CycloneDX** (SBOM): used to structure engineering practice.

## 12. Adoption path for industry (EDGE and its subsidiaries)

Dhill is built as a product, not a demo: versioned API, offline container, SBOM, model card, traceability and a field-validation protocol. Detail in `docs/edge-integration.md`.

- **Entry points:** units that operate or integrate autonomous ground and aerial systems (for example autonomous-systems and vehicle entities within EDGE's Platforms and Systems cluster).
- **Integration:** REST/JSON and Python library; telemetry in CSV; no dependence on cloud services; weather can be supplied from the customer's own station or feed.
- **What EDGE has asked for publicly:** the ATP 2026 challenge on ChallengeOn is about seamless connectivity across wi-fi, mobile, satellite and wired networks, not heat and dust, so Dhill is not a direct answer to that challenge. The route to EDGE is through a pilot or technical conversation, not that track.
- **No endorsement is implied.** References to EDGE entities describe fit, not a relationship.

## 13. Competition and proposal strategy

- **Faculty proposal (Al Ain University):** frame as a research project with a defined field-data campaign. AAU's board approved a Research Center for Energy, Water and Sustainability in January 2026; solar-farm robot operation is a natural first use case. AAU also offers a BSc in AI and Robotics, so the senior's robotics expertise supplies the platform and test access.
- **Competitions:** James Dyson Award (entries for 2026 closed 15 July; target the next cycle; needs a physical element such as a passive shade-dock or cooled enclosure and a prototype video), Khalifa Fund (business case: operating-risk reduction for robot fleet operators), Edge ChallengeOn (harsh-environment operations track when available), and similar. RAK Excellence and COP-related programmes have not yet been researched.
- **Hackathon reuse:** the same core with different "use-case skins": delivery robots, PV cleaning, inspection drones, agricultural robots.

## 14. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| No field data until a robot is instrumented | Decisions remain L0/L1 | Evidence levels shown on every output; protocol and recorder ready; synthetic benchmark clearly labelled |
| Novelty challenged | Weak competition story | R-1 literature check; position novelty as Gulf-specific, field-calibrated, fleet-level combination |
| Weather grid too coarse for dust fronts | Missed local events | Treat dust as a risk input with wide uncertainty; accept local station feed |
| Model errors from lumped assumptions | Wrong decision | Monte-Carlo uncertainty, conservative thresholds, calibration, sensitivity analysis in model card |
| Robot access depends on one person | Schedule slip | Generic profiles; protocol usable on any robot; second-source plan (campus vehicles, PV-cleaning operator) |
| Over-claiming | Loss of credibility | "Aligned to", never "compliant"; TRL stated conservatively; assumptions listed |

## 15. Open decisions for the owner

1. **Licence.** Decided on 23 October 2026: Apache-2.0 (`LICENSE`). See `docs/adr/0002-licensing.md`.
2. **Repository visibility.** The repository is currently public. Everything in it is publishable research and code; decide whether to keep it public.
3. **Affiliation for papers and entries** (University of Stirling vs Al Ain University) once the transfer is settled.
4. **Pilot platform** to instrument first.

## 16. References

- Khaleej Times, UAE 50 °C and record temperatures, Aug 2026: https://www.khaleejtimes.com/uae/weather/uae-records-highest-temperature-of-512c-amid-peak-summer-heat-2 and https://en.aletihad.ae/news/uae/4685402/ncm--highest-temperature-recorded-across-uae-on-saturday-was
- Khaleej Times, autonomous vehicles by 2027 (6 Oct 2026): https://www.khaleejtimes.com/uae/uae-to-have-10000-autonomous-taxis-delivery-vans-by-2027
- Abu Dhabi SASC meeting (Feb 2026): https://www.mediaoffice.abudhabi/en/technology/hamdan-bin-mohamed-bin-zayed-chairs-smart-and-autonomous-systems-council-meeting-2026/
- UAE AI Strategy 2031: https://u.ae/-/media/AI-publications/UAE-National-Strategy-for-Artificial-Intelligence-2031.pdf
- UAE Net Zero 2050: https://u.ae/en/about-the-uae/strategies-initiatives-and-awards/strategies-plans-and-visions/environment-and-energy/the-uae-net-zero-2050-strategy
- Operation 300bn: https://u.ae/en/about-the-uae/strategies-initiatives-and-awards/strategies-plans-and-visions/industry-science-and-technology/the-uae-industrial-strategy
- Abu Dhabi SAVI: https://added.gov.ae/en/invest/growth-sectors/SAVI
- Western UAE PM10 study: https://www.witpress.com/elibrary/wit-transactions-on-ecology-and-the-environment/174/24675
- Abu Dhabi PM10 study: https://link.springer.com/article/10.1007/s41748-020-00186-2
- DEWA PV cleaning robot study: https://www.pv-magazine.com/2026/08/14/dewa-study-assesses-pv-cleaning-robot-performance-and-safety/
- PV cleaning optimisation (BUiD): https://bspace.buid.ac.ae/handle/1234/1314
- Thermal modelling for field robots (Moore et al., 2012): https://independent.academia.edu/BrandonMoore74
- Livox Mid-360 specification: https://www.livoxtech.com/mid-360/specs
- Samsung INR21700-50E datasheet: https://shop.aceongroup.com/cdn/shop/files/RLII-CSI-1618_Samsung_50E_DATASHEET.pdf
- NVIDIA Jetson Linux developer guide (Orin thermal specifications): https://docs.nvidia.com/jetson/archives/r36.4/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html
- Open-Meteo documentation: https://open-meteo.com/en/docs and https://open-meteo.com/en/docs/air-quality-api
- EDGE ATP 2026 challenge: https://challengeon.atrc.ae/en/challenges/atp2026

## 17. Status at v0.5.0

Delivered: all roadmap stages through v0.5.0 (see `CHANGELOG.md`). Deviations from this plan, kept visible: (exceedance probability, time-to-limit and the ageing penalty were added in v0.5.0); derate uses grid-then-refine rather than bisection; ROS 2 node not run on a live graph; repository tags could not be pushed from the build environment (`scripts/tag-releases.sh` provided); GitHub About text and topics could not be edited from the build environment (paste-ready text in the final report). Open decisions in section 15 remain open.
