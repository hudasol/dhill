"""Addendum: a bootstrap over seeds for the H5 coverage interval (known issue 8).

docs/prereg-results.md reports a Wilson interval for H5 that treats every (slot, draw) pair as
independent. Pairs within a run share a hidden robot and a weather series, so that interval is too
narrow. This script resamples whole seeds (all four cases of a seed together), recomputes the
pooled coverage and reports a percentile interval. It reads examples/prereg_results.json and changes
neither that file nor docs/prereg-results.md. The verdict rule of the preregistration (point estimate
between 0.90 and 0.995) is applied unchanged.

Run: python examples/prereg_coverage_bootstrap.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "examples" / "prereg_results.json"
DOC = ROOT / "docs" / "prereg-coverage-bootstrap-addendum.md"
RESAMPLES = 2000
SEED = 99  # same generator seed as the preregistered bootstrap for H4


def per_seed(res: dict) -> dict[int, tuple[int, int]]:
    out: dict[int, list[int]] = {}
    for r in res["raw"]["runs"]:
        c = out.setdefault(r["seed"], [0, 0])
        c[0] += r["coverage"]["covered"]
        c[1] += r["coverage"]["pairs"]
    return {k: (v[0], v[1]) for k, v in out.items()}


def bootstrap(counts: dict[int, tuple[int, int]], n: int = RESAMPLES, seed: int = SEED):
    rng = np.random.default_rng(seed)
    keys = np.array(sorted(counts))
    cov = np.array([counts[k][0] for k in keys], dtype=float)
    pairs = np.array([counts[k][1] for k in keys], dtype=float)
    stats = []
    for _ in range(n):
        idx = rng.integers(0, keys.size, keys.size)
        stats.append(cov[idx].sum() / pairs[idx].sum())
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def render(res: dict) -> str:
    h5 = res["hypotheses"]["H5"]
    counts = per_seed(res)
    lo, hi = bootstrap(counts)
    per = sorted(c / p for c, p in counts.values())
    point = h5["coverage"]
    hit = 0.90 <= point <= 0.995
    return "\n".join(
        [
            "# Preregistered evaluation v0.6: addendum on the H5 coverage interval",
            "",
            "Dated 16 October 2026. Rendered by `examples/prereg_coverage_bootstrap.py` from",
            "`examples/prereg_results.json`; `tests/test_prereg_coverage_bootstrap.py` fails if this",
            "document differs. `docs/prereg-results.md` and the preregistration are unchanged.",
            "**SYNTHETIC world**, as in the original run.",
            "",
            "The original H5 interval (Wilson) treats every (slot, draw) pair as independent. Pairs in one",
            "run share a hidden robot and a weather series, so whole seeds are resampled here instead",
            f"({RESAMPLES} resamples, generator seed {SEED}, all four cases of a seed kept together).",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            f"| Pooled coverage (point estimate, unchanged) | {point:.4f} |",
            f"| Wilson 95 % interval (original, pairs independent) | {h5['ci'][0]:.4f} to {h5['ci'][1]:.4f} |",
            f"| Bootstrap over seeds, 95 % interval | {lo:.4f} to {hi:.4f} |",
            f"| Lowest and highest per seed coverage | {per[0]:.4f} and {per[-1]:.4f} |",
            f"| Seeds | {len(counts)} |",
            "",
            f"Verdict under the preregistered rule (point estimate between 0.90 and 0.995): "
            f"**{'HIT' if hit else 'MISS'}**, unchanged.",
            "",
            "The wider interval "
            + (
                "still lies above 0.995, so the conclusion that the 95 % quantile is more conservative "
                "than its label is not an artefact of the interval method."
                if lo > 0.995
                else "reaches below 0.995, so the evidence that the 95 % quantile is more conservative "
                "than its label is weaker than the original interval suggested."
            ),
            "",
        ]
    )


def main() -> int:
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    DOC.write_text(render(res), encoding="utf-8")
    print(DOC.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
