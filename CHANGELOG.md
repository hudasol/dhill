# Changelog

Each entry maps to a commit on `main`, and each version has an annotated tag of the same name on GitHub (v0.0.1 to v0.5.0 were created with `scripts/tag-releases.sh`).

| Version | Commit | Summary |
|---|---|---|
| v0.0.1 | 00f7153 | Project plan and README |
| v0.1.0 | 1e75158 | Thermal network, battery, dust and perception physics; profiles; tests |
| v0.2.0 | 06b57fc | Weather providers, envelope decisions, fleet planner, calibration, CLI |
| v0.3.0 | 0a59a22 | REST API, offline dashboard, ROS 2 recorder, Docker, CI |
| v0.4.0 | 0e1dcb7 | Documentation set, results, parameter reference, release script, README rewrite |
| v0.5.0 | 3097eec | Exceedance probability, time-to-limit, battery-ageing penalty, sensitivity analysis, policy comparison on a hidden robot, field-test kit, literature protocol |
| v0.6.0 | e1b0198 | Operating calendar on recorded Open-Meteo weather (six sites, 2015 to 2025); patrol route simulation; preregistered evaluations v0.6 (medium UGV, 2 of 6 hits) and v0.7 (Jackal, 6 of 7 hits) with addenda; Jackal conductances made consistent with the rated ambient; physics no longer imports profiles and Envelope has public methods; evidence checks on PM10 fill and day sampling; warning below 64 Monte Carlo samples, API and dashboard default raised to 64; known issues register; release checklist; proposals for Al Ain University and EDGE |
| v0.7.0 | to be recorded after tagging | Field day validation command `dhill validate`; SYNTHETIC dry run of the field day; calibrated profiles load back; roadmap to v1.0; AAU preregistration and email drafts; Apache 2.0 licence; logging session quickstart; Jackal sensitivity of the three parameters to check first |

## What changed and why, v0.5 to v0.7

### v0.5.0

- Added exceedance probability, time to limit and a battery ageing penalty, because a single peak temperature
  did not say how likely or how soon a limit is reached.
- Added a sensitivity analysis (`dhill sensitivity`) to rank which assumed parameters move the answer, so that
  field measurement can start with the most important ones.
- Compared scheduling policies on a hidden SYNTHETIC robot, and added the field test kit and the literature
  search protocol as the route to real evidence.

### v0.6.0

- Built an operating calendar on recorded Open-Meteo weather for six sites, 2015 to 2025, to replace single
  synthetic days with the distribution of real conditions.
- Added a patrol route simulation, to check decisions over a mission rather than one window.
- Ran two preregistered evaluations (v0.6 medium UGV, 2 of 6 hits; v0.7 Jackal, 6 of 7 hits) and published
  the misses, so that the model is tested against predictions fixed in advance.
- Made the Jackal conductances consistent with its rated ambient, after the evaluation showed the profile ran
  too hot within its own rating.
- Separated the physics from the profiles and gave `Envelope` public methods, so that the engine contract is
  testable on its own.
- Added evidence checks on PM10 fill and day sampling, and a warning below 64 Monte Carlo samples (known issue
  19), because the 95 % quantile is unreliable with fewer samples.

### v0.7.0

- Added `dhill validate`, which replays a held out telemetry record and applies the V2 criteria of
  `docs/validation-protocol.md`, so that the AAU validation day has a fixed, scripted pass or fail.
- Added a SYNTHETIC dry run of the field day (`examples/field_day_demo.py`) to show the pipeline runs end to
  end; it is not evidence.
- Fixed the loading of profiles written by `dhill calibrate --out` (known issue 20); without it the day 3 check
  could not use the calibrated profile.
- Wrote the roadmap to v1.0, the AAU preregistration and email drafts, and a one page logging session
  quickstart, so that the session can be agreed and run.
- Licensed the project under Apache 2.0 (ADR 0002), for its patent grant and permissive terms.
- Added the Jackal sensitivity of the three parameters a supervisor would check first
  (`docs/jackal-sensitivity.md`), to show how far each moves the calendar and the die peak.
