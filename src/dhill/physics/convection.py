"""External convective heat transfer for a box-like robot shell.

Combined forced and natural convection from standard textbook correlations
(Incropera and DeWitt; Churchill and Chu). The same vertical-plate natural
convection correlation is used for every face, which slightly under-predicts
the hot-face-up case; this is conservative for thermal margins.
"""

from __future__ import annotations

import numpy as np

from . import air
from .constants import P_SEA_LEVEL


def wind_at_height(v10_ms, height_m: float, exponent: float = 0.2, v_min: float = 0.3):
    """Scale 10 m wind speed to robot height with a power law.

    The exponent (about 0.14-0.25 for open terrain) is an assumption. ``v_min``
    represents turbulent mixing and robot-induced flow that keep the effective
    air speed above zero in a calm forecast.
    """
    v = np.maximum(np.asarray(v10_ms, dtype=float), 0.0) * (max(height_m, 0.1) / 10.0) ** exponent
    return np.maximum(v, v_min)


def nusselt_forced_plate(re, pr):
    """Average Nusselt number for forced flow over a flat plate (laminar or mixed)."""
    re = np.maximum(np.asarray(re, dtype=float), 1.0)
    laminar = 0.664 * np.sqrt(re) * pr ** (1.0 / 3.0)
    mixed = (0.037 * re**0.8 - 871.0) * pr ** (1.0 / 3.0)
    return np.where(re < 5.0e5, laminar, np.maximum(mixed, laminar))


def nusselt_natural_vertical(ra, pr):
    """Churchill-Chu average Nusselt number for a vertical plate, valid for all Ra."""
    ra = np.maximum(np.asarray(ra, dtype=float), 0.0)
    denom = (1.0 + (0.492 / pr) ** (9.0 / 16.0)) ** (8.0 / 27.0)
    return (0.825 + 0.387 * ra ** (1.0 / 6.0) / denom) ** 2


def h_outer(t_surf_k, t_air_k, v_ms, length_m, p_pa: float = P_SEA_LEVEL):
    """Combined convective coefficient, W m^-2 K^-1.

    Nu^3 = Nu_forced^3 + Nu_natural^3 (Churchill's blending rule).
    """
    t_surf = np.asarray(t_surf_k, dtype=float)
    t_air = np.asarray(t_air_k, dtype=float)
    t_film = 0.5 * (t_surf + t_air)
    nu = air.kinematic_viscosity(t_film, p_pa)
    k = air.conductivity(t_film)
    pr = air.prandtl(t_film)
    re = np.asarray(v_ms, dtype=float) * length_m / nu
    ra = air.rayleigh(t_surf - t_air, length_m, t_film, p_pa)
    nu_f = nusselt_forced_plate(re, pr)
    nu_n = nusselt_natural_vertical(ra, pr)
    nu_c = (nu_f**3 + nu_n**3) ** (1.0 / 3.0)
    return nu_c * k / length_m
