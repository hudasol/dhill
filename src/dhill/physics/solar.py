"""Solar geometry and a simple clear-sky model.

Solar position follows the NOAA general solar position equations (Fourier-series
declination and equation of time), accurate to well under a degree, which is
ample for thermal load estimates. All times are UTC.
"""

from __future__ import annotations

import numpy as np

SOLAR_CONSTANT = 1361.0  # W m^-2


def _day_of_year_and_hour(times_utc) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(times_utc).astype("datetime64[s]")
    day = t.astype("datetime64[D]")
    year_start = t.astype("datetime64[Y]").astype("datetime64[D]")
    doy = (day - year_start).astype(int) + 1
    hour = (t - day).astype("timedelta64[s]").astype(float) / 3600.0
    return doy.astype(float), hour


def solar_position(times_utc, lat_deg: float, lon_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Solar elevation and azimuth.

    Args:
        times_utc: array-like of ``datetime64`` in UTC.
        lat_deg: latitude, degrees north.
        lon_deg: longitude, degrees east.

    Returns:
        ``(elevation_rad, azimuth_rad)``; azimuth is measured clockwise from north.
    """
    doy, hour = _day_of_year_and_hour(times_utc)
    gamma = 2.0 * np.pi / 365.0 * (doy - 1.0 + (hour - 12.0) / 24.0)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.00148 * np.sin(3 * gamma)
    )
    tst_min = hour * 60.0 + eqtime + 4.0 * lon_deg
    ha = np.radians(tst_min / 4.0 - 180.0)
    lat = np.radians(lat_deg)
    cos_zen = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
    elevation = np.pi / 2.0 - np.arccos(np.clip(cos_zen, -1.0, 1.0))
    az_south = np.arctan2(np.sin(ha), np.cos(ha) * np.sin(lat) - np.tan(decl) * np.cos(lat))
    azimuth = (az_south + np.pi) % (2.0 * np.pi)
    return elevation, azimuth


def mean_solar_hour(times_utc, lon_deg: float) -> np.ndarray:
    """Mean solar time of day in hours [0, 24) at a longitude."""
    _, hour = _day_of_year_and_hour(times_utc)
    return (hour + lon_deg / 15.0) % 24.0


def clear_sky(elevation_rad, altitude_m: float = 0.0, turbidity_factor: float = 0.88):
    """Simple clear-sky irradiance for synthetic weather.

    Uses the Kasten-Young air mass and a Meinel-type beam attenuation. The
    turbidity factor lowers the beam for the aerosol-laden Gulf atmosphere and
    is an assumption, not a measurement.

    Returns:
        ``(dni, dhi, ghi)`` in W m^-2.
    """
    elev = np.asarray(elevation_rad, dtype=float)
    sin_e = np.sin(elev)
    up = sin_e > 0.0
    e_deg = np.degrees(np.where(up, elev, 0.0))
    air_mass = 1.0 / (np.where(up, sin_e, 1.0) + 0.50572 * (e_deg + 6.07995) ** -1.6364)
    alt_term = 0.14 * (altitude_m / 1000.0)
    beam = SOLAR_CONSTANT * ((1.0 - alt_term) * 0.7 ** (air_mass**0.678) + alt_term)
    dni = np.where(up, beam * turbidity_factor, 0.0)
    dhi = np.where(up, 0.12 * dni, 0.0)
    ghi = dni * np.where(up, sin_e, 0.0) + dhi
    return dni, dhi, ghi
