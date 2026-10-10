from __future__ import annotations

import pytest

from dhill.profiles.loader import load_builtin
from dhill.sensitivity import tornado
from dhill.weather import synthetic_weather

W = synthetic_weather("abu_dhabi", "summer_clear", days=2)
START = "2026-08-05T05:00"


@pytest.fixture(scope="module")
def report():
    return tornado(load_builtin("ugv_medium_inspection"), W, START)


def test_rows_sorted_and_shares_sum_to_one(report):
    swings = [r.swing_k for r in report.rows]
    assert swings == sorted(swings, reverse=True)
    assert sum(r.share for r in report.rows) == pytest.approx(1.0, abs=0.02)
    assert [r.rank for r in report.rows] == list(range(1, len(report.rows) + 1))


def test_fixed_parameters_excluded(report):
    keys = {r.key for r in report.rows}
    assert "battery.cells_series" not in keys  # sigma 0
    assert "cooling.setpoint_c" in keys  # measured, small but not zero


def test_irrelevant_parameter_has_no_thermal_effect(report):
    row = next(r for r in report.rows if r.key == "lidar.range_clear_m")
    assert row.swing_k == pytest.approx(0.0, abs=1e-6)


def test_measuring_gain_bounded_by_swing(report):
    for r in report.rows:
        assert 0 <= r.measured_gain_k <= r.swing_k + 1e-9


def test_tightening_a_parameter_reduces_its_rank_effect():
    prof = load_builtin("ugv_medium_inspection")
    wide = tornado(prof, W, START)
    top = wide.rows[0].key
    tight = prof.with_overrides({top: prof.value(top)}, source="measured")  # sigma 2%
    narrow = tornado(tight, W, START)
    assert next(r for r in narrow.rows if r.key == top).swing_k < wide.rows[0].swing_k
    assert narrow.total_sd_k < wide.total_sd_k
