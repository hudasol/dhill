"""Registry of robot-profile parameters: units, physical bounds and meaning.

Every parameter a profile may set is declared here. The registry drives
validation and the generated parameter reference in ``docs/parameters.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["measured", "datasheet", "textbook", "assumption", "calibrated"]

# Relative one-sigma uncertainty used for Monte-Carlo sampling, by provenance.
SOURCE_SIGMA: dict[str, float] = {
    "measured": 0.02,
    "datasheet": 0.05,
    "textbook": 0.10,
    "assumption": 0.25,
    "calibrated": 0.05,
}


@dataclass(frozen=True)
class ParamDef:
    unit: str
    lo: float
    hi: float
    desc: str
    optional: bool = False
    default: float | None = None


def _p(unit: str, lo: float, hi: float, desc: str, default: float | None = None) -> ParamDef:
    return ParamDef(unit, lo, hi, desc, optional=default is not None, default=default)


PARAMS: dict[str, ParamDef] = {
    # geometry
    "geometry.length_m": _p("m", 0.05, 6.0, "Body length"),
    "geometry.width_m": _p("m", 0.05, 4.0, "Body width"),
    "geometry.height_m": _p("m", 0.03, 3.0, "Body height"),
    "geometry.char_length_m": _p("m", 0.03, 3.0, "Characteristic length for outer convection", 0.0),
    # surface optics
    "surface.alpha_clean": _p("-", 0.05, 0.98, "Solar absorptance of the clean outer surface"),
    "surface.alpha_dust": _p("-", 0.05, 0.98, "Solar absorptance of a fully dust-covered surface"),
    "surface.emissivity": _p("-", 0.03, 0.98, "Longwave emissivity of the outer surface"),
    "surface.dust_m0_g_m2": _p(
        "g/m2", 0.1, 50.0, "Dust loading at which about 63% of the surface is covered"
    ),
    # thermal capacities
    "shell.heat_capacity_j_k": _p("J/K", 100.0, 5.0e5, "Heat capacity of the outer skin"),
    "interior.heat_capacity_j_k": _p(
        "J/K", 100.0, 5.0e5, "Heat capacity of interior air and chassis"
    ),
    "battery.heat_capacity_j_k": _p("J/K", 100.0, 5.0e5, "Heat capacity of the battery pack"),
    "compute.heat_capacity_j_k": _p(
        "J/K", 10.0, 5.0e4, "Heat capacity of the compute module and heat-sink"
    ),
    "lidar.heat_capacity_j_k": _p("J/K", 10.0, 5.0e4, "Heat capacity of the LiDAR housing"),
    "motors.heat_capacity_j_k": _p("J/K", 50.0, 2.0e5, "Heat capacity of the motors"),
    # couplings
    "coupling.ua_shell_interior_w_k": _p("W/K", 0.1, 500.0, "Shell to interior conductance"),
    "coupling.ua_battery_interior_w_k": _p("W/K", 0.05, 200.0, "Battery to interior conductance"),
    "coupling.ua_compute_interior_w_k": _p(
        "W/K", 0.05, 200.0, "Compute heat-sink to interior conductance (clean)"
    ),
    "coupling.ua_lidar_interior_w_k": _p("W/K", 0.01, 50.0, "LiDAR to interior conductance"),
    "coupling.ua_lidar_ambient_w_k": _p("W/K", 0.01, 50.0, "LiDAR housing to ambient conductance"),
    "coupling.ua_motors_interior_w_k": _p("W/K", 0.01, 100.0, "Motors to interior conductance"),
    "coupling.ua_motors_ambient_w_k": _p(
        "W/K", 0.01, 100.0, "Motors to ambient and ground conductance"
    ),
    "coupling.h_bottom_w_m2k": _p(
        "W/m2K", 1.0, 100.0, "Underside to ground coupling (convective + radiative + contact)"
    ),
    "coupling.vent_flow_m3_s": _p(
        "m3/s", 0.0, 1.0, "Filtered ventilation flow when clean (0 = sealed)", 0.0
    ),
    "coupling.filter_ref_g_m2": _p(
        "g/m2", 0.1, 100.0, "Dust loading at which filter flow and heat-sink conductance halve", 5.0
    ),
    # battery
    "battery.cells_series": _p("-", 1.0, 200.0, "Cells in series"),
    "battery.cells_parallel": _p("-", 1.0, 100.0, "Cells in parallel"),
    "battery.cell_capacity_ah": _p("Ah", 0.5, 300.0, "Capacity per cell"),
    "battery.cell_resistance_25c_ohm": _p("ohm", 1e-4, 0.5, "DC resistance per cell at 25 degC"),
    "battery.resistance_ea_j_mol": _p("J/mol", 0.0, 6.0e4, "Activation energy of resistance"),
    "battery.ocv_v0": _p(
        "V", 2.0, 4.0, "Linearised cell open-circuit voltage at 0% state of charge"
    ),
    "battery.ocv_slope": _p("V", 0.0, 2.0, "Cell open-circuit voltage rise from 0% to 100%"),
    "battery.max_discharge_c_rate": _p("1/h", 0.1, 20.0, "Maximum continuous discharge rate"),
    "battery.ageing_ea_j_mol": _p("J/mol", 1.0e4, 1.0e5, "Activation energy of capacity ageing"),
    # compute
    "compute.nominal_power_w": _p("W", 0.1, 500.0, "Compute power at full mission rate"),
    "compute.min_power_fraction": _p(
        "-", 0.05, 1.0, "Compute power fraction at the minimum derate scale"
    ),
    "compute.die_rise_k_per_w": _p(
        "K/W", 0.0, 5.0, "Die temperature rise above the module node per watt"
    ),
    # lidar
    "lidar.power_w": _p("W", 0.0, 100.0, "LiDAR electrical power"),
    "lidar.exposed_area_m2": _p("m2", 0.0, 0.5, "Sun-exposed LiDAR area"),
    "lidar.alpha": _p("-", 0.05, 0.98, "LiDAR housing solar absorptance"),
    "lidar.range_clear_m": _p(
        "m", 0.1, 500.0, "Clear-air detection range for the reference target"
    ),
    # motors
    "motors.loss_fraction_in_motor": _p(
        "-", 0.0, 1.0, "Share of drivetrain losses dissipated in the motor node"
    ),
    "motors.drive_efficiency": _p(
        "-", 0.2, 0.98, "Electrical to mechanical efficiency of the drivetrain"
    ),
    # power system
    "power.comms_w": _p("W", 0.0, 200.0, "Communications and housekeeping load"),
    "power.standby_w": _p("W", 0.0, 200.0, "Parked standby electrical load"),
    "power.dcdc_efficiency": _p("-", 0.5, 0.99, "Power-conversion efficiency"),
    "power.payload_heat_fraction": _p(
        "-", 0.0, 1.0, "Share of payload power dissipated inside the body"
    ),
    # cooling
    "cooling.capacity_w": _p("W", 0.0, 2000.0, "Maximum active cooling power (0 = none)", 0.0),
    "cooling.cop": _p("-", 0.2, 6.0, "Coefficient of performance of active cooling", 1.5),
    "cooling.setpoint_c": _p("degC", 15.0, 60.0, "Interior cooling set-point", 40.0),
    "cooling.gain_w_k": _p("W/K", 1.0, 200.0, "Proportional gain of the cooling controller", 20.0),
    # perception and motion
    "perception.nominal_speed_ms": _p("m/s", 0.05, 30.0, "Nominal mission speed"),
    "perception.decel_ms2": _p("m/s2", 0.1, 10.0, "Safe deceleration"),
    "perception.reaction_s": _p("s", 0.0, 5.0, "System reaction time"),
    "perception.margin_m": _p("m", 0.0, 20.0, "Stopping-distance safety margin"),
    # environment of use
    "environment.albedo": _p("-", 0.0, 0.9, "Ground shortwave reflectance"),
    "environment.ground_rise_k_per_kw_m2": _p(
        "K per kW/m2", 0.0, 60.0, "Ground surface temperature rise above air per kW/m2 of sun"
    ),
    "environment.wind_exponent": _p("-", 0.05, 0.5, "Wind-profile power-law exponent"),
    "environment.deposition_velocity_m_s": _p("m/s", 1e-5, 0.1, "Dust deposition velocity"),
    "environment.rain_clear_mm_h": _p("mm/h", 0.1, 20.0, "Rain rate that washes surfaces clean"),
    "environment.mass_ext_eff_m2_g": _p(
        "m2/g", 0.05, 5.0, "Mass-extinction efficiency of airborne dust"
    ),
}

# Components that are checked against limits. Node mapping lives in the engine.
COMPONENTS = ("battery", "compute_die", "lidar", "motor", "interior")
