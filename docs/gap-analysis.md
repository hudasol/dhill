# Gap analysis and plan to complete Dhill

Date: 27 October 2026. Version audited: v0.7.0 (167 tests passing on Python 3.13).
Evidence level of every shipped profile: L0. Every comparison robot so far is synthetic.

Decision recorded at the top, as the owner asked for decisions rather than questions: the work below
does everything that can be done without a real robot, and keeps a separate list of what only the
Al Ain University logging session, database access or a live ROS graph can close. Nothing in this
document is a field result.

## 1. What the repository shows today

| Area | State | Evidence |
|---|---|---|
| Engine | Six node thermal network, batched backward Euler, Monte Carlo risk quantile, GO / DERATE / PARK | `src/dhill/physics/thermal.py`, `src/dhill/envelope.py` |
| Calendar | Jackal profile, 6 UAE sites, 2015 to 2025: GO 63.9 %, DERATE 16.5 %, PARK 19.6 % | `docs/operating-calendar.md` |
| Preregistered tests | v0.6: 2 of 6 predictions hit. v0.7: 6 of 7 hit | `docs/prereg-results.md`, `docs/prereg-results-v07.md` |
| Tooling | `dhill calibrate`, `dhill validate`, ROS 2 recorder, API, dashboard | `src/dhill/`, `ros2/` |
| Field data | None | `docs/roadmap-to-v1.md` |

## 2. Limitations, ranked

Severity follows `docs/known-issues.md`: High can mislead a reader about what the evidence shows.

| # | Severity | Limitation | Where it shows | Can it be closed without a robot? |
|---|---|---|---|---|
| G1 | High | The "true" robot in every evaluation has the engine's own structure, so structural model error is zero by construction. Calibration is tested on data from the same model (inverse crime). | `docs/known-issues.md` item 2; `docs/model-card.md` | Partly. An independent plant with a different structure measures how large structural error can be when the physics is richer. It does not replace field data. |
| G2 | High | No real robot data. Every parameter of the Jackal thermal model is an assumption; three of them carry 82 % of the variance of peak battery temperature. | `docs/sensitivity.md`; `docs/robot-sources.md` | No. Needs the AAU session. |
| G3 | High | The headline depends on unmeasured parameters: the GO share moved from 6.0 % to 63.9 % when three conductances were corrected. | `docs/operating-calendar.md` | Partly. Sensitivity is reported; measurement is not possible here. |
| G4 | Medium | Shade is a constant fraction and the side faces use a heading average. Real shade moves with the sun azimuth, and a fixed heading loads one face. | `src/dhill/route.py`; known issues item 9 | Yes, in the plant. |
| G5 | Medium | Weather is hourly and interpolated. Gusts, cloud transients and dust storm onset happen on minute scales. | `src/dhill/weather/base.py` | Yes, in the plant. |
| G6 | Medium | Dust acts through one fixed deposition velocity and a clogging law, untested on robot geometry. No storm events are tested. | `docs/model-card.md` | Partly. Storm stress cases can be run; geometry needs field data. |
| G7 | Medium | `dhill calibrate` and `dhill validate` were only tested with white noise on model generated data. Real sensors have lag, bias, dropouts and irregular clocks. | `src/dhill/calibrate.py` `synthetic_telemetry` | Yes. |
| G8 | Medium | Novelty is not established. A granted patent (US 11897509 B2) covers the basic idea of weather and route based thermal prediction. IEEE and Scopus were not searched. | `docs/literature-log.md` | No. Needs database access. |
| G9 | Medium | The ROS 2 recorder has not run on a live graph. | `docs/known-issues.md` item 12 | No. |
| G10 | Low | Route planner is greedy; humidity, condensation, battery ageing feedback on resistance, terrain slope and wind direction are not modelled. | `docs/model-card.md` | Partly. |

## 3. Plan

| Work package | Closes | Output | Status |
|---|---|---|---|
| WP1 Independent plant simulator with a different structure, moving shade, gusts, dust events and sensor model | G1, G4, G5, G6, G7 | `src/dhill/plant/`, tests, a layer test that the plant imports no engine physics | Planned |
| WP2 Preregistered evaluation of the engine against the plant on recorded Gulf weather: prediction error, false GO rate, quantile coverage, comparison with simple rules | G1, G3 | `docs/preregistration-v0.8.md` written before the run, then `docs/prereg-results-v08.md` and raw JSON | Planned |
| WP3 Calibration and validation under structural mismatch with realistic telemetry | G1, G7 | Report of whether `dhill validate` can pass on a robot that the model cannot represent exactly | Planned |
| WP4 Engine changes that the evidence in WP2 and WP3 justifies, each as a separate commit with a test | G1 | Only if a finding requires it; none is assumed in advance | Planned |
| WP5 Update README, model card, known issues, AAU proposal, EDGE brief and deck with the new evidence and its limits | all | Documents | Planned |
| WP6 Items for the owner and AAU | G2, G8, G9 | Listed in section 4 | Not startable here |

Rules for WP1 to WP3: the plant is written without importing `dhill.physics`; its parameters are drawn
around the Jackal profile with spreads wider than the engine's priors; the prediction is committed before
the results exist; every result table states L0 and synthetic; misses are reported with the hits.

## 4. What only the owner or AAU can close

1. One supervised logging session on a real robot (`docs/proposals/aau-robotics-proposal.md`). This is the only way to move any profile above L0.
2. IEEE Xplore and Scopus searches with institutional access, then a read of the full claims of US 11897509 B2.
3. A run of the ROS 2 recorder on a live graph during that session.
4. Pushing tags and sending the email.

## 5. Honest reading of the goal

A simulator cannot make Dhill field validated. What it can do is show a supervisor how the method behaves
when the robot is not the model, which is the question a reviewer asks first. That is the scope of WP1 to WP3.
