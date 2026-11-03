"""Guided creation of a new robot profile from a built in template.

The wizard starts from the template closest to the robot, asks for the few numbers a datasheet usually
gives, and records where each number came from. It never labels a profile above L0: a label above L0
needs measurements of the robot, which an answer to a question is not. Values the user does not know stay
at the template's assumptions, and their provenance stays ``assumption``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .loader import builtin_profile_ids, load_builtin, profile_from_dict
from .schema import Profile

SOURCES = ("datasheet", "measured", "textbook", "assumption")

# (parameter key, question, unit)
PARAMETER_QUESTIONS = [
    ("battery.cells_series", "Battery cells in series", "count"),
    ("battery.cells_parallel", "Battery cells in parallel", "count"),
    ("battery.cell_capacity_ah", "Capacity of one cell", "Ah"),
    ("compute.nominal_power_w", "Compute power in a typical mode", "W"),
    ("lidar.power_w", "LiDAR power", "W"),
    ("power.comms_w", "Communications power", "W"),
    ("power.standby_w", "Standby power of everything else", "W"),
    ("perception.nominal_speed_ms", "Nominal travel speed", "m/s"),
]
LIMIT_QUESTIONS = [
    ("battery", "Battery discharge temperature limit", "degC"),
    ("compute_die", "Compute die throttle temperature", "degC"),
    ("lidar", "LiDAR temperature limit", "degC"),
    ("motor", "Motor winding temperature limit", "degC"),
]
MODE_QUESTIONS = [("drive", "mech_w", "Mechanical power while driving", "W")]

Ask = Callable[[str], str]


def _num(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    return float(text)


def build_profile_dict(base: Profile, answers: dict[str, Any]) -> dict[str, Any]:
    """Apply ``answers`` to a template and return the profile as a plain dict (always evidence L0).

    ``answers`` may hold ``id``, ``name``, ``description``, ``category``, ``parameters`` (key to
    ``{value, source, note}``), ``limits`` (component to ``{limit_c, source, note}``) and ``modes``.
    """
    data = base.model_dump(mode="json")
    data["id"] = answers.get("id", f"{base.id}_copy")
    data["name"] = answers.get("name", data["id"])
    data["description"] = answers.get("description", "")
    data["category"] = answers.get("category", base.category)
    data["evidence_level"] = "L0"
    data["calibrated_from"] = []
    for key, spec in answers.get("parameters", {}).items():
        if key not in data["parameters"]:
            raise KeyError(f"unknown parameter: {key}")
        src = spec.get("source", "datasheet")
        if src not in SOURCES:
            raise ValueError(f"source of {key} must be one of {SOURCES}")
        cur = data["parameters"][key]
        cur.update(value=float(spec["value"]), source=src, note=spec.get("note"))
        cur["rel_sigma"] = None
    for comp, spec in answers.get("limits", {}).items():
        lim = data["limits"][comp]
        lim["limit_c"] = float(spec["limit_c"])
        lim["source"] = spec.get("source", "datasheet")
        if spec.get("note"):
            lim["note"] = spec["note"]
    for mode, spec in answers.get("modes", {}).items():
        data["modes"][mode].update({k: float(v) for k, v in spec.items()})
    note = (
        "Created with the profile wizard from the template "
        f"'{base.id}'. Values not entered keep the template's assumptions. Evidence level L0."
    )
    data["description"] = (data["description"] + " " + note).strip()
    return data


def to_yaml(data: dict[str, Any]) -> str:
    """Write the profile in the nested section layout used by the built in profiles."""
    sections: dict[str, dict[str, Any]] = {}
    for key, spec in data["parameters"].items():
        sec, name = key.split(".", 1)
        item: dict[str, Any] = {"value": spec["value"], "source": spec["source"]}
        if spec.get("note"):
            item["note"] = spec["note"]
        if spec.get("rel_sigma") is not None:
            item["rel_sigma"] = spec["rel_sigma"]
        sections.setdefault(sec, {})[name] = item
    out = {k: v for k, v in data.items() if k != "parameters"}
    out = {
        **{
            k: out[k]
            for k in ("schema_version", "id", "name", "description", "category", "evidence_level")
        },
        "parameters": sections,
        **{
            k: v
            for k, v in out.items()
            if k
            not in ("schema_version", "id", "name", "description", "category", "evidence_level")
        },
    }
    return yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=100)


def run_wizard(ask: Ask, say: Callable[[str], None], base_id: str | None = None) -> dict[str, Any]:
    """Interactive session. Returns the profile dict; the caller validates and writes it."""
    ids = builtin_profile_ids()
    say("Dhill profile wizard. The profile is labelled L0 whatever is entered here.")
    say("Templates: " + ", ".join(ids))
    base_id = base_id or ask(f"Template [{ids[0]}]: ").strip() or ids[0]
    base = load_builtin(base_id)
    answers: dict[str, Any] = {
        "id": ask("Profile id (letters, digits, - or _): ").strip() or f"{base_id}_copy",
        "name": ask("Robot name: ").strip(),
        "description": ask("One line description: ").strip(),
        "category": base.category,
        "parameters": {},
        "limits": {},
        "modes": {},
    }
    say("Press Enter to keep the template value. Say where each number came from.")
    for key, question, unit in PARAMETER_QUESTIONS:
        cur = base.value(key)
        v = _num(ask(f"{question} ({unit}) [{cur:g}]: "))
        if v is not None:
            src = ask(f"  source of this value {SOURCES} [datasheet]: ").strip() or "datasheet"
            answers["parameters"][key] = {"value": v, "source": src}
    for comp, question, unit in LIMIT_QUESTIONS:
        cur = base.limits[comp].limit_c
        v = _num(ask(f"{question} ({unit}) [{cur:g}]: "))
        if v is not None:
            src = ask(f"  source of this value {SOURCES} [datasheet]: ").strip() or "datasheet"
            answers["limits"][comp] = {"limit_c": v, "source": src}
    for mode, field, question, unit in MODE_QUESTIONS:
        cur = getattr(base.modes[mode], field)
        v = _num(ask(f"{question} ({unit}) [{cur:g}]: "))
        if v is not None:
            answers["modes"].setdefault(mode, {})[field] = v
    return build_profile_dict(base, answers)


def write_profile(data: dict[str, Any], path: str | Path) -> Profile:
    """Validate the dict as a profile and write it as YAML. Raises if the profile is invalid."""
    text = to_yaml(data)
    prof = profile_from_dict(yaml.safe_load(text))
    Path(path).write_text(text, encoding="utf-8")
    return prof
