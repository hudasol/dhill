# Preregistered evaluation v0.6: addendum after the Jackal profile fix

Dated 16 October 2026. Rendered by `examples/prereg_eval_fixed_profile.py` from
`examples/prereg_results.json` (before) and `examples/prereg_results_fixed_profile.json` (after).
`tests/test_prereg_addendum.py` fails if this document differs from what the code renders.
`docs/preregistration-v0.6.md` and `docs/prereg-results.md` are unchanged; hypotheses and criteria
are exactly those preregistered. **SYNTHETIC world**, as in the original run.

## Why a rerun

Branch `fix/jackal-rated-ambient` changed three assumed conductances of `clearpath_jackal` so the
profile is consistent with its rated 45 degC ambient. The evaluation was rerun on the fixed profile
with the same seeds, cases, policies and code.

The preregistered evaluation uses only `ugv_medium_inspection` (preregistration, Fixed design), whose
profile file is unchanged by the fix (sha256 prefix `141a14a9049d`). The Jackal
profile does not enter any of H1 to H6.

## Before and after

| ID | Before | After | Verdict before | Verdict after |
|---|---|---|---|---|
| H1 | 80 of 80 (100.0 %) | 80 of 80 (100.0 %) | HIT | HIT |
| H2 | 19 of 80 (23.8 %) | 19 of 80 (23.8 %) | MISS | MISS |
| H3 | 39 of 80 (48.8 %) | 39 of 80 (48.8 %) | MISS | MISS |
| H4 | -0.41 h (-0.71 to -0.18) | -0.41 h (-0.71 to -0.18) | MISS | MISS |
| H5 | 0.9963 | 0.9963 | MISS | MISS |
| H6 | P(viol) 0.0 % vs 0.1 %; finish 71.1 vs 34.0 min | P(viol) 0.0 % vs 0.1 %; finish 71.1 vs 34.0 min | HIT | HIT |

Hits before: 2 of 6. Hits after: 2 of 6.
Raw per run results identical before and after: yes. Result files byte identical: yes.

## What changed and why

Nothing changed. Every hit and miss of `docs/prereg-results.md` stands, and every number is
identical, because the evaluation never used the Jackal profile. The preregistered result was
never evidence about the Jackal, before or after the fix; it describes the medium UGV in a
synthetic world.
