"""Tests of the independent plant simulator (SYNTHETIC)."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from dhill.plant.model import (
    AIR,
    BCORE,
    DIE,
    PlantState,
    draw_plants,
    erbs_split,
    simulate_plant,
    solar_geometry,
)
from dhill.plant.rating import RATED_AMBIENT_C, acceptance_rate, draw_rated_plants, rated_mask
from dhill.plant.scenario import (
    DustEvent,
    Micro,
    PlantWeather,
    build_forcing,
    build_mission,
    build_shade,
    field_schedule,
)
from dhill.plant.sensors import SensorSpec, measure

PLANT_DIR = Path(__file__).parents[1] / "src" / "dhill" / "plant"


def _wx(t_air=45.0, ghi=0.0, wind=2.0, pm=0.0):
    times = np.array(["2024-07-15T00:00", "2024-07-16T00:00"], dtype="datetime64[s]")
    one = np.ones(2)
    return PlantWeather(
        times,
        t_air * one,
        (t_air - 20) * one,
        wind * one,
        ghi * one,
        pm * one,
        0 * one,
        24.45,
        54.38,
    )


def _run(
    n=1,
    t_air=45.0,
    ghi=0.0,
    hours=2.0,
    scale=1.0,
    shade="shelter",
    seed=1,
    micro=False,
    spread=0.0,
    dt=60.0,
):
    p = draw_plants(n, seed, spread)
    steps = int(hours * 3600 / dt)
    rng = np.random.default_rng(seed)
    f = build_forcing(_wx(t_air, ghi), np.full(n, 6 * 3600.0), steps, dt, rng, Micro(enabled=micro))
    d = build_mission(p, np.full(n, scale), 0, steps, dt, rng, stop_share=1e-6, sand_share=1e-6)
    d.shade_beam = build_shade(f, rng, shade)
    return p, f, d, simulate_plant(p, f, d, PlantState.at_ambient(np.full(n, t_air)), diagnose=True)


def _imports(path: Path) -> list[str]:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            out.append("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Import):
            out += [a.name for a in node.names]
    return out


def test_plant_imports_no_engine_physics():
    bad = [
        (f.name, m)
        for f in sorted(PLANT_DIR.glob("*.py"))
        for m in _imports(f)
        if m.startswith("..") or "dhill" in m or "physics" in m
    ]
    assert bad == []


def test_energy_balance_closes():
    _, _, _, tr = _run(hours=3.0, ghi=800.0, shade="none")
    assert tr.residual_w is not None and tr.residual_w < 1e-6


def test_temperature_rises_with_ambient():
    peaks = []
    for t in (30.0, 38.0, 46.0):
        _, _, _, tr = _run(t_air=t)
        peaks.append(tr.temps_c()[0, :, BCORE].max())
    assert peaks[0] < peaks[1] < peaks[2]


def test_sun_warms_and_shade_cools():
    _, _, _, sun = _run(ghi=900.0, shade="none")
    _, _, _, shade = _run(ghi=900.0, shade="shelter")
    assert sun.temps_c()[0, -1, AIR] > shade.temps_c()[0, -1, AIR]


def test_load_raises_die_temperature():
    _, _, _, lo = _run(scale=0.4)
    _, _, _, hi = _run(scale=1.0)
    assert hi.temps_c()[0, :, DIE].max() > lo.temps_c()[0, :, DIE].max()


def test_same_seed_same_result():
    _, _, _, a = _run(n=3, micro=True, spread=1.0, seed=5)
    _, _, _, b = _run(n=3, micro=True, spread=1.0, seed=5)
    assert np.array_equal(a.t_k, b.t_k)


def test_parked_robot_cools_toward_air():
    p = draw_plants(1, 3, 0.0)
    rng = np.random.default_rng(0)
    steps = 240
    f = build_forcing(_wx(30.0), np.array([6 * 3600.0]), steps, 60.0, rng, Micro(enabled=False))
    d = build_mission(p, np.zeros(1), 0, steps, 60.0, rng)
    d.shade_beam = np.ones((1, steps))
    hot = PlantState.at_ambient(np.array([30.0]))
    hot.t_k[:] += 20.0
    tr = simulate_plant(p, f, d, hot)
    assert tr.temps_c()[0, -1, AIR] < tr.temps_c()[0, 0, AIR] - 5.0


def test_most_draws_meet_the_rating_and_filtered_draws_all_do():
    assert 0.5 < acceptance_rate(seed=0, n=200) < 1.0
    kept = draw_rated_plants(10, 4)
    assert kept.n == 10 and rated_mask(kept).all()
    assert RATED_AMBIENT_C == 45.0


def test_solar_geometry_and_erbs_are_sane():
    t = np.array(
        ["2024-06-21T08:00", "2024-06-21T20:00"], dtype="datetime64[s]"
    )  # noon and midnight local
    el, az, doy = solar_geometry(t, 24.45, 54.38)
    assert np.degrees(el[0]) > 80.0 and el[1] < 0.0
    dni, dhi = erbs_split(np.array([900.0, 0.0]), np.sin(el), doy)
    assert 600.0 < dni[0] < 1100.0 and dhi[0] > 0.0 and dni[1] == 0.0


def test_dust_event_raises_pm10_and_cuts_beam():
    wx = _wx(40.0, ghi=800.0, pm=50.0)
    rng = np.random.default_rng(2)
    ev = DustEvent(onset_s=600.0)
    f = build_forcing(wx, np.array([6 * 3600.0]), 120, 60.0, rng, Micro(enabled=True, event=ev))
    g = build_forcing(
        wx, np.array([6 * 3600.0]), 120, 60.0, np.random.default_rng(2), Micro(enabled=True)
    )
    assert f.pm10[0, 40] > g.pm10[0, 40] + 500.0
    assert f.dni[0, 40] < g.dni[0, 40]


def test_shade_moves_with_the_sun_and_is_bounded():
    wx = _wx(40.0, ghi=800.0)
    rng = np.random.default_rng(1)
    f = build_forcing(wx, np.full(4, 2 * 3600.0), 480, 60.0, rng, Micro(enabled=False))
    s = build_shade(f, rng, "urban")
    assert s.shape == (4, 480) and s.min() >= 0.0 and s.max() <= 1.0 and 0.0 < s.mean() < 1.0


def test_field_schedule_drives_only_in_working_hours():
    sched = field_schedule(1, 24 * 60, 60.0, 0.0, np.random.default_rng(0))
    hours = np.arange(24 * 60) / 60.0
    assert sched[0, hours < 6.0].sum() == 0.0 and sched[0, hours >= 20.0].sum() == 0.0
    assert sched[0].max() <= 1.0 and sched[0].sum() > 0.0


def test_sensor_model_lags_adds_bias_and_gaps():
    p, f, d, tr = _run(hours=2.0, ghi=800.0, shade="none")
    rng = np.random.default_rng(0)
    clean = measure(tr, d, 0, rng, SensorSpec(enabled=False))
    noisy = measure(tr, d, 0, np.random.default_rng(0), SensorSpec(dropout_share=0.1))
    assert clean.temps_c["t_interior_c"].shape == noisy.temps_c["t_interior_c"].shape
    assert np.isnan(noisy.temps_c["t_interior_c"]).any()
    assert not np.isnan(noisy.temps_c["t_interior_c"][0])
    diff = np.nanmean(np.abs(noisy.temps_c["t_interior_c"] - clean.temps_c["t_interior_c"]))
    assert 0.05 < diff < 3.0
    assert set(noisy.loads) == {
        "p_compute_w",
        "p_lidar_w",
        "p_comms_w",
        "p_drive_mech_w",
        "p_payload_w",
    }
