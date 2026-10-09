"""Lithium-ion pack model: open-circuit voltage, resistance, heat and ageing.

An equivalent-circuit pack with a linear open-circuit-voltage curve, an
Arrhenius temperature dependence of internal resistance and an Arrhenius
ageing acceleration factor relative to 25 degC. Current follows from the power
demanded at the pack terminals. All fields accept scalars or arrays so that
Monte-Carlo samples can be simulated as a batch.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import R_GAS, T_REF_K


@dataclass(frozen=True)
class PackSpec:
    """Electrical description of a battery pack."""

    cells_series: float
    cells_parallel: float
    cell_capacity_ah: float
    cell_resistance_25c_ohm: float
    resistance_ea_j_mol: float
    ocv_v0: float  # cell open-circuit voltage at 0% state of charge, V
    ocv_slope: float  # cell open-circuit voltage rise from 0% to 100%, V

    @property
    def capacity_ah(self):
        return self.cells_parallel * self.cell_capacity_ah

    @property
    def energy_wh(self):
        v_mid = self.cells_series * (self.ocv_v0 + 0.5 * self.ocv_slope)
        return v_mid * self.capacity_ah


def ocv_pack(spec: PackSpec, soc):
    """Pack open-circuit voltage, V."""
    return spec.cells_series * (spec.ocv_v0 + spec.ocv_slope * np.clip(soc, 0.0, 1.0))


def resistance_pack(spec: PackSpec, t_k, soc):
    """Pack internal resistance, ohm.

    Arrhenius in temperature (lower resistance when warm) with a modest increase
    at low state of charge.
    """
    arr = np.exp(
        spec.resistance_ea_j_mol / R_GAS * (1.0 / np.asarray(t_k, dtype=float) - 1.0 / T_REF_K)
    )
    soc_term = 1.0 + 0.3 * (1.0 - np.clip(soc, 0.0, 1.0))
    r_cell = spec.cell_resistance_25c_ohm * arr * soc_term
    return spec.cells_series / spec.cells_parallel * r_cell


def current_for_power(p_w, v_oc, r_ohm):
    """Terminal current for a power demand, A (discharge positive).

    Solves ``p = (v_oc - i r) i``. If the demand exceeds the maximum power
    transfer ``v_oc^2 / (4 r)`` the current saturates at ``v_oc / (2 r)`` and the
    returned flag is True. Negative ``p_w`` models charging.
    """
    p = np.asarray(p_w, dtype=float)
    disc = v_oc**2 - 4.0 * r_ohm * p
    saturated = disc < 0.0
    root = np.sqrt(np.maximum(disc, 0.0))
    return (v_oc - root) / (2.0 * r_ohm), saturated


def heat_w(current_a, r_ohm):
    """Joule heat in the pack, W."""
    return np.asarray(current_a, dtype=float) ** 2 * r_ohm


def ageing_factor(t_k, ea_j_mol):
    """Ageing acceleration relative to 25 degC (Arrhenius). 1.0 at 25 degC."""
    return np.exp(ea_j_mol / R_GAS * (1.0 / T_REF_K - 1.0 / np.asarray(t_k, dtype=float)))


def soc_after(soc, current_a, dt_s: float, capacity_ah):
    """State of charge after a step of constant current (coulomb counting)."""
    return soc - np.asarray(current_a, dtype=float) * dt_s / (3600.0 * capacity_ah)


def c_rate(current_a, capacity_ah):
    """Current expressed as a multiple of the 1C rate."""
    return np.asarray(current_a, dtype=float) / capacity_ah
