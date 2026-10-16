# Overnight report 2, 16 October 2026

Unattended session, 04:06 to 05:50 local time (UTC+4). Working notes: `docs/overnight-log.md` (section
"Second session"). The first session's report is `docs/overnight-report.md`.

## Starting point (verified)

`main` held PR 1 (Jackal profile). `fix/jackal-rated-ambient` had three commits and no pull request. The
stacked branches of the first session (pull requests 2 to 7) were built on the unfixed profile. No branch had
changed in the previous three hours; `alt/*` branches were left alone. Baseline: 110 tests on `main`, 111 on
the fix branch, 134 on the stacked tip; ruff clean.

## Completed

| Task | Branch | Pull request | Outcome |
|---|---|---|---|
| A Land the profile fix | `fix/jackal-rated-ambient` | https://github.com/hudasol/dhill/pull/8 (into `main`) | Rated ambient test present and passing. Added a plausibility check: all three raised conductances sit at the upper end of what free convection and radiation allow and need chassis conduction or fans the datasheet does not list. Not tuned further. |
| B Rebuild results | `feature/rebase-results` | https://github.com/hudasol/dhill/pull/9 | Stack merged into a branch cut from the fix. Calendar, route demo and preregistered evaluation rerun; before and after tables computed by code and tested; addendum written. |
| C Engine contract | `feature/engine-contract` | https://github.com/hudasol/dhill/pull/10 | Known issues 4 and 5 closed; outputs shown unchanged. |
| D Evidence checks | `feature/evidence-checks` | https://github.com/hudasol/dhill/pull/11 | Known issues 6, 7, 8 and 13 closed; 10 partly closed. |
| E Proposals refresh | `feature/proposals-refresh` | https://github.com/hudasol/dhill/pull/12 | Both proposals lead with the evidence limits; Jackal sensitivity added. |
| Report | `feature/overnight-report-2` | see `docs/overnight-log.md` | This file. |

Nothing was abandoned. Not done: the Moore et al. 2012 reference (known issue 10, second half) could not be
verified and was left unchanged.

**Tests:** 134 before (stacked tip; 110 on `main`), 149 after. Ruff check and format clean before every push.
No existing test was changed; the profile fix did not alter any number an existing test asserts.

## Headline before and after the profile fix

| Statistic | Before | After | Source |
|---|---:|---:|---|
| Calendar GO / DERATE / PARK share of hours | 6.0 / 69.6 / 24.4 % | 63.9 / 16.5 / 19.6 % | `docs/operating-calendar.md` |
| Air above the rated 45 degC | 0.8 % | 0.8 % | same |
| Route, Jackal requests planned by the envelope (Abu Dhabi / Al Ain) | 0/10, 0/10 | 6/10, 4/10 | `docs/route-simulation.md` |
| Preregistered hits | 2 of 6 | 2 of 6 (JSON byte identical) | `docs/prereg-results-addendum-fixed-profile.md` |

## Findings worth knowing

1. **The preregistered evaluation never used the Jackal.** It uses `ugv_medium_inspection` only, so the fix
   could not change it; the rerun produced a byte identical result. The task brief's premise that the 2 of 6
   result described the unfixed Jackal did not hold.
2. **A real bug was found and fixed in the route demo.** Its hidden true Jackal hard coded the old
   conductance; after the fix that would have made it 3.5 times worse coupled than documented. It now scales
   the profile's current values (`examples/route_demo.py`).
3. **The H5 conservatism finding is weaker than first reported.** A seed level bootstrap gives 0.9938 to
   0.9982, reaching below the 0.995 bound (`docs/prereg-coverage-bootstrap-addendum.md`).
4. **The calendar method itself holds up.** The PM10 fill and the five day sampling each move the headline by
   at most 0.3 points (`docs/evidence-checks.md`).

## How Task C was shown not to change behaviour

Six CLI outputs (`timeline`, `decide --json`, `plan`, `sensitivity`, `calibrate`, `value_of_calibration.py`)
were captured before and after and compared with `cmp`: identical. All committed results files were
regenerated after the refactor and `git status` reported no change (git normalises line endings); the
preregistered JSON was also compared byte for byte. An interleaved timing run showed no slowdown.

## Five most important caveats

1. **The Jackal numbers rest on three unmeasured conductances.** Raising them moved GO from 6.0 % to 63.9 %
   of hours, and they sit at the upper end of plausible (`docs/robot-sources.md`).
2. **Every true robot is synthetic** and shares the model's structure and author; no result is field evidence.
3. **The envelope's advantage is a reasoned per component guarantee, not productivity.** Only 2 of 6
   preregistered predictions hit, and a 40 degC air rule was slightly more productive (H4).
4. **No field data and no live ROS 2 run.** All profiles stay at L0.
5. **The calendar assumes a 1.5 h parked soak in full sun before each mission**, and the evidence checks
   cover one site and year for sampling. Novelty is checked by a shallow web pass only
   (`docs/literature-log.md`).

## Recommended next three steps

1. Merge the stack (order below) and tag v0.6.0.
2. Run the supervised logging session in `docs/proposals/aau-robotics-proposal.md`, measuring first the
   DC-DC and drive efficiencies, ground heating and the three conductances.
3. Run the literature protocol on IEEE Xplore and Scopus before any novelty statement.

## What the owner must do by hand

- **Merge order:** #8 into `main` first. Then #9, which contains the work of #2 to #7 on the fixed profile,
  then #10, #11, #12 and the report pull request, each after the one below it, retargeting to `main` as each
  base merges. Close #2 to #7 as superseded by #9, or merge them in order before #9; do not merge them after it.
  Leave `alt/*` alone or delete them yourself.
- **Direct commits to main:** a git instruction received during the session asked for commits straight to
  `main`; work stayed on branches with pull requests (see the log). Decide which practice to keep.
- **Tags:** bump `version` in `pyproject.toml` and `src/dhill/__init__.py` to 0.6.0, update `CHANGELOG.md`,
  then push tags with `scripts/tag-releases.sh`; no tag was pushed in this session.
- **Literature exports:** run and export the IEEE Xplore, Scopus and Web of Science searches listed in
  `docs/literature-log.md` (institutional access needed).
- **Licence decision:** choose a licence (`docs/adr/0002-licensing.md`); the repository is currently all
  rights reserved.
- **CI:** check that GitHub Actions ran on the new branches; this was not checked.
- **Weather cache:** the Open-Meteo cache (90 files) is only on this laptop, in `~/.cache/dhill/climatology`.
