"""Longwave radiation helpers: sky temperature, linearised exchange, ground temperature."""

from __future__ import annotations

import numpy as np

from .constants import SIGMA_SB


def sky_temperature_k(t_air_k, dew_point_c, solar_hour):
    """Effective sky temperature (Berdahl-Martin clear-sky emissivity), K.

    ``solar_hour`` is the mean solar time of day in hours. Cloud cover is not
    modelled; a cloudy sky is warmer, so this is conservative for night cooling
    but not for midday heating (which is dominated by shortwave load).
    """
    td = np.asarray(dew_point_c, dtype=float)
    eps_sky = 0.711 + 0.0056 * td + 7.3e-5 * td**2 + 0.013 * np.cos(2.0 * np.pi * solar_hour / 24.0)
    eps_sky = np.clip(eps_sky, 0.6, 1.0)
    return np.asarray(t_air_k, dtype=float) * eps_sky**0.25


def h_rad(emissivity, t_surf_k, t_surr_k):
    """Linearised radiative coefficient, W m^-2 K^-1."""
    ts = np.asarray(t_surf_k, dtype=float)
    tr = np.asarray(t_surr_k, dtype=float)
    return emissivity * SIGMA_SB * (ts**2 + tr**2) * (ts + tr)


def ground_temperature_k(t_air_k, ghi, rise_k_per_kw_m2, shade_fraction=0.0):
    """Ground (or panel) surface temperature, K.

    The rise above air temperature scales with the global horizontal irradiance
    reaching the ground. The coefficient is surface-specific and an assumption
    until measured: desert sand and asphalt are tens of kelvin above air at
    noon; a PV module follows the NOCT relation (about 31 K per kW m^-2).
    """
    ghi_eff = np.maximum(np.asarray(ghi, dtype=float), 0.0) * (1.0 - np.asarray(shade_fraction))
    return np.asarray(t_air_k, dtype=float) + rise_k_per_kw_m2 * ghi_eff / 1000.0
