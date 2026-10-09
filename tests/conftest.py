"""Shared test helpers."""

from __future__ import annotations

import numpy as np
import pytest

from dhill.physics import solar
from dhill.physics.constants import c_to_k, pressure_at_elevation
from dhill.physics.thermal import Forcing


def make_forcing(
    day="2026-08-05",
    lat=24.45,
    lon=54.38,
    t_min_c=31.0,
    t_max_c=46.0,
    wind=3.0,
    pm10=50.0,
    dt_s=300.0,
    hours=24,
    altitude=10.0,
    dew_c=18.0,
):
    n = int(hours * 3600 / dt_s)
    t0 = np.datetime64(f"{day}T00:00:00")
    times = t0 + (np.arange(n) * dt_s).astype("timedelta64[s]")
    elev, _az = solar.solar_position(times, lat, lon)
    dni, dhi, ghi = solar.clear_sky(elev, altitude)
    hour_local = (np.arange(n) * dt_s / 3600.0 + lon / 15.0) % 24.0
    # temperature wave peaking at 15:00 local solar time
    mid, amp = 0.5 * (t_min_c + t_max_c), 0.5 * (t_max_c - t_min_c)
    t_c = mid + amp * np.cos(2 * np.pi * (hour_local - 15.0) / 24.0)
    return Forcing(
        dt_s=dt_s,
        t_air_k=c_to_k(t_c),
        dew_c=np.full(n, dew_c),
        wind10_ms=np.full(n, wind),
        dni=dni,
        dhi=dhi,
        ghi=ghi,
        sin_elev=np.sin(np.maximum(elev, 0.0)),
        cos_elev=np.cos(np.maximum(elev, 0.0)),
        solar_hour=hour_local,
        pm10=np.full(n, pm10),
        precip_mm_h=np.zeros(n),
        p_pa=pressure_at_elevation(altitude),
    )


@pytest.fixture
def forcing():
    return make_forcing()
