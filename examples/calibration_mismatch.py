"""Experiment E3 of docs/preregistration-v0.8.md: calibration under structural mismatch.

SYNTHETIC and L0 until calibrated: each hidden robot is a sixteen node simulated robot, the engine has six
nodes. For every robot, noisy telemetry from one day is used to calibrate the class profile with
`dhill.calibrate.calibrate`; policy P4 is then run on the other days with the class profile (uncalibrated)
and with the calibrated profile. No real robot is involved.

  python examples/calibration_mismatch.py --robots-per-class 20 --seed 3000 --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from dhill import climatology as clim
from dhill.calibrate import calibrate
from dhill.plant.rating import draw_rated_plants
from dhill.profiles.loader import load_builtin
from dhill.structural import (
    CLASS_PROFILE,
    CLASSES,
    SCENARIOS,
    _outcome,
    field_record,
    oracle_scales,
    p4_scales,
    plant_peaks,
    window_weather,
)

ROOT = Path(__file__).resolve().parents[1]
RECORDS = (("abu_dhabi", 2021), ("abu_dhabi", 2024), ("al_ain", 2024))
CAL_SITE, CAL_YEAR, CAL_START, CAL_HOURS = "abu_dhabi", 2021, "2021-07-02T01:00:00", 20.0
CAL_DAY = "2021-07-02"
ENGINE_SEED = 7


def boot_ci(num: np.ndarray, den: np.ndarray, reps: int = 1000, seed: int = 11):
    rng = np.random.default_rng(seed)
    n = num.size
    idx = rng.integers(0, n, size=(reps, n))
    r = num[idx].sum(1) / np.maximum(den[idx].sum(1), 1e-12)
    return [float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))]


def run(n: int, seed: int, out_path: str) -> dict:
    recs = {
        (s, y): clim.load_site_record(s, (y,), offline=True, cache_root=ROOT / "tests" / "data")
        for s, y in RECORDS
    }
    out: dict = {"seed": seed, "robots_per_class": n, "calibration_day": CAL_DAY, "classes": {}}
    sc = SCENARIOS["S1"]
    for ci, cls in enumerate(CLASSES):
        base = load_builtin(CLASS_PROFILE[cls])
        plants = draw_rated_plants(n, seed + ci, cls=cls)
        cal_profiles, fits, failed = [], [], 0
        for i in range(n):
            one = plants.take(np.array([i]))
            tel, w_st, _ = field_record(
                one, recs[(CAL_SITE, CAL_YEAR)], CAL_START, CAL_HOURS, seed=seed + 100 * ci + i
            )
            try:
                cal, res = calibrate(base, w_st, tel)
                cal_profiles.append(cal)
                fits.append(
                    {
                        "holdout_rmse_k": res.rmse_holdout_k,
                        "prior_holdout_rmse_k": res.rmse_prior_holdout_k,
                        "identified": [p.key for p in res.params if p.identified],
                    }
                )
            except Exception as exc:  # a failed fit keeps the class profile and is counted
                failed += 1
                cal_profiles.append(base)
                fits.append({"error": str(exc)[:120]})
            print(f"{cls} robot {i + 1}/{n} calibrated", file=sys.stderr, flush=True)
        tot = {
            k: np.zeros(n)
            for k in ("op_u", "br_u", "prod_u", "safe_u", "op_c", "br_c", "prod_c", "safe_c", "orc")
        }
        for (site, year), rec in recs.items():
            for di, d in enumerate(np.unique(rec.times_utc.astype("datetime64[D]"))):
                day = str(d)
                if day == CAL_DAY:
                    continue
                w = window_weather(rec, day)
                first = "03" if di == 0 else "02"
                f_utc, l_utc = f"{day}T{first}:00", f"{day}T14:00"
                slot_s, cap, s_u = p4_scales(base, w, f_utc, l_utc, ENGINE_SEED)
                s_c = np.zeros((slot_s.size, n))
                for i, prof in enumerate(cal_profiles):
                    _, _, s_c[:, i] = p4_scales(prof, w, f_utc, l_utc, ENGINE_SEED)
                seed_day = ENGINE_SEED + di
                pk_u, soc_u = plant_peaks(plants, w, slot_s, s_u, sc, seed_day, return_soc=True)
                pk_c, soc_c = plant_peaks(plants, w, slot_s, s_c, sc, seed_day, return_soc=True)
                b_u, _ = _outcome(base, pk_u, soc_u)
                b_c, _ = _outcome(base, pk_c, soc_c)
                su = np.broadcast_to(s_u[:, None], s_c.shape)
                op_u, op_c = su > 0, s_c > 0
                tot["op_u"] += op_u.sum(0)
                tot["br_u"] += (b_u & op_u).sum(0)
                tot["prod_u"] += su.sum(0)
                tot["safe_u"] += (su * ~(b_u & op_u)).sum(0)
                tot["op_c"] += op_c.sum(0)
                tot["br_c"] += (b_c & op_c).sum(0)
                tot["prod_c"] += s_c.sum(0)
                tot["safe_c"] += (s_c * ~(b_c & op_c)).sum(0)
                tot["orc"] += oracle_scales(base, plants, w, slot_s, cap, sc, seed_day).sum(0)
            print(f"{cls} {site} {year} evaluated", file=sys.stderr, flush=True)
        ok = [f for f in fits if "error" not in f]
        red = np.array([1.0 - f["holdout_rmse_k"] / f["prior_holdout_rmse_k"] for f in ok])
        out["classes"][cls] = {
            "robots": n,
            "failed_fits": failed,
            "rmse_reduction_mean": float(red.mean()) if red.size else None,
            "rmse_reduction_median": float(np.median(red)) if red.size else None,
            "breach_rate_uncalibrated": float(tot["br_u"].sum() / max(tot["op_u"].sum(), 1)),
            "breach_ci95_uncalibrated": boot_ci(tot["br_u"], tot["op_u"]),
            "breach_rate_calibrated": float(tot["br_c"].sum() / max(tot["op_c"].sum(), 1)),
            "breach_ci95_calibrated": boot_ci(tot["br_c"], tot["op_c"]),
            "operated_uncalibrated": int(tot["op_u"].sum()),
            "operated_calibrated": int(tot["op_c"].sum()),
            "productive_h_uncalibrated": float(tot["prod_u"].sum()),
            "productive_h_calibrated": float(tot["prod_c"].sum()),
            "safe_h_uncalibrated": float(tot["safe_u"].sum()),
            "safe_h_calibrated": float(tot["safe_c"].sum()),
            "oracle_h": float(tot["orc"].sum()),
            "fits": fits,
        }
    pooled = {
        k: sum(out["classes"][c][k] for c in CLASSES)
        for k in ("operated_uncalibrated", "operated_calibrated")
    }
    brk_u = sum(
        out["classes"][c]["breach_rate_uncalibrated"] * out["classes"][c]["operated_uncalibrated"]
        for c in CLASSES
    )
    brk_c = sum(
        out["classes"][c]["breach_rate_calibrated"] * out["classes"][c]["operated_calibrated"]
        for c in CLASSES
    )
    orc = sum(out["classes"][c]["oracle_h"] for c in CLASSES)
    out["pooled"] = {
        "breach_rate_uncalibrated": brk_u / max(pooled["operated_uncalibrated"], 1),
        "breach_rate_calibrated": brk_c / max(pooled["operated_calibrated"], 1),
        "safe_fraction_of_oracle_uncalibrated": sum(
            out["classes"][c]["safe_h_uncalibrated"] for c in CLASSES
        )
        / max(orc, 1e-12),
        "safe_fraction_of_oracle_calibrated": sum(
            out["classes"][c]["safe_h_calibrated"] for c in CLASSES
        )
        / max(orc, 1e-12),
        "productive_fraction_of_oracle_uncalibrated": sum(
            out["classes"][c]["productive_h_uncalibrated"] for c in CLASSES
        )
        / max(orc, 1e-12),
        "productive_fraction_of_oracle_calibrated": sum(
            out["classes"][c]["productive_h_calibrated"] for c in CLASSES
        )
        / max(orc, 1e-12),
    }
    Path(out_path).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--robots-per-class", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run(args.robots_per_class, args.seed, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
