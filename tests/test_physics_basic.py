"""Unit tests for the physical building blocks against textbook values."""

from __future__ import annotations

import numpy as np
import pytest

from dhill.physics import air, battery, convection, dust, radiation, solar
from dhill.physics.constants import c_to_k, k_to_c, pressure_at_elevation


def test_temperature_roundtrip():
    assert k_to_c(c_to_k(37.5)) == pytest.approx(37.5)


def test_pressure_drops_with_elevation():
    assert pressure_at_elevation(0) == pytest.approx(101325, rel=1e-3)
    assert pressure_at_elevation(1000) == pytest.approx(89875, rel=0.01)


def test_air_properties_textbook():
    # air at 300 K, 1 atm: rho 1.177, mu 1.85e-5, k 0.0263, Pr 0.707
    assert air.density(300.0) == pytest.approx(1.177, rel=0.01)
    assert air.viscosity(300.0) == pytest.approx(1.846e-5, rel=0.02)
    assert air.conductivity(300.0) == pytest.approx(0.0263, rel=0.02)
    assert air.prandtl(300.0) == pytest.approx(0.707, rel=0.03)


def test_dew_point_magnus():
    assert air.dew_point_c(25.0, 60.0) == pytest.approx(16.7, abs=0.4)
    assert air.dew_point_c(40.0, 100.0) == pytest.approx(40.0, abs=0.2)


def test_solar_noon_elevation_dubai_midsummer():
    # 21 June, solar noon at lon 55.3 is about 08:21 UTC; sun almost overhead at 25.2 N
    t = np.array(["2026-06-21T08:21:00"], dtype="datetime64[s]")
    elev, _ = solar.solar_position(t, 25.2, 55.3)
    assert np.degrees(elev[0]) == pytest.approx(90 - 25.2 + 23.44, abs=0.8)


def test_sun_below_horizon_at_night():
    t = np.array(["2026-08-05T20:00:00"], dtype="datetime64[s]")
    elev, _ = solar.solar_position(t, 24.45, 54.38)
    assert elev[0] < 0


def test_clear_sky_magnitudes_and_night():
    elev = np.radians(np.array([-5.0, 30.0, 85.0]))
    dni, dhi, ghi = solar.clear_sky(elev, 0.0)
    assert dni[0] == 0 and ghi[0] == 0
    assert 900 < ghi[2] < 1150
    assert ghi[2] > ghi[1] > 0


def test_forced_convection_flat_plate_textbook():
    # Nu = 0.664 Re^0.5 Pr^(1/3) laminar
    nu = convection.nusselt_forced_plate(1e5, 0.7)
    assert nu == pytest.approx(0.664 * 1e5**0.5 * 0.7 ** (1 / 3), rel=0.15)


def test_h_outer_increases_with_wind_and_is_positive():
    h_calm = convection.h_outer(330.0, 310.0, 0.3, 0.6)
    h_wind = convection.h_outer(330.0, 310.0, 6.0, 0.6)
    assert 2.0 < h_calm < 15.0
    assert h_wind > 2 * h_calm


def test_wind_profile_reduces_at_low_height():
    assert convection.wind_at_height(5.0, 0.5, 0.2) < 5.0


def test_sky_temperature_below_air_and_h_rad_scale():
    t_sky = radiation.sky_temperature_k(c_to_k(40.0), 20.0, 12.0)
    assert t_sky < c_to_k(40.0)
    assert 5.0 < radiation.h_rad(0.9, 330.0, 310.0) < 8.0


def test_shade_reduces_ground_temperature():
    sun = radiation.ground_temperature_k(c_to_k(40), 900.0, 25.0, 0.0)
    shade = radiation.ground_temperature_k(c_to_k(40), 900.0, 25.0, 1.0)
    assert sun > shade >= c_to_k(40)


def test_dust_deposition_accumulates_and_rain_resets():
    pm = np.full(100, 1000.0)
    rain = np.zeros(100)
    rain[60] = 5.0
    m = dust.deposition_series(pm, rain, 600.0, 0.004)
    assert m[59] > m[0] > 0
    assert m[60] == 0
    assert m[-1] < m[59]
    # 1000 ug/m3 * 0.004 m/s * 600 s = 2.4e-3 g/m2 per step
    assert m[0] == pytest.approx(2.4e-3, rel=1e-6)


def test_absorptance_and_clog_limits():
    assert dust.absorptance(0.5, 0.7, 0.0, 2.0) == pytest.approx(0.5)
    assert 0.5 < dust.absorptance(0.5, 0.7, 20.0, 2.0) <= 0.7
    assert dust.clog_factor(0.0, 5.0) == 1.0
    assert dust.clog_factor(5.0, 5.0) == pytest.approx(0.5)


def test_lidar_range_lambert_solution_satisfies_equation():
    r0 = 40.0
    for sigma in (1e-4, 1e-3, 1e-2, 0.1):
        r = float(dust.lidar_range_m(r0, sigma))
        assert r * np.exp(sigma * r) == pytest.approx(r0, rel=1e-6)
    assert float(dust.lidar_range_m(r0, 0.0)) == r0


def test_lidar_range_monotonic_in_concentration():
    sig = dust.extinction_per_m(np.array([10.0, 500.0, 3000.0]), 0.7)
    r = dust.lidar_range_m(40.0, sig)
    assert r[0] > r[1] > r[2] > 0


def test_max_safe_speed_satisfies_stopping_distance():
    v = float(dust.max_safe_speed_ms(30.0, 1.0, 0.6, 3.0))
    assert v * 0.6 + v**2 / 2.0 + 3.0 == pytest.approx(30.0, rel=1e-9)
    assert float(dust.max_safe_speed_ms(2.0, 1.0, 0.6, 3.0)) == pytest.approx(0.0, abs=1e-9)


@pytest.fixture
def pack():
    return battery.PackSpec(14, 6, 5.0, 0.025, 20000.0, 3.40, 0.75)


def test_pack_energy_close_to_expected(pack):
    assert 1300 < pack.energy_wh < 1800


def test_resistance_falls_when_warm(pack):
    assert battery.resistance_pack(pack, 320.0, 0.8) < battery.resistance_pack(pack, 280.0, 0.8)


def test_current_for_power_reproduces_power(pack):
    v = battery.ocv_pack(pack, 0.8)
    r = battery.resistance_pack(pack, 305.0, 0.8)
    i, sat = battery.current_for_power(500.0, v, r)
    assert not np.any(sat)
    assert (v - i * r) * i == pytest.approx(500.0, rel=1e-9)
    assert battery.heat_w(i, r) == pytest.approx(i**2 * r)


def test_ageing_doubles_roughly_every_ten_kelvin(pack):
    ratio = battery.ageing_factor(c_to_k(45.0), 50000.0) / battery.ageing_factor(
        c_to_k(35.0), 50000.0
    )
    assert 1.5 < ratio < 2.3
    assert battery.ageing_factor(c_to_k(25.0), 50000.0) == pytest.approx(1.0)
