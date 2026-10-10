"""Deterministic synthetic weather for offline demos, tests and what-if studies.

Scenarios reproduce typical UAE regimes. They are stylised: they are for
exercising the decision logic and for sensitivity studies, not forecasts.
"""

from __future__ import annotations

import numpy as np

from ..sites import Site, get_site
from .base import Weather

SCENARIOS = {
    "summer_clear": "Typical hot clear summer day",
    "heatwave": "Extreme heat, light wind (about 50 C at the peak)",
    "humid_coastal": "Hot, humid coastal day with high dew point",
    "dust_event": "Clear morning, shamal-driven PM10 surge in the afternoon",
    "shamal_day": "Strong northwesterly winds with sustained high dust",
    "winter_mild": "Mild winter day",
    "rain_event": "Cool, cloudy day with a short rain event",
}

# (t_min_c, t_max_c, dew_c, wind_ms, pm10_ugm3) per scenario and setting scale
_BASE = {
    "summer_clear": (31.0, 44.0, 16.0, 3.5, 70.0),
    "heatwave": (35.0, 50.0, 14.0, 1.8, 90.0),
    "humid_coastal": (32.0, 41.0, 27.0, 3.0, 60.0),
    "dust_event": (30.0, 43.0, 14.0, 3.0, 80.0),
    "shamal_day": (28.0, 40.0, 10.0, 7.5, 450.0),
    "winter_mild": (14.0, 26.0, 8.0, 2.5, 60.0),
    "rain_event": (17.0, 24.0, 15.0, 4.0, 25.0),
}


def synthetic_weather(
    site: Site | str = "abu_dhabi",
    scenario: str = "summer_clear",
    start: str = "2026-08-05T00:00",
    days: int = 2,
    seed: int = 0,
) -> Weather:
    """Hourly synthetic weather, starting at ``start`` (UTC)."""
    if scenario not in _BASE:
        raise KeyError(f"unknown scenario '{scenario}'; available: {sorted(SCENARIOS)}")
    s = get_site(site) if isinstance(site, str) else site
    rng = np.random.default_rng(seed)
    t_min, t_max, dew, wind, pm = _BASE[scenario]
    if s.setting == "desert":
        t_max += 2.0
        t_min -= 3.0
        pm *= 1.5
    elif s.setting == "mountain":
        t_max -= 4.0
        t_min -= 4.0
    elif s.setting == "inland":
        t_max += 1.5
        t_min -= 2.0
    t_max -= 0.0065 * s.altitude_m

    n = days * 24
    t0 = np.datetime64(start, "s")
    times = t0 + (np.arange(n) * 3600).astype("timedelta64[s]")
    hours = np.arange(n)
    local_h = (hours + s.lon / 15.0) % 24.0
    day_idx = hours // 24
    # daily temperature wave peaking at 15:00 local solar time
    mid, amp = 0.5 * (t_min + t_max), 0.5 * (t_max - t_min)
    t_c = (
        mid
        + amp * np.cos(2 * np.pi * (local_h - 15.0) / 24.0)
        + 0.3 * rng.standard_normal(n).cumsum() * 0.05
    )
    dew_c = np.minimum(dew + 0.5 * np.sin(2 * np.pi * (local_h - 6.0) / 24.0), t_c - 0.5)
    # sea-breeze or valley-breeze afternoon maximum
    v = (
        wind
        * (0.75 + 0.5 * np.exp(-0.5 * ((local_h - 14.0) / 3.5) ** 2))
        * (1 + 0.1 * rng.standard_normal(n))
    )
    pm10 = np.full(n, pm) * (1 + 0.15 * rng.standard_normal(n))
    precip = np.zeros(n)
    notes = [SCENARIOS[scenario], "synthetic"]
    ghi = None
    if scenario == "dust_event":
        ramp = np.clip((local_h - 11.0) / 3.0, 0.0, 1.0) * np.clip((22.0 - local_h) / 4.0, 0.0, 1.0)
        pm10 = pm10 + 1800.0 * ramp * (day_idx >= 0)
        v = v + 6.0 * ramp
    if scenario == "shamal_day":
        pm10 = pm10 * (1 + 0.5 * np.sin(2 * np.pi * (local_h - 9.0) / 24.0) ** 2)
    if scenario == "rain_event":
        cloud = 0.45
        rain_window = (local_h > 13.0) & (local_h < 15.0)
        precip[rain_window] = 4.0
        pm10[local_h > 13.0] *= 0.4
        ghi = "cloud"
    out_ghi = None
    if ghi == "cloud":
        out_ghi = _cloudy_ghi(times, s, cloud)
    return Weather(
        times_utc=times,
        t_air_c=t_c,
        dew_c=dew_c,
        wind10_ms=np.maximum(v, 0.2),
        pm10_ugm3=np.maximum(pm10, 5.0),
        precip_mm_h=precip,
        lat=s.lat,
        lon=s.lon,
        altitude_m=s.altitude_m,
        ghi_wm2=out_ghi,
        source="synthetic",
        label=f"{s.id}/{scenario}",
        notes=notes,
    )


def _cloudy_ghi(times, site: Site, cloud_fraction: float):
    from ..physics import solar

    elev, _ = solar.solar_position(times, site.lat, site.lon)
    _, _, ghi = solar.clear_sky(elev, site.altitude_m)
    return ghi * (1.0 - 0.75 * cloud_fraction)
