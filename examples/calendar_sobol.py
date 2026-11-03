"""Experiment E4 of docs/preregistration-v0.8.md: Morris screening and Sobol indices for the calendar.

SYNTHETIC and L0: the Jackal profile is built from datasheets and assumptions, and the weather is the
two 2024 six day July reanalysis windows in `tests/data/climatology` that carry PM10 (a reduced calendar,
not the eleven year one). The model output is the share of hours with decision GO, evaluated nominally (parameter spread and
weather error off) so that it is a deterministic function of the parameter vector.

  python examples/calendar_sobol.py --morris-r 16 --sobol-n 512 --seed 4000 --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from SALib.analyze import morris as morris_analyze
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import morris as morris_sample
from SALib.sample import sobol as sobol_sample
from scipy.stats import truncnorm

from dhill import climatology as clim
from dhill.envelope import EngineConfig
from dhill.profiles.loader import load_builtin
from dhill.profiles.registry import PARAMS

ROOT = Path(__file__).resolve().parents[1]
RECORDS = (("abu_dhabi", 2024), ("al_ain", 2024))
PROFILE = "clearpath_jackal"
CFG = EngineConfig(n_mc=1, sigma_scale=0.0, seed=7)
TRUNC = 2.0
_STATE: dict = {}


def varied_keys(profile) -> list[str]:
    """Parameters whose source is assumption or textbook and whose spread is above zero."""
    return [
        k
        for k in PARAMS
        if k in profile.parameters
        and profile.parameters[k].source in ("assumption", "textbook")
        and profile.sigma(k) > 0
    ]


def to_values(profile, keys: list[str], u: np.ndarray) -> dict[str, float]:
    """Map unit interval coordinates to parameter values: value times exp(sigma z), z truncated normal."""
    z = truncnorm.ppf(np.clip(u, 1e-9, 1 - 1e-9), -TRUNC, TRUNC)
    out = {}
    for k, zi in zip(keys, z, strict=True):
        v = profile.value(k) * np.exp(profile.sigma(k) * zi)
        out[k] = float(np.clip(v, PARAMS[k].lo, PARAMS[k].hi))
    return out


def _records():
    if "rec" not in _STATE:
        _STATE["rec"] = [
            clim.load_site_record(s, (y,), offline=True, cache_root=ROOT / "tests" / "data")
            for s, y in RECORDS
        ]
        _STATE["profile"] = load_builtin(PROFILE)
    return _STATE["rec"], _STATE["profile"]


def go_share(values: dict[str, float]) -> float:
    """Share of hours with decision GO on the reduced calendar for the given parameter values."""
    recs, base = _records()
    prof = base.with_overrides(values, source="assumption") if values else base
    go = total = 0
    for rec in recs:
        rows = clim.run_site(prof, rec, months=[7], cfg=CFG, every_day=True)
        go += sum(1 for r in rows if r.action == "GO")
        total += len(rows)
    return go / total


def _eval_row(args: tuple) -> float:
    keys, u = args
    _, prof = _records()
    return go_share(to_values(prof, keys, np.asarray(u)))


def evaluate_all(
    keys: list[str], pts: np.ndarray, workers: int, label: str, seed: int = 0
) -> np.ndarray:
    """Evaluate every row. With DHILL_EVAL_CACHE set, partial results are stored so a restart resumes."""
    jobs = [(keys, row) for row in pts]
    root = os.environ.get("DHILL_EVAL_CACHE")
    path = Path(root) / f"{label}_{seed}_{len(jobs)}.npy" if root else None
    done: list[float] = []
    if path is not None and path.exists():
        done = list(np.load(path))
    todo = jobs[len(done) :]
    if workers <= 1:
        for i, j in enumerate(todo):
            done.append(_eval_row(j))
            if (len(done)) % 50 == 0:
                print(f"{label} {len(done)}/{len(jobs)}", file=sys.stderr, flush=True)
                if path is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    np.save(path, np.array(done))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for v in ex.map(_eval_row, todo, chunksize=8):
                done.append(v)
                if len(done) % 100 == 0:
                    print(f"{label} {len(done)}/{len(jobs)}", file=sys.stderr, flush=True)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, np.array(done))
    return np.array(done)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--morris-r", type=int, required=True)
    ap.add_argument("--sobol-n", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    _, prof = _records()
    keys = varied_keys(prof)
    d = len(keys)
    point = go_share({})

    # Morris screening over all varied parameters
    pr = {"num_vars": d, "names": keys, "bounds": [[0.0, 1.0]] * d}
    xm = morris_sample.sample(pr, N=args.morris_r, num_levels=4, seed=args.seed)
    ym = evaluate_all(keys, xm, args.workers, "morris", args.seed)
    mo = morris_analyze.analyze(pr, xm, ym, num_levels=4, seed=args.seed)
    order = np.argsort(-np.asarray(mo["mu_star"]))
    top = [keys[i] for i in order[: args.top]]

    # Sobol analysis on the top parameters, the others held at their nominal values
    ps = {"num_vars": len(top), "names": top, "bounds": [[0.0, 1.0]] * len(top)}
    xs = sobol_sample.sample(ps, args.sobol_n, calc_second_order=False, seed=args.seed)
    ys = evaluate_all(top, xs, args.workers, "sobol", args.seed)
    so = sobol_analyze.analyze(
        ps, ys, calc_second_order=False, num_resamples=200, conf_level=0.95, seed=args.seed
    )
    lo, mid, hi = (float(np.quantile(ys, q)) for q in (0.05, 0.5, 0.95))
    out = {
        "profile": PROFILE,
        "evidence_level": prof.evidence_level,
        "calendar": "reduced July calendar, two six day 2024 records, every hour",
        "seed": args.seed,
        "morris_r": args.morris_r,
        "sobol_n": args.sobol_n,
        "evaluations": {"morris": int(len(ym)), "sobol": int(len(ys))},
        "point_value": point,
        "interval_5_95": [lo, hi],
        "median": mid,
        "interval_width_points": 100.0 * (hi - lo),
        "point_inside_interval": bool(lo <= point <= hi),
        "morris": [
            {
                "parameter": keys[i],
                "mu_star": float(mo["mu_star"][i]),
                "sigma": float(mo["sigma"][i]),
                "mu_star_conf": float(mo["mu_star_conf"][i]),
            }
            for i in order
        ],
        "sobol": [
            {
                "parameter": top[i],
                "S1": float(so["S1"][i]),
                "S1_conf": float(so["S1_conf"][i]),
                "ST": float(so["ST"][i]),
                "ST_conf": float(so["ST_conf"][i]),
            }
            for i in range(len(top))
        ],
        "sum_first_order": float(np.sum(so["S1"])),
    }
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
