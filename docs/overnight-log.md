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
- 04:36 Git instructions received mid session asked both for commits straight to main and for feature branches with pull requests per milestone; kept feature branches and pull requests because the work rebuilds results across unmerged stacked branches (the large change case), and followed the small commit habits.
- 05:31 Task C done: public Envelope methods with aliases; parameter builder moved to profiles/thermal_adapter.py with a deprecated alias in physics; tests/test_layers.py fails on the old module. Behaviour check: six CLI outputs identical by cmp before and after; every results file regenerated with no change reported by git; preregistered JSON identical by cmp. 144 tests. https://github.com/hudasol/dhill/pull/10
- 05:34 Task D done (worked in a separate worktree while Task C regenerated): CAMS period calendar differs by at most 0.3 points; Al Ain 2024 sampling error at most 0.3 points a year, 4.3 points worst month; coverage bootstrap 0.9938 to 0.9982 (H5 still a miss, conservatism finding weaker); Aletihad URL verified and fixed, Moore et al. not verified; benchmark script added; known issues statuses with commits. First evidence run failed on a lint error and was rerun. https://github.com/hudasol/dhill/pull/11
- 05:37 Task E done: Jackal section added to docs/sensitivity.md; both proposals refreshed and lead with evidence limits; review pass over touched files (two attribution lines reworded). 149 tests. https://github.com/hudasol/dhill/pull/12
- 05:45 Benchmark: CPU load 87 % and laptop on battery, so absolute times (5 to 7 s) are not comparable with 2.3 s of 15 October; an interleaved before and after run showed no slowdown from Task C.

## Third session, 18 October 2026

- 01:08 Verified state: #8 merged into main (9fad97f); #9 to #13 open and stacked, #9 targeting fix/jackal-rated-ambient; #2 to #7 open on the unfixed profile; only my own merge in the previous 6 hours.
- 01:10 Baseline on the stack tip: 149 tests pass, ruff clean.
- 01:10 #2 to #7 are fully superseded: each head (feature/operating-calendar, route-sim, prereg-eval, adversarial-review, proposals, overnight-report) is an ancestor of feature/rebase-results (#9). Recommendation: close all six as superseded by #9; left open as instructed.
- 01:13 CI failed on #9 to #13 (test on Python 3.11 to 3.13) although tests passed locally: the addendum hashed the profile YAML bytes, which differ between a Windows CRLF checkout and Linux. Fixed on the #9 branch (cdf59bd, cad3f94: line endings normalised before hashing), CI green.
- 01:18 #9 retargeted to main and merged (fae7a2e); 141 tests on main.
- 01:33 #10 to #13: main merged into each branch (no rebase) so CI tested the real merged result; each green, merged with a merge commit (d9a2ada, 5dd2803, 76336cb, 71a4925); gates on main after each; 149 tests on main; CI on main green.
- 01:33 Task 1 done: main contains the fixed profile, climatology, route, preregistration v0.6 with results and addenda, known issues, evidence checks, proposals and both overnight reports. Nothing missing.
- 01:31 Task 2: docs/preregistration-v0.7.md committed and pushed (f07ec6d) before the script existed; script and test added; one check run on seed 999 only.
- 01:45 Task 2 run: 200 runs; 6 of 7 predictions hit; H6 missed (envelope risky in 29 % of W2 runs, predicted 50 % or more); all five risky W1 runs come from one hidden robot with DC-DC efficiency about 0.58. Results and reading committed; https://github.com/hudasol/dhill/pull/14 opened, CI green, merged (03ef92e).
- 01:37 Task 3: Aletihad reference rechecked (still correct); Moore et al. author page returns HTTP 403 and search shows no venue, so the citation stays open; wording pass over README and hand written docs (42c3ae0), 728 numbers identical before and after; CI on main recorded as passing; known issues 14 and 15 closed, 18 added (bfc78e8).
- 01:50 Task 4: quick start from a clean clone and fresh venv works (149 tests, list, decide, timeline). Found that dhill calendar with 8 or 16 Monte Carlo samples gives GO 0 % where 64 give 89.2 % for the same days (order statistic quantile); recorded as known issue 19 (a0bdbe7). Release checklist added (2e6195a). Proposals unchanged: no stated number depends on v0.7.
