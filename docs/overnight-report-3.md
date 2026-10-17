# Overnight report 3, 18 October 2026

Unattended session, 01:08 to about 02:10 local time (UTC+4). Working notes: `docs/overnight-log.md`, section
"Third session".

## Starting point (verified)

Pull request #8 (Jackal profile fix) was merged into main (9fad97f). Pull requests #9 to #13 were open and
stacked; #9 targeted `fix/jackal-rated-ambient`. Pull requests #2 to #7 were open on the unfixed profile.
Baseline on the stack tip: 149 tests pass, ruff clean.

## Completed

| Task | Outcome | Where |
|---|---|---|
| 1 Merge the chain | #9 to #13 merged into main with merge commits, in order, after CI on each merged result. CI had failed on all five because the addendum hashed the profile YAML with platform dependent line endings; fixed on the #9 branch (cdf59bd, cad3f94) before merging. Main contains everything listed in the brief; nothing missing. | merges fae7a2e, d9a2ada, 5dd2803, 76336cb, 71a4925 |
| 2 Preregistration v0.7 (Jackal) | Preregistration committed and pushed first (f07ec6d); 200 runs; 6 of 7 predictions hit. Pull request #14 merged (03ef92e). | `docs/preregistration-v0.7.md`, `docs/prereg-results-v07.md` |
| 3 Review items | Item 10: Aletihad reference still correct; Moore et al. stays open (author page returns HTTP 403, no venue found). Item 14: wording pass, 728 numbers identical before and after (42c3ae0). Item 15: CI on main passes. New item 18 (closed) and item 19 (open). | `docs/known-issues.md` |
| 4 Release readiness | Quick start works from a clean clone and fresh venv. Release checklist written. Proposals unchanged: no stated number depends on v0.7. | `docs/release-checklist.md` |
| Report | This file. | see the pull request list below |

Nothing was abandoned.

**Tests:** 149 before (stack tip), 152 after on main. Ruff and pytest passed before every push; CI passed on
every merged pull request and on main.

## v0.7 in one paragraph

With hidden Jackals drawn from the planner's own prior (W1), the envelope had no risky hour in 95.0 % of runs;
all five exceptions come from one hidden robot whose DC-DC efficiency was drawn near 0.58 against an assumed
0.90. The envelope lost 3.34 productive hours a day to the 40 degC air rule, as predicted. With the three
conductances at their values before the fix (W2) it was risky in 29.0 % of runs, fewer than the predicted 50 %
or more (the one MISS). Source: `docs/prereg-results-v07.md`. All hidden robots are SYNTHETIC.

## Merged and open

- Merged this session: #9, #10, #11, #12, #13, #14.
- Open: #2 to #7 (superseded: each head is contained in #9; recommend closing without merging) and the pull
  request for this report.
- Branches `alt/*`, `fix/jackal-rated-ambient` and the merged feature branches are kept; nothing was deleted.

## Five most important caveats

1. **No field data.** Every profile is L0 and every true robot is synthetic, sharing the model's structure and
   author. Nothing here is evidence about a real Jackal.
2. **The Jackal answer moves with unmeasured parameters.** Three conductances moved the calendar's GO share from
   6.0 % to 63.9 % (`docs/operating-calendar.md`); in v0.7 one low DC-DC efficiency draw was enough to make the
   envelope risky.
3. **The envelope does not buy productivity.** It loses to a 40 degC air rule for the medium UGV (v0.6, H4) and
   by about 3.3 hours a day for the Jackal (v0.7, H4). Its value is a reasoned per component guarantee.
4. **Small Monte Carlo sample counts change decisions** (`docs/known-issues.md` item 19): GO 0 % at 8 or 16
   samples against 89.2 % at 64 for the same days. Published results all use 64.
5. **Novelty and one citation are unverified.** The literature search is a shallow web pass, and the Moore et al.
   2012 citation has no confirmed venue (`docs/literature-log.md`, known issue 10).

## Recommended next three steps

1. Run the supervised logging session in `docs/proposals/aau-robotics-proposal.md`, measuring first DC-DC and
   drive efficiency and the three conductances; v0.7 shows these decide the answer.
2. Guard the sample count (known issue 19): refuse or warn below 64 samples in the CLI and API.
3. Release v0.6.0, choose a licence and run the literature exports (`docs/release-checklist.md`).

## What the owner must do by hand

- Close #2 to #7 as superseded by #9, or leave them; do not merge them.
- Merge the pull request for this report.
- Bump the version, update the changelog and push the tags from your own machine (`docs/release-checklist.md`
  steps 3 and 4); no tag has been pushed.
- Decide the licence (ADR 0002 options in the checklist).
- Run and export the literature searches with institutional access (checklist step 6).
- Optionally delete merged feature branches and `alt/*`; they were left as instructed.
