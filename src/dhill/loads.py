"""Translate a profile's operating mode and a scale factor into electrical loads."""

from __future__ import annotations

import numpy as np

from .physics.thermal import Loads
from .profiles.schema import Profile


def mission_loads(profile: Profile, scale, mode: str = "drive") -> Loads:
    """Loads for ``mode`` at operating scale ``scale`` (scalar or (B,)).

    Speed, drive power and payload power scale linearly with ``scale``. Compute
    power follows ``P_nom (f_min + (1 - f_min) scale)``: an embedded module cannot
    idle below its minimum power fraction while perception runs.
    """
    if mode not in profile.modes:
        raise KeyError(f"unknown mode '{mode}'; available: {sorted(profile.modes)}")
    m = profile.modes[mode]
    s = np.asarray(scale, dtype=float)
    p_nom = profile.value("compute.nominal_power_w")
    f_min = profile.value("compute.min_power_fraction")
    electronics = profile.value("power.comms_w") + profile.value("power.standby_w")
    return Loads(
        p_compute_w=p_nom * (f_min + (1.0 - f_min) * s),
        p_lidar_w=np.full_like(s, profile.value("lidar.power_w"))
        if s.ndim
        else profile.value("lidar.power_w"),
        p_comms_w=np.full_like(s, electronics) if s.ndim else electronics,
        p_drive_mech_w=m.mech_w * s,
        p_payload_w=m.payload_w * s,
    )


def parked_loads(profile: Profile, n: int | None = None) -> Loads:
    """Loads while parked with electronics powered, LiDAR off and compute at idle."""
    f_min = profile.value("compute.min_power_fraction")
    p_c = profile.value("compute.nominal_power_w") * f_min
    electronics = profile.value("power.comms_w") + profile.value("power.standby_w")
    one = np.ones(n) if n is not None else 1.0
    return Loads(p_compute_w=p_c * one, p_lidar_w=0.0 * one, p_comms_w=electronics * one)


def nominal_speed_ms(profile: Profile) -> float:
    return profile.value("perception.nominal_speed_ms")
