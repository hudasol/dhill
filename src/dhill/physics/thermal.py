"""Six-node lumped thermal network with battery, dust and cooling coupling.

Nodes: shell (outer skin), interior (air and chassis), battery, compute module,
LiDAR housing, motors. The network is integrated with backward Euler, which is
unconditionally stable, using coefficients evaluated at the previous step
(convection, radiation, battery resistance). Every quantity carries a leading
batch dimension so that Monte-Carlo samples, derate scales, shade fractions and
start times are simulated together in one vectorised pass.

Temperatures are kelvin inside the solver; callers convert to degC.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace

import numpy as np

from ..profiles.registry import PARAMS
from ..profiles.schema import Profile
from . import air, battery, convection, dust, radiation
from .constants import CP_AIR, K0, P_SEA_LEVEL, c_to_k

NODES = ("shell", "interior", "battery", "compute", "lidar", "motor")
S, I, B, C, L, M = range(6)  # noqa: E741

DIFFUSE_SHADE_FACTOR = 0.5  # shade blocks half as much diffuse as direct beam
COOLING_FLOOR_FLOW = 0.25  # clogged heat-sinks keep at least this share of conductance


@dataclass
class Forcing:
    """Weather forcing on a uniform time grid (leading axis is time)."""

    dt_s: float
    t_air_k: np.ndarray
    dew_c: np.ndarray
    wind10_ms: np.ndarray
    dni: np.ndarray
    dhi: np.ndarray
    ghi: np.ndarray
    sin_elev: np.ndarray
    cos_elev: np.ndarray
    solar_hour: np.ndarray
    pm10: np.ndarray
    precip_mm_h: np.ndarray
    p_pa: float = P_SEA_LEVEL

    @property
    def n(self) -> int:
        return int(self.t_air_k.shape[0])


@dataclass
class Loads:
    """Electrical and mechanical loads. Fields are floats, (B,) or (B, K) arrays.

    ``(B, K)`` arrays are indexed by simulation step; anything else is constant.
    """

    p_compute_w: float | np.ndarray = 0.0
    p_lidar_w: float | np.ndarray = 0.0
    p_comms_w: float | np.ndarray = 0.0
    p_drive_mech_w: float | np.ndarray = 0.0
    p_payload_w: float | np.ndarray = 0.0


@dataclass
class State:
    """Dynamic state: node temperatures (K), state of charge and dust loading (g m^-2)."""

    t_k: np.ndarray  # (B, 6)
    soc: np.ndarray  # (B,)
    dust: np.ndarray  # (B,)

    def copy(self) -> State:
        return State(self.t_k.copy(), self.soc.copy(), self.dust.copy())

    def take(self, idx) -> State:
        return State(self.t_k[idx], self.soc[idx], self.dust[idx])

    @property
    def batch(self) -> int:
        return int(self.t_k.shape[0])


@dataclass
class SimResult:
    rec_step: np.ndarray  # (R,) step index of each record
    t_k: np.ndarray  # (B, R, 6)
    t_die_k: np.ndarray  # (B, R)
    soc: np.ndarray  # (B, R)
    dust: np.ndarray  # (B, R)
    peak_k: np.ndarray  # (B, 6) maximum over every step
    peak_die_k: np.ndarray  # (B,)
    peak_c_rate: np.ndarray  # (B,)
    age_equiv_s: np.ndarray  # (B,) seconds at 25 degC equivalent
    min_soc: np.ndarray  # (B,)
    saturated: np.ndarray  # (B,) bool, demand exceeded maximum deliverable power
    energy_residual_w: float | None
    end: State
    dt_s: float


@dataclass
class ThermalParams:
    """Batched model parameters (each field is a float or an (n,) array)."""

    # geometry
    a_top: np.ndarray
    a_side: np.ndarray
    a_bot: np.ndarray
    side_proj: np.ndarray  # heading-averaged vertical projected area per unit cos(elevation), m^2
    height: np.ndarray
    char_length: np.ndarray
    # optics
    alpha_clean: np.ndarray
    alpha_dust: np.ndarray
    emissivity: np.ndarray
    dust_m0: np.ndarray
    # capacities
    c_shell: np.ndarray
    c_int: np.ndarray
    c_bat: np.ndarray
    c_cmp: np.ndarray
    c_lid: np.ndarray
    c_mot: np.ndarray
    # couplings
    ua_si: np.ndarray
    ua_bi: np.ndarray
    ua_ci: np.ndarray
    ua_li: np.ndarray
    ua_la: np.ndarray
    ua_mi: np.ndarray
    ua_ma: np.ndarray
    h_bot: np.ndarray
    vent_flow: np.ndarray
    filter_ref: np.ndarray
    # lidar optics
    lidar_area: np.ndarray
    lidar_alpha: np.ndarray
    # cooling
    cool_cap: np.ndarray
    cool_cop: np.ndarray
    cool_set_k: np.ndarray
    cool_gain: np.ndarray
    # electrical
    pack: battery.PackSpec
    ageing_ea: np.ndarray
    eta_dcdc: np.ndarray
    eta_drive: np.ndarray
    motor_loss_frac: np.ndarray
    payload_heat_frac: np.ndarray
    die_rise: np.ndarray
    # environment
    albedo: np.ndarray
    ground_rise: np.ndarray
    wind_exp: np.ndarray
    v_dep: np.ndarray
    rain_clear: np.ndarray
    # forecast-error realisations (Monte Carlo)
    d_temp_k: np.ndarray = field(default_factory=lambda: np.zeros(1))
    irr_scale: np.ndarray = field(default_factory=lambda: np.ones(1))
    wind_scale: np.ndarray = field(default_factory=lambda: np.ones(1))

    @property
    def n(self) -> int:
        return int(np.atleast_1d(self.a_top).shape[0])

    # ------------------------------------------------------------------ builders
    @classmethod
    def from_profile(
        cls,
        profile: Profile,
        n: int = 1,
        mc: bool = False,
        rng: np.random.Generator | None = None,
        weather_sigma: tuple[float, float, float] = (1.5, 0.10, 0.25),
        sigma_scale: float = 1.0,
    ) -> ThermalParams:
        """Create parameters from a profile.

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
            out = base * rng.lognormal(mean=0.0, sigma=sig, size=n) if sig > 0 else np.full(n, base)
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
            d_temp = rng.normal(0.0, weather_sigma[0] * sigma_scale, n)
            irr = rng.lognormal(0.0, weather_sigma[1] * sigma_scale, n)
            wnd = rng.lognormal(0.0, weather_sigma[2] * sigma_scale, n)
            d_temp[0], irr[0], wnd[0] = 0.0, 1.0, 1.0
        alpha_clean = np.clip(val("surface.alpha_clean"), 0.05, 0.98)
        alpha_dust = np.clip(val("surface.alpha_dust"), 0.05, 0.98)
        return cls(
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

    # ------------------------------------------------------------------ batching
    def _map(self, fn) -> ThermalParams:
        kwargs = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, battery.PackSpec):
                kwargs[f.name] = replace(
                    v, **{pf.name: fn(getattr(v, pf.name)) for pf in fields(v)}
                )
            else:
                kwargs[f.name] = fn(v)
        return ThermalParams(**kwargs)

    def tile(self, reps: int) -> ThermalParams:
        """Repeat the whole sample set ``reps`` times (case-major batch layout)."""
        return self._map(lambda a: np.tile(np.atleast_1d(a), reps))

    def take(self, idx) -> ThermalParams:
        return self._map(lambda a: np.atleast_1d(a)[idx])

    def replace_values(self, **kwargs) -> ThermalParams:
        """Return a copy with selected fields replaced (arrays or scalars broadcast to n)."""
        out = {}
        for k, v in kwargs.items():
            out[k] = np.broadcast_to(np.asarray(v, dtype=float), (self.n,)).copy()
        return replace(self, **out)


def _at(x, k: int):
    """Value of a load/forcing field at step k (constant or per-step)."""
    a = np.asarray(x, dtype=float)
    if a.ndim == 2:
        return a[:, min(k, a.shape[1] - 1)]
    return a


def initial_state(
    params: ThermalParams, t_air_c: float, soc: float = 1.0, batch: int | None = None
) -> State:
    """All nodes at air temperature, given state of charge and clean surfaces."""
    n = batch if batch is not None else params.n
    t = np.full((n, 6), c_to_k(t_air_c))
    return State(t, np.full(n, soc), np.zeros(n))


def simulate(
    params: ThermalParams,
    forcing: Forcing,
    loads: Loads,
    state0: State,
    start_idx,
    n_steps: int,
    shade=0.0,
    record_every: int = 1,
    diagnose: bool = False,
) -> SimResult:
    """Integrate the network for ``n_steps`` from ``state0``.

    Args:
        params: batched parameters; ``params.n`` must equal the batch size.
        forcing: weather on a uniform grid; batch member ``b`` reads index
            ``start_idx[b] + k`` at step ``k`` (clamped to the last sample).
        loads: electrical and mechanical loads (constant or per step).
        state0: initial state with the same batch size.
        start_idx: scalar or (B,) integer start index into the forcing grid.
        n_steps: number of steps of ``forcing.dt_s``.
        shade: scalar or (B,) shade fraction in [0, 1] (reduces direct beam fully,
            diffuse half, and the ground temperature rise).
        record_every: store every n-th step (the last step is always stored).
        diagnose: also compute the maximum energy-balance residual in watts.
    """
    p = params
    st = state0.copy()
    bsz = st.batch
    dt = forcing.dt_s
    inv = 1.0 / dt
    start = np.broadcast_to(np.asarray(start_idx, dtype=int), (bsz,))
    shade_a = np.broadcast_to(np.asarray(shade, dtype=float), (bsz,))
    last = forcing.n - 1

    cap_ah = np.asarray(p.pack.capacity_ah, dtype=float)
    peak = st.t_k.copy()
    peak_die = np.zeros(bsz)
    peak_c = np.zeros(bsz)
    age = np.zeros(bsz)
    min_soc = st.soc.copy()
    saturated = np.zeros(bsz, dtype=bool)
    resid = 0.0

    rec_step, rec_t, rec_die, rec_soc, rec_dust = [], [], [], [], []

    def record(step: int, die: np.ndarray) -> None:
        rec_step.append(step)
        rec_t.append(st.t_k.copy())
        rec_die.append(die.copy())
        rec_soc.append(st.soc.copy())
        rec_dust.append(st.dust.copy())

    die0 = st.t_k[:, C] + p.die_rise * _at(loads.p_compute_w, 0)
    record(0, die0)
    peak_die = np.maximum(peak_die, die0)

    for k in range(n_steps):
        idx = np.minimum(start + k, last)
        tair = forcing.t_air_k[idx] + p.d_temp_k
        dew = forcing.dew_c[idx] + p.d_temp_k
        v10 = forcing.wind10_ms[idx] * p.wind_scale
        dni = forcing.dni[idx] * p.irr_scale
        dhi = forcing.dhi[idx] * p.irr_scale
        sin_e = forcing.sin_elev[idx]
        cos_e = forcing.cos_elev[idx]
        pm10 = forcing.pm10[idx]
        rain = forcing.precip_mm_h[idx]

        t_s, t_i, t_b, t_c, t_l, t_m = (st.t_k[:, j] for j in range(6))

        # --- solar input ------------------------------------------------------
        dni_eff = dni * (1.0 - shade_a)
        dhi_eff = dhi * (1.0 - DIFFUSE_SHADE_FACTOR * shade_a)
        beam_h = dni_eff * np.maximum(sin_e, 0.0)
        ghi_eff = beam_h + dhi_eff
        q_top = p.a_top * ghi_eff
        q_side = p.side_proj * dni_eff * cos_e + 0.5 * p.a_side * (dhi_eff + p.albedo * ghi_eff)
        alpha = dust.absorptance(p.alpha_clean, p.alpha_dust, st.dust, p.dust_m0)
        q_sol_s = alpha * (q_top + q_side)
        q_sol_l = p.lidar_alpha * p.lidar_area * ghi_eff

        # --- surroundings and external coefficients -------------------------
        t_sky = radiation.sky_temperature_k(tair, dew, forcing.solar_hour[idx])
        t_gnd = radiation.ground_temperature_k(tair, ghi_eff, p.ground_rise)
        # wind-profile exponent is per-sample: recompute the power law explicitly
        v_h = np.maximum(
            np.maximum(v10, 0.0) * (np.maximum(p.height, 0.1) / 10.0) ** p.wind_exp, 0.3
        )
        h_o = convection.h_outer(t_s, tair, v_h, p.char_length, forcing.p_pa)
        h_rs = radiation.h_rad(p.emissivity, t_s, t_sky)
        h_rg = radiation.h_rad(p.emissivity, t_s, t_gnd)
        g_air = h_o * (p.a_top + p.a_side)
        g_sky = h_rs * (p.a_top + 0.5 * p.a_side)
        g_gr = h_rg * 0.5 * p.a_side
        g_bot = p.h_bot * p.a_bot
        t_mix = 0.5 * (tair + t_gnd)

        clog = np.maximum(dust.clog_factor(st.dust, p.filter_ref), COOLING_FLOOR_FLOW)
        ua_ci = p.ua_ci * clog
        g_vent = air.density(tair, forcing.p_pa) * CP_AIR * p.vent_flow * clog

        # --- loads and heat sources -------------------------------------------
        p_c = _at(loads.p_compute_w, k)
        p_l = _at(loads.p_lidar_w, k)
        p_comms = _at(loads.p_comms_w, k)
        p_mech = _at(loads.p_drive_mech_w, k)
        p_pay = _at(loads.p_payload_w, k)
        drive_elec = p_mech / p.eta_drive
        drive_loss = drive_elec - p_mech
        q_m = p.motor_loss_frac * drive_loss
        q_int_static = (
            p_comms + (1.0 - p.motor_loss_frac) * drive_loss + p.payload_heat_frac * p_pay
        )
        bus_static = p_c + p_l + p_comms + drive_elec + p_pay

        q_cool = np.clip(p.cool_gain * (t_i - p.cool_set_k), 0.0, p.cool_cap)
        p_cool = q_cool / p.cool_cop
        bus = bus_static + p_cool
        p_bat = bus / p.eta_dcdc
        dcdc_loss = p_bat - bus

        v_oc = battery.ocv_pack(p.pack, st.soc)
        r_pack = battery.resistance_pack(p.pack, t_b, st.soc)
        cur, sat = battery.current_for_power(p_bat, v_oc, r_pack)
        q_b = battery.heat_w(cur, r_pack)
        q_int = q_int_static + dcdc_loss - q_cool
        q_c = p_c
        q_l = p_l + q_sol_l

        # --- assemble and solve ------------------------------------------------
        a = np.zeros((bsz, 6, 6))
        rhs = np.zeros((bsz, 6))
        a[:, S, S] = p.c_shell * inv + g_air + g_sky + g_gr + g_bot + p.ua_si
        a[:, S, I] = -p.ua_si
        rhs[:, S] = (
            p.c_shell * inv * t_s + q_sol_s + g_air * tair + g_sky * t_sky + (g_gr + g_bot) * t_gnd
        )

        a[:, I, I] = p.c_int * inv + p.ua_si + p.ua_bi + ua_ci + p.ua_li + p.ua_mi + g_vent
        a[:, I, S] = -p.ua_si
        a[:, I, B] = -p.ua_bi
        a[:, I, C] = -ua_ci
        a[:, I, L] = -p.ua_li
        a[:, I, M] = -p.ua_mi
        rhs[:, I] = p.c_int * inv * t_i + q_int + g_vent * tair

        a[:, B, B] = p.c_bat * inv + p.ua_bi
        a[:, B, I] = -p.ua_bi
        rhs[:, B] = p.c_bat * inv * t_b + q_b

        a[:, C, C] = p.c_cmp * inv + ua_ci
        a[:, C, I] = -ua_ci
        rhs[:, C] = p.c_cmp * inv * t_c + q_c

        a[:, L, L] = p.c_lid * inv + p.ua_la + p.ua_li
        a[:, L, I] = -p.ua_li
        rhs[:, L] = p.c_lid * inv * t_l + q_l + p.ua_la * tair

        a[:, M, M] = p.c_mot * inv + p.ua_ma + p.ua_mi
        a[:, M, I] = -p.ua_mi
        rhs[:, M] = p.c_mot * inv * t_m + q_m + p.ua_ma * t_mix

        t_new = np.linalg.solve(a, rhs[..., None])[..., 0]

        if diagnose:
            caps = np.stack([p.c_shell, p.c_int, p.c_bat, p.c_cmp, p.c_lid, p.c_mot], axis=1)
            storage = (caps * (t_new - st.t_k) * inv).sum(axis=1)
            q_in = q_sol_s + q_int + q_b + q_c + q_l + q_m
            tn = t_new
            q_out = (
                g_air * (tn[:, S] - tair)
                + g_sky * (tn[:, S] - t_sky)
                + (g_gr + g_bot) * (tn[:, S] - t_gnd)
                + g_vent * (tn[:, I] - tair)
                + p.ua_la * (tn[:, L] - tair)
                + p.ua_ma * (tn[:, M] - t_mix)
            )
            resid = max(resid, float(np.max(np.abs(q_in - q_out - storage))))

        # --- state updates ---------------------------------------------------
        st.t_k = t_new
        st.soc = battery.soc_after(st.soc, cur, dt, cap_ah)
        st.dust = np.where(rain >= p.rain_clear, 0.0, st.dust + p.v_dep * pm10 * 1e-6 * dt)
        age += battery.ageing_factor(t_new[:, B], p.ageing_ea) * dt
        peak = np.maximum(peak, t_new)
        die = t_new[:, C] + p.die_rise * p_c
        peak_die = np.maximum(peak_die, die)
        peak_c = np.maximum(peak_c, battery.c_rate(cur, cap_ah))
        min_soc = np.minimum(min_soc, st.soc)
        saturated |= sat

        step = k + 1
        if step % record_every == 0 or step == n_steps:
            record(step, die)

    return SimResult(
        rec_step=np.array(rec_step),
        t_k=np.stack(rec_t, axis=1),
        t_die_k=np.stack(rec_die, axis=1),
        soc=np.stack(rec_soc, axis=1),
        dust=np.stack(rec_dust, axis=1),
        peak_k=peak,
        peak_die_k=peak_die,
        peak_c_rate=peak_c,
        age_equiv_s=age,
        min_soc=min_soc,
        saturated=saturated,
        energy_residual_w=resid if diagnose else None,
        end=st,
        dt_s=dt,
    )


__all__ = [
    "K0",
    "NODES",
    "Forcing",
    "Loads",
    "SimResult",
    "State",
    "ThermalParams",
    "initial_state",
    "simulate",
]
