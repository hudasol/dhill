"""Read weather from CSV (columns: time_utc, t_air_c, dew_c, wind10_ms, pm10_ugm3, precip_mm_h[, ghi_wm2])."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .base import Weather

REQUIRED = ("time_utc", "t_air_c", "dew_c", "wind10_ms", "pm10_ugm3", "precip_mm_h")


def load_weather_csv(
    path: str | Path, lat: float, lon: float, altitude_m: float = 0.0, label: str = ""
) -> Weather:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("empty weather CSV")
    missing = [c for c in REQUIRED if c not in rows[0]]
    if missing:
        raise ValueError(f"weather CSV missing columns: {missing}")
    col = {c: np.array([float(r[c]) for r in rows]) for c in REQUIRED[1:]}
    times = np.array([r["time_utc"] for r in rows], dtype="datetime64[s]")
    ghi = np.array([float(r["ghi_wm2"]) for r in rows]) if "ghi_wm2" in rows[0] else None
    return Weather(
        times_utc=times,
        t_air_c=col["t_air_c"],
        dew_c=col["dew_c"],
        wind10_ms=col["wind10_ms"],
        pm10_ugm3=col["pm10_ugm3"],
        precip_mm_h=col["precip_mm_h"],
        lat=lat,
        lon=lon,
        altitude_m=altitude_m,
        ghi_wm2=ghi,
        source="csv",
        label=label or Path(path).stem,
    )
