"""Preregistered evaluation v0.7 of the Jackal profile, run exactly as fixed in docs/preregistration-v0.7.md.

One command runs everything: python examples/prereg_eval_jackal.py
Writes examples/prereg_results_v07.json and renders docs/prereg-results-v07.md from it.
SYNTHETIC hidden robots and SYNTHETIC forecast error draws; weather is synthetic (C1 to C3) or recorded
(C4, C5). The method and the world share an author and a model structure. Reuses the case weather and
helpers of examples/prereg_eval.py (v0.6).
Options: --render-only (re-render from the JSON), --check (one run on seed 999, not an evaluation seed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from dhill import climatology as clim
from dhill.envelope import EngineConfig, Envelope
from dhill.policies import (
    ambient_threshold,
    envelope_policy,
    midday_ban,
    score_policies,
    slot_starts,
)
from dhill.profiles.loader import load_profile
from dhill.route import truth_env

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
import prereg_eval as v06  # noqa: E402

RESULTS = ROOT / "examples" / "prereg_results_v07.json"
DOC = ROOT / "docs" / "prereg-results-v07.md"
SEEDS = list(range(20))
WORLDS = ("W1", "W2")
DRAWS = 200
RESAMPLES = 2000
BOOT_SEED = 99
BASE = load_profile("clearpath_jackal")
CAPS = {"surface.alpha_clean": 0.95, "power.dcdc_efficiency": 0.98, "motors.drive_efficiency": 0.95}
DRAWN = (*v06.DRAWN, "power.dcdc_efficiency", "motors.drive_efficiency")
PRE_FIX = {
    "coupling.ua_shell_interior_w_k": 4.4,
    "coupling.ua_battery_interior_w_k": 1.2,
    "coupling.ua_compute_interior_w_k": 2.0,
}
CASES = {**v06.CASES, "C5": ("al_ain", "recorded")}
POLICIES = v06.POLICIES


def hidden_robot(seed: int, world: str):
    rng = np.random.default_rng(3000 + seed)
    over = {}
    for k in DRAWN:
        v = BASE.value(k) * float(np.exp(BASE.sigma(k) * rng.standard_normal()))
        over[k] = min(v, CAPS[k]) if k in CAPS else v
    if world == "W2":
        over.update(PRE_FIX)
    return BASE.with_overrides(over), over


def weather(case: str):
    if case == "C5":
        w = clim.fixture_weather(ROOT / "tests" / "data" / "climatology", "al_ain", 2024)
        return w, ("2024-07-08T00:00", "2024-07-08T23:00")
    return v06.weather(case)


def run_one(seed: int, case: str, world: str) -> dict:
    truth, _ = hidden_robot(seed, world)
    w, (t0, t1) = weather(case)
    cfg = EngineConfig(n_mc=64, seed=seed)
    env = Envelope(BASE, w, cfg)
    starts = slot_starts(env, t0, t1)
    pol = {
        "P1": ambient_threshold(env, starts, 1.0, 45.0),
        "P2": ambient_threshold(env, starts, 1.0, 40.0),
        "P3": midday_ban(env, starts),
        "P4": envelope_policy(
            BASE, w, starts, 1.0, "drive", EngineConfig(n_mc=64, seed=seed, sigma_scale=0.0)
        ),
        "P5": envelope_policy(BASE, w, starts, 1.0, "drive", cfg),
    }
    scores = score_policies(truth, w, starts, pol, 1.0, "drive", worlds=DRAWS, seed=4000 + seed)
    out = {
        s.name: {
            "productive_h": s.productive_h,
            "risky_hours": s.risky_hours,
            "violation_prob_mean": s.violation_prob_mean,
            "operated_slots": s.operated_slots,
        }
        for s in scores
    }
    sc = pol["P5"]
    op = np.where(sc > 0)[0]
    covered = pairs = 0
    if op.size:
        pred = env.scan(starts[op], sc[op][:, None], 1.0, "drive")
        j = np.argmin(pred["headroom"][:, 0, :], axis=1)
        q95 = pred["risk_peak_c"][np.arange(op.size), 0, j]
        tenv = truth_env(truth, w, DRAWS, 4000 + seed, cfg.dt_s, 0.0)
        tp = tenv.scan(starts[op], sc[op][:, None], 1.0, "drive")["peaks_c"][
            np.arange(op.size), 0, :, j
        ]
        covered, pairs = int(np.sum(tp <= q95[:, None])), int(tp.size)
    out["coverage"] = {"covered": covered, "pairs": pairs}
    return out


def evaluate(seeds=SEEDS) -> list[dict]:
    runs = []
    for seed in seeds:
        for world in WORLDS:
            for case in CASES:
                runs.append(
                    {"seed": seed, "world": world, "case": case, **run_one(seed, case, world)}
                )
                print(f"seed {seed} {world} {case} done", flush=True)
    return runs


# ---------------------------------------------------------------------- statistics
def _by_seed(runs: list[dict], world: str) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in runs:
        if r["world"] == world:
            out.setdefault(r["seed"], []).append(r)
    return out


def _boot(groups: dict[int, list[dict]], stat) -> tuple[float, tuple[float, float]]:
    """Point estimate and percentile interval of ``stat`` over runs, resampling whole seeds."""
    keys = sorted(groups)
    point = stat([r for k in keys for r in groups[k]])
    rng = np.random.default_rng(BOOT_SEED)
    vals = []
    for _ in range(RESAMPLES):
        pick = rng.choice(keys, size=len(keys), replace=True)
        vals.append(stat([r for k in pick for r in groups[k]]))
    return float(point), (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def share(pred):
    return lambda rs: sum(bool(pred(r)) for r in rs) / len(rs)


def mean(f):
    return lambda rs: float(np.mean([f(r) for r in rs]))


def coverage(rs):
    p = sum(r["coverage"]["pairs"] for r in rs)
    return sum(r["coverage"]["covered"] for r in rs) / p if p else float("nan")


def analyse(runs: list[dict]) -> dict:
    w1, w2 = _by_seed(runs, "W1"), _by_seed(runs, "W2")
    n1, n2 = sum(map(len, w1.values())), sum(map(len, w2.values()))
    h = {}
    v, ci = _boot(w1, share(lambda r: r["P5"]["risky_hours"] == 0))
    h["H1"] = {"value": v, "ci": ci, "n": n1, "hit": v >= 0.90}
    v, ci = _boot(w1, share(lambda r: r["P1"]["risky_hours"] >= 1))
    h["H2"] = {"value": v, "ci": ci, "n": n1, "hit": v >= 0.50}
    v, ci = _boot(w1, share(lambda r: r["P4"]["risky_hours"] >= 1))
    h["H3"] = {"value": v, "ci": ci, "n": n1, "hit": v >= 0.30}
    v, ci = _boot(w1, mean(lambda r: r["P5"]["productive_h"] - r["P2"]["productive_h"]))
    h["H4"] = {"value": v, "ci": ci, "n": n1, "hit": v < 0 and ci[1] < 0}
    v, ci = _boot(w1, coverage)
    h["H5"] = {"value": v, "ci": ci, "n": n1, "hit": 0.90 <= v <= 0.995}
    v, ci = _boot(w2, share(lambda r: r["P5"]["risky_hours"] >= 1))
    h["H6"] = {"value": v, "ci": ci, "n": n2, "hit": v >= 0.50}
    v, ci = _boot(
        w2, mean(lambda r: r["P1"]["violation_prob_mean"] - r["P5"]["violation_prob_mean"])
    )
    h["H7"] = {"value": v, "ci": ci, "n": n2, "hit": v > 0 and ci[0] > 0}
    summary = {}
    for world in WORLDS:
        sel = [r for r in runs if r["world"] == world]
        summary[world] = {
            p: {
                "productive_h_mean": float(np.mean([r[p]["productive_h"] for r in sel])),
                "runs_with_risky": int(sum(r[p]["risky_hours"] > 0 for r in sel)),
                "violation_prob_mean": float(np.mean([r[p]["violation_prob_mean"] for r in sel])),
            }
            for p in POLICIES
        }
    per_case = {
        f"{world} {case}": {
            p: {
                "productive_h_mean": float(
                    np.mean(
                        [
                            r[p]["productive_h"]
                            for r in runs
                            if r["world"] == world and r["case"] == case
                        ]
                    )
                ),
                "runs_with_risky": int(
                    sum(
                        r[p]["risky_hours"] > 0
                        for r in runs
                        if r["world"] == world and r["case"] == case
                    )
                ),
            }
            for p in POLICIES
        }
        for world in WORLDS
        for case in CASES
    }
    return {"hypotheses": h, "summary": summary, "per_case": per_case}


# ---------------------------------------------------------------------- rendering
PRED = {
    "H1": "W1: P5 zero risky hours in at least 90 % of runs",
    "H2": "W1: P1 (45 degC rule) at least one risky hour in at least 50 % of runs",
    "H3": "W1: P4 (no uncertainty) at least one risky hour in at least 30 % of runs",
    "H4": "W1: mean (P5 minus P2) productive hours below 0, interval below 0 (envelope loses)",
    "H5": "W1: coverage of the 95 % risk quantile between 0.90 and 0.995",
    "H6": "W2: P5 at least one risky hour in at least 50 % of runs (envelope loses)",
    "H7": "W2: mean (P1 minus P5) violation probability above 0, interval above 0",
}


def _fmt(hid: str, x: float) -> str:
    if hid in ("H4",):
        return f"{x:+.2f} h"
    if hid == "H5":
        return f"{x:.4f}"
    if hid == "H7":
        return f"{100 * x:+.1f} points"
    return v06.pct(x)


def render(res: dict) -> str:
    h = res["hypotheses"]
    mark = {True: "HIT", False: "MISS"}
    L = [
        "# Preregistered evaluation v0.7 (Jackal): results",
        "",
        "Rendered by `examples/prereg_eval_jackal.py` from `examples/prereg_results_v07.json`; do not edit by hand.",
        "`tests/test_prereg_v07.py` fails if a number here differs from the JSON. Design, predictions and failure",
        "criteria were fixed in `docs/preregistration-v0.7.md` and committed before the script existed.",
        "",
        "**SYNTHETIC world.** Hidden robots and forecast error draws are synthetic, built by the same author as",
        "the method, with the same model structure. Weather is synthetic in C1 to C3 and recorded (Open-Meteo",
        "archive and CAMS PM10, July 2024) in C4 (Abu Dhabi) and C5 (Al Ain). The profile is L0.",
        "",
        f"Runs: {h['H1']['n']} in W1 (planner's prior) and {h['H6']['n']} in W2 (three conductances at their",
        "values before the fix). Intervals: 95 % percentile bootstrap over seeds.",
        "",
        "## Predictions against results",
        "",
        "| ID | Prediction | Result | 95 % interval | Verdict |",
        "|---|---|---|---|---|",
    ]
    for hid, v in h.items():
        L.append(
            f"| {hid} | {PRED[hid]} | {_fmt(hid, v['value'])} | {_fmt(hid, v['ci'][0])} to "
            f"{_fmt(hid, v['ci'][1])} | {mark[v['hit']]} |"
        )
    hits = sum(bool(v["hit"]) for v in h.values())
    L += ["", f"{hits} of {len(h)} predictions hit.", ""]
    for world in WORLDS:
        L += [
            f"## Policy summary, {world}",
            "",
            "| Policy | Mean productive h | Runs with a risky hour | Mean P(violation), operated slots |",
            "|---|---:|---:|---:|",
        ]
        for p, v in res["summary"][world].items():
            L.append(
                f"| {p} {v06.NAMES[p]} | {v['productive_h_mean']:.2f} | {v['runs_with_risky']} | "
                f"{v06.pct(v['violation_prob_mean'])} |"
            )
        L.append("")
    L += [
        "## Per world and case (20 seeds each): mean productive hours / runs with a risky hour",
        "",
        "| World and case | " + " | ".join(POLICIES) + " |",
        "|---|" + "---|" * len(POLICIES),
    ]
    for key, v in res["per_case"].items():
        world, case = key.split()
        site, scen = CASES[case]
        L.append(
            f"| {world} {case} {site} {scen} | "
            + " | ".join(
                f"{v[p]['productive_h_mean']:.1f} / {v[p]['runs_with_risky']}" for p in POLICIES
            )
            + " |"
        )
    return "\n".join(L) + "\n"


READING = ""


def main() -> int:
    if "--check" in sys.argv:
        r = run_one(999, "C1", "W1")
        print({k: v for k, v in r.items()})
        return 0
    if "--render-only" in sys.argv:
        res = json.loads(RESULTS.read_text(encoding="utf-8"))
    else:
        runs = evaluate()
        res = {"design": "docs/preregistration-v0.7.md", **analyse(runs), "raw": runs}
        RESULTS.write_text(json.dumps(res, indent=1), encoding="utf-8")
        res = json.loads(RESULTS.read_text(encoding="utf-8"))
    DOC.write_text(render(res) + READING, encoding="utf-8")
    print(DOC.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
