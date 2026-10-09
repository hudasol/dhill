"""Dust deposition, absorptance drift, fouling and LiDAR range loss.

Deposition follows the fixed-velocity soiling form used for photovoltaic
modules (mass flux = deposition velocity x PM10 concentration, reset by rain).
Airborne extinction uses a mass-extinction efficiency. LiDAR range comes from a
two-way Beer-Lambert link budget solved in closed form with the Lambert W
function. Deposition velocity, rain-clearing threshold, mass-extinction
efficiency and filter parameters are assumptions until calibrated in the field.
"""

from __future__ import annotations

import numpy as np
from scipy.special import lambertw

VISIBILITY_CONTRAST = 3.912  # Koschmieder constant (2% contrast threshold)


def deposition_series(
    pm10_ugm3,
    precip_mm_h,
    dt_s: float,
    v_dep_m_s: float,
    rain_clear_mm_h: float = 1.0,
    initial_g_m2: float = 0.0,
) -> np.ndarray:
    """Cumulative dust loading on an upward-facing surface, g m^-2.

    Args:
        pm10_ugm3: PM10 concentration series, ug m^-3.
        precip_mm_h: precipitation rate series, mm h^-1 (same length).
        dt_s: time step of the series, s.
        v_dep_m_s: deposition velocity, m s^-1 (about 0.004 for PM10 in PV soiling work).
        rain_clear_mm_h: rain rate that washes the surface clean.
        initial_g_m2: loading at the first sample.
    """
    c = np.maximum(np.nan_to_num(np.asarray(pm10_ugm3, dtype=float)), 0.0) * 1e-6  # g m^-3
    rain = np.nan_to_num(np.asarray(precip_mm_h, dtype=float))
    flux = v_dep_m_s * c  # g m^-2 s^-1
    out = np.empty_like(c)
    m = float(initial_g_m2)
    for i in range(c.size):
        m = 0.0 if rain[i] >= rain_clear_mm_h else m + flux[i] * dt_s
        out[i] = m
    return out


def absorptance(alpha_clean, alpha_dust, loading_g_m2, m0_g_m2):
    """Solar absorptance drifting from the clean value toward the dust value."""
    cover = 1.0 - np.exp(-np.maximum(loading_g_m2, 0.0) / m0_g_m2)
    return alpha_clean + (alpha_dust - alpha_clean) * cover


def clog_factor(loading_g_m2, m_ref_g_m2):
    """Fraction of clean heat-sink conductance and vent flow remaining, in (0, 1]."""
    return 1.0 / (1.0 + np.maximum(loading_g_m2, 0.0) / m_ref_g_m2)


def extinction_per_m(pm10_ugm3, mass_ext_eff_m2_g: float, visibility_m=None):
    """Optical extinction coefficient, m^-1.

    Dust extinction is ``mass_ext_eff x concentration``. If a visibility forecast
    is supplied (fog, haze), the larger of the two extinctions is used.
    """
    sigma = mass_ext_eff_m2_g * np.maximum(np.asarray(pm10_ugm3, dtype=float), 0.0) * 1e-6
    if visibility_m is not None:
        vis = np.maximum(np.asarray(visibility_m, dtype=float), 1.0)
        sigma = np.maximum(sigma, VISIBILITY_CONTRAST / vis)
    return sigma


def visibility_m(sigma_per_m):
    """Meteorological visibility from extinction (Koschmieder), m."""
    return VISIBILITY_CONTRAST / np.maximum(np.asarray(sigma_per_m, dtype=float), 1e-9)


def lidar_range_m(range_clear_m: float, sigma_per_m):
    """Effective LiDAR detection range of a target of reference reflectivity, m.

    Received power scales as exp(-2 sigma R) / R^2; the threshold equals the
    clear-air value at ``range_clear_m``. Solving R exp(sigma R) = R0 gives
    R = W(sigma R0) / sigma.
    """
    sigma = np.asarray(sigma_per_m, dtype=float)
    small = sigma < 1e-9
    safe = np.where(small, 1.0, sigma)
    r = lambertw(safe * range_clear_m).real / safe
    return np.where(small, range_clear_m, r)


def max_safe_speed_ms(range_eff_m, decel_ms2: float, reaction_s: float, margin_m: float):
    """Largest speed whose stopping distance fits inside the sensing range.

    Solves v t + v^2 / (2 a) + margin = R for v.
    """
    avail = np.maximum(np.asarray(range_eff_m, dtype=float) - margin_m, 0.0)
    at = decel_ms2 * reaction_s
    return -at + np.sqrt(at**2 + 2.0 * decel_ms2 * avail)
