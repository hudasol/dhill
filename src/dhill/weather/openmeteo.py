"""Open-Meteo forecast, archive and air-quality client with a small disk cache.

Open-Meteo is used under its terms for non-commercial use; production use
should switch to a licensed feed (see docs/data-sources). Failures raise
``WeatherUnavailable`` so callers can fall back explicitly and say so.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx
import numpy as np

from ..sites import Site, get_site
from .base import Weather

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

_WX_VARS = "temperature_2m,dew_point_2m,wind_speed_10m,shortwave_radiation,precipitation"
CACHE_TTL_S = 1800.0


class WeatherUnavailable(RuntimeError):
    """The online weather source could not be used."""


def _cache_dir() -> Path:
    d = Path(os.environ.get("DHILL_CACHE_DIR", Path.home() / ".cache" / "dhill"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(
    url: str, params: dict, ttl_s: float = CACHE_TTL_S, client: httpx.Client | None = None
) -> dict:
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:24]
    path = _cache_dir() / f"{key}.json"
    if path.exists() and time.time() - path.stat().st_mtime < ttl_s:
        return json.loads(path.read_text())
    try:
        own = client is None
        client = client or httpx.Client(timeout=20.0)
        try:
            r = client.get(url, params=params)
        finally:
            if own:
                client.close()
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherUnavailable(f"{url}: {exc}") from exc
    if "error" in data and data.get("error"):
        raise WeatherUnavailable(f"{url}: {data.get('reason', 'error')}")
    path.write_text(json.dumps(data))
    return data


def _hourly(data: dict) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    h = data.get("hourly")
    if not h or "time" not in h:
        raise WeatherUnavailable("response has no hourly block")
    times = np.array(h["time"], dtype="datetime64[s]")
    cols = {
        k: np.array([np.nan if v is None else v for v in vals], dtype=float)
        for k, vals in h.items()
        if k != "time"
    }
    return times, cols


def _fill(a: np.ndarray, default: float) -> np.ndarray:
    a = np.asarray(a, dtype=float).copy()
    bad = ~np.isfinite(a)
    if bad.all():
        return np.full_like(a, default)
    if bad.any():
        idx = np.arange(a.size)
        a[bad] = np.interp(idx[bad], idx[~bad], a[~bad])
    return a


def fetch_weather(
    site: Site | str,
    forecast_days: int = 3,
    past_days: int = 0,
    client: httpx.Client | None = None,
) -> Weather:
    """Forecast weather plus CAMS PM10 for a site, UTC hourly."""
    s = get_site(site) if isinstance(site, str) else site
    base = {
        "latitude": s.lat,
        "longitude": s.lon,
        "timezone": "UTC",
        "forecast_days": forecast_days,
        "past_days": past_days,
    }
    wx = _get(FORECAST_URL, {**base, "hourly": _WX_VARS, "wind_speed_unit": "ms"}, client=client)
    t_w, c_w = _hourly(wx)
    notes = ["Open-Meteo forecast"]
    pm = np.full(t_w.shape, np.nan)
    try:
        aq = _get(AIR_URL, {**base, "hourly": "pm10,dust"}, client=client)
        t_a, c_a = _hourly(aq)
        pm_a = np.fmax(
            c_a.get("pm10", np.full(t_a.shape, np.nan)), c_a.get("dust", np.full(t_a.shape, np.nan))
        )
        lookup = {t: v for t, v in zip(t_a, pm_a, strict=True)}
        pm = np.array([lookup.get(t, np.nan) for t in t_w], dtype=float)
        notes.append("CAMS PM10/dust via Open-Meteo air-quality")
    except WeatherUnavailable as exc:
        notes.append(f"air-quality unavailable ({exc}); PM10 assumed 80 ug/m3")
    if np.isfinite(pm).sum() < 0.5 * pm.size:
        notes.append("PM10 mostly missing; filled with 80 ug/m3")
    return Weather(
        times_utc=t_w,
        t_air_c=_fill(c_w["temperature_2m"], 30.0),
        dew_c=_fill(c_w["dew_point_2m"], 15.0),
        wind10_ms=_fill(c_w["wind_speed_10m"], 3.0),
        pm10_ugm3=_fill(pm, 80.0),
        precip_mm_h=_fill(c_w["precipitation"], 0.0),
        lat=s.lat,
        lon=s.lon,
        altitude_m=s.altitude_m,
        ghi_wm2=_fill(c_w["shortwave_radiation"], 0.0),
        source="open-meteo",
        label=s.id,
        notes=notes,
    )


def fetch_archive(
    site: Site | str, start: str, end: str, client: httpx.Client | None = None
) -> Weather:
    """Reanalysis weather for past dates (YYYY-MM-DD), used for back-casting."""
    s = get_site(site) if isinstance(site, str) else site
    params = {
        "latitude": s.lat,
        "longitude": s.lon,
        "start_date": start,
        "end_date": end,
        "timezone": "UTC",
        "hourly": _WX_VARS,
        "wind_speed_unit": "ms",
    }
    t, c = _hourly(_get(ARCHIVE_URL, params, ttl_s=86400.0, client=client))
    return Weather(
        times_utc=t,
        t_air_c=_fill(c["temperature_2m"], 30.0),
        dew_c=_fill(c["dew_point_2m"], 15.0),
        wind10_ms=_fill(c["wind_speed_10m"], 3.0),
        pm10_ugm3=np.full(t.shape, 80.0),
        precip_mm_h=_fill(c["precipitation"], 0.0),
        lat=s.lat,
        lon=s.lon,
        altitude_m=s.altitude_m,
        ghi_wm2=_fill(c["shortwave_radiation"], 0.0),
        source="open-meteo-archive",
        label=s.id,
        notes=["Open-Meteo archive (reanalysis); PM10 not retrieved, 80 ug/m3 assumed"],
    )
