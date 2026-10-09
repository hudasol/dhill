from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from dhill.profiles.loader import builtin_profile_ids, load_builtin, load_profile, profile_from_dict
from dhill.profiles.registry import PARAMS


def test_builtin_profiles_present():
    assert {"ugv_medium_inspection", "sidewalk_delivery_robot", "pv_cleaning_robot"} <= set(
        builtin_profile_ids()
    )


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
    assert p.value("surface.alpha_clean") == 0.55


def test_load_unknown_builtin():
    with pytest.raises(KeyError):
        load_profile("nope")
