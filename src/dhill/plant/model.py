"""Independent plant simulator: a thirteen node thermal model of a small wheeled robot.

Purpose: provide a "true" robot whose structure differs from the six node engine in
``dhill.physics``, so that the engine can be tested against structural model error. The plant
shares no code with the engine and imports nothing from ``dhill.physics`` (guarded by
``tests/test_plant.py``). It is SYNTHETIC: a reasoned design, not a measurement of any robot.

Differences from the engine, on purpose:

* The shell is four body faces and a top plate. Each face receives beam sun by its own azimuth.
* Chassis and interior air are separate nodes. Battery has a core and a surface; the compute
  module has a die and a heat sink with its own capacities.
* Internal convection is nonlinear (natural convection, conductance rises with temperature difference).
* External convection mixes forced and natural terms; wind uses a logarithmic profile.
* Ground temperature lags the air by a first order time constant.
* The battery has a polarisation branch; converter and drive efficiency depend on load.
* Beam and diffuse irradiance come from an Erbs decomposition of measured global irradiance.
* Shade moves with the sun; gusts, cloud flicker and dust fronts act on a minute scale.

Temperatures are kelvin inside the solver. Every array has a leading batch dimension.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import numpy as np

SIGMA = 5.670374419e-8
K0 = 273.15
RHO_CP_AIR = 1200.0  # J m^-3 K^-1, near 40 degC at sea level

NODE_NAMES = (
    "top",
    "front",
    "right",
    "back",
    "left",
    "air",
    "chassis",
    "batt_surface",
    "batt_core",
    "heatsink",
    "die",
    "lidar",
    "motor",
)
TOP, FRONT, RIGHT, BACK, LEFT, AIR, CHASSIS, BSURF, BCORE, HSINK, DIE, LIDAR, MOTOR = range(13)
N = 13


# ---------------------------------------------------------------------------- solar geometry
def solar_geometry(times_utc, lat_deg: float, lon_deg: float):
    """Elevation and azimuth (rad, azimuth clockwise from north), Cooper declination."""
    t = np.asarray(times_utc).astype("datetime64[s]")
    day = t.astype("datetime64[D]")
    doy = (day - day.astype("datetime64[Y]")).astype(float) + 1.0
    hour_utc = (t - day).astype("timedelta64[s]").astype(float) / 3600.0
    decl = np.radians(23.45) * np.sin(2.0 * np.pi * (284.0 + doy) / 365.0)
    b = 2.0 * np.pi * (doy - 81.0) / 364.0
    eot_min = 9.87 * np.sin(2.0 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)
    solar_time = hour_utc + lon_deg / 15.0 + eot_min / 60.0
    ha = np.radians(15.0 * (solar_time - 12.0))
    lat = np.radians(lat_deg)
    sin_el = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
    el = np.arcsin(np.clip(sin_el, -1.0, 1.0))
    cos_el = np.maximum(np.cos(el), 1e-6)
    cos_az = (np.sin(decl) - np.sin(el) * np.sin(lat)) / (cos_el * np.cos(lat))
    az = np.arccos(np.clip(cos_az, -1.0, 1.0))
    az = np.where(ha > 0.0, 2.0 * np.pi - az, az)
    return el, az, doy


def erbs_split(ghi, sin_el, doy):
    """Beam normal and diffuse horizontal irradiance from global horizontal (Erbs correlation)."""
    ghi = np.maximum(ghi, 0.0)
    i0 = 1361.0 * (1.0 + 0.033 * np.cos(2.0 * np.pi * doy / 365.0))
    se = np.maximum(sin_el, 0.0)
    kt = np.where(se > 0.05, np.clip(ghi / (i0 * np.maximum(se, 0.05)), 0.0, 1.0), 0.0)
    kd = np.where(
        kt <= 0.22,
        1.0 - 0.09 * kt,
        np.where(
            kt <= 0.80,
            0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4,
            0.165,
        ),
    )
    dhi = np.where(se > 0.05, kd * ghi, ghi)
    dni = np.where(se > 0.05, np.clip((ghi - dhi) / np.maximum(se, 0.05), 0.0, 1100.0), 0.0)
    return dni, dhi


# ---------------------------------------------------------------------------- parameters
@dataclass
class PlantParams:
    """Batched plant parameters; every field is an array of shape (B,)."""

    length: np.ndarray
    width: np.ndarray
    height: np.ndarray
    c_top: np.ndarray
    c_side: np.ndarray
    c_air: np.ndarray
    c_chassis: np.ndarray
    c_bsurf: np.ndarray
    c_bcore: np.ndarray
    c_hsink: np.ndarray
    c_die: np.ndarray
    c_lidar: np.ndarray
    c_motor: np.ndarray
    alpha_paint: np.ndarray
    alpha_dust: np.ndarray
    eps: np.ndarray
    lidar_alpha: np.ndarray
    lidar_area: np.ndarray
    albedo: np.ndarray
    g_panel_chassis: np.ndarray
    h_int0: np.ndarray
    a_chassis_air: np.ndarray
    g_chassis_ground: np.ndarray
    a_batt: np.ndarray
    g_bs_chassis: np.ndarray
    g_core_surf: np.ndarray
    g_die_hs: np.ndarray
    g_hs_air: np.ndarray
    g_hs_chassis: np.ndarray
    g_lidar_chassis: np.ndarray
    a_lidar_ext: np.ndarray
    g_motor_chassis: np.ndarray
    a_motor_ext: np.ndarray
    q_inf0: np.ndarray
    q_inf1: np.ndarray
    z0: np.ndarray
    ground_tau_s: np.ndarray
    ground_gain: np.ndarray
    cells_s: np.ndarray
    cells_p: np.ndarray
    cell_ah: np.ndarray
    r25_cell: np.ndarray
    r_ea: np.ndarray
    r1_frac: np.ndarray
    tau1_s: np.ndarray
    dcdc_pk: np.ndarray
    drive_pk: np.ndarray
    drive_p0: np.ndarray
    motor_frac: np.ndarray
    payload_heat_frac: np.ndarray
    wheel_heat_frac: np.ndarray
    p_comp_idle: np.ndarray
    p_comp_max: np.ndarray
    p_lidar_on: np.ndarray
    p_elec: np.ndarray
    v_dep0: np.ndarray
    v_dep1: np.ndarray
    m_half: np.ndarray
    m_clog: np.ndarray

    @property
    def n(self) -> int:
        return int(self.length.shape[0])

    def take(self, idx) -> PlantParams:
        return PlantParams(**{f.name: getattr(self, f.name)[idx] for f in fields(self)})

    def tile(self, reps: int) -> PlantParams:
        return PlantParams(**{f.name: np.tile(getattr(self, f.name), reps) for f in fields(self)})

    def repeat(self, reps: int) -> PlantParams:
        return PlantParams(**{f.name: np.repeat(getattr(self, f.name), reps) for f in fields(self)})


# nominal design values with the relative spread of a plausible build. The body size and the pack
# layout follow the manufacturer datasheet of the reference robot; everything thermal is reasoned
# from geometry, masses and textbook correlations, not copied from the engine's profile.
_NOMINAL = {
    # name: (value, relative sigma, low clip, high clip)
    "c_top": (1300.0, 0.25, 600.0, 2600.0),
    "c_side": (650.0, 0.25, 300.0, 1300.0),
    "c_air": (500.0, 0.30, 200.0, 1200.0),
    "c_chassis": (6000.0, 0.20, 3000.0, 10000.0),
    "c_bsurf": (450.0, 0.25, 200.0, 900.0),
    "c_bcore": (900.0, 0.20, 500.0, 1600.0),
    "c_hsink": (280.0, 0.30, 100.0, 600.0),
    "c_die": (12.0, 0.30, 5.0, 30.0),
    "c_lidar": (300.0, 0.30, 120.0, 600.0),
    "c_motor": (1100.0, 0.25, 500.0, 2200.0),
    "alpha_paint": (0.50, 0.18, 0.30, 0.85),
    "alpha_dust": (0.68, 0.08, 0.55, 0.80),
    "eps": (0.90, 0.04, 0.80, 0.97),
    "lidar_alpha": (0.80, 0.08, 0.6, 0.95),
    "lidar_area": (0.02, 0.30, 0.008, 0.05),
    "albedo": (0.32, 0.20, 0.20, 0.45),
    "g_panel_chassis": (1.8, 0.40, 0.6, 4.0),
    "h_int0": (1.7, 0.20, 1.1, 2.4),
    "a_chassis_air": (0.55, 0.20, 0.3, 0.9),
    "g_chassis_ground": (4.5, 0.35, 1.8, 9.0),
    "a_batt": (0.08, 0.20, 0.05, 0.12),
    "g_bs_chassis": (1.4, 0.45, 0.4, 3.5),
    "g_core_surf": (4.0, 0.40, 1.5, 9.0),
    "g_die_hs": (5.0, 0.30, 2.5, 9.0),
    "g_hs_air": (1.0, 0.35, 0.4, 2.2),
    "g_hs_chassis": (2.6, 0.45, 0.8, 6.0),
    "g_lidar_chassis": (0.5, 0.45, 0.15, 1.4),
    "a_lidar_ext": (0.03, 0.30, 0.012, 0.07),
    "g_motor_chassis": (2.2, 0.40, 0.8, 5.0),
    "a_motor_ext": (0.06, 0.30, 0.025, 0.12),
    "q_inf0": (0.0006, 0.50, 0.0001, 0.002),
    "q_inf1": (0.0003, 0.50, 0.00005, 0.001),
    "z0": (0.03, 0.40, 0.005, 0.1),
    "ground_tau_s": (1800.0, 0.35, 600.0, 4000.0),
    "ground_gain": (20.0, 0.25, 10.0, 35.0),
    "cell_ah": (5.4, 0.04, 4.5, 6.0),
    "r25_cell": (0.028, 0.25, 0.015, 0.06),
    "r_ea": (22000.0, 0.15, 14000.0, 32000.0),
    "r1_frac": (0.6, 0.30, 0.2, 1.2),
    "tau1_s": (45.0, 0.40, 15.0, 120.0),
    "dcdc_pk": (0.92, 0.025, 0.85, 0.96),
    "drive_pk": (0.80, 0.07, 0.62, 0.90),
    "drive_p0": (6.0, 0.40, 2.0, 14.0),
    "motor_frac": (0.62, 0.15, 0.4, 0.8),
    "payload_heat_frac": (0.5, 0.2, 0.25, 0.8),
    "wheel_heat_frac": (0.10, 0.4, 0.03, 0.25),
    "p_comp_idle": (10.0, 0.25, 5.0, 18.0),
    "p_comp_max": (35.0, 0.12, 24.0, 45.0),
    "p_lidar_on": (8.0, 0.25, 4.0, 14.0),
    "p_elec": (13.0, 0.25, 7.0, 22.0),
    "v_dep0": (0.0025, 0.5, 0.0008, 0.008),
    "v_dep1": (0.0006, 0.5, 0.0001, 0.0018),
    "m_half": (3.0, 0.4, 1.0, 8.0),
    "m_clog": (3.0, 0.5, 1.0, 9.0),
}


def draw_plants(n: int, seed: int, spread: float = 1.0) -> PlantParams:
    """Draw ``n`` plausible robots around the nominal design. ``spread`` scales every sigma."""
    rng = np.random.default_rng(seed)
    out = {}
    for name, (v, sig, lo, hi) in _NOMINAL.items():
        out[name] = np.clip(v * np.exp(spread * sig * rng.standard_normal(n)), lo, hi)
    one = np.ones(n)
    out["length"] = 0.508 * one
    out["width"] = 0.430 * one
    out["height"] = 0.250 * one
    out["cells_s"] = 7.0 * one
    out["cells_p"] = 2.0 * one
    return PlantParams(**out)


def nominal_plant(n: int = 1) -> PlantParams:
    return draw_plants(n, 0, spread=0.0)


# ---------------------------------------------------------------------------- forcing and drive
@dataclass
class PlantForcing:
    """Weather on the plant time grid, arrays of shape (B, T)."""

    dt_s: float
    t_air_c: np.ndarray
    dew_c: np.ndarray
    wind10: np.ndarray
    dni: np.ndarray
    dhi: np.ndarray
    ghi: np.ndarray
    sin_el: np.ndarray
    cos_el: np.ndarray
    azimuth: np.ndarray
    pm10: np.ndarray
    rain_mm_h: np.ndarray
    solar_hour: np.ndarray

    @property
    def steps(self) -> int:
        return int(self.t_air_c.shape[1])


@dataclass
class PlantDrive:
    """Loads, motion and shading, arrays of shape (B, T)."""

    p_comp: np.ndarray
    p_lidar: np.ndarray
    p_elec: np.ndarray
    p_mech: np.ndarray
    p_payload: np.ndarray
    speed: np.ndarray
    heading: np.ndarray
    shade_beam: np.ndarray  # share of the beam blocked, 0 to 1


@dataclass
class PlantTrace:
    dt_s: float
    t_k: np.ndarray  # (B, T+1, N)
    soc: np.ndarray  # (B, T+1)
    dust_g_m2: np.ndarray  # (B,) at the end
    p_bat: np.ndarray  # (B, T)
    current: np.ndarray  # (B, T)
    heat_in: np.ndarray  # (B, T) total heat entering the nodes
    residual_w: float | None = None

    def temps_c(self) -> np.ndarray:
        return self.t_k - K0


@dataclass
class PlantState:
    t_k: np.ndarray  # (B, N)
    soc: np.ndarray
    v1: np.ndarray
    t_ground_k: np.ndarray
    dust: np.ndarray
    foul: np.ndarray

    @classmethod
    def at_ambient(cls, t_air_c: np.ndarray, soc: float = 0.95, dust=0.0, foul=0.0):
        b = t_air_c.shape[0]
        t = np.repeat((t_air_c + K0)[:, None], N, axis=1)
        return cls(
            t,
            np.full(b, soc),
            np.zeros(b),
            t[:, 0].copy(),
            np.broadcast_to(np.asarray(dust, dtype=float), (b,)).copy(),
            np.broadcast_to(np.asarray(foul, dtype=float), (b,)).copy(),
        )

    def copy(self) -> PlantState:
        return PlantState(
            self.t_k.copy(),
            self.soc.copy(),
            self.v1.copy(),
            self.t_ground_k.copy(),
            self.dust.copy(),
            self.foul.copy(),
        )


# ---------------------------------------------------------------------------- component laws
def _ocv_cell(soc):
    s = np.clip(soc, 0.0, 1.0)
    return 3.20 + 0.90 * s - 0.35 * s**2 + 0.35 * s**3


def _r_cell(p: PlantParams, t_k, soc):
    arr = np.exp(p.r_ea / 8.314 * (1.0 / np.maximum(t_k, 230.0) - 1.0 / 298.15))
    return p.r25_cell * arr * (1.0 + 0.6 * (1.0 - np.clip(soc, 0.0, 1.0)) ** 2)


def _sky_temp(t_air_k, dew_c, solar_hour):
    eps = (
        0.711 + 0.0056 * dew_c + 7.3e-5 * dew_c**2 + 0.013 * np.cos(2.0 * np.pi * solar_hour / 24.0)
    )
    return t_air_k * np.clip(eps, 0.6, 1.0) ** 0.25


def _h_mixed(dt_k, v, c_nat):
    h_f = 5.7 + 3.8 * v
    h_n = c_nat * np.abs(dt_k) ** (1.0 / 3.0)
    return (h_f**3 + h_n**3) ** (1.0 / 3.0)


def _h_rad(eps, ts, tr):
    return eps * SIGMA * (ts**2 + tr**2) * (ts + tr)


def _add(a, i, j, g):
    a[:, i, i] += g
    a[:, j, j] += g
    a[:, i, j] -= g
    a[:, j, i] -= g


# ---------------------------------------------------------------------------- simulation
def simulate_plant(
    p: PlantParams,
    forc: PlantForcing,
    drv: PlantDrive,
    state0: PlantState,
    diagnose: bool = False,
) -> PlantTrace:
    """Integrate the plant with backward Euler; coefficients use the previous step."""
    b = p.n
    dt = forc.dt_s
    inv = 1.0 / dt
    steps = forc.steps
    st = state0.copy()

    area_top = p.length * p.width
    area_fb = p.width * p.height  # front and back faces
    area_lr = p.length * p.height  # left and right faces
    a_face = np.stack([area_top, area_fb, area_lr, area_fb, area_lr], axis=1)  # (B,5)
    a_panels = a_face.sum(axis=1)
    caps = np.zeros((b, N))
    caps[:, TOP] = p.c_top
    for k in (FRONT, BACK):
        caps[:, k] = p.c_side * area_fb / (0.5 * (area_fb + area_lr))
    for k in (RIGHT, LEFT):
        caps[:, k] = p.c_side * area_lr / (0.5 * (area_fb + area_lr))
    caps[:, AIR] = p.c_air
    caps[:, CHASSIS] = p.c_chassis
    caps[:, BSURF] = p.c_bsurf
    caps[:, BCORE] = p.c_bcore
    caps[:, HSINK] = p.c_hsink
    caps[:, DIE] = p.c_die
    caps[:, LIDAR] = p.c_lidar
    caps[:, MOTOR] = p.c_motor

    cap_pack_ah = p.cell_ah * p.cells_p
    ns_over_np = p.cells_s / p.cells_p
    t_hist = np.empty((b, steps + 1, N))
    soc_hist = np.empty((b, steps + 1))
    pbat_hist = np.empty((b, steps))
    cur_hist = np.empty((b, steps))
    qin_hist = np.empty((b, steps))
    t_hist[:, 0] = st.t_k
    soc_hist[:, 0] = st.soc
    resid = 0.0

    face_off = np.array([0.0, 0.0, 0.5 * np.pi, np.pi, 1.5 * np.pi])  # body face normal offsets

    for k in range(steps):
        tk = st.t_k
        t_air = forc.t_air_c[:, k] + K0
        v10 = forc.wind10[:, k]
        # wind at robot height, logarithmic profile over rough ground
        h_ref = np.maximum(0.5 * p.height, 0.05)
        v_w = np.maximum(v10 * np.log(h_ref / p.z0) / np.log(10.0 / p.z0), 0.15)
        speed = drv.speed[:, k]
        v_rel = np.sqrt(v_w**2 + speed**2)

        # solar input by face
        dni = forc.dni[:, k] * (1.0 - drv.shade_beam[:, k])
        dhi = forc.dhi[:, k] * (1.0 - 0.5 * drv.shade_beam[:, k])
        ghi = forc.ghi[:, k]
        sin_el = np.maximum(forc.sin_el[:, k], 0.0)
        cos_el = forc.cos_el[:, k]
        az = forc.azimuth[:, k]
        ghi_eff = dni * sin_el + dhi
        i_face = np.zeros((b, 5))
        i_face[:, 0] = dni * sin_el + dhi
        for f in range(1, 5):
            normal = drv.heading[:, k] + face_off[f]
            beam = dni * cos_el * np.maximum(np.cos(az - normal), 0.0)
            i_face[:, f] = beam + 0.5 * dhi + 0.5 * p.albedo * ghi_eff
        dust_frac = st.dust / (st.dust + p.m_half)
        alpha_top = p.alpha_paint + (p.alpha_dust - p.alpha_paint) * dust_frac
        alpha_side = p.alpha_paint + (p.alpha_dust - p.alpha_paint) * 0.3 * dust_frac
        alpha = np.stack([alpha_top] + [alpha_side] * 4, axis=1)
        q_sol = alpha * a_face * i_face  # (B,5)
        q_sol_lidar = p.lidar_alpha * p.lidar_area * ghi_eff

        # surroundings
        t_sky = _sky_temp(t_air, forc.dew_c[:, k], forc.solar_hour[:, k])
        t_g = st.t_ground_k

        a = np.zeros((b, N, N))
        rhs = np.zeros((b, N))
        a[:, np.arange(N), np.arange(N)] += caps * inv
        rhs += caps * inv * tk

        # outer faces: convection, radiation, conduction to the air node
        for f in range(5):
            node = f
            ts = tk[:, node]
            c_nat = 1.5 if f == 0 else 1.25
            h_c = _h_mixed(ts - t_air, v_rel, c_nat)
            sky_view = 1.0 if f == 0 else 0.5
            h_rs = _h_rad(p.eps, ts, t_sky) * sky_view
            h_rg = _h_rad(p.eps, ts, t_g) * (1.0 - sky_view)
            g_ext = (h_c + h_rs + h_rg) * a_face[:, f]
            a[:, node, node] += g_ext
            rhs[:, node] += (h_c * a_face[:, f]) * t_air
            rhs[:, node] += (h_rs * a_face[:, f]) * t_sky + (h_rg * a_face[:, f]) * t_g
            rhs[:, node] += q_sol[:, f]
            h_in = np.maximum(p.h_int0 * np.abs(ts - tk[:, AIR]) ** 0.25, 1.5)
            _add(a, node, AIR, h_in * a_face[:, f])
            _add(a, node, CHASSIS, p.g_panel_chassis * a_face[:, f] / a_panels)

        # interior couplings
        h_ca = np.maximum(p.h_int0 * np.abs(tk[:, CHASSIS] - tk[:, AIR]) ** 0.25, 1.5)
        _add(a, CHASSIS, AIR, h_ca * p.a_chassis_air)
        g_cg = p.g_chassis_ground * (1.0 + 0.15 * speed)
        a[:, CHASSIS, CHASSIS] += g_cg
        rhs[:, CHASSIS] += g_cg * t_g
        h_ba = np.maximum(p.h_int0 * np.abs(tk[:, BSURF] - tk[:, AIR]) ** 0.25, 1.5)
        _add(a, BSURF, AIR, h_ba * p.a_batt)
        _add(a, BSURF, CHASSIS, p.g_bs_chassis)
        _add(a, BCORE, BSURF, p.g_core_surf)
        clog = 1.0 / (1.0 + st.foul / p.m_clog)
        _add(a, DIE, HSINK, p.g_die_hs)
        _add(a, HSINK, AIR, p.g_hs_air * clog)
        _add(a, HSINK, CHASSIS, p.g_hs_chassis)
        _add(a, LIDAR, CHASSIS, p.g_lidar_chassis)
        h_l = _h_mixed(tk[:, LIDAR] - t_air, v_rel, 1.25)
        g_l = h_l * p.a_lidar_ext
        a[:, LIDAR, LIDAR] += g_l
        rhs[:, LIDAR] += g_l * t_air + q_sol_lidar
        _add(a, MOTOR, CHASSIS, p.g_motor_chassis)
        h_m = 6.0 + 6.0 * v_rel
        g_m = h_m * p.a_motor_ext
        a[:, MOTOR, MOTOR] += g_m
        rhs[:, MOTOR] += g_m * t_air
        # infiltration of outside air through seals
        g_inf = RHO_CP_AIR * (p.q_inf0 + p.q_inf1 * v_w)
        a[:, AIR, AIR] += g_inf
        rhs[:, AIR] += g_inf * t_air

        # loads and heat sources
        p_mech = drv.p_mech[:, k]
        eta_d = np.where(p_mech > 0.1, p.drive_pk * p_mech / (p_mech + p.drive_p0), 1.0)
        p_drive_el = np.where(p_mech > 0.1, p_mech / np.maximum(eta_d, 0.05), 0.0)
        drive_loss = p_drive_el - p_mech
        p_bus = (
            drv.p_comp[:, k]
            + drv.p_lidar[:, k]
            + drv.p_elec[:, k]
            + p_drive_el
            + drv.p_payload[:, k]
        )
        x = p_bus / 150.0
        eta_c = np.clip(p.dcdc_pk - 0.10 * ((x - 0.6) / 0.6) ** 2, 0.70, 0.97)
        p_bat = p_bus / eta_c
        dcdc_loss = p_bat - p_bus

        # battery electrical state
        ocv = p.cells_s * _ocv_cell(st.soc)
        r0 = ns_over_np * _r_cell(p, tk[:, BCORE], st.soc)
        r1 = p.r1_frac * r0
        e_eff = ocv - st.v1
        disc = np.maximum(e_eff**2 - 4.0 * r0 * p_bat, 0.0)
        cur = (e_eff - np.sqrt(disc)) / (2.0 * r0)
        v1_new = (st.v1 + dt / p.tau1_s * cur * r1) / (1.0 + dt / p.tau1_s)
        q_core = cur**2 * r0 + v1_new**2 / np.maximum(r1, 1e-6)

        rhs[:, DIE] += drv.p_comp[:, k]
        rhs[:, LIDAR] += drv.p_lidar[:, k]
        rhs[:, MOTOR] += p.motor_frac * drive_loss
        rhs[:, AIR] += (
            drv.p_elec[:, k]
            + (1.0 - p.motor_frac) * drive_loss
            + p.payload_heat_frac * drv.p_payload[:, k]
            + dcdc_loss
        )
        rhs[:, CHASSIS] += p.wheel_heat_frac * p_mech
        rhs[:, BCORE] += q_core

        t_new = np.linalg.solve(a, rhs[..., None])[..., 0]

        if diagnose:
            q_in = rhs.sum(axis=1) - (caps * inv * tk).sum(axis=1)
            # heat leaving to boundaries is recovered from the assembled matrix: sum of columns
            # minus the storage term gives net outflow when temperatures are those of the new step
            storage = (caps * (t_new - tk) * inv).sum(axis=1)
            out = (a.sum(axis=1) * t_new).sum(axis=1) - (caps * inv * t_new).sum(axis=1)
            resid = max(resid, float(np.max(np.abs(q_in - out - storage))))

        # ground, dust, fouling, state of charge
        ghi_ground = np.maximum(ghi, 0.0)
        tg_target = t_air + p.ground_gain * ghi_ground / 1000.0
        st.t_ground_k = (st.t_ground_k + dt / p.ground_tau_s * tg_target) / (
            1.0 + dt / p.ground_tau_s
        )
        v_dep = p.v_dep0 + p.v_dep1 * v10
        pm = forc.pm10[:, k]
        dep = v_dep * pm * 1e-6 * dt
        resus = np.where(v10 > 8.0, np.exp(-dt / 10800.0), 1.0)
        st.dust = np.where(forc.rain_mm_h[:, k] >= 1.0, 0.0, (st.dust + dep) * resus)
        st.foul = st.foul + 0.5 * dep * (0.5 + v10 / 5.0)
        st.soc = np.clip(st.soc - cur * dt / (3600.0 * cap_pack_ah), 0.0, 1.0)
        st.v1 = v1_new
        st.t_k = t_new

        t_hist[:, k + 1] = t_new
        soc_hist[:, k + 1] = st.soc
        pbat_hist[:, k] = p_bat
        cur_hist[:, k] = cur
        qin_hist[:, k] = q_in_total(
            drv, k, p, p_drive_el, p_mech, dcdc_loss, q_core, q_sol, q_sol_lidar
        )

    trace = PlantTrace(dt, t_hist, soc_hist, st.dust.copy(), pbat_hist, cur_hist, qin_hist)
    trace.residual_w = resid if diagnose else None
    trace.end_state = st  # type: ignore[attr-defined]
    return trace


def q_in_total(drv, k, p, p_drive_el, p_mech, dcdc_loss, q_core, q_sol, q_sol_lidar):
    """Heat released inside the robot plus absorbed sun, for reporting."""
    return (
        drv.p_comp[:, k]
        + drv.p_lidar[:, k]
        + drv.p_elec[:, k]
        + (p_drive_el - p_mech)
        + p.payload_heat_frac * drv.p_payload[:, k]
        + p.wheel_heat_frac * p_mech
        + dcdc_loss
        + q_core
        + q_sol.sum(axis=1)
        + q_sol_lidar
    )
