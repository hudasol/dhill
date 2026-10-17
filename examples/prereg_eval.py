"""Preregistered evaluation, run exactly as fixed in docs/preregistration-v0.6.md.

One command runs everything: python examples/prereg_eval.py
Writes examples/prereg_results.json and renders docs/prereg-results.md from it.
SYNTHETIC hidden robots and SYNTHETIC forecast error draws; weather is synthetic (C1 to C3) or
recorded (C4). The method and the world share an author and a model structure.
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
from dhill.route import PlanningProblem, compare, truth_env
from dhill.weather import synthetic_weather

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
import route_demo  # noqa: E402

RESULTS = ROOT / "examples" / "prereg_results.json"
DOC = ROOT / "docs" / "prereg-results.md"
SEEDS = list(range(20))
WORLDS = 200
DRAWN = (
    "surface.alpha_clean",
    "coupling.ua_shell_interior_w_k",
    "shell.heat_capacity_j_k",
    "interior.heat_capacity_j_k",
    "battery.cell_resistance_25c_ohm",
    "compute.die_rise_k_per_w",
    "coupling.ua_compute_interior_w_k",
    "coupling.ua_battery_interior_w_k",
    "environment.ground_rise_k_per_kw_m2",
)
CASES = {
    "C1": ("abu_dhabi", "summer_clear"),
    "C2": ("sweihan", "heatwave"),
    "C3": ("dubai", "humid_coastal"),
    "C4": ("abu_dhabi", "recorded"),
}
POLICIES = ("P1", "P2", "P3", "P4", "P5")
BASE = load_profile("ugv_medium_inspection")


def hidden_robot(seed: int):
    rng = np.random.default_rng(1000 + seed)
    over = {}
    for k in DRAWN:
        v = BASE.value(k) * float(np.exp(BASE.sigma(k) * rng.standard_normal()))
        over[k] = min(v, 0.95) if k == "surface.alpha_clean" else v
    return BASE.with_overrides(over), over


def weather(case: str):
    site, scen = CASES[case]
    if scen == "recorded":
        return clim.fixture_weather(ROOT / "tests" / "data" / "climatology", site, 2024), (
            "2024-07-03T00:00",
            "2024-07-03T23:00",
        )
    return synthetic_weather(site, scen, days=3), ("2026-08-06T00:00", "2026-08-06T23:00")


def run_policies(seed: int, case: str) -> dict:
    truth, _ = hidden_robot(seed)
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
    scores = score_policies(truth, w, starts, pol, 1.0, "drive", worlds=WORLDS, seed=2000 + seed)
    out = {
        s.name: {
            "productive_h": s.productive_h,
            "risky_hours": s.risky_hours,
            "violation_prob_mean": s.violation_prob_mean,
            "operated_slots": s.operated_slots,
        }
        for s in scores
    }
    # coverage of the engine's 95 % risk quantile for the binding component (P5)
    sc = pol["P5"]
    op = np.where(sc > 0)[0]
    covered = total = 0
    if op.size:
        pred = env.scan(starts[op], sc[op][:, None], 1.0, "drive")
        j = np.argmin(pred["headroom"][:, 0, :], axis=1)
        q95 = pred["risk_peak_c"][np.arange(op.size), 0, j]
        tenv = truth_env(truth, w, WORLDS, 2000 + seed, cfg.dt_s, 0.0)
        true_pk = tenv.scan(starts[op], sc[op][:, None], 1.0, "drive")["peaks_c"]
        tp = true_pk[np.arange(op.size), 0, :, j]  # (S, worlds)
        covered = int(np.sum(tp <= q95[:, None]))
        total = int(tp.size)
    out["coverage"] = {"covered": covered, "pairs": total}
    return out


def run_route(seed: int) -> dict:
    truth, _ = hidden_robot(seed)
    rows = []
    for site, days in route_demo.CASES.items():
        w = route_demo.recorded_weather(site)
        for day in days:
            for h in route_demo.REQUEST_LOCAL_H:
                t = np.datetime64(f"{day}T00:00") + np.timedelta64(h - 4, "h")
                pp = PlanningProblem(
                    BASE,
                    w,
                    route_demo.GRAPH,
                    "depot",
                    route_demo.CHECKPOINTS,
                    str(t),
                    deadline_min=route_demo.DEADLINE_MIN,
                )
                for s in compare(pp, truth, worlds=100, seed=2000 + seed):
                    rows.append({"site": site, "day": day, "local_h": h, **s.__dict__})
    return {"requests": rows}


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(c - h), float(c + h))


def boot_mean(
    per_seed: dict[int, list[float]], n: int = 2000, seed: int = 99
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    keys = sorted(per_seed)
    means = []
    for _ in range(n):
        pick = rng.choice(keys, size=len(keys), replace=True)
        vals = [v for k in pick for v in per_seed[k]]
        means.append(np.mean(vals))
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def evaluate() -> dict:
    runs = []
    for seed in SEEDS:
        for case in CASES:
            r = run_policies(seed, case)
            runs.append({"seed": seed, "case": case, **r})
            print(f"seed {seed} {case} done", flush=True)
    route = []
    for seed in SEEDS:
        route.append({"seed": seed, **run_route(seed)})
        print(f"route seed {seed} done", flush=True)
    return {"runs": runs, "route": route}


def analyse(raw: dict) -> dict:
    runs = raw["runs"]
    n = len(runs)
    h = {}
    k1 = sum(r["P5"]["risky_hours"] == 0 for r in runs)
    h["H1"] = {"k": k1, "n": n, "share": k1 / n, "ci": wilson(k1, n), "hit": k1 / n >= 0.90}
    k2 = sum(r["P4"]["risky_hours"] >= 1 for r in runs)
    h["H2"] = {"k": k2, "n": n, "share": k2 / n, "ci": wilson(k2, n), "hit": k2 / n >= 0.50}
    k3 = sum(r["P1"]["risky_hours"] >= 1 for r in runs)
    h["H3"] = {"k": k3, "n": n, "share": k3 / n, "ci": wilson(k3, n), "hit": k3 / n >= 0.50}
    per_seed: dict[int, list[float]] = {}
    for r in runs:
        per_seed.setdefault(r["seed"], []).append(r["P5"]["productive_h"] - r["P2"]["productive_h"])
    diffs = [v for vs in per_seed.values() for v in vs]
    ci = boot_mean(per_seed)
    h["H4"] = {
        "mean": float(np.mean(diffs)),
        "ci": ci,
        "hit": float(np.mean(diffs)) > 0 and ci[0] > 0,
    }
    cov = sum(r["coverage"]["covered"] for r in runs)
    pairs = sum(r["coverage"]["pairs"] for r in runs)
    c = cov / pairs if pairs else float("nan")
    h["H5"] = {
        "covered": cov,
        "pairs": pairs,
        "coverage": c,
        "ci": wilson(cov, pairs),
        "hit": 0.90 <= c <= 0.995,
    }
    reqs = [q for s in raw["route"] for q in s["requests"]]
    pol = {}
    for name in dict.fromkeys(q["policy"] for q in reqs):
        sel = [q for q in reqs if q["policy"] == name]
        planned = [q for q in sel if q["planned"]]
        pol[name] = {
            "requests": len(sel),
            "planned": len(planned),
            "p_violation_mean": float(np.mean([q["p_violation"] for q in planned]))
            if planned
            else 0.0,
            "completion_mean": float(np.mean([q["completion_rate"] for q in sel])),
            "finish_mean": float(np.mean([q["finish_min"] for q in planned]))
            if planned
            else float("nan"),
        }
    e, s_ = pol["envelope"], pol["shortest"]
    h["H6"] = {
        "policies": pol,
        "hit": e["p_violation_mean"] <= s_["p_violation_mean"]
        and e["completion_mean"] >= s_["completion_mean"]
        and e["finish_mean"] > s_["finish_mean"],
    }
    summary = {}
    for p in POLICIES:
        summary[p] = {
            "productive_h_mean": float(np.mean([r[p]["productive_h"] for r in runs])),
            "risky_hours_mean": float(np.mean([r[p]["risky_hours"] for r in runs])),
            "runs_with_risky": int(sum(r[p]["risky_hours"] > 0 for r in runs)),
            "violation_prob_mean": float(np.mean([r[p]["violation_prob_mean"] for r in runs])),
        }
    per_case = {}
    for case in CASES:
        sel = [r for r in runs if r["case"] == case]
        per_case[case] = {
            p: {
                "productive_h_mean": float(np.mean([r[p]["productive_h"] for r in sel])),
                "runs_with_risky": int(sum(r[p]["risky_hours"] > 0 for r in sel)),
            }
            for p in POLICIES
        }
    return {"hypotheses": h, "summary": summary, "per_case": per_case}


NAMES = {
    "P1": "Air at or below 45 degC",
    "P2": "Air at or below 40 degC",
    "P3": "Midday ban 12:30 to 15:00",
    "P4": "Envelope, no uncertainty",
    "P5": "Envelope L0",
}


def pct(x: float, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f} %"


def ci_pct(ci) -> str:
    return f"{pct(ci[0])} to {pct(ci[1])}"


def render(res: dict) -> str:
    h = res["hypotheses"]
    mark = {True: "HIT", False: "MISS"}
    L = [
        "# Preregistered evaluation v0.6: results",
        "",
        "Rendered by `examples/prereg_eval.py` from `examples/prereg_results.json`. Do not edit by hand;",
        "`tests/test_prereg.py` fails if a number here differs from the JSON. The design, predictions and",
        "failure criteria were fixed in `docs/preregistration-v0.6.md` and committed before the first run.",
        "",
        "**SYNTHETIC world.** Hidden robots and forecast error draws are synthetic and were built by the",
        "same author as the method, with the same model structure. Weather is synthetic in C1 to C3 and",
        "recorded (Open-Meteo archive and CAMS PM10, Abu Dhabi, July 2024) in C4; H6 uses the recorded",
        "Abu Dhabi and Al Ain July 2024 days of `examples/route_demo.py`. The profile is L0.",
        "",
        f"Runs: {h['H1']['n']} (20 seeds x 4 cases) for H1 to H5; "
        f"{h['H6']['policies']['shortest']['requests']} route requests for H6.",
        "",
        "## Predictions against results",
        "",
        "| ID | Prediction | Result | 95 % interval | Verdict |",
        "|---|---|---|---|---|",
        f"| H1 | P5 zero risky hours in at least 90 % of runs | {h['H1']['k']} of {h['H1']['n']} runs ({pct(h['H1']['share'])}) | {ci_pct(h['H1']['ci'])} | {mark[h['H1']['hit']]} |",
        f"| H2 | P4 at least one risky hour in at least 50 % of runs | {h['H2']['k']} of {h['H2']['n']} ({pct(h['H2']['share'])}) | {ci_pct(h['H2']['ci'])} | {mark[h['H2']['hit']]} |",
        f"| H3 | P1 at least one risky hour in at least 50 % of runs | {h['H3']['k']} of {h['H3']['n']} ({pct(h['H3']['share'])}) | {ci_pct(h['H3']['ci'])} | {mark[h['H3']['hit']]} |",
        f"| H4 | Mean (P5 minus P2) productive hours above 0, interval excludes 0 | {h['H4']['mean']:+.2f} h | {h['H4']['ci'][0]:+.2f} to {h['H4']['ci'][1]:+.2f} h | {mark[h['H4']['hit']]} |",
        f"| H5 | Coverage of the 95 % risk quantile between 0.90 and 0.995 | {h['H5']['coverage']:.4f} ({h['H5']['covered']} of {h['H5']['pairs']} pairs) | {h['H5']['ci'][0]:.4f} to {h['H5']['ci'][1]:.4f} | {mark[h['H5']['hit']]} |",
    ]
    r6 = h["H6"]["policies"]
    e, s = r6["envelope"], r6["shortest"]
    L.append(
        f"| H6 | Envelope routing: P(violation) at or below shortest, completion at or above, finish later | "
        f"P(viol) {pct(e['p_violation_mean'])} vs {pct(s['p_violation_mean'])}; completion "
        f"{pct(e['completion_mean'])} vs {pct(s['completion_mean'])}; finish {e['finish_mean']:.1f} vs {s['finish_mean']:.1f} min | "
        f"not computed | {mark[h['H6']['hit']]} |"
    )
    hits = sum(bool(v["hit"]) for v in h.values())
    L += [
        "",
        f"{hits} of {len(h)} predictions hit.",
        "",
        "## Policy summary over all 80 runs",
        "",
        "| Policy | Mean productive h | Runs with a risky hour | Mean risky hours | Mean P(violation), operated slots |",
        "|---|---:|---:|---:|---:|",
    ]
    for p, v in res["summary"].items():
        L.append(
            f"| {p} {NAMES[p]} | {v['productive_h_mean']:.2f} | {v['runs_with_risky']} | "
            f"{v['risky_hours_mean']:.2f} | {pct(v['violation_prob_mean'])} |"
        )
    L += [
        "",
        "## Per case (20 seeds each): mean productive hours / runs with a risky hour",
        "",
        "| Case | " + " | ".join(POLICIES) + " |",
        "|---|" + "---|" * len(POLICIES),
    ]
    for case, v in res["per_case"].items():
        site, scen = CASES[case]
        L.append(
            f"| {case} {site} {scen} | "
            + " | ".join(
                f"{v[p]['productive_h_mean']:.1f} / {v[p]['runs_with_risky']}" for p in POLICIES
            )
            + " |"
        )
    L += [
        "",
        "## Route requests (H6), all seeds",
        "",
        "| Policy | Requests | Planned | Mean P(violation), planned | Mean completion | Mean finish, planned (min) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, v in r6.items():
        L.append(
            f"| {name} | {v['requests']} | {v['planned']} | {pct(v['p_violation_mean'])} | "
            f"{pct(v['completion_mean'])} | {v['finish_mean']:.1f} |"
        )
    return "\n".join(L) + "\n"


def main() -> int:
    if "--render-only" in sys.argv:
        res = json.loads(RESULTS.read_text(encoding="utf-8"))
    else:
        raw = evaluate()
        res = {"design": "docs/preregistration-v0.6.md", **analyse(raw), "raw": raw}
        RESULTS.write_text(json.dumps(res, indent=1), encoding="utf-8")
    DOC.write_text(render(res) + READING, encoding="utf-8")
    print(DOC.read_text(encoding="utf-8"))
    return 0


READING = """
## Reading

Written after the run. It interprets the tables above and changes none of them.

- **H1 hit.** The uncertainty aware envelope had no risky hour in any run, including runs where the
  hidden robot was hotter than the profile and the forecast error was heavier than the engine assumes.
  This is the central claim of the method and it held in this synthetic world.
- **H2 and H3 missed.** The predictions that the no uncertainty envelope and the 45 degC rule would
  be unsafe in at least half of the runs were too pessimistic. Hidden robots drawn from the profile's
  own prior are on average not hotter than the profile, unlike the single hotter robot in
  `docs/policy-comparison.md` that informed these predictions. Simple rules and the nominal model were
  unsafe in a minority of runs, not a majority. The midday ban (P3) was the policy with the most runs
  containing a risky hour.
- **H4 missed, and in the wrong direction.** The conservative 40 degC rule delivered slightly more
  productive hours on average than the envelope, with an interval that excludes zero. The 40 degC rule
  did have risky hours in some runs (mainly the humid coastal and recorded cases), while the envelope had
  none. The envelope's value in this evaluation is safety with stated reasons, not productivity.
- **H5 missed on the high side.** The engine's 95 % risk quantile covered the true peak more often than
  the preregistered upper bound of 0.995. The envelope is more conservative than its label says, which
  is consistent with H4. The interval shown treats (slot, draw) pairs as independent, which they are not;
  it understates the real uncertainty of the coverage estimate.
- **H6 hit, narrowly.** The envelope planner's routes had no violations and the shortest path had very
  few. The hit rests on a very small difference in violation probability bought with roughly double the
  finish time. It confirms the cost of caution more than a safety gain.

## Limitations

- The world is synthetic and shares the engine's model structure and author. Structural model error,
  which real robots will have, is absent; a real test is the instrumented run in `docs/field-test-kit.md`.
- Hidden robots vary nine thermal parameters only; drive efficiency and converter efficiency, which
  `docs/sensitivity.md` ranks highly, were held at nominal.
- One profile (the medium UGV). The Jackal profile was excluded for the reason given in the
  preregistration; its behaviour is reported in `docs/operating-calendar.md` and `docs/route-simulation.md`.
- Before the full run, seed 0 of cases C1 and C4 was executed once to check that the script ran. Nothing
  in the design or code was changed after that check.
"""

if __name__ == "__main__":
    raise SystemExit(main())
