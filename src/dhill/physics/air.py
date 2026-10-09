"""Moist-air transport properties and psychrometrics.

Textbook approximations valid for roughly 250-400 K near atmospheric pressure.
Viscosity uses Sutherland's law; thermal conductivity a power law fitted to
tabulated dry-air values. Accuracy is a few percent, which is far below the
uncertainty of the other model inputs.
"""

from __future__ import annotations

import numpy as np

from .constants import CP_AIR, G_ACC, K0, P_SEA_LEVEL, R_AIR


def density(t_k, p_pa: float = P_SEA_LEVEL):
    """Dry-air density from the ideal gas law, kg m^-3."""
    return p_pa / (R_AIR * np.asarray(t_k, dtype=float))


def viscosity(t_k):
    """Dynamic viscosity (Sutherland's law), Pa s."""
    t = np.asarray(t_k, dtype=float)
    return 1.458e-6 * t**1.5 / (t + 110.4)


def conductivity(t_k):
    """Thermal conductivity of air, W m^-1 K^-1 (power-law fit to tables, 250-400 K)."""
    t = np.asarray(t_k, dtype=float)
    return 0.0263 * (t / 300.0) ** 0.8


def kinematic_viscosity(t_k, p_pa: float = P_SEA_LEVEL):
    """Kinematic viscosity, m^2 s^-1."""
    return viscosity(t_k) / density(t_k, p_pa)


def prandtl(t_k):
    """Prandtl number of air."""
    return CP_AIR * viscosity(t_k) / conductivity(t_k)


def thermal_diffusivity(t_k, p_pa: float = P_SEA_LEVEL):
    """Thermal diffusivity, m^2 s^-1."""
    return conductivity(t_k) / (density(t_k, p_pa) * CP_AIR)


def saturation_vapour_pressure_pa(t_c):
    """Saturation vapour pressure over water (Magnus form), Pa."""
    t = np.asarray(t_c, dtype=float)
    return 610.94 * np.exp(17.625 * t / (t + 243.04))


def dew_point_c(t_c, rh_pct):
    """Dew point (Magnus), degC. ``rh_pct`` is clipped to [1, 100]."""
    t = np.asarray(t_c, dtype=float)
    rh = np.clip(np.asarray(rh_pct, dtype=float), 1.0, 100.0) / 100.0
    a, b = 17.625, 243.04
    g = np.log(rh) + a * t / (b + t)
    return b * g / (a - g)


def rayleigh(delta_t, length_m, t_film_k, p_pa: float = P_SEA_LEVEL):
    """Rayleigh number for natural convection, using |delta_t|."""
    nu = kinematic_viscosity(t_film_k, p_pa)
    alpha = thermal_diffusivity(t_film_k, p_pa)
    beta = 1.0 / np.asarray(t_film_k, dtype=float)
    return G_ACC * beta * np.abs(delta_t) * length_m**3 / (nu * alpha)


__all__ = [
    "K0",
    "conductivity",
    "density",
    "dew_point_c",
    "kinematic_viscosity",
    "prandtl",
    "rayleigh",
    "saturation_vapour_pressure_pa",
    "thermal_diffusivity",
    "viscosity",
]
