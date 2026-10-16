"""Patrol route simulation: shortest path vs air temperature rule vs envelope aware planning.

Weather: recorded Open-Meteo archive hours with recorded CAMS PM10 for Abu Dhabi (1 to 6 July
2024) and Al Ain (6 to 11 July 2024), the trimmed real responses in tests/data/climatology. The weather draws used to
score each plan are SYNTHETIC perturbations of that record (forecast error heavier than the
engine assumes). The "true" robots are SYNTHETIC: hotter versions of the L0 profiles.

This is a kinematic and thermal simulation in Python. It is not Gazebo, not a dynamics
simulator and not a physical test. Run: python examples/route_demo.py [--plot]
Output: examples/route_demo_output.txt, docs/img/route-simulation.png with --plot.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

from dhill import climatology as clim
from dhill.profiles.loader import load_profile
from dhill.route import PlanningProblem, RouteGraph, Segment, Waypoint, compare

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data" / "climatology"
OUT = ROOT / "examples" / "route_demo_output.txt"
BEFORE_OUT = ROOT / "examples" / "before-fix" / "route_demo_output.txt"
DOC = ROOT / "docs" / "route-simulation.md"
START, END = "<!-- route-results:start -->", "<!-- route-results:end -->"
IMG = ROOT / "docs" / "img" / "route-simulation.png"
SEED = 123
WORLDS = 200
DEADLINE_MIN = 360.0
LOCAL_OFFSET_H = 4

# A perimeter patrol at an illustrative solar or industrial site. Lengths and shade fractions
# are assumptions chosen to make a sun route and a longer, partly shaded route; they are not
# a survey of any real site.
GRAPH = RouteGraph(
    waypoints={
        "depot": Waypoint("depot", shade=0.9, note="covered shelter"),
        "gate": Waypoint("gate", shade=0.0),
        "canopy": Waypoint("canopy", shade=0.85, note="shade canopy midway"),
        "north": Waypoint("north", shade=0.0, note="checkpoint"),
        "east": Waypoint("east", shade=0.0, note="checkpoint"),
    },
    segments=[
        Segment("depot", "gate", 300.0, 0.0),
        Segment("gate", "north", 900.0, 0.0),
        Segment("north", "east", 800.0, 0.0),
        Segment("east", "depot", 1000.0, 0.0),
        Segment("depot", "canopy", 600.0, 0.6),
        Segment("canopy", "north", 700.0, 0.6),
        Segment("canopy", "east", 800.0, 0.6),
    ],
)
CHECKPOINTS = ("north", "east")

# Hotter hidden robots (SYNTHETIC). For the medium UGV these are the overrides used in
# docs/policy-comparison.md; the Jackal gets the same relative changes.
TRUTH = {
    "ugv_medium_inspection": {
        "surface.alpha_clean": 0.52,
        "coupling.ua_shell_interior_w_k": 14.0,
        "shell.heat_capacity_j_k": 24000.0,
    },
    "clearpath_jackal": {
        "surface.alpha_clean": 0.45 * 0.52 / 0.40,
        "coupling.ua_shell_interior_w_k": 4.4 * 14.0 / 18.0,
    },
}
# Recorded days: two ordinary July days on the coast and the two hottest days of 2024 inland
# (Al Ain daily maximum 49.0 and 47.7 degC in the archive).
CASES = {"abu_dhabi": ("2024-07-02", "2024-07-04"), "al_ain": ("2024-07-08", "2024-07-09")}
DAYS = CASES["abu_dhabi"]
REQUEST_LOCAL_H = (6, 9, 12, 15, 18)


def recorded_weather(site: str = "abu_dhabi"):
    return clim.fixture_weather(DATA, site, 2024)


def run() -> list[dict]:
    rows = []
    for pid, over in TRUTH.items():
        prof = load_profile(pid)
        truth = prof.with_overrides(over)
        for site, day in [(s, d) for s, days in CASES.items() for d in days]:
            w = recorded_weather(site)
            for h in REQUEST_LOCAL_H:
                t = np.datetime64(f"{day}T00:00") + np.timedelta64(h - LOCAL_OFFSET_H, "h")
                pp = PlanningProblem(
                    prof, w, GRAPH, "depot", CHECKPOINTS, str(t), deadline_min=DEADLINE_MIN
                )
                air = float(pp.air_c()[pp.request_idx])
                for s in compare(pp, truth, worlds=WORLDS, seed=SEED):
                    rows.append(
                        {
                            "profile": pid,
                            "site": site,
                            "day": day,
                            "local_h": h,
                            "air_c": air,
                            **s.__dict__,
                        }
                    )
    return rows


def summary(rows: list[dict]) -> list[str]:
    out = []
    for pid, site in [(p, s) for p in TRUTH for s in CASES]:
        for pol in dict.fromkeys(r["policy"] for r in rows):
            sel = [
                r for r in rows if r["profile"] == pid and r["site"] == site and r["policy"] == pol
            ]
            planned = [r for r in sel if r["planned"]]
            fin = [r["finish_min"] for r in planned]
            out.append(
                f"{pid:<24}{site:<11}{pol:<16}{len(planned):>4}/{len(sel):<4}"
                f"{np.mean(fin) if fin else float('nan'):>10.1f}"
                f"{np.mean([r['completion_rate'] for r in sel]):>12.1%}"
                f"{np.mean([r['p_violation'] for r in planned]) if planned else 0.0:>12.1%}"
                f"{sum(r['p_violation'] > 0.05 for r in planned):>8d}"
            )
    return out


def report(rows: list[dict]) -> str:
    lines = [
        "Route simulation (kinematic and thermal, Python; not Gazebo, not a physical test)",
        "Weather: recorded Open-Meteo archive and CAMS PM10, Abu Dhabi and Al Ain, July 2024.",
        f"Scoring: SYNTHETIC hotter true robots, {WORLDS} SYNTHETIC weather draws, seed {SEED}.",
        f"Deadline {DEADLINE_MIN:g} min from the request. Patrol depot-north-east-depot.",
        "",
        "Per request",
        f"{'profile':<24}{'site':<11}{'day':<12}{'local':>6}{'air C':>7}  {'policy':<16}{'plan':>5}"
        f"{'finish min':>11}{'complete':>10}{'P(viol)':>9}  route / scale / delay / wait",
    ]
    for r in rows:
        lines.append(
            f"{r['profile']:<24}{r['site']:<11}{r['day']:<12}{r['local_h']:>4}:00{r['air_c']:>7.1f}  "
            f"{r['policy']:<16}{'yes' if r['planned'] else 'no':>5}{r['finish_min']:>11.1f}"
            f"{r['completion_rate']:>10.1%}{r['p_violation']:>9.1%}  "
            + (
                f"{r['route']} / {r['scale']:.1f} / {r['delay_min']:g} / {r['wait'] or '-'}"
                if r["planned"]
                else "-"
            )
        )
    lines += [
        "",
        "Summary per profile, site and policy",
        f"{'profile':<24}{'site':<11}{'policy':<16}{'planned':>9}{'mean finish':>10}{'completion':>12}"
        f"{'P(viol)':>12}{'risky':>8}",
        *summary(rows),
        "",
        "completion: share of (request, draw) pairs finished within the deadline with no hard",
        "limit exceeded; requests with no plan count as not completed. P(viol): mean share of",
        "draws exceeding a hard limit over requests that were planned. risky: planned requests",
        "with P(viol) above 5 %. mean finish: over planned requests only.",
    ]
    return "\n".join(lines)


def plot(rows: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pols = list(dict.fromkeys(r["policy"] for r in rows))
    colors = {pols[0]: "#2a78d6", pols[1]: "#eb6834", pols[2]: "#1baf7a"}
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.5), constrained_layout=True)
    fig.patch.set_facecolor("#fcfcfb")
    for ax, pid in zip(axes, TRUTH, strict=True):
        sel = [r for r in rows if r["profile"] == pid]
        labels = list(dict.fromkeys(f"{r['site']} {r['day'][5:]} {r['local_h']:02d}h" for r in sel))
        x = np.arange(len(labels))
        width = 0.26
        for k, pol in enumerate(pols):
            vals = [r["completion_rate"] for r in sel if r["policy"] == pol]
            ax.bar(x + (k - 1) * width, vals, width * 0.92, color=colors[pol], label=pol)
        ax.set_xticks(x, labels, rotation=45, ha="right", fontsize=8, color="#52514e")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("completed without hard limit violation", fontsize=8, color="#52514e")
        ax.set_title(f"{pid} (L0 planner, synthetic true robot)", fontsize=9, loc="left")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].legend(fontsize=8, frameon=False, loc="lower left")
    fig.suptitle(
        "Route simulation, SYNTHETIC true robots and weather draws on recorded July 2024 weather, "
        f"{WORLDS} synthetic weather draws",
        fontsize=10,
    )
    IMG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG, dpi=130, facecolor=fig.get_facecolor())


SUMMARY_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\d+)/(\d+)\s+(\S+)\s+([\d.]+)%\s+([\d.]+)%\s+(\d+)$"
)


def parse_summary(text: str) -> dict[tuple[str, str, str], dict]:
    """Summary block of a route demo output file, keyed by (profile, site, policy)."""
    out = {}
    block = text.split("Summary per profile, site and policy", 1)[1]
    for line in block.splitlines():
        m = SUMMARY_RE.match(line.strip())
        if m:
            pid, site, pol, planned, n, fin, comp, pv, risky = m.groups()
            out[(pid, site, pol)] = {
                "planned": int(planned),
                "n": int(n),
                "finish": float(fin),
                "completion": float(comp),
                "p_viol": float(pv),
                "risky": int(risky),
            }
    return out


def results_markdown(after_text: str, before_text: str) -> str:
    after, before = parse_summary(after_text), parse_summary(before_text)

    def fin(v: dict) -> str:
        return "n/a" if v["planned"] == 0 else f"{v['finish']:.1f}"

    lines = [
        "SYNTHETIC true robots and weather draws on recorded weather; generated by",
        "`python examples/route_demo.py --doc` from `examples/route_demo_output.txt`.",
        "",
        "| Profile | Site | Policy | Planned | Mean finish (min) | Completion | Mean P(violation) | Risky requests |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for (pid, site, pol), v in after.items():
        lines.append(
            f"| {pid} | {site} | {pol} | {v['planned']}/{v['n']} | {fin(v)} | "
            f"{v['completion']:.1f} % | {v['p_viol']:.1f} % | {v['risky']} |"
        )
    lines += [
        "",
        "Before and after the Jackal profile fix (before: `examples/before-fix/route_demo_output.txt`).",
        "The medium UGV rows are a control: its profile did not change.",
        "",
        "| Profile | Site | Policy | Completion before | Completion after | Mean finish before | Mean finish after |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for key, v in after.items():
        b = before.get(key)
        if b is None:
            continue
        lines.append(
            f"| {key[0]} | {key[1]} | {key[2]} | {b['completion']:.1f} % | {v['completion']:.1f} % | "
            f"{fin(b)} | {fin(v)} |"
        )
    return "\n".join(lines)


def update_doc() -> None:
    text = DOC.read_text(encoding="utf-8")
    a, b = text.index(START) + len(START), text.index(END)
    block = results_markdown(
        OUT.read_text(encoding="utf-8"), BEFORE_OUT.read_text(encoding="utf-8")
    )
    DOC.write_text(text[:a] + "\n" + block + "\n" + text[b:], encoding="utf-8")


if __name__ == "__main__":
    if "--doc-only" in sys.argv:
        update_doc()
        raise SystemExit(0)
    rows = run()
    text = report(rows)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(text)
    if "--plot" in sys.argv:
        plot(rows)
    if "--doc" in sys.argv:
        update_doc()
