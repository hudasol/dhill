# Overnight report, 15 October 2026

Unattended session, 14:35 to 15:30 local time (UTC+4). Working notes: `docs/overnight-log.md`.

## Starting point

The session folder was empty, so the repository was cloned from https://github.com/hudasol/dhill.
`profile/clearpath-jackal` was not merged into `main`, so all work starts from it. Baseline: 110 tests passing,
ruff clean. Each task has its own branch; branches are stacked in task order because nothing was merged,
and each pull request targets the branch below it. Merge them in order, starting with `profile/clearpath-jackal`.

## Completed

| Task | Branch | Pull request | Main outputs |
|---|---|---|---|
| 1 Operating calendar | `feature/operating-calendar` | https://github.com/hudasol/dhill/pull/2 | `src/dhill/climatology.py`, `dhill calendar`, `docs/operating-calendar.md`, `docs/img/operating-calendar.png`, `examples/operating_calendar_*` |
| 2 Route simulation | `feature/route-sim` | https://github.com/hudasol/dhill/pull/3 | `src/dhill/route.py`, `examples/route_demo.py`, `docs/route-simulation.md`, `docs/img/route-simulation.png` |
| 3 Preregistered evaluation | `feature/prereg-eval` | https://github.com/hudasol/dhill/pull/4 | `docs/preregistration-v0.6.md` (committed first), `examples/prereg_eval.py`, `docs/prereg-results.md` |
| 4 Adversarial review | `feature/adversarial-review` | https://github.com/hudasol/dhill/pull/5 | Review fixes and open items, `docs/known-issues.md` |
| 5 Proposals | `feature/proposals` | https://github.com/hudasol/dhill/pull/6 | `docs/proposals/aau-robotics-proposal.md`, `docs/proposals/edge-brief.md` |
| Report | `feature/overnight-report` | see below | this file |

Nothing was abandoned. One approach was replaced: the first envelope route search was exhaustive and took
minutes per request for the Jackal; it now integrates the depot wait once per delay and searches a narrower
candidate set (`docs/overnight-log.md`). Downloads from Open-Meteo completed for all six sites and eleven
years with no gaps; no weather was invented.

**Tests:** 134 passing (110 at the start; 12 calendar, 8 route and 4 evaluation tests added). Ruff check and
format clean before every push. No existing test or result was changed by new code; stale numbers in the
README and `docs/results.md` were corrected after rerunning the commands that produce them.

## Results in one line each

- **Calendar:** air above the Jackal's rated 45 degC in 0.8 % of recorded hours; the L0 Jackal profile is
  GO in only 6.0 % of hours and never above about 20 degC air (`docs/operating-calendar.md`).
- **Routes:** the envelope changes the plan (shade, waiting, timing) but loses in two documented cases
  (`docs/route-simulation.md`).
- **Preregistered evaluation:** 2 of 6 predictions hit; the envelope had no risky hour in 80 runs, but a
  40 degC rule was slightly more productive and the 95 % quantile is conservative (`docs/prereg-results.md`).

## Five most important caveats

1. **The Jackal profile is not credible yet.** It forbids full speed above about 20 degC air against a
   45 degC datasheet rating. Every Jackal number (calendar, routes, proposals) describes the assumptions,
   chiefly the assumed computer heat path, not the robot.
2. **Every "true robot" is synthetic and shares the model's structure and author.** Policy comparison,
   route simulation and the preregistered evaluation show internal consistency, not field performance.
3. **The envelope's advantage is safety with reasons, not productivity.** Preregistered H4 missed in the
   wrong direction, and in routing the envelope bought a small safety gain with large delays.
4. **No field data exists.** All profiles are L0; the ROS 2 recorder has never run on a live graph.
5. **PM10 before August 2022 is a climatological fill** (71 % of weighted sampled calendar days), and the
   novelty search is a shallow web pass only (`docs/literature-log.md`).

## Recommended next three steps

1. **Fix the profile by measurement:** on any available Jackal or similar robot, log computer die
   temperature against processor load at two ambient temperatures, take the processor limit from the vendor
   datasheet, update the profile and rerun `python scripts/gen_operating_calendar.py` and
   `python examples/route_demo.py --plot`.
2. **Send the AAU proposal** (`docs/proposals/aau-robotics-proposal.md`) and run the supervised logging
   session with a prediction committed before the validation day (`docs/prediction-template.md`).
3. **Address the two structural review items** before external review: move `ThermalParams.from_profile`
   out of the physics layer and give `Envelope` public methods for the private ones other modules use
   (`docs/known-issues.md`, items 4 and 5).

## Not done or not checked

- Whether GitHub Actions CI runs on the new branches was not checked.
- Press figures in `plan.md` and `docs/uae-alignment.md` were not re-verified.
- The Open-Meteo cache (about 90 files, in `~/.cache/dhill/climatology`) is local to this machine and not
  committed; the calendar can be regenerated from it offline or downloaded again.
