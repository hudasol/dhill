"""Experiments E1 and E2 of docs/preregistration-v0.8.md: the engine against hidden synthetic robots.

SYNTHETIC and L0: the robots come from the independent reference simulator (`dhill.plant`), the weather is
three six day July reanalysis windows from `tests/data/climatology`. No real robot is involved.

  python examples/structural_eval.py fit-conformal --robots-per-class 68 --seed 2000 --out OFFSETS.json
  python examples/structural_eval.py evaluate --robots-per-class 68 --seed 1000 --offsets OFFSETS.json --out RESULTS.json

`fit-conformal` computes Mondrian (class by component) split conformal offsets on calibration robots.
`evaluate` runs policies P1 to P6 on disjoint evaluation robots for scenarios S1 to S5.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from dhill import climatology as clim
from dhill.plant.rating import draw_rated_plants
from dhill.profiles.loader import load_builtin
from dhill.profiles.registry import COMPONENTS
from dhill.structural import (
    CLASS_PROFILE,
    CLASSES,
    POLICIES,
    SCENARIOS,
    conformal_offset,
    engine_slots,
    run_class_day,
    window_weather,
)

ROOT = Path(__file__).resolve().parents[1]
RECORDS = (("abu_dhabi", 2021), ("abu_dhabi", 2024), ("al_ain", 2024))
ENGINE_SEED = 7
_REC: dict = {}
_PLANTS: dict = {}


def days() -> list[tuple[str, int, str, bool]]:
    """(site, year, ISO day, is_first_day) for the 18 days of the three records."""
    out = []
    for site, year in RECORDS:
        rec = _record(site, year)
        d = np.unique(rec.times_utc.astype("datetime64[D]"))
        out += [(site, year, str(x), i == 0) for i, x in enumerate(d)]
    return out


def _record(site: str, year: int):
    key = (site, year)
    if key not in _REC:
        _REC[key] = clim.load_site_record(
            site, (year,), offline=True, cache_root=ROOT / "tests" / "data"
        )
    return _REC[key]


def _plants(cls: str, n: int, seed: int):
    key = (cls, n, seed)
    if key not in _PLANTS:
        _PLANTS[key] = draw_rated_plants(n, seed + CLASSES.index(cls), cls=cls)
    return _PLANTS[key]


def task(args: tuple) -> dict:
    cls, day_idx, site, year, day, first, n, seed, scen_names, offsets = args
    profile = load_builtin(CLASS_PROFILE[cls])
    w = window_weather(_record(site, year), day)
    es = engine_slots(
        profile,
        w,
        f"{day}T{'03' if first else '02'}:00",
        f"{day}T14:00",
        ENGINE_SEED,
        offsets_k=offsets,
    )
    plants = _plants(cls, n, seed)
    out: dict = {"cls": cls, "n_slots": int(es.slot_s.size), "scen": {}}
    for sn in scen_names:
        cd = run_class_day(profile, plants, w, es, SCENARIOS[sn], ENGINE_SEED + day_idx)
        rec = {}
        for pol in POLICIES:
            sc = cd.scales[pol]
            sc2 = sc if sc.ndim == 2 else np.broadcast_to(sc[:, None], (sc.shape[0], n))
            op = sc2 > 0
            rec[pol] = {
                "operated": op.sum(0).tolist(),
                "breach": (cd.breach[pol] & op).sum(0).tolist(),
                "hard": (cd.hard[pol] & op).sum(0).tolist(),
                "productive": sc2.sum(0).tolist(),
                "safe": (sc2 * ~(cd.breach[pol] & op)).sum(0).tolist(),
            }
        op4 = es.scale["P4"] > 0
        err4 = cd.peak_p4[op4] - es.risk_peak[op4][:, None, :]  # (Sop, P, 5)
        op5 = es.scale["P5"] > 0
        off = np.zeros(len(COMPONENTS)) if offsets is None else np.asarray(offsets)
        err5 = cd.peak_p5[op5] - (es.risk_peak5[op5] + off)[:, None, :]
        rec["err4"] = err4.transpose(2, 0, 1).reshape(len(COMPONENTS), -1).tolist()
        rec["cover_before"] = (err4 <= 0).sum(axis=0).tolist()  # (P, 5)
        rec["cover_after"] = (err5 <= 0).sum(axis=0).tolist()
        rec["n_op4"] = int(op4.sum())
        rec["n_op5"] = int(op5.sum())
        out["scen"][sn] = rec
    return out


def run_tasks(n: int, seed: int, scen_names: list[str], offsets: dict | None) -> list[dict]:
    jobs = []
    for cls in CLASSES:
        for i, (site, year, day, first) in enumerate(days()):
            off = None if offsets is None else tuple(offsets[cls]["offsets_k"])
            jobs.append((cls, i, site, year, day, first, n, seed, scen_names, off))
    with ProcessPoolExecutor(max_workers=2) as ex:
        results = []
        for k, r in enumerate(ex.map(task, jobs)):
            results.append(r)
            print(f"done {k + 1}/{len(jobs)}", file=sys.stderr, flush=True)
    return results


def fit_conformal(n: int, seed: int) -> dict:
    res = run_tasks(n, seed, ["S1"], None)
    out: dict = {"seed": seed, "robots_per_class": n, "classes": {}}
    for cls in CLASSES:
        errs = np.concatenate(
            [np.array(r["scen"]["S1"]["err4"]) for r in res if r["cls"] == cls], axis=1
        )  # (5, cases)
        offs, rows = [], {}
        for j, c in enumerate(COMPONENTS):
            o = conformal_offset(errs[j])
            offs.append(o)
            rows[c] = {
                "offset_k": o,
                "cases": int(errs.shape[1]),
                "coverage_before": float((errs[j] <= 0).mean()),
            }
        out["classes"][cls] = {"offsets_k": offs, "components": rows}
    return out


def boot_ci(num: np.ndarray, den: np.ndarray, reps: int = 1000, seed: int = 11):
    """Bootstrap interval over robots for the ratio sum(num) / sum(den)."""
    rng = np.random.default_rng(seed)
    n = num.size
    idx = rng.integers(0, n, size=(reps, n))
    r = num[idx].sum(1) / np.maximum(den[idx].sum(1), 1e-12)
    return [float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))]


def evaluate(n: int, seed: int, offsets: dict) -> dict:
    scen = list(SCENARIOS)
    res = run_tasks(n, seed, scen, offsets["classes"])
    out: dict = {"seed": seed, "robots_per_class": n, "scenarios": {}, "errors": {}}
    for sn in scen:
        out["scenarios"][sn] = {}
        for cls in [*CLASSES, "all"]:
            sel = [r for r in res if cls == "all" or r["cls"] == cls]
            rows = {}
            for pol in POLICIES:
                tot = {
                    k: np.sum([r["scen"][sn][pol][k] for r in sel], axis=0)
                    for k in ("operated", "breach", "hard", "productive", "safe")
                }
                if cls == "all":
                    # per robot arrays are class specific; concatenate over classes
                    tot = {
                        k: np.concatenate(
                            [
                                np.sum(
                                    [r["scen"][sn][pol][k] for r in res if r["cls"] == c], axis=0
                                )
                                for c in CLASSES
                            ]
                        )
                        for k in tot
                    }
                slots = np.sum([r["n_slots"] for r in sel if cls != "all"]) if cls != "all" else 0
                rows[pol] = {
                    "breach_rate_operated": float(
                        tot["breach"].sum() / max(tot["operated"].sum(), 1)
                    ),
                    "breach_ci95": boot_ci(tot["breach"], tot["operated"]),
                    "operated_cases": int(tot["operated"].sum()),
                    "breach_cases": int(tot["breach"].sum()),
                    "hard_cases": int(tot["hard"].sum()),
                    "productive_h": float(tot["productive"].sum()),
                    "productive_safe_h": float(tot["safe"].sum()),
                    "cases": int(slots * n) if cls != "all" else 0,
                }
            oracle = rows["P6"]["productive_h"]
            for pol in POLICIES:
                rows[pol]["fraction_of_oracle"] = rows[pol]["productive_h"] / max(oracle, 1e-12)
                rows[pol]["safe_fraction_of_oracle"] = rows[pol]["productive_safe_h"] / max(
                    oracle, 1e-12
                )
                rows[pol]["missed_h"] = max(oracle - rows[pol]["productive_h"], 0.0)
            out["scenarios"][sn][cls] = rows
    for cls in CLASSES:
        sel = [r for r in res if cls == r["cls"]]
        e = np.concatenate([np.array(r["scen"]["S1"]["err4"]) for r in sel], axis=1)
        rows = {}
        for j, c in enumerate(COMPONENTS):
            q = np.quantile(e[j], [0.25, 0.5, 0.75])
            cb = np.sum([np.array(r["scen"]["S1"]["cover_before"])[:, j] for r in sel], axis=0)
            ca = np.sum([np.array(r["scen"]["S1"]["cover_after"])[:, j] for r in sel], axis=0)
            n4 = int(np.sum([r["scen"]["S1"]["n_op4"] for r in sel]))
            n5 = int(np.sum([r["scen"]["S1"]["n_op5"] for r in sel]))
            rows[c] = {
                "median_k": float(q[1]),
                "iqr_k": float(q[2] - q[0]),
                "cases_p4": n4,
                "coverage_before": float(cb.sum() / max(n4 * n, 1)),
                "coverage_before_ci95": boot_ci(cb.astype(float), np.full(n, n4 / 1.0)),
                "cases_p5": n5,
                "coverage_after": float(ca.sum() / max(n5 * n, 1)),
                "coverage_after_ci95": boot_ci(ca.astype(float), np.full(n, n5 / 1.0)),
            }
        out["errors"][cls] = rows
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("fit-conformal")
    b = sub.add_parser("evaluate")
    for p in (a, b):
        p.add_argument("--robots-per-class", type=int, required=True)
        p.add_argument("--seed", type=int, required=True)
        p.add_argument("--out", required=True)
    b.add_argument("--offsets", required=True)
    args = ap.parse_args()
    if args.cmd == "fit-conformal":
        out = fit_conformal(args.robots_per_class, args.seed)
    else:
        offsets = json.loads(Path(args.offsets).read_text(encoding="utf-8"))
        out = evaluate(args.robots_per_class, args.seed, offsets)
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
