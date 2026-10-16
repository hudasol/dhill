# Preregistered evaluation v0.6: addendum on the H5 coverage interval

Dated 16 October 2026. Rendered by `examples/prereg_coverage_bootstrap.py` from
`examples/prereg_results.json`; `tests/test_prereg_coverage_bootstrap.py` fails if this
document differs. `docs/prereg-results.md` and the preregistration are unchanged.
**SYNTHETIC world**, as in the original run.

The original H5 interval (Wilson) treats every (slot, draw) pair as independent. Pairs in one
run share a hidden robot and a weather series, so whole seeds are resampled here instead
(2000 resamples, generator seed 99, all four cases of a seed kept together).

| Quantity | Value |
|---|---:|
| Pooled coverage (point estimate, unchanged) | 0.9963 |
| Wilson 95 % interval (original, pairs independent) | 0.9960 to 0.9965 |
| Bootstrap over seeds, 95 % interval | 0.9938 to 0.9982 |
| Lowest and highest per seed coverage | 0.9816 and 1.0000 |
| Seeds | 20 |

Verdict under the preregistered rule (point estimate between 0.90 and 0.995): **MISS**, unchanged.

The wider interval reaches below 0.995, so the evidence that the 95 % quantile is more conservative than its label is weaker than the original interval suggested.
