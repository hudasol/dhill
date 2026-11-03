"""Fleet file, profile wizard and the rule that nothing above L0 is claimed without measurements."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from dhill.cli import main
from dhill.fleet import FleetSpec, fleet_json_schema, load_fleet
from dhill.profiles.loader import load_builtin, load_profile_file, profile_from_dict
from dhill.profiles.wizard import build_profile_dict, run_wizard, to_yaml, write_profile

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "fleet_example.yaml"


def test_example_fleet_expands_copies():
    fleet = load_fleet(EXAMPLE)
    names = [n for n, _ in fleet.expand()]
    assert names == ["inspector-01", "inspector-02", "courier"]
    assert set(fleet.profiles()) == {"ugv_medium_inspection", "sidewalk_delivery_robot"}


def test_fleet_rejects_unknown_site_duplicate_ids_and_bad_mode():
    base = {
        "name": "x",
        "site": "al_ain",
        "robots": [{"id": "a", "profile": "ugv_medium_inspection"}],
    }
    FleetSpec.model_validate(base)
    with pytest.raises(ValidationError):
        FleetSpec.model_validate({**base, "site": "nowhere"})
    with pytest.raises(ValidationError):
        FleetSpec.model_validate({**base, "robots": base["robots"] * 2})
    bad = FleetSpec.model_validate(
        {**base, "robots": [{"id": "a", "profile": "ugv_medium_inspection", "mode": "fly"}]}
    )
    with pytest.raises(ValueError, match="no mode"):
        bad.profiles()


def test_committed_fleet_schema_is_current():
    committed = json.loads((ROOT / "docs" / "fleet.schema.json").read_text(encoding="utf-8"))
    assert committed == fleet_json_schema()


def test_wizard_answers_make_an_l0_profile_with_stated_provenance(tmp_path):
    answers = yaml.safe_load((ROOT / "examples" / "profile_answers_example.yaml").read_text())
    base = load_builtin(answers["base"])
    data = build_profile_dict(base, answers)
    out = tmp_path / "p.yaml"
    prof = write_profile(data, out)
    assert prof.evidence_level == "L0" and prof.id == "demo_courier"
    assert prof.value("battery.cells_series") == 13
    assert prof.parameters["battery.cells_series"].source == "datasheet"
    assert prof.limits["compute_die"].limit_c == 95
    assert load_profile_file(out).value("compute.nominal_power_w") == 18


def test_measured_sources_still_give_l0_from_the_wizard():
    base = load_builtin("ugv_medium_inspection")
    data = build_profile_dict(
        base,
        {
            "id": "m",
            "parameters": {"battery.cell_capacity_ah": {"value": 4.8, "source": "measured"}},
        },
    )
    assert data["evidence_level"] == "L0"


def test_l1_needs_a_measured_parameter():
    base = load_builtin("ugv_medium_inspection").model_dump(mode="json")
    base["evidence_level"] = "L1"
    for spec in base["parameters"].values():
        if spec["source"] == "measured":
            spec["source"] = "assumption"
    with pytest.raises(ValueError, match="measured"):
        profile_from_dict(yaml.safe_load(to_yaml(base)))
    base["parameters"]["battery.cell_capacity_ah"]["source"] = "measured"
    assert profile_from_dict(yaml.safe_load(to_yaml(base))).evidence_level == "L1"


def test_interactive_wizard_with_scripted_answers():
    script = iter(
        [
            "sidewalk_delivery_robot",
            "scripted",
            "Scripted robot",
            "A test",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        + [""] * 12
    )
    lines: list[str] = []
    data = run_wizard(lambda _p: next(script), lines.append, None)
    assert data["id"] == "scripted" and data["evidence_level"] == "L0"


def test_cli_profile_new_check_and_fleet(tmp_path, capsys):
    out = tmp_path / "demo.yaml"
    answers = ROOT / "examples" / "profile_answers_example.yaml"
    assert main(["profile", "new", "--answers", str(answers), "--out", str(out)]) == 0
    assert main(["profile", "check", str(out)]) == 0
    assert "L0" in capsys.readouterr().out
    assert main(["fleet", "check", str(EXAMPLE)]) == 0
    assert main(["plan", "--fleet", str(EXAMPLE), "--samples", "16", "--json"]) == 0
