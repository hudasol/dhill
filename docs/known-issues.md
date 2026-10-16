# Known issues

Result of a sceptical review of the whole repository on 15 October 2026, written from the point of view of
a defence robotics engineer deciding whether to spend time on it. Small, clearly wrong items were fixed on
branch `feature/adversarial-review` (listed at the end). Everything else is listed here with a severity.

Severity: **High** can mislead a reader about what the evidence shows; **Medium** weakens the evidence or
the code; **Low** is style or housekeeping.

## Open

| # | Severity | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|
| 1 | High | `src/dhill/profiles/builtin/clearpath_jackal.yaml` | The datasheet anchored Jackal profile forbids full speed above about 20 degC air (`docs/operating-calendar.md`), while the manufacturer rates the robot to 45 degC ambient. The assumed compute heat path (35 W, 4.4 W/K shell to interior, 0.5 K/W die rise, 85 degC allowed die) binds in every non GO hour. Any Jackal result is therefore a statement about the assumptions. | Measure die temperature against processor load at two ambient temperatures; take the processor junction limit from the Intel datasheet; update the profile; rerun the calendar and route demo. | Partly closed by 6f38479 (`fix/jackal-rated-ambient`): conductances raised so the profile matches the rating in shade; calendar and routes rebuilt on `feature/rebase-results`. The values remain unmeasured assumptions (`docs/robot-sources.md`). |
| 2 | High | All evaluations (`docs/policy-comparison.md`, `docs/route-simulation.md`, `docs/prereg-results.md`, `docs/results.md`) | Every comparison against a "true" robot uses a robot built by the same author with the same six node model structure. Structural model error is absent by construction. The documents say so, but a reader skimming tables can miss it. | Keep the label in every table header; the first real check is the instrumented run in `docs/field-test-kit.md`. | Open |
| 3 | High | `docs/prereg-results.md` | The preregistered evaluation hit 2 of 6 predictions. The envelope was never risky, but the 40 degC rule was slightly more productive (H4) and the 95 % risk quantile covered the truth 99.6 % of the time (H5). `docs/policy-comparison.md` already concluded that the envelope's edge is a reasoned per component guarantee rather than productivity; the preregistered result supports that reading and no stronger one. | Do not describe the envelope as more productive than a conservative ambient rule. Consider calibrating the uncertainty spreads so the 95 % label is closer to its coverage. | Open |
| 4 | Medium | `src/dhill/physics/thermal.py` lines 19 to 20 | The physics layer imports `profiles.registry` and `profiles.schema` (to build `ThermalParams.from_profile`). Physics should not depend on the profile layer. | Move `from_profile` into `profiles` or a small adapter module; leave `thermal.py` with plain arrays. | Open |
| 5 | Medium | `policies.py`, `sensitivity.py`, `climatology.py`, `route.py` | These modules call private `Envelope` methods (`_idx`, `_steps`, `_soak_state`). The contract between the engine and its users is implicit. | Add public `index_of`, `steps_for` and `soak_state` methods; keep the private names as aliases. | Open |
| 6 | Medium | `docs/operating-calendar.md` | PM10 before August 2022 is a climatological fill (median CAMS value per site, month and local hour); 71 % of weighted sampled days use it. PM10 acts through the LiDAR range cap and dust deposition; its effect on the calendar was not isolated. | Restrict the calendar to 2022-08 onwards as a sensitivity check, or source an earlier PM10 record. | Open |
| 7 | Medium | `docs/operating-calendar.md` | Five sampled days per site and month estimate hour shares; there is no estimate of the sampling error. | Run every day for one site as a check and report the difference. | Open |
| 8 | Medium | `docs/prereg-results.md`, H5 | The Wilson interval on coverage treats (slot, draw) pairs as independent; they are not, so the interval is too narrow. | Bootstrap over seeds, as for H4. | Open |
| 9 | Medium | `src/dhill/route.py` | Shade fractions are constant in time; real shade moves with the sun. Speed is constant per segment; no slope or terrain heat. | Shade as a function of solar azimuth for each segment, once a real site is mapped. | Open |
| 10 | Medium | `plan.md` section 16 | One reference URL is malformed (`.../4685402/javasxript:`), and the Moore et al. 2012 reference points to an author profile, not the paper. | Replace with the article URL and a full citation after checking. | Open |
| 11 | Medium | `docs/literature-log.md` | The novelty search is a shallow web pass; IEEE Xplore, Scopus and Web of Science were not searched. Already stated; repeated here because proposals depend on it. | Run the protocol with institutional access before any novelty statement. | Open |
| 12 | Medium | `ros2/`, `docs/requirements-traceability.md` FR-10 | The ROS 2 recorder has not run on a live ROS graph. | Run it once on the host robot during the logging session. | Open |
| 13 | Low | `README.md`, `docs/requirements-traceability.md` NFR-02 | Timing claims are measured by hand and not covered by a test (2.3 s for a 72 hour timeline on 2026-10-15; 1.2 s on the original build machine). | Add a benchmark script; keep timing out of unit tests. | Open |
| 14 | Low | `README.md`, older docs | Many hyphenated compounds ("operating-envelope", "battery-ageing") and some marketing tone in the tagline. New documents follow the house style; older ones were not rewritten to avoid churn. | Edit in one pass when the documents are next revised. | Open |
| 15 | Low | `docs/requirements-traceability.md` NFR-06, `docs/threat-model.md` | CI with `pip-audit` and SBOM is configured; whether it has run on GitHub was not checked in this review. | Check the Actions tab and record the first passing run. | Open |
| 16 | Low | `examples/prereg_results.json` | 485 kB of raw results in the repository. | Acceptable for traceability; compress or move to a release asset if it grows. | Open |
| 17 | Low | `src/dhill/route.py` `plan_envelope` | The search is greedy (earliest accepted start) and coarse (two paths per leg, two scales, one wait length). It can miss faster safe plans. | Documented in `docs/route-simulation.md`; refine if routing becomes a product feature. | Open |

## Numbers checked in this review

| Claim | Where | Checked against | Status |
|---|---|---|---|
| Fixed shift breaches 20 of 24 blocks; 4.0 h usable | `README.md`, `docs/results.md` | `dhill plan --robots ugv_medium_inspection sidewalk_delivery_robot` | Corrected (was 22 of 24 and 2.0 h) |
| Sweihan timeline sample (0.56, 0.91 derate) | `README.md`, `docs/results.md` | `dhill timeline --site sweihan --scenario heatwave --step-min 120` | Corrected (was 0.57, 0.78) |
| Nominal model unsafe in 8 slots; hold-out 1.17 K to 0.39 K | `README.md`, `docs/results.md` | `python examples/value_of_calibration.py` | Matches |
| L0 and L2 productive hours 14.9 and 13.6 | `docs/results.md` | same | Corrected (was 13.9 and 13.2) |
| Policy comparison table | `docs/policy-comparison.md` | rerun of `examples/policy_comparison.py`, identical to `examples/policy_comparison_output.txt` | Matches |
| Live forecast reading (GO overnight, PARK 07:00 to 11:00 UTC, GO from 14:00 UTC) | `README.md`, `docs/results.md` | `examples/live_forecast_abu_dhabi_2026-10-10.txt` | Matches the file (a past live run; not reproducible) |
| At least 80 % of bundled parameters are assumptions | `README.md`, `docs/model-card.md` | `Profile.assumption_fraction()`: 0.817 to 0.860 for the four profiles | Matches |
| Provenance spreads 2 % to 25 %; forecast error 1.5 K, 10 %, 25 % | `README.md`, `docs/model-card.md` | `profiles/registry.py` `SOURCE_SIGMA`; `physics/thermal.py` `weather_sigma` | Matches |
| Calendar headline (GO 6.0 %, DERATE 69.6 %, PARK 24.4 %, air above 45 degC 0.8 %) | `docs/operating-calendar.md`, `README.md` | `tests/test_climatology.py::test_published_headline_is_computed_from_the_csv` | Matches |
| Route table | `docs/route-simulation.md`, `README.md` | `examples/route_demo_output.txt` | Matches |
| Preregistered results | `docs/prereg-results.md`, `README.md` | `tests/test_prereg.py` | Matches |
| Test count 134 | `README.md` | `pytest --collect-only` | Matches |
| 72 hour timeline time | `README.md` | measured 2.3 s | Corrected (was "about a second") |

Press figures in `plan.md` and `docs/uae-alignment.md` (temperatures, policy dates) are cited to news and
government pages and were not re-verified here; `docs/uae-alignment.md` already lists them as to verify.

## Fixed on this branch

- `docs/literature-log.md`: removed an assistant attribution from the status line.
- `plan.md`: two em dashes replaced.
- `docs/requirements-traceability.md`: the deviations section contradicted the table; rows now point at
  the covering tests, and post v0.5 additions are listed.
- `README.md`, `docs/results.md`: stale example outputs replaced with rechecked ones; test count and timing
  updated; new work and the Jackal profile problem added to the limits.
- `docs/model-card.md`: post v0.5 additions and the coverage result.
- `src/dhill/route.py`: an unused parameter removed.
