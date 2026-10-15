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
