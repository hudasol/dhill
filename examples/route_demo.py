"""Patrol route simulation: shortest path, air temperature rule and envelope aware planning.

Plans are made from the forecast and the Jackal profile; they are executed by a hidden, hotter
robot over 100 weather realisations with forecast error heavier than the engine assumes.
Cases: four synthetic scenarios and four real reanalysis days (Abu Dhabi 2024, recorded
Open-Meteo response in tests/data). The graph is illustrative. This is a kinematic and thermal
simulation in Python, not Gazebo and not a physical test.

Usage: python examples/route_demo.py [--out-csv examples/route_results.csv] [--fig docs/img/route_simulation.png]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from dhill import route as R
from dhill.calibrate import calibrate, synthetic_telemetry
from dhill.envelope import EngineConfig, Envelope
from dhill.profiles.loader import load_builtin
from dhill.weather import synthetic_weather
from dhill.weather.base import Weather

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "data" / "openmeteo_archive_abu_dhabi_2024.json"
START_HOURS_UTC = (2, 4, 6, 8, 10, 12, 14)  # 06:00 to 18:00 local
WORLDS = 100
CFG = EngineConfig(n_mc=48, dt_s=120.0, parked_shade=0.9)

BASE = load_builtin("clearpath_jackal")
TRUTH = BASE.with_overrides(
    {
        "surface.alpha_clean": 0.57,
        "coupling.ua_shell_interior_w_k": 9.0,
        "shell.heat_capacity_j_k": 6500.0,
    }
)
GRAPH = R.patrol_graph()
MISSION = R.Mission()

SYNTHETIC = [
    ("abu_dhabi", "summer_clear"),
    ("dubai", "humid_coastal"),
    ("sweihan", "heatwave"),
    ("al_ain", "winter_mild"),
]


def real_days() -> list[tuple[str, Weather, str]]:
    """Four real reanalysis days at Abu Dhabi: a median and a hot day from shoulder months."""
    raw = json.loads(FIXTURE.read_text())["hourly"]
    t = np.array(raw["time"], dtype="datetime64[s]")
    arr = {k: np.array(v, dtype=float) for k, v in raw.items() if k != "time"}
    n = t.size
    w_all = Weather(
        times_utc=t,
        t_air_c=arr["temperature_2m"],
        dew_c=arr["dew_point_2m"],
        wind10_ms=arr["wind_speed_10m"],
        pm10_ugm3=np.full(n, 80.0),
        precip_mm_h=arr["precipitation"],
        lat=24.45,
        lon=54.38,
        altitude_m=10.0,
        ghi_wm2=arr["shortwave_radiation"],
        source="open-meteo-archive",
        label="abu_dhabi",
    )
    out = []
    hours = t.astype("datetime64[h]").astype(int) % 24
    starts = np.where(hours == 0)[0]
    starts = starts[(starts >= 3) & (starts + 33 < n)]
    months = t[starts].astype("datetime64[M]").astype(int) % 12 + 1
    for month, q, label in (
        (4, 0.5, "median April day"),
        (5, 0.9, "hot May day"),
        (9, 0.9, "hot September day"),
        (10, 0.5, "median October day"),
    ):
        cand = starts[months == month]
        dmax = np.array([w_all.t_air_c[i : i + 24].max() for i in cand])
        i = int(cand[np.argsort(dmax, kind="stable")[int(round(q * (cand.size - 1)))]])
        sl = slice(i - 3, i + 33)
        w = Weather(
            times_utc=t[sl],
            t_air_c=w_all.t_air_c[sl],
            dew_c=w_all.dew_c[sl],
            wind10_ms=w_all.wind10_ms[sl],
            pm10_ugm3=w_all.pm10_ugm3[sl],
            precip_mm_h=w_all.precip_mm_h[sl],
            lat=24.45,
            lon=54.38,
            altitude_m=10.0,
            ghi_wm2=w_all.ghi_wm2[sl],
            source="open-meteo-archive",
            label="abu_dhabi",
        )
        day = str(t[i].astype("datetime64[D]"))
        out.append((f"abu_dhabi {day} real, {label}", w, day))
    return out


def calibrated_profile():
    """Fit the Jackal profile on synthetic telemetry from the hidden robot (inverse crime applies)."""
    w = synthetic_weather("abu_dhabi", "summer_clear", start="2026-08-05T00:00", days=3)
    tel = synthetic_telemetry(TRUTH, w, "2026-08-05T01:00", hours=18, seed=3)
    cal, _ = calibrate(BASE, w, tel)
    return cal


def run_case(args):
    name, weather, day0 = args
    cal = calibrated_profile()
    truth = R.truth_env(TRUTH, weather, WORLDS, CFG)
    env0 = Envelope(BASE, weather, CFG)
    rows = []
    for h in START_HOURS_UTC:
        first = (
            weather.times_utc[0].astype("datetime64[D]") if day0 is None else np.datetime64(day0)
        )
        t0 = np.datetime64(str(first) + f"T{h:02d}:00", "s")
        idx = env0._idx(t0)
        air = float(env0.forcing.t_air_k[idx] - 273.15)
        for s in R.compare_case(
            BASE, TRUTH, weather, idx, GRAPH, MISSION, CFG, WORLDS, cal, truth=truth
        ):
            rows.append(
                dict(
                    case=name,
                    start_utc_h=h,
                    air_c=round(air, 1),
                    policy=s.policy,
                    runs=int(s.runs),
                    completed=round(s.completed, 3),
                    violation_prob=None if not s.runs else round(s.violation_prob, 3),
                    minutes=None if not s.runs else round(s.minutes, 1),
                    reason=s.reason,
                )
            )
    return rows


def cases():
    out = []
    for site, scen in SYNTHETIC:
        w = synthetic_weather(site, scen, start="2026-08-05T00:00", days=2)
        out.append((f"{site} {scen} synthetic", w, None))
    out += real_days()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-csv", default=str(ROOT / "examples" / "route_results.csv"))
    ap.add_argument("--fig", default=str(ROOT / "docs" / "img" / "route_simulation.png"))
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(argv)
    cs = cases()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(run_case, cs))
    rows = [r for rs in results for r in rs]
    with open(a.out_csv, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print_summary(rows)
    try:
        figure(rows, a.fig)
    except ImportError:
        print("matplotlib not installed; figure skipped", file=sys.stderr)
    return 0


POLICIES = ["shortest", "air_rule", "envelope_l0", "envelope_l2"]


def print_summary(rows):
    cases_ = list(dict.fromkeys(r["case"] for r in rows))
    print(
        "Synthetic weather and an illustrative graph. Mean over seven start hours (06:00 to 18:00 local)."
    )
    print(f"{'case':<50}{'policy':<13}{'ran':>5}{'P(complete)':>13}{'violation':>11}{'minutes':>9}")
    for c in cases_:
        for p in POLICIES:
            rs = [r for r in rows if r["case"] == c and r["policy"] == p]
            ran = sum(r["runs"] for r in rs) / len(rs)
            comp = float(np.mean([r["completed"] for r in rs]))
            v = [r["violation_prob"] for r in rs if r["runs"]]
            m = [r["minutes"] for r in rs if r["runs"]]
            print(
                f"{c:<50}{p:<13}{ran:>5.0%}{comp:>13.2f}{(np.mean(v) if v else float('nan')):>11.2f}"
                f"{(np.mean(m) if m else float('nan')):>9.0f}"
            )
    print("\nCases where another policy completed more often than envelope_l0 by at least 0.05:")
    for c in cases_:
        for h in START_HOURS_UTC:
            sub = {r["policy"]: r for r in rows if r["case"] == c and r["start_utc_h"] == h}
            best = max((sub[p]["completed"], p) for p in POLICIES)
            if best[0] >= sub["envelope_l0"]["completed"] + 0.05:
                print(
                    f"  {c}, start {h:02d} UTC: {best[1]} {best[0]:.2f} vs envelope_l0 {sub['envelope_l0']['completed']:.2f}"
                )


def figure(rows, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cases_ = list(dict.fromkeys(r["case"] for r in rows))
    fig, axes = plt.subplots(2, 4, figsize=(15, 6.5), sharey=True)
    colours = {
        "shortest": "#b0b0b0",
        "air_rule": "#e0a03a",
        "envelope_l0": "#c2557a",
        "envelope_l2": "#6b2a4a",
    }
    for ax, c in zip(axes.ravel(), cases_, strict=False):
        for p in POLICIES:
            ys = [
                next(
                    r["completed"]
                    for r in rows
                    if r["case"] == c and r["policy"] == p and r["start_utc_h"] == h
                )
                for h in START_HOURS_UTC
            ]
            ax.plot(
                [h + 4 for h in START_HOURS_UTC], ys, marker="o", ms=3, label=p, color=colours[p]
            )
        ax.set_title(c.replace(" synthetic", " (synthetic)"), fontsize=8)
        ax.set_ylim(-0.05, 1.05)
        ax.set_xlabel("start, local hour", fontsize=8)
    axes[0, 0].set_ylabel("P(mission completed safely)")
    axes[1, 0].set_ylabel("P(mission completed safely)")
    axes[0, 0].legend(fontsize=7)
    fig.suptitle(
        "Route simulation, SYNTHETIC patrol graph, hidden hotter robot, 100 weather draws, Jackal profile at L0",
        fontsize=10,
    )
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)


if __name__ == "__main__":
    raise SystemExit(main())
