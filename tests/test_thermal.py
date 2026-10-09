"""Invariants of the thermal network solver."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import make_forcing
from dhill.physics.thermal import Loads, ThermalParams, initial_state, simulate
from dhill.profiles.loader import load_builtin

STEP_PER_H = 12  # 300 s


def run(
    profile="ugv_medium_inspection",
    hours=3.0,
    start_h=10.0,
    loads=None,
    shade=0.0,
    forcing=None,
    params=None,
    **kw,
):
    f = forcing or make_forcing()
    p = params or ThermalParams.from_profile(load_builtin(profile))
    st = initial_state(p, 31.0, 0.95)
    loads = loads or Loads(p_compute_w=45, p_lidar_w=14, p_comms_w=8, p_drive_mech_w=300)
    return simulate(
        p, f, loads, st, int(start_h * STEP_PER_H), int(hours * STEP_PER_H), shade=shade, **kw
    )


def test_energy_balance_closes():
    r = run(diagnose=True)
    assert r.energy_residual_w is not None and r.energy_residual_w < 1e-6


def test_zero_load_night_relaxes_to_air_temperature():
    f = make_forcing(t_min_c=30.0, t_max_c=30.0, wind=2.0)
    p = ThermalParams.from_profile(load_builtin("sidewalk_delivery_robot"))
    st = initial_state(p, 30.0, 0.9)
    st.t_k[:] += 15.0  # start hot
    r = simulate(p, f, Loads(), st, 0, 18 * STEP_PER_H)  # night to sunrise, no loads
    assert np.all(r.end.t_k[0] < st.t_k[0])
    assert np.max(np.abs(r.end.t_k[0] - (30.0 + 273.15))) < 6.0


def test_more_load_is_hotter():
    lo = run(loads=Loads(p_compute_w=20, p_lidar_w=14, p_comms_w=8, p_drive_mech_w=100))
    hi = run(loads=Loads(p_compute_w=45, p_lidar_w=14, p_comms_w=8, p_drive_mech_w=400))
    assert np.all(hi.peak_k >= lo.peak_k - 1e-9)
    assert hi.peak_die_k[0] > lo.peak_die_k[0]


def test_shade_reduces_every_peak():
    sun = run(start_h=9.0, hours=5.0)
    shd = run(start_h=9.0, hours=5.0, shade=1.0)
    assert np.all(shd.peak_k <= sun.peak_k + 1e-9)
    assert shd.peak_k[0, 0] < sun.peak_k[0, 0] - 3.0  # shell clearly cooler


def test_hotter_air_is_hotter_robot():
    cool = run(forcing=make_forcing(t_min_c=22, t_max_c=34))
    hot = run(forcing=make_forcing(t_min_c=31, t_max_c=46))
    assert hot.peak_die_k[0] > cool.peak_die_k[0]


def test_dust_raises_shell_peak_and_is_recorded():
    clean = run(forcing=make_forcing(pm10=5.0), hours=6.0, start_h=4.0)
    dusty = run(forcing=make_forcing(pm10=2000.0), hours=6.0, start_h=4.0)
    assert dusty.end.dust[0] > clean.end.dust[0] >= 0
    assert dusty.peak_k[0, 0] >= clean.peak_k[0, 0]


def test_soc_decreases_under_load_and_rest_holds():
    r = run(hours=1.0)
    assert r.soc[0, -1] < r.soc[0, 0]
    idle = run(hours=1.0, loads=Loads(p_comms_w=0.0))
    drop_idle = idle.soc[0, 0] - idle.soc[0, -1]  # standby and comms draw only
    drop_load = r.soc[0, 0] - r.soc[0, -1]
    assert 0 <= drop_idle < 0.2 * drop_load


def test_batch_matches_single_runs():
    prof = load_builtin("ugv_medium_inspection")
    p1 = ThermalParams.from_profile(prof, n=1)
    pb = ThermalParams.from_profile(prof, n=3)
    f = make_forcing()
    starts = np.array([9 * STEP_PER_H, 10 * STEP_PER_H, 11 * STEP_PER_H])
    loads = Loads(p_compute_w=45, p_lidar_w=14, p_comms_w=8, p_drive_mech_w=300)
    rb = simulate(pb, f, loads, initial_state(pb, 31.0, 0.95), starts, 2 * STEP_PER_H)
    for i, s in enumerate(starts):
        r1 = simulate(p1, f, loads, initial_state(p1, 31.0, 0.95), int(s), 2 * STEP_PER_H)
        assert rb.peak_die_k[i] == pytest.approx(r1.peak_die_k[0], abs=1e-9)


def test_monte_carlo_first_sample_is_nominal_and_spread_positive():
    prof = load_builtin("ugv_medium_inspection")
    nominal = ThermalParams.from_profile(prof, n=1)
    mc = ThermalParams.from_profile(prof, n=64, mc=True, rng=np.random.default_rng(1))
    f = make_forcing()
    loads = Loads(p_compute_w=45, p_lidar_w=14, p_comms_w=8, p_drive_mech_w=300)
    r0 = simulate(nominal, f, loads, initial_state(nominal, 31.0, 0.95), 10 * STEP_PER_H, 24)
    rm = simulate(mc, f, loads, initial_state(mc, 31.0, 0.95), 10 * STEP_PER_H, 24)
    assert rm.peak_die_k[0] == pytest.approx(r0.peak_die_k[0], abs=1e-9)
    assert np.std(rm.peak_die_k) > 0.3


def test_no_nan_and_physical_ranges_in_extreme_heat():
    f = make_forcing(t_min_c=36, t_max_c=51, wind=0.0, pm10=3000)
    r = run(forcing=f, hours=6.0, start_h=8.0)
    assert np.all(np.isfinite(r.t_k))
    assert np.all(r.t_k > 250) and np.all(r.t_k < 450)


def test_record_every_keeps_last_step():
    r = run(hours=1.0, record_every=5)
    assert r.rec_step[-1] == 1 * STEP_PER_H
