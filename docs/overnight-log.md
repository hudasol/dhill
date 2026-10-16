# Overnight log

Working memory for the unattended session of 15 October 2026. One line per finished or abandoned step,
local time (UTC+4).

- 14:35 Repository was not present in the session folder; cloned https://github.com/hudasol/dhill.
- 14:36 Branch profile/clearpath-jackal is not merged into main; all work branches from it.
- 14:39 Baseline: `pip install -e ".[dev]"` in a local virtual environment; 110 tests pass; ruff check and ruff format clean.
- 14:41 Open-Meteo archive and air quality endpoints reachable. CAMS PM10 through the air quality API returns null before 2022-08; earlier hours need a stated fill.
- 14:42 Task branches are stacked (each starts from the previous task branch) because nothing is merged yet; each pull request targets the branch below it.
- 14:58 Task 1 done: climatology module, dhill calendar CLI, 12 tests on trimmed real fixtures, calendar for six sites 2015 to 2025 with no download gaps. Finding: the L0 Jackal profile returns GO only below about 20 degC air (compute die binds in every non GO hour), which contradicts the 45 degC datasheet rating; documented as a profile problem, not a robot property.
- 15:06 Task 2 done: route.py (graph, plans, three planners, scoring), 8 tests, demo on recorded Abu Dhabi and Al Ain July 2024 days. First version of the envelope search was too slow for the Jackal (exhaustive, no feasible plan); replaced with a shared depot wait per delay and a narrower candidate set. Envelope loses in two cases, both documented.
- 15:17 Task 3 done: preregistration committed and pushed first (ffaad20), then script, 80 runs plus 400 route requests. 2 of 6 predictions hit (H1, H6); H2, H3, H4, H5 missed and are reported. A one off smoke run of seed 0 preceded the full run; recorded in the results.
- 15:20 Task 4 done: review fixes committed one per change (non author attribution, em dashes, contradictory traceability, stale outputs, README, model card, unused parameter); 17 open items in docs/known-issues.md; number check table included.
- 15:21 Task 5 done: docs/proposals/aau-robotics-proposal.md and docs/proposals/edge-brief.md, numbers cited by path.
- 15:24 Final report written (docs/overnight-report.md); 134 tests pass; all tasks finished, none abandoned.

## Second session, 16 October 2026

- 04:06 Verified state: main holds PR 1; fix/jackal-rated-ambient has three commits on main and no pull request; stacked branches unchanged; alt/* branches present and left alone. No commits on any branch in the previous 3 hours.
- 04:09 Baseline gates: stacked tip (feature/overnight-report) 134 tests pass; fix/jackal-rated-ambient 111 tests pass; ruff clean on both.
- 04:11 Task A done: reviewed the fix; rated ambient test present and passing; added a plausibility check of the three conductances to docs/robot-sources.md (upper end of plausible; need chassis conduction or fans not in the datasheet); opened https://github.com/hudasol/dhill/pull/8 into main.
- 04:12 Task B: created feature/rebase-results from fix/jackal-rated-ambient and merged feature/overnight-report without conflicts (135 tests pass).
- 04:20 Calendar rerun from the local cache (90 files, no download needed, no gaps): GO 63.9 %, DERATE 16.5 %, PARK 19.6 % (was 6.0, 69.6, 24.4); binding component now battery.
- 04:31 Found and fixed a bug in examples/route_demo.py: the hidden true Jackal hard coded the old shell to interior conductance (4.4 x 14/18), which after the fix made it 3.5 times worse coupled than documented; now scaled from the profile's current values. Route demo rerun after the fix only.
- 04:33 Preregistered rerun, same seeds, cases and code: result JSON byte identical to the original (checked with cmp); 2 of 6 hits unchanged because the evaluation uses only ugv_medium_inspection. Addendum written; original files untouched.
- 04:32 Task B done: calendar, route and README numbers rebuilt and covered by tests (calendar headline and before and after table, route tables, README calendar numbers, addendum); 141 tests pass.
