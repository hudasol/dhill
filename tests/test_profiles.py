from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from dhill.profiles.loader import builtin_profile_ids, load_builtin, load_profile, profile_from_dict
from dhill.profiles.registry import PARAMS


def test_builtin_profiles_present():
    assert {
        "ugv_medium_inspection",
        "sidewalk_delivery_robot",
        "pv_cleaning_robot",
        "clearpath_jackal",
    } <= set(builtin_profile_ids())


@pytest.mark.parametrize("pid", builtin_profile_ids())
def test_builtin_profiles_valid_and_honest(pid):
    p = load_builtin(pid)
    assert p.evidence_level == "L0"
    assert p.assumption_fraction() > 0.5  # illustrative profiles must say so
    assert "L0" in p.evidence_text()
    for key in PARAMS:
        assert p.value(key) is not None


def test_sigma_follows_provenance_and_override():
    p = load_builtin("ugv_medium_inspection")
    assert p.sigma("battery.cells_series") == 0
    assert p.sigma("geometry.length_m") == pytest.approx(0.03)
    assert p.sigma("surface.alpha_clean") == pytest.approx(0.10)  # textbook


def test_unknown_parameter_rejected():
    import importlib.resources as r

    raw = yaml.safe_load(
        r.files("dhill.profiles.builtin").joinpath("pv_cleaning_robot.yaml").read_text()
    )
    raw["parameters"]["geometry"]["bogus"] = 1
    with pytest.raises(ValidationError):
        profile_from_dict(raw)


def test_out_of_bounds_rejected():
    import importlib.resources as r

    raw = yaml.safe_load(
        r.files("dhill.profiles.builtin").joinpath("pv_cleaning_robot.yaml").read_text()
    )
    raw["parameters"]["surface"]["emissivity"] = 1.7
    with pytest.raises(ValidationError):
        profile_from_dict(raw)


def test_calibrated_levels_require_provenance():
    import importlib.resources as r

    raw = yaml.safe_load(
        r.files("dhill.profiles.builtin").joinpath("pv_cleaning_robot.yaml").read_text()
    )
    raw["evidence_level"] = "L2"
    with pytest.raises(ValidationError):
        profile_from_dict(raw)


def test_with_overrides_does_not_mutate():
    p = load_builtin("ugv_medium_inspection")
    q = p.with_overrides({"surface.alpha_clean": 0.2})
    assert q.value("surface.alpha_clean") == 0.2
    assert p.value("surface.alpha_clean") == 0.40


def test_load_unknown_builtin():
    with pytest.raises(KeyError):
        load_profile("nope")


def test_jackal_matches_datasheet_energy_and_runtime():
    """Pack energy ~270 Wh and heavy use runtime ~2 h, from the manufacturer datasheet."""
    import numpy as np

    from dhill.loads import mission_loads

    p = load_builtin("clearpath_jackal")
    wh = (
        p.value("battery.cells_series")
        * p.value("battery.cells_parallel")
        * p.value("battery.cell_capacity_ah")
        * 3.6
    )
    assert wh == pytest.approx(270, rel=0.02)
    ld = mission_loads(p, np.array([1.0]), "drive")
    watts = float(
        ld.p_drive_mech_w[0] / p.value("motors.drive_efficiency")
        + (ld.p_compute_w[0] + ld.p_lidar_w[0] + ld.p_comms_w[0]) / p.value("power.dcdc_efficiency")
    )
    assert wh / watts == pytest.approx(2.0, rel=0.1)
    assert p.value("geometry.length_m") == pytest.approx(0.508)
    assert p.evidence_level == "L0"  # thermal parameters are still assumptions
    assert p.assumption_fraction() > 0.5


def test_jackal_is_consistent_with_its_rated_ambient():
    """At the manufacturer's rated 45 degC ambient, in shade, under sustained heavy use, the
    robot must stay inside every hard limit, and the battery must be within 10 K of its own
    (the profile must not be absurdly loose either). The conductances are chosen to satisfy this."""
    import numpy as np

    from dhill.envelope import EngineConfig, Envelope
    from dhill.loads import mission_loads
    from dhill.physics.constants import c_to_k, k_to_c
    from dhill.physics.thermal import State, simulate
    from dhill.weather.base import Weather

    p = load_builtin("clearpath_jackal")
    n = 10
    t = np.arange("2026-08-05T20:00", "2026-08-06T06:00", dtype="datetime64[h]")
    w = Weather(
        times_utc=t,
        t_air_c=np.full(n, 45.0),
        dew_c=np.full(n, 15.0),
        wind10_ms=np.full(n, 2.0),
        pm10_ugm3=np.full(n, 50.0),
        precip_mm_h=np.zeros(n),
        lat=24.45,
        lon=54.38,
        altitude_m=10,
        ghi_wm2=np.zeros(n),
    )
    env = Envelope(p, w, EngineConfig(n_mc=1, sigma_scale=0.0, dt_s=300.0))
    st = State(np.full((1, 6), c_to_k(45.0)), np.array([0.95]), np.zeros(1))
    res = simulate(
        env.params, env.forcing, mission_loads(p, 1.0, "drive"), st, 0, 96, record_every=10**6
    )
    peak = {
        "battery": k_to_c(res.peak_k[0, 2]),
        "compute_die": k_to_c(res.peak_die_k[0]),
        "lidar": k_to_c(res.peak_k[0, 4]),
        "motor": k_to_c(res.peak_k[0, 5]),
        "interior": k_to_c(res.peak_k[0, 1]),
    }
    for comp, val in peak.items():
        assert val < p.limits[comp].limit_c, (comp, val)
    assert p.limits["battery"].limit_c - peak["battery"] < 10.0


def test_calibrated_profile_dump_loads_back(tmp_path):
    """A profile saved by `dhill calibrate --out` (flat dotted keys) must load with load_profile."""
    import json

    from dhill.profiles.loader import load_profile

    p = load_builtin("clearpath_jackal").with_overrides({"surface.alpha_clean": 0.5})
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(p.model_dump(mode="json")), encoding="utf-8")
    q = load_profile(str(path))
    assert q.evidence_level == p.evidence_level
    assert q.parameters == p.parameters
    assert q.value("surface.alpha_clean") == 0.5
