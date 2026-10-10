# Requirements traceability

Requirement IDs refer to `plan.md` section 5. Status is stated honestly: where the shipped code differs from the plan, the deviation is listed below the table.

| ID | Status | Implementation | Verified by |
|---|---|---|---|
| FR-01 | Met | `Envelope.decide` | `tests/test_envelope.py` |
| FR-02 | Partly | Limiting constraint and headroom (K) per component reported; time-to-limit and exceedance probability not yet | `test_go_decision_has_nonnegative_headroom...` |
| FR-03 | Met, method changed | Grid-then-refine search instead of bisection; shade requirement by grid and refine | `test_derate_scale_is_actually_feasible...`, `test_shade_requirement...` |
| FR-04 | Met | `physics/dust.py`, `thermal.simulate` | `test_physics_basic.py`, `test_dust_*` |
| FR-05 | Met | `Envelope.timeline` (multi-day) | `test_night_go_midday_park...` |
| FR-06 | Partly | MILP with rest gap and concurrency; no ageing penalty yet | `tests/test_planner_calibrate_cli.py` |
| FR-07 | Met | `calibrate.calibrate` with Jacobian CIs and identifiability flag | recovery test (synthetic only) |
| FR-08 | Met | `weather/` | `tests/test_weather.py` (recorded Open-Meteo response, mocked transport) |
| FR-09 | Met | CLI, library, REST | `tests/test_api.py`, CLI tests |
| FR-10 | Partly | Recorder logic tested; ROS 2 node not run against a live graph | `tests/test_recorder.py` |
| FR-11 | Met | `Profile.source_counts`, `Decision.evidence_level` | `test_decision_carries_evidence...` |
| NFR-01 | Met | Core has no network use; live weather opt-in | CLI synthetic default |
| NFR-02 | Met | 72 h hourly timeline, 64 Monte Carlo samples: about 1.2 s on the build machine | measured |
| NFR-03 | Met | Seeded sampling | `test_synthetic_is_deterministic`, seed tests |
| NFR-04 | Met | ruff, pytest, CI workflow | CI |
| NFR-05 | Met | FastAPI OpenAPI at `/openapi.json` | `tests/test_api.py` |
| NFR-06 | Configured | `pip-audit` and CycloneDX in `ci.yml`; first CI run pending | CI |
| NFR-07 | Met | API key, audit log, bounded inputs | `test_api_key_enforced`, `test_audit_log_written` |
| NFR-08 | Met | Offline single-file dashboard; text and pattern encode status | visual check |

## Deviations from the plan
- Exceedance probability and time-to-limit are not reported; headroom at the risk quantile is.
- The planner has no ageing penalty; battery ageing is computed by the simulator but not used in scheduling.
- ROS 2 node unverified on a live robot or graph.
