"""Adapter from robot profiles to the solver's parameter arrays.

The physics layer defines ``ThermalParams`` and knows nothing about profiles. This module, in the
profile layer, reads a profile's values, provenance spreads and bounds and builds the arrays.
"""

from __future__ import annotations

import numpy as np

from ..physics import battery
from ..physics.constants import c_to_k
from ..physics.thermal import ThermalParams, lhs_normal, register_profile_builder
from .registry import PARAMS
from .schema import Profile


def thermal_params(
    profile: Profile,
    n: int = 1,
    mc: bool = False,
    rng: np.random.Generator | None = None,
    weather_sigma: tuple[float, float, float] = (1.5, 0.10, 0.25),
    sigma_scale: float = 1.0,
) -> ThermalParams:
    """Batched solver parameters from a profile.

    With ``mc=True`` each parameter is multiplied by an independent lognormal
    factor whose spread comes from the parameter's provenance, and forecast
    error realisations (temperature bias, irradiance and wind scale) are drawn.
    The first sample is always the nominal parameter set.
    """
    rng = rng or np.random.default_rng(0)

    def val(key: str) -> np.ndarray:
        base = profile.value(key)
        if not mc or n == 1:
            return np.full(n, base, dtype=float)
        sig = profile.sigma(key) * sigma_scale
        out = base * np.exp(sig * lhs_normal(rng, n)) if sig > 0 else np.full(n, base)
        out[0] = base
        d = PARAMS[key]
        if not (d.optional and base == d.default):
            out = np.clip(out, d.lo, d.hi)
        return out

    length, width, height = (
        val("geometry.length_m"),
        val("geometry.width_m"),
        val("geometry.height_m"),
    )
    char = val("geometry.char_length_m")
    char = np.where(char <= 0.0, height, char)
    a_top = length * width
    a_side = 2.0 * (length + width) * height
    side_proj = (2.0 / np.pi) * height * (length + width)

    pack = battery.PackSpec(
        cells_series=val("battery.cells_series"),
        cells_parallel=val("battery.cells_parallel"),
        cell_capacity_ah=val("battery.cell_capacity_ah"),
        cell_resistance_25c_ohm=val("battery.cell_resistance_25c_ohm"),
        resistance_ea_j_mol=val("battery.resistance_ea_j_mol"),
        ocv_v0=val("battery.ocv_v0"),
        ocv_slope=val("battery.ocv_slope"),
    )
    d_temp = np.zeros(n)
    irr = np.ones(n)
    wnd = np.ones(n)
    if mc and n > 1:
        d_temp = weather_sigma[0] * sigma_scale * lhs_normal(rng, n)
        irr = np.exp(weather_sigma[1] * sigma_scale * lhs_normal(rng, n))
        wnd = np.exp(weather_sigma[2] * sigma_scale * lhs_normal(rng, n))
        d_temp[0], irr[0], wnd[0] = 0.0, 1.0, 1.0
    alpha_clean = np.clip(val("surface.alpha_clean"), 0.05, 0.98)
    alpha_dust = np.clip(val("surface.alpha_dust"), 0.05, 0.98)
    return ThermalParams(
        a_top=a_top,
        a_side=a_side,
        a_bot=length * width,
        side_proj=side_proj,
        height=height,
        char_length=char,
        alpha_clean=alpha_clean,
        alpha_dust=alpha_dust,
        emissivity=np.clip(val("surface.emissivity"), 0.03, 0.98),
        dust_m0=val("surface.dust_m0_g_m2"),
        c_shell=val("shell.heat_capacity_j_k"),
        c_int=val("interior.heat_capacity_j_k"),
        c_bat=val("battery.heat_capacity_j_k"),
        c_cmp=val("compute.heat_capacity_j_k"),
        c_lid=val("lidar.heat_capacity_j_k"),
        c_mot=val("motors.heat_capacity_j_k"),
        ua_si=val("coupling.ua_shell_interior_w_k"),
        ua_bi=val("coupling.ua_battery_interior_w_k"),
        ua_ci=val("coupling.ua_compute_interior_w_k"),
        ua_li=val("coupling.ua_lidar_interior_w_k"),
        ua_la=val("coupling.ua_lidar_ambient_w_k"),
        ua_mi=val("coupling.ua_motors_interior_w_k"),
        ua_ma=val("coupling.ua_motors_ambient_w_k"),
        h_bot=val("coupling.h_bottom_w_m2k"),
        vent_flow=val("coupling.vent_flow_m3_s"),
        filter_ref=val("coupling.filter_ref_g_m2"),
        lidar_area=val("lidar.exposed_area_m2"),
        lidar_alpha=np.clip(val("lidar.alpha"), 0.05, 0.98),
        cool_cap=val("cooling.capacity_w"),
        cool_cop=val("cooling.cop"),
        cool_set_k=c_to_k(val("cooling.setpoint_c")),
        cool_gain=val("cooling.gain_w_k"),
        pack=pack,
        ageing_ea=val("battery.ageing_ea_j_mol"),
        eta_dcdc=np.clip(val("power.dcdc_efficiency"), 0.5, 0.99),
        eta_drive=np.clip(val("motors.drive_efficiency"), 0.2, 0.98),
        motor_loss_frac=np.clip(val("motors.loss_fraction_in_motor"), 0.0, 1.0),
        payload_heat_frac=np.clip(val("power.payload_heat_fraction"), 0.0, 1.0),
        die_rise=val("compute.die_rise_k_per_w"),
        albedo=np.clip(val("environment.albedo"), 0.0, 0.9),
        ground_rise=val("environment.ground_rise_k_per_kw_m2"),
        wind_exp=val("environment.wind_exponent"),
        v_dep=val("environment.deposition_velocity_m_s"),
        rain_clear=val("environment.rain_clear_mm_h"),
        d_temp_k=d_temp,
        irr_scale=irr,
        wind_scale=wnd,
    )


register_profile_builder(thermal_params)
