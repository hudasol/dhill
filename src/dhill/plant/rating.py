"""Datasheet consistency filter for plant robots.

A reference robot is rated by its maker to a stated ambient air temperature. A plausible plant robot must
survive that rating: sustained heavy use for two hours at the rated ambient, in shade, without any hard
limit being exceeded. Draws that fail are rejected, the same way a maker would reject a design.
"""

from __future__ import annotations

import numpy as np

from .model import (
    AIR,
    BCORE,
    DIE,
    LIDAR,
    MOTOR,
    PlantParams,
    PlantState,
    draw_plants,
    simulate_plant,
)
from .scenario import PlantWeather, build_forcing, build_mission

RATED_AMBIENT_C = 45.0
RATING_HOURS = 2.0
HARD_LIMITS_C = {"batt_core": 60.0, "die": 100.0, "lidar": 80.0, "motor": 140.0, "air": 70.0}


def _rating_weather(t_air_c: float) -> PlantWeather:
    times = np.array(["2024-07-15T00:00", "2024-07-16T00:00"], dtype="datetime64[s]")
    two = np.ones(2)
    return PlantWeather(
        times,
        t_air_c * two,
        (t_air_c - 20.0) * two,
        1.5 * two,
        0.0 * two,
        0.0 * two,
        0.0 * two,
        24.45,
        54.38,
    )


def rating_peaks_c(
    p: PlantParams, t_air_c: float = RATED_AMBIENT_C, dt: float = 60.0
) -> dict[str, np.ndarray]:
    """Peak node temperatures of each robot after heavy use at ``t_air_c`` in shade."""
    n = p.n
    steps = int(RATING_HOURS * 3600 / dt)
    rng = np.random.default_rng(11)
    wx = _rating_weather(t_air_c)
    forc = build_forcing(wx, np.full(n, 3.0 * 3600.0), steps, dt, rng)
    drv = build_mission(p, np.ones(n), 0, steps, dt, rng, stop_share=1e-6, sand_share=1e-6)
    drv.shade_beam = np.ones((n, steps))
    soak = PlantState.at_ambient(np.full(n, t_air_c))
    tr = simulate_plant(p, forc, drv, soak)
    t = tr.temps_c().max(axis=1)
    return {
        "batt_core": t[:, BCORE],
        "die": t[:, DIE],
        "lidar": t[:, LIDAR],
        "motor": t[:, MOTOR],
        "air": t[:, AIR],
    }


def rated_mask(p: PlantParams) -> np.ndarray:
    peaks = rating_peaks_c(p)
    ok = np.ones(p.n, dtype=bool)
    for k, lim in HARD_LIMITS_C.items():
        ok &= peaks[k] <= lim
    return ok


def draw_rated_plants(n: int, seed: int, spread: float = 1.0) -> PlantParams:
    """``n`` robots that pass the rating check, drawn with ``seed`` (deterministic)."""
    got: list[PlantParams] = []
    have = 0
    attempt = 0
    while have < n:
        batch = draw_plants(max(4 * (n - have), 16), seed * 1000 + attempt, spread)
        keep = rated_mask(batch)
        if keep.any():
            got.append(batch.take(np.where(keep)[0]))
            have += int(keep.sum())
        attempt += 1
        if attempt > 50:
            raise RuntimeError("could not draw enough robots that meet the rating")
    from dataclasses import fields

    merged = {
        f.name: np.concatenate([getattr(g, f.name) for g in got])[:n] for f in fields(PlantParams)
    }
    return PlantParams(**merged)


def acceptance_rate(seed: int = 0, n: int = 400, spread: float = 1.0) -> float:
    return float(rated_mask(draw_plants(n, seed, spread)).mean())
