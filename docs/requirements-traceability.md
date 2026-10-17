# Requirements traceability

Requirement IDs refer to `plan.md` section 5. Status is stated honestly: where the shipped code differs from the plan, the deviation is listed below the table.

| ID | Status | Implementation | Verified by |
|---|---|---|---|
| FR-01 | Met | `Envelope.decide` | `tests/test_envelope.py` |
| FR-02 | Met | Limiting constraint, headroom (K), hard-limit exceedance probability and time-to-limit reported | `test_go_decision_has_nonnegative_headroom...`, `test_exceedance_probability_ordering`, `test_time_to_limit_*` |
| FR-03 | Met, method changed | Grid-then-refine search instead of bisection; shade requirement by grid and refine | `test_derate_scale_is_actually_feasible...`, `test_shade_requirement...` |
| FR-04 | Met | `physics/dust.py`, `thermal.simulate` | `test_physics_basic.py`, `test_dust_*` |
| FR-05 | Met | `Envelope.timeline` (multi-day) | `test_night_go_midday_park...` |
| FR-06 | Met | MILP with rest gap, concurrency and a battery-ageing penalty | `tests/test_planner_calibrate_cli.py` (`test_ageing_penalty_reduces_ageing_without_losing_work`) |
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
- Exceedance probability, time to limit and the scheduler's ageing penalty were missing in v0.4 and were added in v0.5.0 (rows FR-02 and FR-06 above).
- ROS 2 node unverified on a live robot or graph.

## Added after v0.5.0 (not in the plan's requirement list)
| Item | Implementation | Verified by |
|---|---|---|
| Operating calendar on recorded weather | `src/dhill/climatology.py`, `dhill calendar`, `scripts/gen_operating_calendar.py` | `tests/test_climatology.py` (recorded fixtures, headline consistency) |
| Patrol route simulation | `src/dhill/route.py`, `examples/route_demo.py` | `tests/test_route.py` |
| Preregistered evaluation | `docs/preregistration-v0.6.md`, `examples/prereg_eval.py` | `tests/test_prereg.py` (document equals JSON) |
