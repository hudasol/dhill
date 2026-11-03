"""Experiment E5 of docs/preregistration-v0.8.md: obstacle shade from solar position.

SYNTHETIC and L0: the street canyons are idealised (infinite parallel walls of equal height, the robot on
the centre line of the street), the robot is the L0 Jackal profile, and the weather is the three six day
July reanalysis windows in `tests/data/climatology`. Nothing here describes a real street or a real robot.

The beam shade at the robot comes from solar position (`pvlib`) and the obstruction angle of the canyon.
The solver's shade input is the share of global irradiance blocked, so the blocked beam is converted to a
share of global irradiance with the Erbs decomposition. The fixed shade of 0.6 used on the canopy segments
of `examples/route_demo.py` is shown beside the geometric result.

  python examples/route_solar_shade.py --out OUT.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

from dhill import climatology as clim
from dhill.envelope import EngineConfig, Envelope
from dhill.policies import slot_starts
from dhill.profiles.loader import load_builtin
from dhill.structural import LOCAL_OFFSET_H, window_weather

ROOT = Path(__file__).resolve().parents[1]
RECORDS = (("abu_dhabi", 2021), ("abu_dhabi", 2024), ("al_ain", 2024))
RATIOS = (0.0, 0.2, 0.5, 1.0, 2.0)
ORIENTATIONS = {"north_south": 0.0, "east_west": 90.0}
FIXED_SHADE = 0.6
WINDOWS = {"morning": (6, 10), "midday": (10, 15), "afternoon": (15, 19)}
PROFILE = "clearpath_jackal"
SAMPLES = 12  # sun positions per one hour mission


def canyon_beam_blocked(
    azimuth_deg: np.ndarray, elevation_deg: np.ndarray, ratio: float, axis_deg: float
) -> np.ndarray:
    """1 where the canyon walls hide the sun from the centre of the street, else 0.

    Walls of height H stand at W / 2 on each side of the axis. Towards a direction at angle D from the
    axis the nearest wall is at (W / 2) / |sin D|, so the obstruction elevation satisfies
    tan(e) = 2 (H / W) |sin D|.
    """
    d = np.radians(azimuth_deg - axis_deg)
    obstruction = np.degrees(np.arctan(2.0 * ratio * np.abs(np.sin(d))))
    return ((elevation_deg > 0) & (elevation_deg < obstruction)).astype(float)


def shade_fraction(w, start_idx_times: np.ndarray, ratio: float, axis_deg: float) -> np.ndarray:
    """Share of global irradiance blocked over each hour starting at ``start_idx_times`` (UTC)."""
    out = np.zeros(start_idx_times.size)
    if ratio <= 0:
        return out
    t_rec = (w.times_utc - w.times_utc[0]).astype("timedelta64[s]").astype(float)
    for i, t0 in enumerate(start_idx_times):
        times = t0 + (np.arange(SAMPLES) * 3600.0 / SAMPLES).astype("timedelta64[s]")
        idx = pd.DatetimeIndex(times.astype("datetime64[ns]"))
        sp = pvlib.solarposition.get_solarposition(idx, w.lat, w.lon, w.altitude_m)
        secs = (times - w.times_utc[0]).astype("timedelta64[s]").astype(float)
        ghi = np.interp(secs, t_rec, w.ghi_wm2)
        zen = sp["apparent_zenith"].to_numpy()
        er = pvlib.irradiance.erbs(ghi, zen, idx)
        dni = np.nan_to_num(er["dni"].to_numpy())
        horiz_beam = dni * np.cos(np.radians(zen)).clip(min=0.0)
        blocked = canyon_beam_blocked(
            sp["azimuth"].to_numpy(), sp["apparent_elevation"].to_numpy(), ratio, axis_deg
        )
        tot = ghi.sum()
        out[i] = float((horiz_beam * blocked).sum() / tot) if tot > 1.0 else 0.0
    return out


def run(out_path: str) -> dict:
    prof = load_builtin(PROFILE)
    cfg = EngineConfig(n_mc=64, seed=7)
    configs: dict[str, tuple[float, float] | None] = {"none": None, "fixed_0.6": None}
    for o, ax in ORIENTATIONS.items():
        for r in RATIOS[1:]:
            configs[f"{o}_{r:g}"] = (r, ax)
    acc = {k: {w: [] for w in WINDOWS} for k in configs}
    mean_shade = {k: [] for k in configs}
    n_days = 0
    for site, year in RECORDS:
        rec = clim.load_site_record(site, (year,), offline=True, cache_root=ROOT / "tests" / "data")
        for i, d in enumerate(np.unique(rec.times_utc.astype("datetime64[D]"))):
            day = str(d)
            w = window_weather(rec, day)
            env = Envelope(prof, w, cfg)
            first_local = 7 if i == 0 else 6
            starts = slot_starts(
                env,
                f"{day}T{first_local - LOCAL_OFFSET_H:02d}:00",
                f"{day}T{18 - LOCAL_OFFSET_H:02d}:00",
            )
            t_start = np.array(
                [w.times_utc[0] + np.timedelta64(int(s * cfg.dt_s), "s") for s in starts]
            )
            local = (
                (t_start - t_start.astype("datetime64[D]")).astype("timedelta64[s]").astype(float)
                / 3600.0
            ) + LOCAL_OFFSET_H
            for name, spec in configs.items():
                if name == "none":
                    sh = np.zeros(starts.size)
                elif name == "fixed_0.6":
                    sh = np.full(starts.size, FIXED_SHADE)
                else:
                    sh = shade_fraction(w, t_start, spec[0], spec[1])
                scale, _ = env.best_scale(starts, 1.0, "drive", shade=sh[:, None])
                go = scale >= 0.999
                for wn, (a, b) in WINDOWS.items():
                    sel = (local >= a) & (local < b)
                    acc[name][wn].append(float(go[sel].sum()))
                mean_shade[name].append(float(sh[(local >= 10) & (local < 15)].mean()))
            n_days += 1
            print(f"day {n_days} {site} {day}", flush=True)
    base = {wn: np.array(acc["none"][wn]) for wn in WINDOWS}
    rows = []
    for name in configs:
        row = {"config": name, "mean_midday_shade": float(np.mean(mean_shade[name]))}
        for wn in WINDOWS:
            arr = np.array(acc[name][wn])
            row[f"go_hours_per_day_{wn}"] = float(arr.mean())
            row[f"gain_{wn}"] = float((arr - base[wn]).mean())
            row[f"max_day_gain_{wn}"] = float((arr - base[wn]).max())
        rows.append(row)
    out = {
        "profile": PROFILE,
        "evidence_level": prof.evidence_level,
        "days": n_days,
        "ratios": list(RATIOS),
        "windows_local_hours": WINDOWS,
        "rows": rows,
    }
    Path(out_path).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
